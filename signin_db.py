# #############################################################################
#
#  signin_db.py - sqlite3 database layer code for sign-in app
#     this code is meant to be called from the app running on a local node,
#     and also by the API code running on the server
#
#  sign-in is developed for Nevada County Sheriff's Search and Rescue
#    Copyright (c) 2019 Tom Grundy
#
#  http://github.com/ncssar/sign-in
#
#  Contact the author at nccaves@yahoo.com
#   Attribution, feedback, bug reports and feature requests are appreciated
#
#  REVISION HISTORY
#-----------------------------------------------------------------------------
#   DATE   | AUTHOR | VER |  NOTES
#-----------------------------------------------------------------------------
#
# #############################################################################

import sqlite3
import json
import time

EVENTS_COLS=[
    # on the cloud server, LocalEventID will equal CloudEventID
    ["CloudEventID","INTEGER"],
    ["LANIDString","TEXT"],
    ["EventType","TEXT"],
    ["EventName","TEXT"],
    ["EventLocation","TEXT"],
    ["EventStartDate","TEXT"],
    ["EventStartTime","TEXT"],
    ["EventStartEpoch","REAL"],
    ["Finalized","TEXT"],
    ["LastEditEpoch","REAL"]]

SIGNIN_COLS=[
    ["ID","TEXT"],
    ["Name","TEXT"],
    ["Agency","TEXT"],
    ["Resource","TEXT"],
    ["TimeIn","TEXT"],
    ["TimeOut","TEXT"],
    ["Total","TEXT"],
    ["InEpoch","REAL"],
    ["OutEpoch","REAL"],
    ["TotalSec","REAL"],
    ["CellNum","TEXT"],
    ["Status","TEXT"],
    ["Synced","INTEGER"]]


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def q(query):
    print("q called: "+query)
    conn = sqlite3.connect('SignIn.db')
    conn.row_factory = dict_factory
    cur = conn.cursor()
    r=cur.execute(query).fetchall()
    conn.commit()
    print("  result:" +str(r))
    return r

def createEventsTableIfNeeded():
    # on the cloud server, LocalEventID will equal CloudEventID
    colString="'LocalEventID' INTEGER PRIMARY KEY AUTOINCREMENT,"
    colString+=', '.join([str(x[0])+" "+str(x[1]) for x in EVENTS_COLS])
    query='CREATE TABLE IF NOT EXISTS "Events" ('+colString+');'
    return q(query)

def qInsert(tableName,d):
    colList="({columns})".format(
                columns=', '.join(d.keys()))
    valList="{values}".format(
                values=tuple(d.values()))  
    query="INSERT INTO '{tablename}' {colList} VALUES {valList};".format(
        tablename=tableName,
        colList=colList,
        valList=valList)
    return q(query)
    
def sdbNewEvent(d):
#     app.logger.info("new called")
#     if not request.json:
#         app.logger.info("no json")
#         return "<h1>400</h1><p>Request has no json payload.</p>", 400
#     if type(request.json) is str:
#         d=json.loads(request.json)
#     else: #kivy UrlRequest sends the dictionary itself
#         d=request.json

#     query="CREATE TABLE IF NOT EXISTS {id}_meta (\n"+',\n'.join(META_COLS)
#     app.logger.info("query to add meta table:")
#     colList="({columns})".format(
#                 columns=', '.join(d.keys()))
#     valList="{values}".format(
#                 values=tuple(d.values()))  
#     query="INSERT INTO Events {colList} VALUES {valList};".format(
#         colList=colList,
#         valList=valList)
    createEventsTableIfNeeded()
    d["EventStartEpoch"]=time.time()
    qInsert("Events",d)
    # now get the same record(s) from the local (host) db so the downstream tool can validate
    #  note that it should only return one record; the downstream tool should check;
    #  also note that strictly descending order is only safe because the table uses AUTOINCREMENT
    r=q("SELECT * FROM Events ORDER BY LocalEventID DESC LIMIT 1;")
    validate=r[0]
#     app.logger.info(str(validate))
    colString=', '.join([str(x[0])+" "+str(x[1]) for x in SIGNIN_COLS])
    query='CREATE TABLE IF NOT EXISTS "'+str(validate["LocalEventID"])+'_SignIn" ('+colString+');'
#     app.logger.info("query to add signin table:")
#     app.logger.info(query)
    q(query)
    
    # in url request context, we want to return a full flask jsonify object and a response code
    #  but since we are not using flask here, just return a dictionary and a response code,
    #  and any downstream tool that needs to send json will have to jsonify the dictionary
    return {'query': query,'validate': validate}, 200
    
def sdbHome():
    return '''<h1>SignIn Database API</h1>
<p>API for interacting with the sign-in databases</p>'''

# getSyncCandidates: return a list of non-finalized events in the current time window
def sdbGetSyncCandidates(timeWindowDaysAgo=1):
    now=time.time()
    dayAgo=now-(timeWindowDaysAgo*24*60*60)
#     candidates=q('SELECT * FROM Events ORDER BY LocalEventID WHERE Finalized != "Yes" AND EventStartEpoch BETWEEN '+str(now)+' AND '+str(dayAgo)+';')
    query='SELECT * FROM Events WHERE "EventStartEpoch" > '+str(dayAgo)+' ORDER BY LocalEventID;'
    print("query string: "+query)
    candidates=q(query)
    return candidates
    
