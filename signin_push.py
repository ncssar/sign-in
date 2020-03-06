##
##  Routine to read member data from d4h and populate a roster table
##   with username, sar_id, d4h_id, cell#, resources
##
import requests
import json
import sys
import os
import sqlite3
import time
from threading import Thread
from datetime import datetime,timezone
from pathlib import Path

# on pythonanywhere, the relative path ./sign-in should be added instead of ../sign-in
#  since the current working dir while this script is running is /home/caver456
#  even though the script is in /home/caver456/signin_api
# while it should be ok to load both, it's a lot cleaner to check for the
#  one that actually exists
p=Path('../sign-in')
if not p.exists():
    p=Path('./sign-in')
pr=str(p.resolve())
sys.path.append(pr)
print("python search path:"+str(sys.path))

from signin_db import *

    
def utc_to_local(utc_dt,tz=None):
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=tz)

# sdbPush: update a d4h activity's attendance records based on the finalized signin
#   database; should only be called from the server api request handler
#  note: response.status_code is defined in requests module; d4h also responds
#    with a key in the dictionary (json.loads(response.text)) called statusCode
def sdbPush(eventID,blocking=True):    

    offsetSec=28800.0
    d4hServer="https://api.d4h.org"
    d4h_api_key = os.environ.get("D4H_API_KEY")
     
    # 1. get the corresponding D4H activity ID
    #### NOTE - need to develop some methods to make sure we are pushing to the
    ####  correct activity, and that we aren't clobbering existing attendance records
    event=sdbGetEvents(eventID=eventID)[0]
    print("returned event: "+str(event))
    d4h_activity_id=event["D4HID"]
    print("D4H activity id = "+str(d4h_activity_id))
    if d4h_activity_id is None:
        return {"statusCode":100,"message":"No corresponding D4H activity; bulk push not needed."}
     
    response=requests.request("GET", d4hServer+"/v2/team/activities/"+str(d4h_activity_id),
                headers={'Authorization':'Bearer '+d4h_api_key})
    rt=json.loads(response.text)
    print("response:"+str(rt))
    if response.status_code>299:
        return rt
    if "data" not in rt.keys():
        return {"statusCode":500,"message":"No 'data' key found in activities response."}
    d4hActivity=rt["data"]
         
    attendanceType=d4hActivity["attendance_type"]
    print("attendance type:"+str(attendanceType))
                                        
#         roster=sdbGetRoster()["roster"]
     
    # 2. get the existing D4H attendance records for this activity
    response=requests.request("GET", d4hServer+"/v2/team/attendance?activity_id="+str(d4h_activity_id),
                headers={'Authorization':'Bearer '+d4h_api_key})
    d4hAttendanceRecords=json.loads(response.text)["data"]
    # save a backup; 55KB for a full-team event
    with open("prepush_"+str(d4h_activity_id)+".json","w") as outFile:
            json.dump(d4hAttendanceRecords,outFile)
     
    # 3. get the signin event data
    signInRecords=sdbGetEvent(eventID)
    signin_d4h_ids=[x["D4HMemberID"] for x in signInRecords]
    print("signin_d4h_ids:"+str(signin_d4h_ids))
    
    # 4. build the list of requests
    #  Special cases:
    #  - DNSO (did not sign out)
    #      - sign the member out one minute later than their sign-in time;
    #         this means DNSO time is not universal for the event - it may be
    #         different for each sign-in record
    #  - more than one record for the same member (this is possible if they
    #     actually left in the middle of the event then came back)
    #      - D4H is OK with multiple records of the same member 
    requestList=[] # list of dictionaries
    latestSignOut=max([x["OutEpoch"] for x in signInRecords])
    if latestSignOut<1e6:
        latestSignOut=max([x["InEpoch"] for x in signInRecords])+60
