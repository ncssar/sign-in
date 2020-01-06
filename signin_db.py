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
#  12-11-19   TMG     0.9   first upload to cloud
#  12-14-19   TMG     0.91  don't try to return http-style responses with
#                             result code; the api layer should do that; just
#                             return dictionaries, strings, etc.; get rid of
#                             sdbPageNotFound for the same reason
#
# #############################################################################

import sqlite3
import time

EVENTS_COLS=[
    # LocalEventID is hardcoded as the primary key
    ["CloudEventID","INTEGER"],
    ["D4HID","INTEGER"],
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

# needed to make query return values dictionaries instead of lists of tuples
def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

# each machine running this code will have its own local database file SignIn.db;
#  they are kept separate by the fact that only one separate instance of this code
#  is running on each machine involved (one on each server, one on each client)
def q(query,params=None):
    print("q called: "+query)
    conn = sqlite3.connect('SignIn.db')
    conn.row_factory = dict_factory # so that return value is a dict instead of tuples
    cur = conn.cursor()
    # fetchall if params is blank seems to only return a tuple, not a dict
    if params is not None:
        r=cur.execute(query,params).fetchall()
    else:
        r=cur.execute(query).fetchall()
    conn.commit()
    print("  result:" +str(r))
    return r

def createEventsTableIfNeeded():
    colString="'LocalEventID' INTEGER PRIMARY KEY AUTOINCREMENT,"
    colString+=', '.join([str(x[0])+" "+str(x[1]) for x in EVENTS_COLS])
    query='CREATE TABLE IF NOT EXISTS "Events" ('+colString+');'
    return q(query)


# intercept any None values and change them to NULL
# def noneToQuestion(x):
#     if x is None:
#         return 'NULL'
#     else:
#         return x
    
# def qInsert(tableName,d):
#     print("qInsert called: tableName="+str(tableName)+"  d="+str(d))
#     colList="({columns})".format(
#                 columns=', '.join(d.keys()))
# #     values=list(map(noneToNull,d.values()))
#     values=list(d.values())
#     print("  mapped values="+str(values))
#     valList="{values}".format(
#                 values=tuple(values))
#     
#     query="INSERT INTO '{tablename}' {colList} VALUES {valList};".format(
#         tablename=tableName,
#         colList=colList,
#         valList=valList)
#     return q(query)

# insert using db parameters to avoid SQL injection attack and to correctly handle None
def qInsert(tableName,d):
    print("qInsert called: tableName="+str(tableName)+"  d="+str(d))
    colList="({columns})".format(
            columns=', '.join(d.keys()))
    valList="({columns})".format(
            columns=", ".join([":"+str(x) for x in d.keys()]))
    query="INSERT INTO '{tablename}' {colList} VALUES {valList};".format(
            tablename=tableName,
            colList=colList,
            valList=valList)
    return q(query,d)
    
#####################################
## BEGIN SDB FUNCTIONS
#####################################
## sdb = 'sign-in database'
## these functions are called directly from kivy / python code running locally
##   on client nodes, and also from API handlers running on the server(s)
## return values from these functions do not need to be jsonified, since this
##   code is called from other python code in one way or another; the API
##   handlers that call this code should perform jsonification, while client
##   nodes do not need to do any jsonification

# sdbNewEvent - create a new event
#   d = dictionary of all required key-value pairs required to create a new event
#   return = dictionary so that the caller can validate the added event
def sdbNewEvent(d):
    createEventsTableIfNeeded()
    # set start time to current time if none was specified
    if d.get("EventStartEpoch",0)==0:
        d["EventStartEpoch"]=time.time()
    # add the new event record in the Events table
    qInsert("Events",d)
    # now get the same record db so the caller can validate
    #  also note that strictly descending order is only safe because the table uses AUTOINCREMENT
    r=q("SELECT * FROM Events ORDER BY LocalEventID DESC LIMIT 1;")
    validate=r[0]
    # create the corresponding <LocalEventID>_SignIn table
    colString=', '.join([str(x[0])+" "+str(x[1]) for x in SIGNIN_COLS])
    query='CREATE TABLE IF NOT EXISTS "'+str(validate["LocalEventID"])+'_SignIn" ('+colString+');'
    q(query)
    return {'query': query,'validate': validate}

# sdbSetCloudEventID - pair a local event to a cloud event
#   this function will only be called from clients, not from servers
def sdbSetCloudEventID(localEventID,cloudEventID):
    return q("UPDATE 'Events' SET CloudEventID = {cloudEventID} WHERE LocalEventID = {localEventID};".format(
            cloudEventID=cloudEventID,
            localEventID=localEventID))

# sdbHome - return a welcome message to verify that this code is running
def sdbHome():
    return '''<h1>SignIn Database API</h1>
            <p>API for interacting with the sign-in databases</p>'''

# sdbGetEvents - query the Events table
#  lastEditSince [0] - only return events whose LastEditEpoch is greater than this value
#  eventStartSince [0] - only return events whose EventStartEpoch is greater than this value
#  nonFinalizedOnly [False] - if True, only return events whose Finalized value is 0
#  return - list of matching record(s)
def sdbGetEvents(lastEditSince=0,eventStartSince=0,nonFinalizedOnly=False):
    print("sdbGetEvents called: lastEditedSince="+str(lastEditSince)+"  eventStartSince="+str(eventStartSince)+"  nonFinalizedOnly="+str(nonFinalizedOnly))
    createEventsTableIfNeeded()
    condition="EventStartEpoch > '{eventStartSince}' AND LastEditEpoch > '{lastEditSince}'".format(
        eventStartSince=eventStartSince,lastEditSince=lastEditSince)
    if nonFinalizedOnly:
        condition+=" AND Finalized = 0"
    return q("SELECT * FROM 'Events' WHERE {condition};".format(
            condition=condition))

def sdbGetEvent(eventID):
    tableName=str(eventID)+"_SignIn"
    all=q("SELECT * FROM '"+tableName+"';")
    return all

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

def sdbUpdateLastEditEpoch(eventID):
    query="UPDATE 'Events' SET LastEditEpoch = "+str(round(time.time(),2))+" WHERE LocalEventID = "+str(eventID)+";"
    r=q(query)

# it's cleaner to let the host decide whether to add or to update;
# if ID, Agency, Name, and InEpoch match those of an existing record,
#  then update that record; otherwise, add a new record;
# PUT seems like a better fit than POST based on the HTTP docs
#  note: only store inEpoch to the nearest hundredth of a second since
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
        sdbUpdateLastEditEpoch(eventID)
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
        sdbUpdateLastEditEpoch(eventID)
    else:
        return {'error': 'more than one record in the host database matched the ID,Name,Agency,InEpoch values from the sign-in action'}, 405

    # now get the same record(s) from the local (host) db so the downstream tool can validate
    #  note that it should only return one record; the downstream tool should check
    validate=q("SELECT * FROM '{tablename}' WHERE {condition};".format(
            tablename=tablename,
            condition=condition))

    # in url request context, we want to return a full flask jsonify object and a response code
    #  but since we are not using flask here, just return a dictionary and a response code,
    #  and any downstream tool that needs to send json will have to jsonify the dictionary
#     return jsonify({'query': query,'validate': validate}), 200
    return {'query': query,'validate': validate}