def sdbGetEvent(eventID):
    return jsonify(q('SELECT * FROM '+str(eventID)+'_SignIn;'))

def sdbAll():
    return jsonify(q('SELECT * FROM SignIn;'))

def sdbGetEventHTML(eventID):
    tableName=str(eventID)+"_SignIn"
    all=q('SELECT * FROM '+tableName+';')
    here=q("SELECT * FROM "+tableName+" WHERE Status != 'SignedOut';")
    cols=["ID","Name","TimeIn","TimeOut","Total","Status"]
    html = "<html><head><title>SignIn Database</title></head><body>"
    html+="Total:"+str(len(all))+"&nbsp&nbsp&nbspHere:"+str(len(here))
    html+="<table border='1'>"
    html+="<tr>"
    for col in cols:
        html+="<th>"+col+"</th>"
    html+="</tr>"
    for row in all:
        html+="<tr>"
        for col in cols:
            html+="<td>"+row[col]+"</td>"
        html+="</tr>"
    html+="</body></html>"
    return html

# it's cleaner to let the host decide whether to add or to update;
# if ID, Agency, Name, and InEpoch match those of an existing record,
#  then update that record; otherwise, add a new record;
# PUT seems like a better fit than POST based on the HTTP docs
#  note: only store inEpoch to the nearest hunredth of a second since
#  comparison beyond 5-digits-right-of-decimal has shown truncation differences

def sdbAddOrUpdate(eventID,d):
#     app.logger.info("put1")
#     app.logger.info("put called for event "+str(eventID))
#     if not request.json:
#         app.logger.info("no json")
#         return "<h1>400</h1><p>Request has no json payload.</p>", 400
#     if type(request.json) is str:
#         d=json.loads(request.json)
#     else: #kivy UrlRequest sends the dictionary itself
#         d=request.json

#     d['InEpoch']=round(d['InEpoch'],2)
#     d['OutEpocj']=round(d['OutEpoch'],2)
    
    # query builder from a dictionary that allows for different data types
    #  https://stackoverflow.com/a/54611514/3577105
#     colVal="({columns}) VALUES {values}".format(
#                 columns=', '.join(d.keys()),
#                 values=tuple(d.values())
#             )
#     colList="({columns})".format(
#                 columns=', '.join(d.keys()))
#     valList="{values}".format(
#                 values=tuple(d.values()))        
    # 1. find any record(s) that should be modified
    tablename=str(eventID)+"_SignIn"
    condition="ID = '{id}' AND Name = '{name}' AND Agency = '{agency}' AND InEpoch = '{inEpoch}'".format(
            id=d['ID'],name=d['Name'],agency=d['Agency'],inEpoch=d['InEpoch'])
    query="SELECT * FROM '{tablename}' WHERE {condition};".format(
            tablename=tablename,condition=condition)
#     app.logger.info('query:'+query)
    r=q(query)
#     app.logger.info("result:"+str(r))
    if len(r)==0: # no results: this is a new sign-in; add a new record
        # query builder from a dictionary that allows for different data types
        #  https://stackoverflow.com/a/54611514/3577105
#         query="INSERT INTO {tablename} ({columns}) VALUES {values};" .format(
#                 tablename='SignIn',
#                 columns=', '.join(d.keys()),
#                 values=tuple(d.values())
#             )
#         query="INSERT INTO {tablename} {colList} VALUES {valList};".format(
#                 tablename='SignIn',
#                 colList=colList,
#                 valList=valList)
#         app.logger.info("query string: "+query)
#         q(query)
        qInsert(tablename,d)
    elif len(r)==1: # one result found; this is a sign-out, status udpate, etc; modify existing record
        # UPDATE .. SET () = () syntax is only supported for sqlite3 3.15.0 and up;
        #  pythonanywhere only has 3.11.0, so, use simpler queries instead
#       query="UPDATE {tablename} SET {colList} = {valList} WHERE {condition};".format(
#               tablename='SignIn',
#               colList=colList,
#               valList=valList,
#               condition=condition)
        query="UPDATE '{tablename}' SET ".format(tablename=tablename)
        for key in d.keys():
            query+="{col} = '{val}', ".format(
                col=key,
                val=d[key])
        query=query[:-2] # get rid of the final comma and space
        query+=" WHERE {condition};".format(condition=condition)
#         app.logger.info("query string: "+query)
        q(query)
    else:
        return jsonify({'error': 'more than one record in the host database matched the ID,Name,Agency,InEpoch values from the sign-in action'}), 405

    # now get the same record(s) from the local (host) db so the downstream tool can validate
    #  note that it should only return one record; the downstream tool should check
    validate=q("SELECT * FROM '{tablename}' WHERE {condition};".format(
            tablename=tablename,
            condition=condition))
    
    # in url request context, we want to return a full flask jsonify object and a response code
    #  but since we are not using flask here, just return a dictionary and a response code,
    #  and any downstream tool that needs to send json will have to jsonify the dictionary
#     return jsonify({'query': query,'validate': validate}), 200
    return {'query': query,'validate': validate}, 200

def sdbPageNotFound(e):
    return "<h1>404</h1><p>The resource could not be found.</p>", 404