#         dnsoEpoch=utc_to_local(latestSignOut+60)
    dnsoEpoch=latestSignOut+offsetSec
     
    # NOTE that this logic is necessarily complicated because D4H dosn't have
    #  any distinction between "planning to attend" and "had planned to attend"
    #  and "actually attended".  If someone signals their intent to attend
    #  before the activity, then they are automatically converted to "attended"
    #  after the event time has passed, regardless of whether they actually
    #  attended.  If there were another status option "planned" which didn't
    #  change after the event time passed, this logic could be simplified.
    # This feature request has been submitted to D4H support.
     
    # we need to account for these possibilities:
    #  - someone has added attendance records reflecting actual attendance
    #     before the bulk push operation took place; we want to preserve those!
    #     They may or may not have exact attendance times.  If not, how do we
    #     identify these records that we want to keep?  If the member signed
    #     in on paper instead of tablet, then they got entered in to d4h based
    #     on the paper but their time was left at the event time default,
    #     then how would the bulk push know to not overwrite or delete that
    #     attendance record?
     
    # There are three lists that could be iterated over: roster, sign-in records,
    #   or d4h attendance records.  The trick is to pick the right one.
     
    # - if this is a FULL-TEAM d4h activity: iterate over d4h attendance records,
    #     since that list will be equal to the roster at the time the activity
    #     was created (though the roster may have changed since then!); then iterate
    #     over sign-in records to make sure they all have corresponding attendance
    #     records - this is needed in case the roster changed.
    #   
    #   simpler but slower due to roughly twice as many requests:
    #   - get all d4h attendance records regardless of status; extract a list of
    #      d4h member IDs from those records
    #   - delete all d4h attendance records
    #   - add a new record (attending or absent) for each d4h member ID from the list above
     
     
    #   more complex but twice as fast:
    #   - for each d4h attendance record:
    #     - is status 'attending'?
    #       - yes    (they indicated intent to attend, and/or have been manually updated)
    #         - does the member have a sign-in record i.e. actually did attend?
    #           - yes    (they indicated intent to attend, and did sign in with app)
    #             - change d4h attendance record times to match sign-in times
    #           - no    (they indicated intent to attend, but did not sign in with app)
    #             - was the d4h attendance record modified since the original invitation, or,
    #                     are in/out times different than activity start/stop times?
    #               - yes   (they did not sign in with the app but have been hand-entered)
    #                  - leave it as 'attended' and don't modify the times
    #               - no    (must assume they did not actually attend or signed in on paper
    #                          in which case they need to be hand-entered later)
    #                  - change d4h attendance record to 'absent'
    #                            (or should this be 'unconfirmed' as a flag for further attention?)
    #       - no    (they either declined or did not respond - we don't yet know if they actually did attend)
    #         - does the member have a sign-in record i.e. actually did attend?
    #           - yes    (they declined or did not respond, but did sign in with app)
    #             - change d4h attendance record to 'attending' with sign-in times
    #           - no    (the declined or did not respond, and did not sign in with the app)
    #             - change d4h attendance record to 'absent'
    #  - finally, iterate over sign-in records and add any that weren't accounted for above
 
    # - if this is a SELECTIVE-ATTENDANCE d4h activity:
    #    1. delete all d4h attendance records
    #    2. add d4h attendance records from sign-in records
    
    if attendanceType=='full':
        print("Beginning iteration over d4h attendance records")
        ar_d4h_member_ids=[]
        for ar in d4hAttendanceRecords:
            ar_id=ar["id"]
#             print("attendance record "+str(ar_id))
            status=ar["status"]
            d4h_member_id=ar["member"]["id"]
            ar_d4h_member_ids.append(d4h_member_id)
            if status=="attending":
                if d4h_member_id in signin_d4h_ids:
                    # they indicated intent to attend, and did sign in with the app:
                    #  update the d4h date/enddate values from the sign-in and -out times
                    tt=getIsoTimeText([x for x in signInRecords if str(x["D4HMemberID"])==str(d4h_member_id)][0],offsetSec,dnsoEpoch)
                    # incremental push: don't do the request if it is already accurate!
                    #  only compare until the final colon since d4h could round seconds and adds 'Z'
                    if timesAreDifferent(ar,tt):
                        body={
                            "status":"attending",
                            "date":tt["in"],
                            "enddate":tt["out"]}
                        requestList.append(["team/attendance/"+str(ar_id),"PUT",body])
                elif arIsModified(ar):
                    # they did not sign in with the app but have already been hand-entered:
                    #  don't change anything
                    pass
                else:
                    # must assume they did not actually attend, or signed in on paper
                    #   in which case they need to be hand-entered later:
                    #  change to absent (or unconfirmed as a flag for later attention?)
                    body={
                        "status":"absent"}
                    requestList.append(["team/attendance/"+str(ar_id),"PUT",body])
            else:
                # status before the activity was absent or unconfirmed
#                 print("  did not indicate intent to attend:"+str(d4h_member_id))
                if d4h_member_id in signin_d4h_ids:
#                     print("    but actually attended.")
                    # they attended even though they indicated intent to be absent or did not respond:
                    # change the record to "attending" with times from sign-in
                    tt=getIsoTimeText([x for x in signInRecords if str(x["D4HMemberID"])==str(d4h_member_id)][0],offsetSec,dnsoEpoch)
                    body={
                        "status":"attending",
                        "date":tt["in"],
                        "enddate":tt["out"]}
                    requestList.append(["team/attendance/"+str(ar_id),"PUT",body])
                else:
                    # did not attend:
                    # change the record to "absent" if needed
                    if ar["status"]!="absent":
                        body={
                            "status":"absent"}
                        requestList.append(["team/attendance/"+str(ar_id),"PUT",body])
        # done iterating through d4h attendance records;
        # now add any d4h records for any sign-in records that haven't already been processed
        print("Beginning iteration over signin records")
        for sr in signInRecords:
            d4h_member_id=sr["D4HMemberID"]
            if d4h_member_id not in ar_d4h_member_ids:
                # add an "attending" record with times from sign-in record
                tt=getIsoTimeText([x for x in signInRecords if str(x["D4HMemberID"])==str(d4h_member_id)][0],offsetSec,dnsoEpoch)
                body={
                    "activity_id":d4h_activity_id,
                    "member":d4h_member_id,
                    "status":"absent",
                    "date":tt["in"],
                    "enddate":tt["out"]}
                requestList.append(["team/attendance","POST",body])

    elif attendanceType=="selective":
        ar_d4h_member_ids=[]
        for ar in d4hAttendanceRecords:
            ar_id=ar["id"]
            status=ar["status"]
            d4h_member_id=ar["member"]["id"]
            if status=="attending":
                if d4h_member_id in signin_d4h_ids:
                    # they signaled intent to attend, and they signed in with the app:
                    #  update the times based on sign-in
                    ar_d4h_member_ids.append(d4h_member_id) # only add entries that won't be deleted
                    tt=getIsoTimeText([x for x in signInRecords if str(x["D4HMemberID"])==str(d4h_member_id)][0],offsetSec,dnsoEpoch)
                    # incremental push: don't do the request if it is already accurate!
                    if tt["in"]!=ar["date"] or tt["out"]!=ar["enddate"]:
                        body={
                            "status":"attending",
                            "date":tt["in"],
                            "enddate":tt["out"]}
                        requestList.append(["team/attendance/"+str(ar_id),"PUT",body])
                else:
                    # they signaled intent to attend, but did not sign in with the app:
                    #  delete the record
                    requestList.append(["team/attendance/"+str(ar_id),"DELETE",None])
            else:
                # they signaled intent to be absent, or did not respond:
                #  delete the record
                requestList.append(["team/attendance/"+str(ar_id),"DELETE",None])
                
        # done iterating through d4h attendance records;
        # now add any d4h records for any sign-in records that haven't already been processed 
        for sr in signInRecords:
            d4h_member_id=sr["D4HMemberID"]
            if d4h_member_id not in ar_d4h_member_ids:
                # add an "attending" record with times from sign-in record
                tt=getIsoTimeText([x for x in signInRecords if str(x["D4HMemberID"])==str(d4h_member_id)][0],offsetSec,dnsoEpoch)
                body={
                    "activity_id":d4h_activity_id,
                    "member":d4h_member_id,
                    "status":"attending",
                    "date":tt["in"],
                    "enddate":tt["out"]}
                requestList.append(["team/attendance","POST",body])            
  
    else:
        print("error: unknown attendance type '"+str(attendanceType)+"'")
        return {"statusCode":500,"message":"Unknown D4H activity attendance type:\n'"+str(attendanceType)+"'"}
    
    
#     print("request list:"+str(requestList))
    # 5. send the requests (synchronously for now; consider async later)
    rval="NOT SENT"
    if blocking:
        rval=d4hFinalize(d4hServer,d4h_activity_id,requestList)
    else:
        print("Sorry, pythonanywhere does not support threading, so the sign-in app won't use threading either.\n  https://help.pythonanywhere.com/pages/AsyncInWebApps/")
#         d4hThread=Thread(target=d4hFinalize,args=(d4hServer,d4h_activity_id,requestList))
#         d4hThread.start()
#         print("Job submitted.")
    return {"statusCode":200,"message":rval}

def d4hFinalize(d4hServer,d4h_activity_id,requestList):
    print("Beginning bulk push to D4H activity "+str(d4h_activity_id)+" with request list "+str(requestList))
    d4h_api_key = os.environ.get("D4H_API_KEY")
    responses=[]
    print("about to send "+str(len(requestList))+" request(s)...")
    for rq in requestList:
        [rqUrlTail,rqType,rqBody]=rq
        url=d4hServer+"/v2/"+rqUrlTail
        print(str(rqType)+"  URL:'"+url+"'  "+str(rqBody))
        response = requests.request(rqType, url,
                    headers={'Authorization':'Bearer '+d4h_api_key}, data = rqBody)
#         print("  request sent")
        print("  response:"+str(response))
        try:
            print("  response.status_code:"+str(response.status_code))
        except:
            print("  response.status_code could not be printed / does not exist")
        try:
            print("  response.text:"+str(response.text))
        except:
            print("  reponse.text could not be printed / does not exist")
        try:
            rq.append(json.loads(response.text))
        except:
            # for DELETE, no response text is generated, but response.status_code should be 204;
            #   store it as json like other responses, for ease of downstream handling
            rq.append({"statusCode":response.status_code,"message":str(response.status_code)+": NO RESPONSE"})
            print("  NO RESPONSE")
        
        responses.append(rq)

#         print("   response code: "+str(json.loads(response.text)['statusCode']))
    print("Bulk push complete.")
    # return the full request and response data set if needed for debugging;
    #  also return a summary ready for display in the app: number of requests by
    #  type (add, delete, modify) and status (attending, absent, unconfirmed) 
    #  and success/fail count for each
    adds=[x for x in responses if x[1]=="POST"]
    print("  adds:"+str(adds))
    adds_attending=[x for x in adds if x[2]["status"]=="attending"]
    print("    adds_attending:"+str(adds_attending))
    adds_attending_fails=[x for x in adds_attending if x[3]["statusCode"]>299]
    print("      adds_attending_fails:"+str(adds_attending_fails))
    adds_absent=[x for x in adds if x[2]["status"]=="absent"]
    print("    adds_absent:"+str(adds_absent))
    adds_absent_fails=[x for x in adds_absent if x[3]["statusCode"]>299]
    print("      adds_absent_fails:"+str(adds_absent_fails))
    deletes=[x for x in responses if x[1]=="DELETE"]
    print("  deletes:"+str(deletes))
    deletes_fails=[x for x in deletes if x[3]["statusCode"]>299]
    print("    deletes_fails:"+str(deletes_fails))
    updates=[x for x in responses if x[1]=="PUT"]
    print("  updates:"+str(updates))
    updates_fails=[x for x in updates if x[3]["statusCode"]>299]
    print("    updates_fails:"+str(updates_fails))
    adds_attending_fails_str=""
    adds_absent_fails_str=""
    deletes_fails_str=""
    updates_fails_str=""
    if len(adds_attending_fails)>0:
        adds_attending_fails_str=" ({} failed)\n".format(len(adds_attending_fails))
        msgs=[x[3]['message'] for x in adds_attending_fails]
        for msg in set(msgs):
            adds_attending_fails_str+="    [{}] {}\n".format(msgs.count(msg),msg)
    if len(adds_absent_fails)>0:
        adds_absent_fails_str=" ({} failed)\n".format(len(adds_absent_fails))
        msgs=[x[3]['message'] for x in adds_absent_fails]
        for msg in set(msgs):
            adds_absent_fails_str+="    [{}] {}\n".format(msgs.count(msg),msg)
    if len(deletes_fails)>0:
        deletes_fails_str=" ({} failed)\n".format(len(deletes_fails))
        msgs=[x[3]['message'] for x in deletes_fails]
        for msg in set(msgs):
            deletes_fails_str+="    [{}] {}\n".format(msgs.count(msg),msg)
    if len(updates_fails)>0:
        updates_fails_str=" ({} failed)\n".format(len(updates_fails))
        msgs=[x[3]['message'] for x in updates_fails]
        for msg in set(msgs):
            updates_fails_str+="    [{}] {}\n".format(msgs.count(msg),msg)
        
    summary="Added records:{}\n  Attended:{}{}  Absent:{}{}\nDeleted records:{}{}\nUpdated records:{}{}".format(
            len(adds),
            len(adds_attending),
            adds_attending_fails_str,
            len(adds_absent),
            adds_absent_fails_str,
            len(deletes),
            deletes_fails_str,
            len(updates),
            updates_fails_str)
    return {"responses":responses,"summary":summary}


# getIsoTimeText: extract the iso-formatted in and out time texts
#   from a signin record
# optionally specify a fixed didn-not-sign-out time, otherwise it
#  will be one hour after sign-in time
# if there are multiple signin records for the same member, 
#  we should also make the same multiple d4h attendance records
def getIsoTimeText(sr,offsetSec,dnsoEpoch=False):
    # just go with the first matching record for now
#     sr=[x for x in signInRecords if str(x["D4HMemberID"])==str(d4h_member_id)][0]
    d4h_member_id=sr["D4HMemberID"]
    inEpoch=int(sr.get("InEpoch",0))+offsetSec
    outEpoch=int(sr.get("OutEpoch",0))+offsetSec
    dnsoEpoch=dnsoEpoch or inEpoch+3600 # if not specified, use sign-in time plus one hour
    if dnsoEpoch<=inEpoch: # if it was specified, make sure it is greater than the sign-in time!
        dnsoEpoch=inEpoch+60
    if outEpoch==offsetSec:
        outEpoch=dnsoEpoch
#     print("inEpoch:"+str(inEpoch)+"  outEpoch="+str(outEpoch))
    inObj=datetime.fromtimestamp(inEpoch)
    outObj=datetime.fromtimestamp(outEpoch)
#     print("  inObj="+str(inObj)+"  outObj="+str(outObj))
#             inText=inObj.strftime(d4h_datetimeformat)
    inText=inObj.isoformat()
#             outText=outObj.strftime(d4h_datetimeformat)
    outText=outObj.isoformat()
    return {"in":inText,"out":outText}


# timesAreDifferent
#  used to determine if a given sign-in record needs to be pushed to d4h
#  ar = d4h attendance record
#  tt = dictionary of iso-formated time strings (from getIsoText)
#  return True if in time from d4h attendance record is not the same as in
#   time from sign-in record, or if out time from d4h attendance record is
#   not the same as out time from sign-in record; comparisons are truncated
#   to the minute
def timesAreDifferent(ar,tt):
    i1=ar["date"]
    o1=ar["enddate"]
    i2=tt["in"]
    o2=tt["out"]
    i1=i1[0:i1.rfind(':')]
    o1=o1[0:o1.rfind(':')]
    i2=i2[0:i2.rfind(':')]
    o2=o2[0:o2.rfind(':')]
#     print(i1+"<-->"+i2)
#     print(o1+"<-->"+o2)
    return i1!=i2 or o1!=o2

    
# arIsModified: if the attendance record has been modified, return True; this could
#  be indicated by attendance record in/out times not equal to activity start/stop times,
#  or in the future by a json attribute in the return value from the d4h request
#  indicating it has been modified 
def arIsModified(ar):
    activity=ar["activity"]
    if activity["date"]!=ar["date"] or activity["enddate"]!=ar["enddate"]:
        return True
    else:
        return False


# # setup to load api key for d4h into environment variable
# import sys
# path = '/home/caver456/.local/lib/python3.6/site-packages'
# if path not in sys.path:
#     sys.path.append(path)
# from dotenv import load_dotenv
# project_folder = os.path.expanduser('~/')
# load_dotenv(os.path.join(project_folder, '.env'))

# class Push():
#     def __init__(self):
#         d4hServer="https://api.d4h.org"
#         d4h_api_key = os.environ.get("D4H_API_KEY")
#         # D4H uses ISO 8601 time format strings, with the UTC offset (Z) at the end
#         # use datetime.isoformat() to accomplish this instead of specifying a
#         #  hardcoded format string
# #         d4h_datetimeformat="%Y-%m-%dT%H:%M:%S.000Z" # used by strftime and strptime
#         pushAll(11)
# #         deleteAll(391413)
#         
# #     def deleteAll(self,D4HID):
# #         response = requests.request("GET", d4hServer+"/v2/team/attendance?activity_id="+str(D4HID),
# #             headers={'Authorization':'Bearer '+d4h_api_key})
# #         data=json.loads(response.text)["data"]
# #         for record in data:
# #             aid=record["id"]
# #             print("deleting attendance record "+str(aid)+" ("+str(record["activity"]["title"])+")")
# #             r2=requests.request("DELETE", d4hServer+"/v2/team/attendance/"+str(aid),
# #                 headers={'Authorization':'Bearer '+d4h_api_key})
#         
#     def pushAll(self,eventID):
#         offsetSec=28800
#         
#         # 1. get the corresponding D4H activity ID
#         #### NOTE - need to develop some methods to make sure we are pushing to the
#         ####  correct activity, and that we aren't clobbering existing attendance records
#         event=sdbGetEvents(eventID=eventID)[0]
#         print("returned event: "+str(event))
#         D4HID=event["D4HID"]
#         print("D4HID = "+str(D4HID))
# #         roster=sdbGetRoster()["roster"]
#         
#         # 2. get the existing D4H attendance records for this activity
#         d4hAttendanceRecords = requests.request("GET", d4hServer+"/v2/team/attendance?activity_id="+str(D4HID),
#                     headers={'Authorization':'Bearer '+d4h_api_key})
#         
#         # 3. get the signin event data
#         signInRecords=sdbGetEvent(eventID)
#         
#         # 4. build the list of requests
#         #  Special cases:
#         #  - DNSO (did not sign out)
#         #      - sign the member out one minute later than the latest actual signout
#         #  - more than one record for the same member (this is possible if they
#         #     actually left in the middle of the event then came back)
#         #      - D4H is OK with multiple records of the same member 
#         bodyList=[] # list of dictionaries
#         latestSignOut=max([x["OutEpoch"] for x in all])
# #         dnsoEpoch=utc_to_local(latestSignOut+60)
#         dnsoEpoch=latestSignOut+offsetSec
#         
#         # note that this logic is necessarily complicated because D4H dosn't have
#         #  any distinction between "planning to attend" and "had planned to attend"
#         #  and "actually attended".  If someone signals their intent to attend
#         #  before the activity, then they are automatically converted to "attended"
#         #  after the event time has passed, regardless of whether they actually
#         #  attended.  If there were another status option "planned" which didn't
#         #  change after the event time passed, this logic could be simplified.
#         # we need to account for these possibilities:
#         #  - someone has added attendance records reflecting actual attendance
#         #     before the bulk push operation took place; we want to preserve those!
#         #     They may or may not have exact attendance times.  If not, how do we
#         #     identify these records that we want to keep?  If the member signed
#         #     in on paper instead of tablet, then they got entered in to d4h based
#         #     on the paper but their time was left at the event time default,
#         #     then how would the bulk push know to not overwrite or delete that
#         #     attendance record?
#         # for each signin record:
#         # - if full-team activity:
#         # -- do any attendance records already exist with same member but same
#         #       start and end times as the activity?
#         # --- yes:
#         # ---- delete the matching attendance record(s) (normally just one)
#         # ---- add one attendance record matching the signin record
#         # --- no: add an attendance record (this will include cases where there
#         #       is already an attendance record .
#         for sr in signInRecords:
# #             memberID=[x["d4h_id"] for x in roster if x["name"] == record["Name"]][0]
#             memberID=sr["D4HMemberID"]
# #             inEpoch=int(utc_to_local(record.get("InEpoch",0)))
# #             outEpoch=int(utc_to_local(record.get("OutEpoch",0)))
#             inEpoch=int(sr.get("InEpoch",0))+offsetSec
#             outEpoch=int(sr.get("OutEpoch",0))+offsetSec
#             if outEpoch==offsetSec:
#                 outEpoch=dnsoEpoch
#             print("inEpoch:"+str(inEpoch)+"  outEpoch="+str(outEpoch))
#             inObj=datetime.fromtimestamp(inEpoch)
#             outObj=datetime.fromtimestamp(outEpoch)
#             print("  inObj="+str(inObj)+"  outObj="+str(outObj))
# #             inText=inObj.strftime(d4h_datetimeformat)
#             inText=inObj.isoformat()
# #             outText=outObj.strftime(d4h_datetimeformat)
#             outText=outObj.isoformat()
#             if fullTeam:
#                 for dr in d4hAttendanceRecords:
#                     
#             body={
#                 "activity_id":D4HID,
#                 "member":memberID,
#                 "status":"attending",
#                 "date":inText,
#                 "enddate":outText}
#             bodyList.append(body)
#         
#         # 5. send the requests (synchronously for now; consider asynch later)
# #         pushSuccessList=[]
#         print("Beginning bulk push of "+str(len(bodyList))+" attendance record(s) to D4H activity "+str(D4HID)+"...")
#         for body in bodyList:
#             print(" sending attendance record POST request for "+str(body["member"]))
#             print("   "+str(body))
#             response = requests.request("POST", d4hServer+"/v2/team/attendance",
#                         headers={'Authorization':'Bearer '+d4h_api_key}, data = body)
#             print("   response code: "+str(json.loads(response.text)['statusCode']))
#         print("Bulk push complete.")
# 
# Push()

#             request=UrlRequest(d4hServer+"/v2/team/activities?"+urlParamString,
#                 on_success=on_push_success,
#                 on_failure=on_push_error,
#                 on_error=on_push_error,
#         #         timeout=3,
#                 method="GET",
#                 req_body=body,
#                 req_headers={'Authorization':'Bearer '+d4h_api_key},
#                 debug=True)
#     
#     def on_push_success(self,request,result):
#         member=request.req_body["member"]
#         Logger.info("SUCCESS:"+str(member))
#         pushSuccessList.append(member)
# 
#     def on_push_error(self,request,result):
#         Logger.info("on_push_error called:")
#         Logger.info("  request="+str(request))
#         Logger.info("    request body="+str(request.req_body))
#         Logger.info("    request headers="+str(request.req_headers))
#         Logger.info("  result="+str(result))
    
# #print("key:%s:x"%type(API_KEY))
# mem_url = "https://api.d4h.org/v2/team/members"
# grp_url = "https://api.d4h.org/v2/team/groups"
# payload = {}
# headers = {
#   'Authorization': 'Bearer '+API_KEY
# }
# 
# ##########  read all groups and check to see that all items in resour are found
# ##########    If not output a message and continue.  Do not have means to check for
# ##########    new, relavent Groups
# 
# ## group data search
# grp_dic = []
# response = requests.request("GET", grp_url, headers=headers, data = payload)
# dic1 = json.loads(response.text)  ## get a list of all groups
# stat = dic1['statusCode']
# if (stat != '200'): quit   #################  add informational message
# 
# dic2=dic1['data']  ## data section of retrieved group list
# 
# ## test to see if all groups are still defined
# for iu in range(0,len(resour)):
#   ifnd = 0
#   for iw in range(0, len(dic2)):
#     if (resour[iu] in dic2[iw]['title']): ifnd = 1
#   if (ifnd == 0):
#     ### add informational message - group name has changed
#     print("<h1>406</h1><p>A group definition in d4h has changed <%s>.  Need to update roster creator</p>"% resour[iu])
# # continue anyway
# 
# ## member data
# mem_dic = {}
# 
# response = requests.request("GET", mem_url, headers=headers, data = payload)
# dic1 = json.loads(response.text)  ## get a list of all members
# stat = dic1['statusCode']
# if (stat != '200'): quit   #################  add informational message
# 
# dic2=dic1['data']  ## data section of retrieved member list
# for iu in range(0,len(dic2)):
#   rlist = []
#   m=dic2[iu]          ## record number for a given member
# 
#   ##  Get the groups for each member
#   #print("%s %s %s %s"%(m['id'], m['name'], m['ref'], m['mobilephone'])) # basic member data
#   memgrp_url = "https://api.d4h.org/v2/team/members/"+str(m['id'])+"/groups"
#   response = requests.request("GET", memgrp_url, headers=headers, data = payload)
#   dic3 = json.loads(response.text)
#   stat = dic3['statusCode']
#   if (stat != '200'): quit
#   dic4=dic3['data']  ## data section of retrieved member's groups
#   for ix in range(0,len(dic4)):
#     ####  pick resources by name
#     for iw in range(0, len(resour)):
#       if (resour[iw] in dic4[ix]['title'] and resourTR[iw] not in rlist):
#         rlist.append(resourTR[iw])  ## assemble list of extracted groups (resources)
#   # print(rlist)
#   ## create record in memory
#   mem_dic[iu] = {'name': m['name'], 'sar_id': m['ref'], 'd4h_id': m['id'], 'cell': m['mobilephone'], 'rsour': str(rlist)}
# 
# #print(mem_dic)
# 
# ##### Initialize database connection and update
# c_roster = sqlite3.connect(r"SignIn.db")       ## add roster and dbInfo tables to signin.db file
# 
# try:
#   c = c_roster.cursor()
# except sqlite3.Error as er:
#   print("Error initializing roster db cursor: %s\n" % er)
#   quit
# 
# try:  ##  Create the table if it does not exist
#   c.execute('''CREATE TABLE IF NOT EXISTS roster (name text, sar_id text, d4h_id text, cell text, rsour text)''')
# except sqlite3.Error as er:
#   print("Error creating roster table: %s\n" % er)
#   quit
# 
# try:  ##  Create the table if it does not exist
#   c.execute('''CREATE TABLE IF NOT EXISTS dbInfo (id int, roster_date text)''')
# except sqlite3.Error as er:
#   print("Error creating dbInfo table: %s\n" % er)
#   quit
# 
# 
# # Insert rows of data
# c.execute("DELETE FROM roster")   # remove all rows prior to rebuilding
# for iu in range(0, len(mem_dic)):
#   c.execute("INSERT INTO roster (name, sar_id, d4h_id, cell, rsour) VALUES (?,?,?,?,?)", \
#           (mem_dic[iu]['name'],mem_dic[iu]['sar_id'],mem_dic[iu]['d4h_id'],mem_dic[iu]['cell'],mem_dic[iu]['rsour']))
# 
# # Time
# tx = str(time.time())
# c.execute("SELECT * FROM dbInfo")  ## check if record exists
# rec=c.fetchone()
# if (rec == None):
#   c.execute("INSERT INTO dbInfo (id, roster_date) VALUES (?,?)", (1,tx))
# c.execute("UPDATE dbInfo SET roster_date = ?", (tx,))  # make it a tuple
# # Save (commit) the changes
# c_roster.commit()
# print("End")
# 
# '''
# ## test
# c.execute("SELECT * FROM roster")
# rec=c.fetchall()
# for row in rec:
#   print(row)
# c.execute("SELECT * FROM dbInfo")
# rec=c.fetchall()
# print(rec)
# print("end Test")
# '''

