############################################################################
#
#  main.py - main entry point for sign-in app
#
#  sign-in is developed for Nevada County Sheriff's Search and Rescue
#    Copyright (c) 2019 Tom Grundy
#
#   sign-in (c) 2019 Tom Grundy, using kivy and buildozer
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

## csv file spec to interface with t-card program 8-16-19:
## SARID, "NAME(LAST,FIRST)", AGENCY, RESOURCES, TIME-IN(HUMAN), TIME-OUT, TIME-DELTA, TIME-IN(EPOCH FLOAT),
##         TIME-OUT, TIME-DELTA, CELL#, "STATUS(SignIn, SignOut, OnTcard, RmTcard)"
##     Status exchange: SignIn from Sign-in program, acknowledge by OnTcard from Tcard
##                      then, RmTcard from Tcard enabling SignOut at Sign-Out
__version__ = '1.0'

# perform any calls to Config.set before importing any kivy modules!
# (https://kivy.org/docs/api-kivy.config.html)
from kivy.config import Config
Config.set('kivy','keyboard_mode','system')
Config.set('kivy','log_dir','log')
Config.set('kivy','log_enable',1)
Config.set('kivy','log_level','info')
Config.set('kivy','log_maxfiles',5)
Config.set('graphics','width','505')
Config.set('graphics','height','800')

import time
import csv
import os
import copy
import shutil
import sqlite3
import re
from datetime import datetime,timezone
# import requests
# from requests.exceptions import Timeout
import json
from functools import partial
import urllib.parse
import certifi # attempt to fix SSL shared-token problem on Android


# database interface module shared by this app and the signin_api
from signin_db import *

# from reportlab.lib import colors,utils
# from reportlab.lib.pagesizes import letter,landscape
# from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image, Spacer
# from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
# from reportlab.lib.units import inch

import kivy
kivy.require('1.9.1')

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.button import Button
from kivy.uix.recyclegridlayout import RecycleGridLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.recyclegridlayout import RecycleGridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.switch import Switch
from kivy.uix.checkbox import CheckBox
from kivy.uix.popup import Popup
from kivy.uix.dropdown import DropDown
from kivy.uix.textinput import TextInput
from kivy.properties import BooleanProperty, ListProperty, StringProperty, ObjectProperty,NumericProperty
from kivy.clock import Clock
from kivy.utils import platform
from kivy.core.window import Window

# custom version of kivy/network/urlrequest.py to allow synchronous (blocking) requests
from urlrequest_tmg import UrlRequest

# # from kivy.garden import datetimepicker
# # DatePicker from https://github.com/Skucul/datepicker
# from datepicker import DatePicker
from datepicker import *
# # TimePicker from https://github.com/Skucul/timepicker
from timepicker import *

from kivy.logger import Logger

if platform in ('android'):
    from jnius import cast
    from jnius import autoclass
    
    # android pyjnius stuff, used for download and for FLAG_KEEP_SCREEN_ON
    Environment=autoclass('android.os.Environment')
    PythonActivity=autoclass('org.kivy.android.PythonActivity')
    View = autoclass('android.view.View') # to avoid JVM exception re: original thread
    Params = autoclass('android.view.WindowManager$LayoutParams')
    mActivity=PythonActivity.mActivity
    Context=autoclass('android.content.Context')
    DownloadManager=autoclass('android.app.DownloadManager')

    # SSL fix https://github.com/kivy/python-for-android/issues/1827#issuecomment-500028459    
    os.environ['SSL_CERT_FILE']=certifi.where()

    
#     # SymmetricDS
#     Logger.info("trace1")
#     symmetricService=autoclass('org.jumpmind.symmetric.SymmetricService')
#     Logger.info("trace2")
#     arg=''
#     Logger.info("trace3")
#     symmetricService.start(mActivity,arg)
#     Logger.info("trace4")

def sortSecond(val):
    return val[1]

def utc_to_local(utc_dt,tz=None):
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=tz)

def toast(text):
    if platform in ('android'):
        PythonActivity.toastError(text)
    else:
        Logger.info("TOAST:"+text)

CERT_DICT={
    "IC":"IC Team Member",
    "LD":"Field Team Leader",
    "DR":"Trailer Driver",
    "K9":"K9 Handler",
    "M":"Motorcycle Driver",
    "R":"Ropes Team Member",
    "EMT":"Emergency Medical Tech.",
    "H":"Mounted Team Member",
    "HT":"Hasty Team Member",
    "SC":"Snow Cat Driver",
    "PM":"Paramedic",
    "SM":"Snowmobile Driver",
    "N":"Nordic Team Member",
    "UTV1":"UTV Type 1 Driver",
    "ATV1":"ATV Type 1 Driver",
    "CI":"Crisis Team Member",
    "MT":"Tracking Team Member",
    "E":"Evidence Team Member",
    "D":"Dive Team Member",
    "RN":"Registered Nurse"}

# for searches, the following certs will prompt the member as to whether
#  they are ready to deploy as that resource type; include
#  resource types that need special gear (dog, horse, atv, extra clothing)
CERTS_NEED_PROMPT=["K9","M","H","SC","SM","N","ATV1","D"]

class signinApp(App):
    def build(self):
        Logger.info("build starting...")
        Logger.info("platform="+str(platform))
        # from https://pastebin.com/5e7ymKTU
        Window.bind(on_request_close=self.on_request_close)
        Window.bind(on_keyboard=self.on_keyboard)
        self.defaultTextHeightMultiplier=0.7
        self.gui=Builder.load_file('main.kv')
        self.adminCode='925'
        self.adminMode=False
        self.signin_dateformat="%a %b %d %Y"
        self.signin_timeformat="%H:%M"
        self.signin_datetimeformat=self.signin_dateformat+" "+self.signin_timeformat
        
        self.d4hServer="https://api.d4h.org"
        self.d4h_api_key="c04df203ed6776b0088534301612f010cafb8eed" # owner=Ash Defour
        self.d4h_datetimeformat="%Y-%m-%dT%H:%M:%S.000Z" # used by strftime and strptime
        self.d4h_timezone_name="America/Los_Angeles" # updated during checkForD4H
        self.cloudServer="http://127.0.0.1:5000" # localhost, for development
        self.cloudServer="http://caver456.pythonanywhere.com"
        
#         self.columns=["ID","Name","Agency","Resource","TimeIn","TimeOut","Total","InEpoch","OutEpoch","TotalSec","CellNum","Status"]
        self.columns=[x[0] for x in SIGNIN_COLS]
#         self.realCols=["InEpoch","OutEpoch","TotalSec"] # all others are TEXT
        self.roster={}
        self.eventType="Meeting"
        self.eventName=""
        self.eventLocation=""
        self.eventStartDate=""
        self.eventStartTime=""
        self.localEventID=None
        self.cloudEventID=None
        self.signInTableName="SignIn"
#         self.syncChoicesList=[] # redundant
        self.signInList=[]
#         self.exportList=[]
#         self.csvFileName="C:\\Users\\caver\\Downloads\\sign-in.csv"
        if platform in ('windows'):
            self.downloadDir=os.path.join(os.path.expanduser('~'),"Downloads")
            # downloadDir and csvDir cannot be the same - if they are, you get
            #  a warning during download when it tries to copy the file from
            #  csvDir to downloadDir, obviously
            self.rosterDir=os.path.join(os.path.expanduser('~'),"Documents")
            self.csvDir=self.rosterDir
        else:
#             self.rosterDir="/storage/emulated/0/Download"
            self.downloadDir="/storage/emulated/0/Download"
            self.csvDir=os.path.dirname(os.path.abspath(__file__))
#             self.rosterDir=self.csvDir # need to get permision to read local files, then use a file browser
            self.rosterDir=self.downloadDir # TO DO: implement a dir search tree
        self.rosterFileName=os.path.join(self.rosterDir,"roster.csv")
        self.csvFileName=os.path.join(self.csvDir,"sign-in.csv")
        self.printLogoFileName="images/logo.jpg"
        self.syncCloudIconFileName="images/cloud_white_64x64.png"
        self.syncLocalIconFileName="images/local_icon.png"
        self.syncD4HIconFileName="images/d4h_logo_green.png"
        self.syncCloudUploadStartIconFileName="images/cloud_upload_white_64x64.png"
        self.syncCloudUploadSuccessIconFileName="images/cloud_upload_white_64x64.png"
        self.syncCloudDownloadStartIconFileName="images/cloud_download_white_64x64.png"
        self.syncCloudDownloadSuccessIconFileName="images/cloud_download_white_64x64.png"
        self.syncNoneIconFileName="images/blank_64x64.png"
        self.agencyNameForPrint="NEVADA COUNTY SHERIFF'S SEARCH AND RESCUE"
        self.topbar=TopBar()
        self.topbar.ids.syncButtonImage.source=self.syncNoneIconFileName
        self.sm=ScreenManager()
        self.sm.add_widget(KeypadScreen(name='keypad'))
        self.sm.add_widget(SignInScreen(name='signin'))
#         self.sm.add_widget(SignInTypeScreen(name='signintype'))
        self.sm.add_widget(SignOutScreen(name='signout'))
        self.sm.add_widget(AlreadySignedOutScreen(name='alreadysignedout'))
        self.sm.add_widget(ThankyouScreen(name='thankyou'))
        self.sm.add_widget(ListScreen(name='theList'))
        self.sm.add_widget(LookupScreen(name='lookup'))
        self.sm.add_widget(NewEventScreen(name='newevent'))
        self.sm.add_widget(DetailsScreen(name='details'))
        self.keypad=self.sm.get_screen('keypad')
        self.signin=self.sm.get_screen('signin')
#         self.signintype=self.sm.get_screen('signintype')
        self.signout=self.sm.get_screen('signout')
        self.alreadysignedout=self.sm.get_screen('alreadysignedout')
        self.thankyou=self.sm.get_screen('thankyou')
        self.theList=self.sm.get_screen('theList')
        self.lookup=self.sm.get_screen('lookup')
        # auto-raise the keyboard when the lookup screen is shown;
        # auto-blank the lookup text and results when the screen is changed
        self.lookup.on_enter=self.lookupEnter
        self.lookup.on_leave=self.lookupLeave
        self.newevent=self.sm.get_screen('newevent')
        self.details=self.sm.get_screen('details')
#         self.keypad.on_enter=self.setKeepScreenOn()
#         self.keypad.on_leave=self.clearKeepScreenOn()
#         self.details.ids.eventStartTimeLabel.bind(on_touch_down=DatetimePicker)
        self.defaultNameButtonText='Enter your SAR #'
#         self.exitAdminMode()
        self.enterAdminMode()
        self.typed=''
        self.finalized=False
        self.details.rosterFileName=self.rosterFileName
        self.startTime=round(time.time(),2) # round to hundredth of a second to aid database comparison 
        self.readRoster()
#         self.setupAlphaGrouping()
        self.clocktext=self.topbar.ids.clocktext
        Clock.schedule_interval(self.clocktext.update,1)
        self.showDetails()
            
#         self.recoverIfNeeded()
        Logger.info("Valid roster files:"+str(self.scanForRosters()))
          
#         self.initCloud()
# #         self.initSql()
#         self.sync()
        
        self.container=BoxLayout(orientation='vertical')
        self.container.add_widget(self.topbar)
        self.container.add_widget(self.sm)

        self.initPopup=self.textpopup(title='Please Wait',text='Checking connections...',size_hint=(0.9,0.3))

        # do the rest of the startup after GUI is launched:
        #  (this method is recommended in some posts, and is more reliable
        #   that on_start which runs before the main loop starts, meaning
        #   code during on_start happens with a frozed white GUI; but it also
        #   has a race condition - if you call it too soon, you get a crazy GUI)
        Clock.schedule_once(self.startup,2)
        
        return self.container

#     def q(self,query):
# #         Logger.info("** EXECUTING QUERY: "+str(query))
#         self.cur.execute(query)
        
#     def initSql(self):
#         self.con=sqlite3.connect('SignIn.db')
#         with self.con:
#             self.cur=self.con.cursor()
# #             self.q("CREATE TABLE IF NOT EXISTS About("
# #                 "EventName TEXT,"
# #                 "")
#             # build the initialization query
#             query="CREATE TABLE IF NOT EXISTS SignIn("
#             colTextList=[]
#             for c in self.columns:
#                 type='TEXT'
#                 if c in self.realCols:
#                     type='REAL'
#                 colTextList.append(c+" "+type)
#             query+=','.join(colTextList)
#             query+=")"
#             Logger.info("init query:"+query)
#             self.q(query)
# #             self.q("CREATE TABLE IF NOT EXISTS SignIn("
# #                 "ID TEXT,"
# #                 "Name TEXT,"
# #                 "Agency TEXT,"
# #                 "Resources TEXT,"
# #                 "TimeIn TEXT,"
# #                 "TimeOut TEXT,"
# #                 "TotalTime TEXT,"
# #                 "EpochIn REAL,"
# #                 "EpochOut REAL,"
# #                 "TotalSec REAL,"
# #                 "CellNum TEXT,"
# #                 "Status TEXT)")

    # restart: called from GUI; disallow auto-recover - show all choices
    def restart(self,*args):
        self.startup(allowRecoverIfNeeded=False)
        
    def startup(self,*args,allowRecoverIfNeeded=True):
        # perform startup tasks here that should take place after the GUI is alive:
        # - check for connections (cloud and LAN(s))
        Logger.info("startup called")
#         popup=self.textpopup(title='Please Wait',text='Checking connections...',buttonText=None,size_hint=(0.9,0.3))
#         popup=self.textpopup(title='Please Wait',text='Checking connections...',size_hint=(0.9,0.3))
        createEventsTableIfNeeded()
        self.checksComplete=0
        # these are all asynchronous requests, so, wait until there is an answer (or timeout) from each
        Logger.info("calling checkForCloud")
        self.checkForCloud()
        Logger.info("calling checkForD4H")
        self.checkForD4H()
        Logger.info("calling checkForLANs")
        self.checkForLANs()
#         tc=0
#         while self.checksComplete<3 and tc<10:
#             Logger.info("startup timer = "+str(tc)+"; checks complete = "+str(self.checksComplete))
#             time.sleep(1)
#             Clock.tick() # required! process pending kivy events, such as checking for responses!
#             tc+=1
        self.initPopup.dismiss()
        if allowRecoverIfNeeded:
            if not self.recoverIfNeeded():
                Logger.info("calling buildSyncChoicesList")
                self.buildSyncChoicesList()       
        else:
            Logger.info("calling buildSyncChoicesList")
            self.buildSyncChoicesList()
            
#     def startup_part2(self):
#         Logger.info("calling initLANs")
#         self.initLANs()
#         Logger.info("calling popup.dismiss")
# #         popup.dismiss()
#         self.initPopup.dismiss()
#         if not self.recoverIfNeeded():
#             Logger.info("calling buildSyncChoicesList")
#             self.buildSyncChoicesList()
#         Logger.info("startup complete")

    def checkForCloud(self):
        self.cloud=False
        request=UrlRequest(self.cloudServer,
                on_success=self.on_checkForCloud_success,
                on_failure=self.on_checkForCloud_error,
                on_error=self.on_checkForCloud_error,
                timeout=5,
                method="GET",
                debug=True)
#         request.wait()
    
    def on_checkForCloud_success(self,request,result):
        Logger.info("on_checkForCloud_success called: response="+str(result))
        if 'SignIn Database API' in str(result):
            Logger.info("  valid response detected; cloud connection established.")
            self.cloud=True
#         self.checksComplete+=1
#         self.startup_part2()
    
    def on_checkForCloud_error(self,request,result):
        Logger.info("on_checkForCloud_error called:")
        Logger.info("  request was sent to "+str(request.url))
        Logger.info("    request body="+str(request.req_body))
        Logger.info("    request headers="+str(request.req_headers))
        Logger.info("  result="+str(result))
#         self.startup_part2()
#         self.checksComplete+=1
    
    def checkForD4H(self):
        self.d4h=False
        request=UrlRequest(self.d4hServer+"/v2/team",
                on_success=self.on_checkForD4H_success,
                on_failure=self.on_checkForD4H_error,
                on_error=self.on_checkForD4H_error,
                req_headers={'Authorization':'Bearer '+self.d4h_api_key},
                method="GET",
                timeout=5,
                debug=True)
#                 ca_file="certs.pem") # attempt to fix SSL shared-token problem on Android
#         request.wait()
    
    def on_checkForD4H_success(self,request,result):
        Logger.info("on_checkForD4H_success called: response="+str(result))
        if 'Nevada County SAR' in str(result):
            Logger.info("  valid response detected; D4H connection established.")
            self.d4h=True
            # get the team account timezone offset
            self.d4h_timezone_offset=result["data"]["timezone"]["offset"]
#         self.checksComplete+=1
#         self.startup_part2()
    
    def on_checkForD4H_error(self,request,result):
        Logger.info("on_checkForD4H_error called:")
        Logger.info("  request was sent to "+str(request.url))
        Logger.info("    request body="+str(request.req_body))
        Logger.info("    request headers="+str(request.req_headers))
        Logger.info("  result="+str(result))
#         self.startup_part2()
#         self.checksComplete+=1    
#     def initCloud(self):
#         self.cloud=False
#         try:
#             response=requests.get(self.cloudServer+"/api/v1/",timeout=(3,2))
#         except Timeout:
#             Logger.info('Cloud server did not respond in the allowed timeout period.  Proceeding without cloud connection.')
#         except ConnectionRefusedError:
#             Logger.info('Cloud server connection refused.  Proceeding without cloud connection.')
#         except:
#             Logger.info('CLoud server unhandled exception.  Proceeding without cloud connection.')
#         else:
#             Logger.info('Cloud server connection established.')
#             self.cloud=True

    def checkForLANs(self):
        self.checksComplete+=1
    
#         request=UrlRequest(self.cloudServer+"/api/v1/",
#             on_success=lambda *args: self.cloud=True,
#             on_failure=lambda *args: self.cloud=False,
#             on_error=lambda *args: self.cloud=False,
#             timeout=3,
#             method="GET",
#             debug=True)
#              
    def on_keyboard(self,window,key,*args):
#         Logger.info("key pressed:"+str(key))
        if key==27: # esc key, or android 'back' button
            Logger.info("  esc pressed")
            if self.adminMode:
                self.on_request_close()
            elif self.sm.current=='keypad':
                self.keyDown("bs") # backspace
            elif self.sm.current=='lookup':
                self.switchToBlankKeypad()
            else:
                self.sm.current='keypad'
        elif key==8: # backspace
            Logger.info("  backspace pressed")
            self.keyDown("bs")
        # unicode decimal 32-126 should be printable, so, pass them
        #  to keyDown directly
        elif 31<key<127: # letter or number, regardless of shift key
            self.keyDown(chr(key)) # if not esc or bs, emulate a button press of the same letter/number
        return True
    
    def recoverIfNeeded(self):
        Logger.info("entering recoverIfNeeded")
#         candidates=sdbGetSyncCandidates()
        candidates=sdbGetEvents(lastEditSince=time.time()-1800,nonFinalizedOnly=True)
        Logger.info("  sync candidates:"+str(candidates))
        if len(candidates)==1:
            Logger.info("  just one candidate found in local db; syncing to that event")
            self.syncToEvent(candidates[0])
            self.exitAdminMode()
            self.switchToBlankKeypad()
            return candidates[0]
        
#     def recoverIfNeeded(self): # CSV-based
#         # 1. check for files in the data dir with modification date within 24 hours
#         # 2. of those, check to see which are not finalized
#         # 3. if just one is not finalized, and it's the most recent one, load it
#         # 4. if more than one is not finalized, show a pick box to let user
#         #      select which one to restore
#         # 5. if everything within the last 24 hours is finalized, do not load anything
#         #   if a finalized version of a file exists, don't try to load any of its .bak<x>.csv files
#         Logger.info("entering recoverIfNeeded: start time="+str(self.startTime))
#         csvList=self.scanForCSV()
#         Logger.info("Valid CSV files:"+str(csvList))
#         finalized=[x[0] for x in csvList if x[4]]
#         Logger.info("Finalized CSV files:"+str(finalized))
# #         each sublist is [<filename>,<file_time>,<event_name>,<header_time>,<finalized>]
#         csvCandidates1=[x for x in csvList if self.startTime-x[1]<86400 and not x[4]]
#         csvCandidates1.sort(key=sortSecond)
#         csvCandidates1.reverse() # most recent first, i.e. descending order
#         # remove .bak files that have a finalized non-.bak version - could probably be refactored
#         csvCandidates=[]
#         for x in csvCandidates1:
#             excludeFlag=False
#             if re.match(".*\.bak[0-9]+\.csv$",x[0]): # it's a backup file
#                 nonBakName=re.sub("\.bak[0-9]+","",x[0])
#                 Logger.info("  found a backup file "+x[0]+" - looking for finalized original file "+nonBakName)
#                 if nonBakName in finalized:
#                     Logger.info("    found finalized original file "+nonBakName+"; excluding "+x[0]+" from candidates list")
#                     excludeFlag=True
#             if not excludeFlag:
#                 csvCandidates.append(x)
# 
#         Logger.info("Candidates for recover:"+str(csvCandidates))
#         if len(csvCandidates)>>0:
#             Logger.info("Reading "+csvCandidates[0][0])
#             self.readCSV(csvCandidates[0][0])
#             self.switchToBlankKeypad()
#             toast("Automatically recovering:\n"+csvCandidates[0][2]+"\nEvent started:"+str(csvCandidates[0][3]))
    
    def lookupEnter(self):
        Logger.info("lookupEnter called")
        c=self.lookup.ids.combo
        c.focus=True
        c.drop_down.open(c)
    
    def lookupLeave(self):
        Logger.info("lookupLeave called")
        self.lookup.ids.combo.text='' # for some reason this doesn't call on_options
        self.lookup.ids.combo.options=[] # so call it specifically
        
    def exitAdminMode(self):
        Logger.info("Exiting admin mode")
        self.topbar.ids.listbutton.opacity=0
        self.topbar.ids.listbutton.disabled=True
        self.topbar.ids.listbutton.width=0
        self.topbar.ids.detailsbutton.opacity=0
        self.topbar.ids.detailsbutton.disabled=True
        self.topbar.ids.detailsbutton.width=0
        self.topbar.ids.keypadbutton.opacity=0
        self.topbar.ids.keypadbutton.disabled=True
        self.topbar.ids.keypadbutton.width=0
        self.typed=""
        self.keypad.ids.topLabel.text=""
        self.hide()
        self.adminMode=False
    
    def enterAdminMode(self):
        Logger.info("Entering admin mode")
        self.topbar.ids.listbutton.opacity=1
        self.topbar.ids.listbutton.disabled=False
        self.topbar.ids.listbutton.width=64
        self.topbar.ids.detailsbutton.opacity=1
        self.topbar.ids.detailsbutton.disabled=False
        self.topbar.ids.detailsbutton.width=64
        self.topbar.ids.keypadbutton.opacity=0
        self.topbar.ids.keypadbutton.disabled=True
        self.topbar.ids.keypadbutton.width=0
        self.keypad.ids.nameButton.background_color=(1,0.6,0,1)
        self.keypad.ids.nameButton.text="Admin Mode"
        self.keypad.ids.bottomLabel.text="(tap above to exit)"
        self.keypad.ids.topLabel.text=""
        self.adminMode=True
    
    def hide(self):
        self.keypad.ids.bottomLabel.opacity=0
        self.keypad.ids.bottomLabel.height=0
        self.keypad.ids.nameButton.text=self.defaultNameButtonText
        self.keypad.ids.nameButton.background_color=(0,0,0,0)

    def show(self):
        self.keypad.ids.bottomLabel.opacity=1
        self.keypad.ids.bottomLabel.height=100
        self.keypad.ids.bottomLabel.text="You entered: "+self.typed

    def setKeepScreenOn(self):
        toast("setKeepScreenOn called")
        pass
#         View = autoclass('android.view.View') # to avoid JVM exception re: original thread
#         Params = autoclass('android.view.WindowManager$LayoutParams')
#         PythonActivity.mActivity.getWindow().addFlags(Params.FLAG_KEEP_SCREEN_ON)
        
    def clearKeepScreenOn(self):
        toast("clearKeepScreenOn called")
        pass
#         View = autoclass('android.view.View') # to avoid JVM exception re: original thread
#         Params = autoclass('android.view.WindowManager$LayoutParams')
#         PythonActivity.mActivity.getWindow().clearFlags(Params.FLAG_KEEP_SCREEN_ON)
        
# self.roster is a dictionary: key=ID, val=[name,certifications,cell#]
#  where 'certs' is a string of the format "K9,M,DR," etc as specified in the
#  master roster document; relevant certifications will result in questions
#   "are you ready to deploy as <cert>?" during sign-in
    def readRoster(self):
        self.nextXID=1 # note this means the X# IDs will reset with each roster load
        # which could be a problem if a roster is loaded when people are already signed in
        self.roster={}
        try:
            Logger.info("reading roster file:"+self.details.rosterFileName)
            # on android, default encoding (utf-8) resulted in failure to read roster
            #  with the following error after opening but before the first row is read:
            # [WARNING] 'utf-8' codec can't decode byte 0xb4 in position 736: invalid start byte
            #  (0xb4 is a grave accent which appears in one member's name)
            #  changing to latin-1 solved it in this case, but a better catch-all solution
            #  is probably to use default encoding with a better 'errors' argument:
#             with open(self.details.rosterFileName,'r',encoding='latin-1') as rosterFile:
            with open(self.details.rosterFileName,'r',errors='ignore') as rosterFile:
#                 self.details.ids.rosterTimeLabel.text=time.strftime("%a %b %#d %Y %H:%M:%S",time.localtime(os.path.getmtime(self.details.rosterFileName))) # need to use os.stat(path).st_mtime on linux
                csvReader=csv.reader(rosterFile)
                Logger.info("opened...")
                leoPattern=re.compile("[1234][TSEPDVN][0-9]+")
                for row in csvReader:
                    # critera for adding a row to the roster:
                    #  row[7] (DOE = Date Of Entry) must be non-blank (volunteers)
                    #   OR
                    #  row[0] must match [1234][TSEPDVN][0-9]+ (law enforcement)
                    #  if row[0] (ID) is blank, assign a unique ID here 
                    #   to allow the rest of this app to work.  Start with 'X1'.
#                     Logger.info("row:"+str(row[0])+":"+row[1])
                    # if the first token has any digits, add it to the roster
                    if row[7] not in ("","DOE") or leoPattern.search(row[0]): # skip blanks and the header
#                     if any(i.isdigit() for i in row[0]):
                        if row[0]=="":
                            row[0]="X"+str(self.nextXID)
                            Logger.info("  no ID exists for "+row[1]+": assigning ID "+row[0])
                            self.nextXID=self.nextXID+1
                        self.roster[row[0]]=[row[1],row[5],row[3]]
                        Logger.info("adding:"+str(self.roster[row[0]]))
                self.details.ids.rosterStatusLabel.text=str(len(self.roster))+" roster entries have been loaded."
        except Exception as e:
            self.details.ids.rosterStatusLabel.text="Specified roster file is not valid."
            self.details.ids.rosterTimeLabel.text=""
            Logger.warning(str(e))

    # decide how to optimally split the roster into n roughly-evenly-sized-lists
    #  grouped on first letters of last names;
    def setupAlphaGrouping(self,numOfGroups=5):
        # 1. create a dict whose keys are lowercase letters a thru z, and
        #     values are lists of all members whose last name starts with
        #     that letter
        alphaDict={}
        for key,val in self.roster.items():
            first=str(val[0][0]).lower()
            alphaDict.setdefault(first,[]).append(val[0])
        # 2. create a 26-element list, each element is the number of folks
        #     whose last name starts with that ordinal letter
        letters=list(map(chr,range(97,123)))
        alphaGroupList=[0]*26
        for letter in letters:
            n=ord(letter)-97
            Logger.info("letter:"+letter+" n:"+str(n)+" list:"+str(len(alphaDict.get(letter,[])))+":"+str(alphaDict.get(letter,[])))
            alphaGroupList[n]=len(alphaDict.get(letter,[]))
        Logger.info("alphaGroupList:"+str(alphaGroupList))
        # 3. group the letters into numOfGroups groups, such that all the group
        #     lengths are as close together as possible
        #     (target group length = total roster length / numOfGroups)
        target=len(self.roster)/numOfGroups
        next=0
#         for groupNum in range(numOfGroups):
#             groupSize=0
#             while groupSize<

    def getName(self,id):
        return self.roster.get(id,"")[0]
    
    def getCell(self,id):
        return self.roster.get(id,"")[2]
    
    def getId(self,name):
        Logger.info("looking up ID for "+name)
#         i=self.roster.keys()[self.roster.values().index(name)]
#         i=[item for item in self.roster.items() if item[1]==name][0][0]
        Logger.info("Roster:"+str(self.roster))
        try:
            key=next(key for key,value in self.roster.items() if value[0]==name)
        except:
            key=""
        Logger.info("   key="+str(key))
        return str(key)
#         Logger.info("   i="+str(i))
        # note this returns the >first< index, and dicts are not ordered,
        #  so this will only work as expected if all values are unique
        # see https://stackoverflow.com/a/11658633/3577105
#         return str(i)
        
    def getIdText(self,id):
        idText=str(id)
        if id.isdigit():
            idText="SAR "+str(id)
        if str(id).startswith("X"): # no ID assigned to this person on the roster
            idText=""
        return idText
    
    def getFinalizedText(self):
        if self.finalized:
            return "YES"
        else:
            return "NO"
    
    def getCerts(self,id):
        # return a list of two lists: [[not-prompted],[prompted]] cert types
        not_prompted=[]
        prompted=[]
        if self.roster[id]:
            # parse the certifications field, using either space or comma as delimiter,
            #  removing blank strings due to back-to-back delimiters due to loose syntax
            allCerts=[x for x in self.roster[id][1].replace(' ',',').split(',') if x]
            Logger.info("roster certs for "+id+":"+str(allCerts)+"  (raw="+str(self.roster[id][1])+")")
            prompted=[x for x in allCerts if x in CERTS_NEED_PROMPT]
            not_prompted=[x for x in allCerts if x not in prompted]
#             for possibleCert in CERTS_NEED_PROMPT:
#                 if possibleCert in idCerts:
#                     certs.append(CERT_DICT[possibleCert])
#                     certs.append(possibleCert)
        certs=[not_prompted,prompted]
        Logger.info("Certifications for "+id+":"+str(certs))
        return certs

    def downloadFile(self,filename,mimetype,doToast=True):
        path=self.downloadDir+"/"+os.path.basename(filename)
        Logger.info("Downloading i.e. copying from "+filename+" to "+path+" doToast:"+str(doToast))
        try:
            shutil.copy(filename,path)
        except PermissionError as ex:
            Logger.warning("Could not write file "+path+":")
            Logger.warning(ex)
            if doToast:
                toast("File not written: Permission denied\n\nPlease add Storage permission for this app using your device's Settings menu, then try again.\n\nYou should not need to restart the app.")
                toast("File not written: "+str(ex))
        except Exception as ex:
            Logger.warning("Could not write file "+path+":")
            Logger.warning(ex)
            if doToast:
                toast("File not written: "+str(ex))
        else:
            Logger.info("Download successful")
            if platform in ('android'):
                DownloadService=mActivity.getSystemService(Context.DOWNLOAD_SERVICE)
                DownloadService.addCompletedDownload(path,path,True,mimetype,path,os.stat(path).st_size,True)    
                if doToast:
                    toast("File created successfully:\n\n"+path+"\n\nCheck your 'download' notifications for single-tap access.")
 
    def scanForCSV(self,dirname=None):
        # return a list of lists: each sublist is [<filename>,<file_time>,<event_name>,<header_time>,<finalized>]
        rval=[]
        if not dirname:
            dirname=self.csvDir
        if not os.path.isdir(dirname):
            self.textpopup("ERROR: specified CSV directory "+dirname+" is not a valid directory.")
            return rval
#         Logger.info("beginning scan for valid CSV files in directory "+dirname)
        for file in os.listdir(dirname):
#             Logger.info("file:"+str(file))
            if file.endswith(".csv"):
#                 Logger.info("  csvfile:"+str(file))
                path=os.path.join(dirname,file)
#                 Logger.info("  path:"+str(path))
                # use errors='ignore' to skip errors about grave accent (utf-8 0xb4)
                with open(path,'r',errors='ignore') as csvFile:
#                     Logger.info("  opened")
                    valid=False
                    finalized=False
                    name=""
                    start=""
                    for line in csvFile:
                        if line.startswith('## NCSSAR Sign-in Sheet'):
                            valid=True
                        elif line.startswith('## Event Name:'):
                            name=line.split(':')[1]
                        elif line.startswith('## Event Date and Start Time:'):
                            start=line.split(':')[1]
                        elif line.startswith('## end of list; FINALIZED:'):
#                             Logger.info("finalized line:"+line)
                            finalized=line.rstrip().split(':')[1]==" YES" # True or False
#                             Logger.info("   finalized="+str(finalized))
                    if valid:
                        rval.append([path,os.path.getmtime(path),name,start,finalized])
                    csvFile.close()
#         Logger.info("complete list:"+str(rval))
        return rval
        
    def scanForRosters(self,dirname=None):
        rval=[]
        if not dirname:
            dirname=self.rosterDir
        if not os.path.isdir(dirname):
            self.textpopup("ERROR: specified roster directory "+dirname+" is not a valid directory.")
            return rval
#         Logger.info("beginning scan for valid roster files in directory "+dirname)
        for file in os.listdir(dirname):
            if file.endswith(".csv"):
                path=os.path.join(dirname,file)
                # use errors='ignore' to skip errors about grave accent (utf-8 0xb4)
                with open(path,'r',errors='ignore') as myFile:
                    if '## Sign-in Roster' in myFile.read():
                        rval.append(path)
        return rval
             
    def readCSV(self,filename=None):
        if not filename:
            filename=self.csvFileName
        Logger.info("readCSV called: filename="+str(filename))
        with open(filename,'r') as csvFile:
            Logger.info("csv file "+filename+" opened for read")
            self.signInList=[] # take some steps to verify (or save) before nuking the existing list!
            csvReader=csv.reader(csvFile)
            for row in csvReader:
                Logger.info("row:"+str(row))
                if len(row)==0: # skip any blank rows
                    continue
                if not row[0].startswith("#") and row[0]!="ID": # prune comment lines and header
                    row[7]=float(row[7]) # use the epoch sec for time-in
                    row[8]=float(row[8]) # use the epoch sec for time-out
                    row[9]=float(row[9]) # use the number of sec for total time
                    self.signInList.append(row)
                elif row[0].startswith("## Event Date and Start Time:"):
                    startDateTime=row[0].split(': ')[1]
                    startDateTimeParse=startDateTime.split(" ")
                    self.details.eventStartDate=" ".join(startDateTimeParse[0:-1])
                    Logger.info("recovered event start date:"+str(self.details.eventStartDate))
                    self.details.eventStartTime=startDateTimeParse[-1]
                    Logger.info("recovered event start time:"+str(self.details.eventStartTime))
                elif row[0].startswith("## Event Name:"):
                    self.details.eventName=row[0].split(': ')[1]
                    Logger.info("recovered event name:"+str(self.details.eventName))
                elif row[0].startswith("## Event Type:"):
#                     Logger.info("  event type before read: "+str(self.eventType))
                    self.details.eventType=row[0].split(': ')[1]
#                     Logger.info("  event type after read: "+str(self.eventType))
#                     cmd="self.details.ids."+self.eventType.lower()+"CheckBox.active=True"
#                     Logger.info("cmd:"+str(cmd))
#                     eval(cmd)
                elif row[0].startswith("## Event Location:"):
                    self.details.eventLocation=row[0].split(': ')[1]
                    Logger.info("recovered event location:"+str(self.details.eventLocation))
#             self.exportList=copy.deepcopy(self.signInList) # otherwise this only happens on sign in/out
            Logger.info(str(len(self.signInList))+" entries read")
            Logger.info(str(self.signInList))
    
    def updateCSVFileName(self):
        f="sign-in"
        if self.details.ids.eventNameField.text!="":
            f=f+"_"+self.details.ids.eventNameField.text
        f=f+"_"+self.details.ids.eventStartDate.text+"_"+self.details.ids.eventStartTime.text
        f=f+".csv"
        f=f.replace(" ","_") # do not have spaces in filename
        f=f.replace(":","") # colon will break the filename on Windows; it's already 24h time
        Logger.info("updated CSV filename:"+f)
        self.csvFileName=os.path.join(self.csvDir,f)
        
    def writeCSV(self,rotate=True,download=False,doToastOverride=False):
        self.updateCSVFileName()
        # rotate first, since it moves the base file to .bak1
        Logger.info("writeCSV called")
        if rotate and os.path.isfile(self.csvFileName):
            self.rotateCSV()
        with open(self.csvFileName,'w') as csvFile:
            Logger.info("csv file "+self.csvFileName+" opened")
            csvWriter=csv.writer(csvFile)
            csvWriter.writerow(["## NCSSAR Sign-in Sheet"])
            csvWriter.writerow(["## Event Date and Start Time: "+self.details.ids.eventStartDate.text+" "+self.details.ids.eventStartTime.text])
            csvWriter.writerow(["## Event Name: "+self.details.ids.eventNameField.text])
            csvWriter.writerow(["## Event Type: "+self.details.eventType])
            csvWriter.writerow(["## Event Location: "+self.details.eventLocation])
            csvWriter.writerow(["## File written "+time.strftime("%a %b %#d %Y %H:%M:%S")])
            csvWriter.writerow(self.columns)
            for entry in self.signInList:
#                 # copy in, out, and total seconds to end of list
#                 entry.append(entry[3])
#                 entry.append(entry[4])
#                 entry.append(entry[5])
#                 # change entries 2,3,4 to human-readable in case the csv is
#                 #  imported to a spreadsheet
#                 entry[3]=self.timeStr(entry[3])
#                 entry[4]=self.timeStr(entry[4])
#                 entry[5]=self.timeStr(entry[5])
#                 # csv apparently knows to wrap the string in quotes only if the
#                 #  same character used as the delimiter appears in the string
                csvWriter.writerow(entry)
            csvWriter.writerow(["## end of list; FINALIZED: "+self.getFinalizedText()])
        doToast=True
        if self.details.ids.autoExport.active:
            download=True
            doToast=doToastOverride # toast if export button was hit, even if auto-export is on
        if download and os.path.isfile(self.csvFileName):
            self.downloadFile(self.csvFileName,"text/csv",doToast)
        self.q("DELETE FROM "+self.signInTableName) # easiest code is to delete all rows and start from scratch
        for entry in self.signInList:
            self.q("INSERT INTO "+self.signInTableName+" VALUES('{0}','{1}','{2}','{3}','{4}','{5}','{6}',{7},{8},{9},'{10}','{11}')".format(*entry))
        self.con.commit()
        
    def rotateCSV(self,depth=5):
        # move e.g. 4 to 5, then 3 to 4, then 2 to 3, then 1 to 2, then <base> to 1
        Logger.info("rotateCSV called")
        for n in range(depth-1,0,-1):
            name1=self.csvFileName.replace('.csv','.bak'+str(n)+'.csv')
            name2=self.csvFileName.replace('.csv','.bak'+str(n+1)+'.csv')
            if os.path.isfile(name1):
                shutil.move(name1,name2) # shutil.move will overwrite; os.rename will not
        shutil.move(self.csvFileName,name1)
                
    def finalize(self):
        self.finalized=True # should make sure that everyone is signed out first!
        self.export()
    
    def export(self):
        # exporting should not cause a file rotation; if it did, then the most
        #  recent backup woult be the same as the most recent file except with
        #  finalize=NO meaning it would be a candidate for auto-recover, which
        #  we do not want.
        self.writeCSV(download=True,rotate=False,doToastOverride=True)
        self.writePDF(download=True)
        
#     def writePDFHeaderFooter(self,canvas,doc):
#         canvas.saveState()
#         styles = getSampleStyleSheet()
#         self.img=None
#         printInfoText="NOT FINALIZED"
#         if self.finalized:
#             printInfoText="Total attending: "+str(self.getTotalAttendingCount())
#         if os.path.isfile(self.printLogoFileName):
# #             rprint("valid logo file "+self.printLogoFileName)
#             imgReader=utils.ImageReader(self.printLogoFileName)
#             imgW,imgH=imgReader.getSize()
#             imgAspect=imgH/float(imgW)
#             self.img=Image(self.printLogoFileName,width=0.54*inch/float(imgAspect),height=0.54*inch)
#             headerTable=[
#                     [self.img,self.agencyNameForPrint],
#                     ["Event Sign In List","Event Name: "+self.details.ids.eventNameField.text,"Event Type: "+self.details.eventType,"Event Date: "+"12345"],
#                     ["Start Time: "+"54321","Printed at: "+time.strftime("%a %b %d, %Y  %H:%M"),printInfoText]]
#             t=Table(headerTable,colWidths=[x*inch for x in [2,2,1.75,1.75]],rowHeights=[x*inch for x in [1.6,1.3,1.3]])
#             t.setStyle(TableStyle([('FONT',(1,0),(1,0),'Helvetica-Bold',18),
# #                                           ('FONT',(2,0),(3,0),'Helvetica-Bold'),
# #                                    ('FONTSIZE',(1,0),(1,1),18),
# #                                           ('SPAN',(0,0),(0,1)),
# #                                           ('SPAN',(1,0),(1,1)),
# #                                           ('LEADING',(1,0),(1,1),20),
# #                                           ('TOPADDING',(1,0),(1,0),0),
# #                                           ('BOTTOMPADDING',(1,1),(1,1),4),
#                                 ('VALIGN',(0,0),(-1,-1),"MIDDLE"),
#                                 ('ALIGN',(1,0),(1,-1),"CENTER"),
#                                          ('ALIGN',(0,0),(0,1),"CENTER"),
#                                         ('BOX',(0,0),(-1,-1),2,colors.black),
#                                         ('BOX',(2,0),(-1,-1),2,colors.black),
#                                         ('INNERGRID',(2,0),(3,1),0.5,colors.black)]))
# #         else:
# #             headerTable=[
# #                     [self.img,self.agencyNameForPrint,"Incident: "+self.incidentName,formNameText+" - Page "+str(canvas.getPageNumber())],
# #                     ["","","Operational Period: ","Printed: "+time.strftime("%a %b %d, %Y  %H:%M")]]
# #             t=Table(headerTable,colWidths=[x*inch for x in [0.0,5,2.5,2.5]],rowHeights=[x*inch for x in [0.3,0.3]])
# #             t.setStyle(TableStyle([('FONT',(1,0),(1,1),'Helvetica-Bold'),
# #                                    ('FONT',(2,0),(3,0),'Helvetica-Bold'),
# #                                    ('FONTSIZE',(1,0),(1,1),18),
# #                                           ('SPAN',(0,0),(0,1)),
# #                                           ('SPAN',(1,0),(1,1)),
# #                                           ('LEADING',(1,0),(1,1),20),
# #                                  ('VALIGN',(1,0),(-1,-1),"MIDDLE"),
# #                                  ('ALIGN',(1,0),(1,-1),"CENTER"),
# #                                           ('BOX',(0,0),(-1,-1),2,colors.black),
# #                                           ('BOX',(2,0),(-1,-1),2,colors.black),
# #                                           ('INNERGRID',(2,0),(3,1),0.5,colors.black)]))
#         w,h=t.wrapOn(canvas,doc.width,doc.height)
# # #         self.logMsgBox.setInformativeText("Generating page "+str(canvas.getPageNumber()))
# #         QCoreApplication.processEvents()
# #         rprint("Page number:"+str(canvas.getPageNumber()))
# #         rprint("Height:"+str(h))
# #         rprint("Pagesize:"+str(doc.pagesize))
#         t.drawOn(canvas,doc.leftMargin,doc.pagesize[1]-h-0.5*inch) # enforce a 0.5 inch top margin regardless of paper size
# # ##        canvas.grid([x*inch for x in [0,0.5,1,1.5,2,2.5,3,3.5,4,4.5,5,5.5,6,6.5,7,7.5,8,8.5,9,9.5,10,10.5,11]],[y*inch for y in [0,0.5,1,1.5,2,2.5,3,3.5,4,4.5,5,5.5,6,6.5,7,7.5,8,8.5]])
# #         rprint("done drawing printLogHeaderFooter canvas")
#         canvas.restoreState()
# #         rprint("end of printLogHeaderFooter")
        
    # optional argument 'teams': if True, generate one pdf of all individual team logs;
    #  so, this function should be called once to generate the overall log pdf, and
    #  again with teams=True to generate team logs pdf
    # if 'teams' is an array of team names, just print those team log(s)
    def writePDF(self,download=False):
        pass
#         Logger.info("print job started")
#         pdfName=self.csvFileName.replace(".csv",".pdf")
#         try:
#             f=open(pdfName,"wb")
#         except:
#             Logger.error("writePDF: could not open file for write: "+pdfName)
#             return
#         else:
#             f.close()
#         doc = SimpleDocTemplate(pdfName, pagesize=letter,leftMargin=0.5*inch,rightMargin=0.5*inch,topMargin=1.03*inch,bottomMargin=0.5*inch)
#         elements=[]
#         pdfList=[["ID","Name","Time In","Time Out","Total"]]
#         for entry in self.exportList:
#             pdfList.append([entry[0],entry[1],entry[3],entry[4],entry[5]])
#         t=Table(pdfList,repeatRows=1,colWidths=[x*inch for x in [0.75,3,1.25,1.25,1.5]]) 
#         t.setStyle(TableStyle([('FONT',(0,0),(-1,-1),'Helvetica',14),
#                                 ('FONT',(0,0),(-1,0),'Helvetica-Bold',14),
# #                                 ('FONTSIZE',(0,0),(-1,-1),16),
#                                 ('ALIGN',(0,0),(-1,-1),'CENTER'),
#                                 ('ALIGN',(1,0),(1,-1),'LEFT'),
#                                 ('INNERGRID', (0,0), (-1,-1), 1, colors.black),
#                                 ('BOX', (0,0), (-1,-1), 1, colors.black),
#                                 ('BOX', (0,0), (-1,0), 2, colors.black)]))
# 
# #         for team in teamFilterList:
# #             extTeamNameLower=getExtTeamName(team).lower()
# #             radioLogPrint=[]
# #             styles = getSampleStyleSheet()
# #             radioLogPrint.append(MyTableModel.header_labels[0:6])
# #             for row in self.radioLog:
# #                 opStartRow=False
# #                 if row[3].startswith("Radio Log Begins:"):
# #                     opStartRow=True
# #                 if row[3].startswith("Operational Period") and row[3].split()[3] == "Begins:":
# #                     opStartRow=True
# #                     entryOpPeriod=int(row[3].split()[2])
# #                 if entryOpPeriod == opPeriod:
# #                     if team=="" or extTeamNameLower==getExtTeamName(row[2]).lower() or opStartRow: # filter by team name if argument was specified
# #                         radioLogPrint.append([row[0],row[1],row[2],Paragraph(row[3],styles['Normal']),Paragraph(row[4],styles['Normal']),Paragraph(row[5],styles['Normal'])])
# #             if not teams or len(radioLogPrint)>2: # don't make a table for teams that have no entries during the requested op period
# #                 t=Table(radioLogPrint,repeatRows=1,colWidths=[x*inch for x in [0.5,0.6,1.25,5.5,1.25,0.9]])
# #                 t.setStyle(TableStyle([('FONT',(0,0),(-1,-1),'Helvetica'),
# #                                         ('FONT',(0,0),(-1,1),'Helvetica-Bold'),
# #                                         ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
# #                                        ('BOX', (0,0), (-1,-1), 2, colors.black),
# #                                        ('BOX', (0,0), (5,0), 2, colors.black)]))
#         elements.append(t)
#         doc.build(elements,onFirstPage=self.writePDFHeaderFooter,onLaterPages=self.writePDFHeaderFooter)         
#         Logger.info("print job completed")
#         
#     def sync(self):
#         pass
    
    def newEventPrompt(self):
        if len(self.signInList)>0:
            self.textpopup(title='New Event', text='This will delete all entries; are you sure?',on_release=self.newEvent)
        else:
            self.newEvent()

#     def newEvent(self,*args,eventType=None,eventName=None,eventLocation=None,eventStartDate=None,eventStartTime=None):
# newEvent: d is a dictionary in the same format as a record in the Events table
# if called with no dictionary, it is probably being called from the Create New Event
#  button in the newevent page of the GUI, so, use the values from that form if they exist
#  and try to create both local and cloud events by default in that case
    def newEvent(self,*args,d=None,createLocal=True,createCloud=True):
        Logger.info("newEvent called")
        t=time.time()
        if not d: # no dictionary specified - use GUI values
            eventType=self.newevent.eventType or "Not Specified"
            eventName=self.newevent.eventName or "Not Specified"
            eventLocation=self.newevent.eventLocation or "Not Specified"
            eventStartDate=self.newevent.eventStartDate or today_date()
            eventStartTime=self.newevent.eventStartTime or datetime.datetime.fromtimestamp(t).strftime("%H:%M")
            eventStartEpoch=datetime.datetime.strptime(eventStartDate+" "+eventStartTime,self.signin_datetimeformat).timestamp()
            d={
                "EventType":eventType,
                "EventName":eventName,
                "EventLocation":eventLocation,
                "EventStartDate":eventStartDate,
                "EventStartTime":eventStartTime,
                "EventStartEpoch":eventStartEpoch,
                "Finalized":0,
                "LastEditEpoch":t}
#         if not eventType:
#             eventType=""
#         if not eventStartDate:
#             eventStartDate=today_date()
#         if not eventStartTime:
#             eventStartTime=datetime.datetime.now().strftime("%H:%M")
#         if not eventName:
#             eventName=""
#         if not eventLocation:
#             eventLocation=""
#         self.details.eventName=eventName
#         self.details.eventLocation=eventLocation
#         self.details.eventStartDate=eventStartDate
#         self.details.eventStartTime=eventStartTime

#         if eventType:
#             self.newevent.eventType=eventType
#         else:
#             eventType=self.newevent.eventType or "Not Specified"
#         if eventName:
#             self.newevent.eventName=eventName
#         else:
#             eventName=self.newevent.eventName or "Not Specified"
#         if eventStartDate:
#             self.newevent.eventStartDate=eventStartDate
#         else:
#             eventStartDate=self.newevent.eventStartDate or today_date()
#         if eventStartTime:
#             self.newevent.eventStartTime=eventStartTime
#         else:
#             eventStartTime=self.newevent.eventStartTime or datetime.datetime.now().strftime("%H:%M")
#         if eventLocation:
#             self.newevent.eventLocation=eventLocation
#         else:
#             eventLocation=self.newevent.eventLocation or "Not Specified"
        
#         Logger.info("sendAction called")
#         d=dict(zip(self.columns,entry))
        d["Finalized"]=0
        # if LastEditEpoch already exists, preserve it; otherwise set to now
        if not d.get("LastEditEpoch",None):
            d["LastEditEpoch"]=t

        j=json.dumps(d)
        Logger.info("dict:"+str(d))
        Logger.info("json:"+str(j))
        
        self.cloudEventID=d.get("CloudEventID",None)
        
#         self.cloudEventID=None # if creating both cloud and local, this is obvious;
         # if creating local only, we still don't want to use the previous cloudEventID;
         #  that scenario is instead handled by syncing to an existing cloud event in
         #  which case ...?
         
        if createCloud:
            # create the new cloud event first, so the ID can be used for the local and/or LAN events
            # UrlRequest sends body as plain text by default; need to send json header
            #  but the api still shows that it came across as an actual dictionary
            #  rather than plain text; added a handler for this in the api
            headers = {'Content-type': 'application/json','Accept': 'text/plain'}
            self.cloudEventID=None # make sure we don't accidentally sync to a different cloud event
            self.checkForCloud() # check for cloud right now
            if self.cloud:
                request=UrlRequest(self.cloudServer+"/api/v1/events/new",
                        on_success=self.on_newCloudEvent_success,
                        on_failure=self.on_newCloudEvent_error,
                        on_error=self.on_newCloudEvent_error,
                        req_body=j,
                        req_headers=headers,
                        method="POST",
                        timeout=3,
                        debug=True)
                # since the request was synchronous, self.cloudEventID should exist by now
                if self.cloudEventID:
                    d["cloudEventID"]=self.cloudEventID # use it in local and/or LAN events
            else:
                Logger.info("no cloud contact; new cloud event request not sent")
                
        if createLocal:
            self.signInList=[] # delete all current sign-in records
#             d={
#                 "EventType":eventType,
#                 "EventName":eventName,
#                 "EventLocation":eventLocation,
#                 "EventStartDate":eventStartDate,
#                 "EventStartTime":eventStartTime,
#                 "Finalized":0,
#                 "LastEditEpoch":time.time()}
            
            # create the new local event
            r=sdbNewEvent(d)
            Logger.info("  return val from sdbNewEvent:"+str(r))
            self.localEventID=r['validate']['LocalEventID']
            if self.cloudEventID:
                sdbSetCloudEventID(self.localEventID,self.cloudEventID)
            Logger.info("  new localEventID="+str(self.localEventID))

        self.sync()
        self.switchToBlankKeypad()
        
    def timeStr(self,sec):
        Logger.info("calling timeStr:"+str(sec))
        if isinstance(sec,str): # return strings as-is
            return sec
        if sec==0:
            return "--"
        if sec<1e6: # assume it's an elapsed / total time
            t=time.gmtime(sec)
            if t.tm_hour>1: # plural hours if needed
                s='s'
            else:
                s=''
            # stripping of leading zeros in format strings in strftime
            #  is not platform-intependent; just use tm_min/tm_hour instead
            mStr=str(t.tm_min)+" min"
            hStr=str(t.tm_hour)+" hr"+s
            if t.tm_hour==0: # don't show hours if total is <1hr
                return mStr
            return hStr+" "+mStr
        return time.strftime("%H:%M",time.localtime(sec))
    
    def switchToBlankKeypad(self,*args):
        self.topbar.ids.listbutton.opacity=0
        self.topbar.ids.listbutton.disabled=True
        self.topbar.ids.listbutton.width=0
        self.topbar.ids.detailsbutton.opacity=0
        self.topbar.ids.detailsbutton.disabled=True
        self.topbar.ids.detailsbutton.width=0
        self.topbar.ids.keypadbutton.opacity=0
        self.topbar.ids.keypadbutton.disabled=True
        self.topbar.ids.keypadbutton.width=0
        self.updateHeaderCount()
        self.typed=''
        self.hide()
        self.sm.current='keypad'
        if self.adminMode:
            self.exitAdminMode()
        if self.getTotalAttendingCount()>0 and self.getCurrentlySignedInCount()<1:
            self.keypad.ids.topLabel.text="READY TO FINALIZE"
            self.keypad.ids.topLabel.background_color=(0,0,0.5,1)
        else:
            self.keypad.ids.topLabel.text=""

    def updateHeaderCount(self):
        self.topbar.ids.headerLabel.text=" Total: "+str(self.getTotalAttendingCount())+"   Here: "+str(self.getCurrentlySignedInCount())
            
    def getCurrentlySignedInCount(self,*args):
        # get the number of entries in signInList that are not signed out
#         Logger.info("Getting signed-in count.  Current signInList:"+str(self.signInList))
        return len([x for x in self.signInList if x[5]==0 or x[5]=='--'])
    
    def getTotalAttendingCount(self,*Args):
        # get the number of unique IDs in signInList
        return len(list(set([x[0] for x in self.signInList])))
         
    def showList(self,*args):
        Logger.info("showList called")
#         self.theList.ids.listHeadingLabel.text=self.details.eventType+": "+self.details.ids.eventNameField.text+"  Currently here: "+str(self.getCurrentlySignedInCount())+"   Total: "+str(self.getTotalAttendingCount())
        # recycleview needs a single list of strings; it divides into rows every nth element
#         self.theList.bigList=[str(x) for entry in self.signInList for x in entry[0:7]]
        self.theList.bigList=[]
        for entry in self.signInList:
            row=copy.deepcopy(entry[0:7])
            # show blank ID for X# entries (folks without assigned ID in the roster)
            if str(row[0]).startswith('X'):
                row[0]=""
            self.theList.bigList=self.theList.bigList+row
        self.sm.transition.direction='up'
        self.sm.current='theList'
        self.sm.transition.direction='down'

    def showNewEvent(self,*args):
        self.newevent.ids.eventNameField=''
        self.newevent.ids.eventLocationField=''
        self.newevent.ids.eventStartDate=today_date()
        self.newevent.ids.eventStartTime=datetime.datetime.now().strftime("%H:%M")
        self.sm.current='newevent'
        
    def showDetails(self,*args):
        self.topbar.ids.listbutton.opacity=1
        self.topbar.ids.listbutton.disabled=False
        self.topbar.ids.listbutton.width=64
        self.topbar.ids.detailsbutton.opacity=0
        self.topbar.ids.detailsbutton.disabled=True
        self.topbar.ids.detailsbutton.width=0
        self.topbar.ids.keypadbutton.opacity=1
        self.topbar.ids.keypadbutton.disabled=False
        self.topbar.ids.keypadbutton.width=64
        self.sm.transition.direction='up'
        self.sm.current='details'
        self.sm.transition.direction='down'
        
    def showLookup(self,*args):
#         self.lookup.rosterList=sorted([str(val[0])+" : "+str(key) for key,val in self.roster.items()])
        self.topbar.ids.listbutton.opacity=0
        self.topbar.ids.listbutton.disabled=True
        self.topbar.ids.listbutton.width=0
        self.topbar.ids.detailsbutton.opacity=0
        self.topbar.ids.detailsbutton.disabled=True
        self.topbar.ids.detailsbutton.width=0
        self.topbar.ids.keypadbutton.opacity=1
        self.topbar.ids.keypadbutton.disabled=False
        self.topbar.ids.keypadbutton.width=64
        self.lookup.rosterList=[]
        for key,val in self.roster.items():
            if str(key).startswith("X"):
                suffix=""
            else:
                suffix=" : "+str(key)
            self.lookup.rosterList.append(str(val[0])+suffix)
        self.lookup.rosterList.sort()
#         Logger.info(str(self.lookup.rosterList))
        self.sm.transition.direction='left'
        self.sm.current='lookup'
        self.sm.transition.direction='right'
#         self.lookup.ids.combo.focus=True # automatically raise the keyboard
#         self.lookup.ids.combo.show_keyboard()
        
    def signInNameTextUpdate(self):
        self.setTextToFit(self.signin.ids.nameLabel,self.signin.ids.nameLabel.text)

    def signOutNameTextUpdate(self):
        self.setTextToFit(self.signout.ids.nameLabel,self.signout.ids.nameLabel.text)
        
    def alreadySignedOutNameTextUpdate(self):
        self.setTextToFit(self.alreadysignedout.ids.nameLabel,self.alreadysignedout.ids.nameLabel.text)
        
    def thankyouNameTextUpdate(self):
        self.setTextToFit(self.thankyou.ids.nameLabel,self.thankyou.ids.nameLabel.text,initialFontSize=self.thankyou.height*0.1)
                        
    def showSignIn(self,id,fromLookup=False):
        self.sm.current='signin'
        self.setTextToFit(self.signin.ids.nameLabel,self.getName(id))
        # fit the text again after the transition is done, since the widget
        #  size (and therefore the text height) is wacky until the screen has
        #  been displayed for the first time
        self.signin.on_enter=self.signInNameTextUpdate
        self.signin.ids.idLabel.text=self.getIdText(id)
        self.signin.fromLookup=fromLookup
        certsNeedPrompt=self.getCerts(id)[1]
        self.signin.ids.certBox.clear_widgets()
        self.signin.ids.certHeader.opacity=0
        if self.details.eventType=="Search" and certsNeedPrompt:
            self.signin.ids.certHeader.opacity=1
            for cert in certsNeedPrompt:
                Logger.info("adding certification question for "+cert)
                certLayout=BoxLayout(orientation='horizontal',size_hint=(1,0.1))
#                 certLabel=Label(text=cert+'?',font_size=self.signin.ids.certHeader.font_size)
                certLabel=Label(text=CERT_DICT[cert]+'?')
                certSwitch=YesNoSwitch()
                certSwitch.cert=cert # pass the cert name as a property of the switch
        #                         certSwitch.bind(active=self.certSwitchCB)
                certLayout.add_widget(certLabel)
                certLayout.add_widget(certSwitch)
                self.signin.ids.certBox.add_widget(certLayout)
        
#     def certSwitchCB(self,instance,value):
#         Logger.info("certSwitchCB called:"+str(instance)+":"+str(value))
#         Logger.info("  cert:"+str(instance.cert))

    def setTextToFit(self,widget,text,initialFontSize=None):   
        # for long names, reduce font size until it fits in its widget
        if initialFontSize:
            m=initialFontSize/widget.height
            widget.font_size=initialFontSize
        else:
            m=self.defaultTextHeightMultiplier
            widget.font_size=widget.height*m
        widget.text=text
        widget.texture_update()
#         Logger.info("font size:"+str(widget.font_size))
#         Logger.info("widget width:"+str(widget.width))
#         Logger.info("widget height:"+str(widget.height))
#         Logger.info("texture width:"+str(widget.texture_size[0]))
        while m>0.1 and widget.texture_size[0]>widget.width:
            m=m-0.05
            widget.font_size=widget.height*m
            widget.texture_update()
#             Logger.info("  font size:"+str(widget.font_size))
#             Logger.info("  widget width:"+str(widthWidget.width))
#             Logger.info("  texture width:"+str(widget.texture_size[0]))

#     def updateSyncLabel(self,text):
#         t=self.keypad.ids.syncLabel.text
#         self.keypad.ids.syncLabel.text=t+text
#         self.keypad.ids.syncLabel.background_color=1,0,0,1
#         self.thankyou.ids.syncLabel.text=t+text
#         
#     def clearSyncLabel(self,*args):
#         self.keypad.ids.syncLabel.text=''
#         self.thankyou.ids.syncLabel.text=''
        
    def sendAction(self,entry):
        Logger.info("sendAction called")
        d=dict(zip(self.columns,entry))
        sdbAddOrUpdate(self.localEventID,d) # local db
        if self.cloudEventID:
            # UrlRequest sends body as plain text by default; need to send json header
            #  but the api still shows that it came across as an actual dictionary
            #  rather than plain text; added a handler for this in the api
            headers = {'Content-type': 'application/json','Accept': 'text/plain'}
            uri=self.cloudServer+"/api/v1/events/"+str(self.cloudEventID)
            Logger.info("about to send request to "+uri)
            j=json.dumps(d)
    #         Logger.info("dict:"+str(d))
            Logger.info("json:"+str(j))
            request=UrlRequest(uri,
                    on_success=self.on_sendAction_success,
                    on_failure=self.on_sendAction_failure,
                    on_error=self.on_sendAction_error,
                    req_body=j,
                    req_headers=headers,
                    method="PUT",
                    debug=True)
            Logger.info("asynchronous request sent:"+str(request))
            self.topbar.ids.syncButtonImage.source=self.syncCloudUploadStartIconFileName
#           self.updateSyncLabel("--> C :")

#     def sendAction(self,entry):
#         Logger.info("sendAction called")
#         d=dict(zip(self.columns,entry))
#         j=json.dumps(d)
#         Logger.info("dict:"+str(d))
#         Logger.info("json:"+str(j))
#         try:
#             r=requests.put(url=self.cloudServer+"/api/v1/events/current",json=j)
#         except Exception as e:
#             Logger.info("error during PUT request:\n"+str(e))
#             return -1
#         try:
#             rj=r.json()
#         except:
#             Logger.info("reponse error: PUT response has no json:\n"+str(r))
#             return -1
#         Logger.info("response json:"+str(rj))
#         if "validate" not in rj:
#             Logger.info("response error: PUT response json has no 'validate' entry:\n"+str(rj))
#             return -1
#         v=rj["validate"]
#         if len(v) != 1:
#             Logger.info("response error: PUT response json 'validate' entry should contain exactly one record but it contains "+str(len(v))+":\n"+str(rj["validate"]))
#             return -1
#         if d != v[0]:
#             Logger.info("response error: data record returned from PUT request is not equal to the pushed data:\n    pushed:"+str(d)+"\n  response:"+str(v[0]))
#             return -1
#         Logger.info("PUT response has been validated.")
#         return 0
#     
    def on_sendAction_success(self,request,result):
        Logger.info("on_sendAction_success called:")
        d=eval(request.req_body) # request body is a string; we want dict for comparison below
        v=result["validate"]
        if len(v) != 1:
            Logger.info("response error: PUT response json 'validate' entry should contain exactly one record but it contains "+str(len(v))+":\n"+str(rj["validate"]))
            return -1
        if d != v[0]:
            Logger.info("response error: data record returned from PUT request is not equal to the pushed data:\n    pushed:"+str(d)+"\n  response:"+str(v[0]))
            return -1
        Logger.info("PUT response has been validated.")
#         self.updateSyncLabel(" OK")
        self.topbar.ids.syncButtonImage.source=self.syncCloudIconFileName
        
        # now set the 'Synced' column on the local db to indicate successful sync
        d["Synced"]=self.cloudEventID
        sdbAddOrUpdate(self.localEventID,d)
        
        # do a new sync in case anything changed on the server from other nodes
        self.sync()
        
    def on_sendAction_failure(self,request,result):
        Logger.info("on_sendAction_failure called:")
        Logger.info("  request was sent to "+str(request.url))
        Logger.info("    request body="+str(request.req_body))
        Logger.info("    request headers="+str(request.req_headers))
        Logger.info("  result="+str(result))
        self.topbar.ids.syncButtonImage.source=self.syncNoneIconFileName
#         self.updateSyncLabel(" X")
#         Clock.schedule_once(self.clearSyncLabel,3)
        
    def on_sendAction_error(self,request,result):
        Logger.info("on_sendAction_error called:")
        Logger.info("  request was sent to "+str(request.url))
        Logger.info("    request body="+str(request.req_body))
        Logger.info("    request headers="+str(request.req_headers))
        Logger.info("  result="+str(result))
        self.topbar.ids.syncButtonImage.source=self.syncNoneIconFileName

    def on_newCloudEvent_success(self,request,result):
        Logger.info("on_newCloudEvent_success called:")
        Logger.info("  result="+str(result))
        d=result
#         d=eval(json.loads(result))
#         d=eval(result) # result body is a string; we want dict for comparison below
#         d=eval(request.req_body) # request body is a string; we want dict for comparison below
        v=d["validate"]
        self.cloudEventID=v["LocalEventID"]
        # since this request will respond after the local event is already made, 
#         self.signInTableName=str(self.eventID)+"_SignIn"
#         if len(v) != 1:
#             Logger.info("response error: PUT response json 'validate' entry should contain exactly one record but it contains "+str(len(v))+":\n"+str(rj["validate"]))
#             return -1
#         if d != v[0]:
#             Logger.info("response error: data record returned from PUT request is not equal to the pushed data:\n    pushed:"+str(d)+"\n  response:"+str(v[0]))
#             return -1
        Logger.info("new cloud event response has been validated.  New cloud event ID = "+str(self.cloudEventID))
        if self.localEventID: # localEventID will not exist yet if cloud event is being made first from newEvent
            sdbSetCloudEventID(self.localEventID,self.cloudEventID)
#         self.updateSyncLabel(" OK")
#         self.switchToBlankKeypad()
        self.topbar.ids.syncButtonImage.source=self.syncCloudIconFileName
        self.sync()

    def on_newCloudEvent_error(self,request,result):
        self.on_sendAction_error(request,result)
        self.switchToBlankKeypad()

    def showStartupSyncChoices(self,*args):
        createEventsTableIfNeeded()
        self.initCloud()
        self.buildSyncChoicesList()
        # don't display the dialog here; display it in each callback, since UrlRequest
        #  cannot be made syncronous (wait() doesn't work)
        
#     def showStartupSyncChoices_part2(self):
#         # this function will be called from one of two places:
#         #  1. after a successful cloud event query (from on_getCloudEvents_success)
#         #    OR
#         #  2. from buildSyncChoicesList, if the cloud is not connected
#         #  either way, syncChoicesList should be completely built and uniquified
#         #   before this function is called
#         if len(self.syncChoicesList)==0:
#             self.textpopup(
#                     title='No sync choices',
#                     text='No sync choices were found;\nfill out the following form to create a new event:',
#                     on_release=self.showNewEvent)
#         else:
#             self.syncChoicesPopup()

    # must jump through these hoops to call the parts in sequence, since UrlRequest
    #  cannot be made syncronous (the wait() function hangs for error or failure)                    
    def buildSyncChoicesList(self):
        backDays=0.5
        aheadDays=2
        t=time.time() # current epoch seconds
        
        # first, add all recent events from the local database
        self.syncChoicesList=sdbGetEvents(lastEditSince=time.time()-60*60*24*10) # edited in the last 10 days
        Logger.info("sync choices after local:"+str(self.syncChoicesList))
        
        # next, check for cloud events:
        #  connected to cloud server? If so, check for non-finalized cloud events in current time window
        if self.cloud:
            startSince=t-60*60*24*backDays
            params={'eventStartSince':startSince}
            urlParamString=urllib.parse.urlencode(params)
            Logger.info("requesting cloud events with paramstring: "+urlParamString)
            request=UrlRequest(self.cloudServer+"/api/v1/events?"+urlParamString,
                on_success=self.on_getCloudEvents_success,
                on_failure=self.on_getCloudEvents_error,
                on_error=self.on_getCloudEvents_error,
                timeout=3,
                method="GET",
                debug=True)
        Logger.info("sync choices after cloud:"+str(self.syncChoicesList))
        
        # next, check for d4h events
        if self.d4h:
            afterObj=datetime.datetime.fromtimestamp(t-60*60*24*backDays)
            beforeObj=datetime.datetime.fromtimestamp(t+60*60*24*aheadDays)
            afterText=afterObj.strftime(self.d4h_datetimeformat)
            beforeText=beforeObj.strftime(self.d4h_datetimeformat)
            params={'before':beforeText,"after":afterText}
            urlParamString=urllib.parse.urlencode(params)
            Logger.info("requesting d4h events with paramstring: "+urlParamString)
            request=UrlRequest(self.d4hServer+"/v2/team/activities?"+urlParamString,
                on_success=self.on_getD4HEvents_success,
                on_failure=self.on_getD4HEvents_error,
                on_error=self.on_getD4HEvents_error,
                timeout=3,
                method="GET",
                req_headers={'Authorization':'Bearer '+self.d4h_api_key},
                debug=True)
        Logger.info("sync choices after d4h:"+str(self.syncChoicesList))

#         else:
# #             self.showStartupSyncChoices_part2()
#             self.syncChoicesPopup()
        self.syncChoicesPopup()
            
#     def buildSyncChoicesList_part2(self):
#         # this function will be called from one of two places:
#         #  1. after a successful cloud event query (from on_getCloudEvents_success)
#         #    OR
#         #  2. from buildSyncChoicesList, if the cloud is not connected
#         Logger.info("buildSyncChoicesList_part2 called")
#         # add local sync choices here
# #         self.syncChoicesList.extend(sdbGetSyncCandidates(timeWindowDaysAgo=10)) # get local sync choices
#         # get local sync choices
# #         localSyncChoices=sdbGetEvents(lastEditSince=time.time()-60*60*24*10)
# #         localChoicesToAddToSyncChoices=[]
#         for localChoice in localSyncChoices:
#             Logger.info("  checking localChoice "+str(localChoice))
#             for remoteChoice in self.syncChoicesList:
#                 Logger.info("    checking remoteChoice "+str(remoteChoice))
#                 same=set(localChoice.items()).intersection(set(remoteChoice.items()))
#                 sameKeys=[x[0] for x in same]
#                 Logger.info("sameKeys:"+str(sameKeys))
#                 if 'CloudEventID' not in sameKeys:
#                     Logger.info("      this local event has no cloud counterpart; will add it")
#                     localChoicesToAddToSyncChoices.append(localChoice)
#         self.syncChoicesList.extend(localChoicesToAddToSyncChoices)
#         # uniquify: if multiple choices have the start date, start time, name, and location,
#         #  and one of them has a cloudEventID but the other does not, get rid of the one that
#         #  does not have a cloudEventID
#         Logger.info("sync candidates:"+str(self.syncChoicesList))
#         # show the dialog now
#         self.showStartupSyncChoices_part2()
        
    def on_getCloudEvents_success(self,request,result):
        Logger.info("on_getCloudEvents_success called:")
        Logger.info("  result="+str(result))
        # add cloud sync choices here; response will have LocalEventID but here we
        #  need to map that to CloudEventID instead
        for choice in result:
            choice["CloudEventID"]=choice["LocalEventID"]
            choice["LocalEventID"]=None
#             self.syncChoicesList.append(choice)
            
#         localSyncChoices=sdbGetEvents(lastEditSince=time.time()-60*60*24*10)
        cloudChoicesToAddToSyncChoices=[]
        for cloudChoice in result:
            # default is to add the cloudChoice; test local choices to see if that remains true
            addFlag=True
            Logger.info("  checking cloudChoice "+str(cloudChoice))
            for localChoice in self.syncChoicesList:
                Logger.info("    checking localChoice "+str(localChoice))
                same=set(localChoice.items()).intersection(set(cloudChoice.items()))
                sameKeys=[x[0] for x in same]
                Logger.info("sameKeys:"+str(sameKeys))
                if 'CloudEventID' in sameKeys and 'EventStartDate' in sameKeys and 'EventStartTime' in sameKeys:
                    Logger.info("      this cloud event is already referenced by the local event, so will not be added as a unique sync choice")
                    addFlag=False
            if addFlag:
                cloudChoicesToAddToSyncChoices.append(cloudChoice)
        self.syncChoicesList.extend(cloudChoicesToAddToSyncChoices)
        
#         self.showStartupSyncChoices_part2()
#         self.syncChoicesPopup()

    def on_getCloudEvents_error(self,request,result):
        Logger.info("on_getCloudEvents_error called:")
        Logger.info("  request was sent to "+str(request.url))
        Logger.info("    request body="+str(request.req_body))
        Logger.info("    request headers="+str(request.req_headers))
        Logger.info("  result="+str(result))
#         self.showStartupSyncChoices_part2()
#         self.syncChoicesPopup()
        
    def on_getD4HEvents_success(self,request,result):
        Logger.info("on_getD4HEvents_success called:")
        Logger.info("  result="+str(result))
        # add d4h sync choices here; response items are not in the same format
        #  as sign-in db records, so, create a fake 'record' here with just enough
        #  data to populate the sync choices form: EventName and EventStartEpoch
        # NOTE that d4h activity date/time stamps are UTC - need to adjust for timezone;
        #  offset should be taken from the D4H team information; easier to add the offset
        #  than to import the pytz module
        # d4h support confirms that API v2 has no call to get the location bookmark details
        #  but such a call may exist in v3
        for activity in result["data"]:
            if activity["id"] not in [x["D4HID"] for x in self.syncChoicesList]: # don't add duplicates
                d4hdate_text=activity["date"]
                d4hdate_naive=datetime.datetime.strptime(activity["date"],self.d4h_datetimeformat)
    # #             d4hdate_aware=pytz.timezone(self.d4h_timezone_name).localize(d4hdate_naive)
    #             d4hdate_aware_utc=pytz.utc.localize(d4hdate_naive)
    #             d4hdate_aware_local=d4hdate_aware_utc.astimezone(pytz.timezone(self.d4h_timezone_name))
                d4hdate_aware_local=utc_to_local(d4hdate_naive)
                self.syncChoicesList.append({
                        "EventName":activity["ref_desc"],
                        "EventStartEpoch":d4hdate_aware_local.timestamp(),
                        "EventStartDate":d4hdate_aware_local.strftime(self.signin_dateformat),
                        "EventStartTime":d4hdate_aware_local.strftime(self.signin_timeformat),
                        "LocalEventID":None,
                        "CloudEventID":None,
                        "D4HID":activity["id"]}) # D4H ref_autoid value is a string and is not guaranteed to be unique
#             self.syncChoicesList.append(choice)
#             
# #         localSyncChoices=sdbGetEvents(lastEditSince=time.time()-60*60*24*10)
#         cloudChoicesToAddToSyncChoices=[]
#         for cloudChoice in result:
#             # default is to add the cloudChoice; test local choices to see if that remains true
#             addFlag=True
#             Logger.info("  checking cloudChoice "+str(cloudChoice))
#             for localChoice in self.syncChoicesList:
#                 Logger.info("    checking localChoice "+str(localChoice))
#                 same=set(localChoice.items()).intersection(set(cloudChoice.items()))
#                 sameKeys=[x[0] for x in same]
#                 Logger.info("sameKeys:"+str(sameKeys))
#                 if 'CloudEventID' in sameKeys and 'EventStartDate' in sameKeys and 'EventStartTime' in sameKeys:
#                     Logger.info("      this cloud event is already referenced by the local event, so will not be added as a unique sync choice")
#                     addFlag=False
#             if addFlag:
#                 cloudChoicesToAddToSyncChoices.append(cloudChoice)
#         self.syncChoicesList.extend(cloudChoicesToAddToSyncChoices)

    def on_getD4HEvents_error(self,request,result):
        Logger.info("on_getD4HEvents_error called:")
        Logger.info("  request was sent to "+str(request.url))
        Logger.info("    request body="+str(request.req_body))
        Logger.info("    request headers="+str(request.req_headers))
        Logger.info("  result="+str(result))

    def getStartedTimeText(self,startEpoch=0):
        if startEpoch==0:
            return ""
        t=time.time()
        if startEpoch<t:
            prefix="Started "
            suffix=" ago"
        else:
            prefix="Starts in "
            suffix=""
        dt=abs(t-startEpoch)
        dtd=int(dt/(60*60*24)) # truncated total number of days
        dth=int(dt/(60*60)) # truncated total number of hours
        dtm=int(dt/60) # truncated total number of minutes
        if dth==0: # within one hour
            dtText=str(int(dt/60))+" minute"
            if dtm!=1:
                dtText+="s"
        elif dth<3: # between one hour and three hours
            dtTextH=str(dth)+" hour"
            if dth!=1:
                dtTextH+="s"
            dtdm=int(dtm-(60*dth))
            dtTextM=str(dtdm)+" minute"
            if dtdm!=1:
                dtTextM+="s"
            # now put it together; omit minutes if zero
            if dtdm!=0:
                dtText=dtTextH+" "+dtTextM
            else:
                dtText=dtTextH
        elif dth<24:
            dtText=str(dth)+" hour"
            if dth!=1:
                dtText+="s"
        else:
            dtText=str(dtd)+" day"
            if dtd!=1:
                dtText+="s"
        return prefix+dtText+suffix
        
    def syncChoicesPopup(self,choices=None):
        choices=choices or self.syncChoicesList
        Logger.info("syncChoicesPopup called; choices="+str(choices))
        box=BoxLayout(orientation='vertical')
        popup=Popup(title='Sync Choices',content=box,size_hint=(0.8,0.2+(0.1*len(choices))))
        if len(choices)>0:
            box.add_widget(Label(text='Join an existing event:'))
            buttons=[]
#             popup=Popup(title='Sync Choices',content=box,size_hint=(0.8,0.6))
            for choice in choices:
                startedText=self.getStartedTimeText(choice.get("EventStartEpoch",0))
                button=ButtonWithFourImages(markup=True,halign='center')
                button.text="[size=24]"+choice['EventName']+"\n[size=12]"+startedText
                if choice.get("D4HID",None):
                    button.source1=self.syncD4HIconFileName
                if choice.get("LocalEventID",None):
                    button.source2=self.syncLocalIconFileName
                if choice.get("CloudEventID",None):
                    button.source3=self.syncCloudIconFileName
                box.add_widget(button)
                button.bind(on_release=partial(self.syncToEvent,choice))
                button.bind(on_release=popup.dismiss)
            box.add_widget(Label(text='Or tap below to create a new event:'))
        else:
            box.add_widget(Label(text='No syncable events were found.'))
#             button=Button(text='Refresh / Check Again')
#             box.add_widget(button)
#             button.bind(on_release=popup.dismiss)
#             button.bind(on_release=self.startup)
        button=Button(text='New Event')
        box.add_widget(button)
        button.bind(on_release=popup.dismiss)
        button.bind(on_release=self.showNewEvent)
        button=Button(text='Refresh this list')
        box.add_widget(button)
        button.bind(on_release=popup.dismiss)
        button.bind(on_release=self.restart)
        popup.open()
    
    # syncToEvent - set the d4h/cloud/localEventID variables based on the selected
    #   sync target, and create corresponding cloud/local events as needed; then
    #   call sync() to do the actual data syncing
    
    def syncToEvent(self,choice,*args):
        Logger.info("syncToEvent called: "+str(choice))
        # cloud's response LocalEventID becomes this session's cloudEventID
        self.d4hEventID=choice.get("D4HID",None)
        self.cloudEventID=choice.get("CloudEventID",None)
        self.localEventID=choice.get("LocalEventID",None)
        if self.d4hEventID and not self.cloudEventID and not self.localEventID:
            Logger.info("Synced to a D4H event that has no local or cloud event ID")
            if self.cloud:
                Logger.info("  Cloud is responding; sending the request to make the cloud event")
                r=self.newEvent(d=choice,createLocal=True,createCloud=True)
            else:
                Logger.info("   Cloud is not responding; could not create the cloud event; createing the local event")
                # in this case, the local event will be created as below
        if not self.localEventID:
            Logger.info("Synced to an event that has no localEventID - probably the first time syncing to a cloud or D4H event")
            # this would be the case if it is an event from cloud or LAN which
            #  hasn't been edited on this node; create a new local event
            choice.pop("LocalEventID",None) # delete the LocalEventID key, if it exists, to force a new one to be assigned
#             r=sdbNewEvent(choice)
            r=self.newEvent(d=choice,createLocal=True,createCloud=False)
#             Logger.info("  return val from newEvent:"+str(r))
#             self.localEventID=r['validate']['LocalEventID']
            Logger.info("  created a new local event with localEventID "+str(self.localEventID))

        self.sync()
 
    # sync tasks and workflow
    # - pushes (add or update) to self.signInList are done when 'Sign In Now' or
    #    'Sign Out Now' are tapped, in keyDown()
    # - pushes to local db and any remote dbs are done separately, in sendAction,
    #    called from those same taps in keyDown() (after self.signInList is updated)
    # - so, remaining tasks are to bring the local db and self.signInList up to date
    #    with any entries that were added or modified by a different node, i.e.
    #    change the local db and self.signInList as needed to make them the same as
    #    the remote sync target
    # - sync() should do these actions:
    #   1 - fetch the entire database from the remote sync target (could see about
    #         doing some cacheing as a future enhancement using 'since' which would
    #         be different per node)
    #   2 - for every record in the remote sync target, add or update to local db
    #   3 - rebuild self.signInList from local db (this may involve a lot of data
    #         but it is all local so not really a problem unless it is too slow)
    def sync(self,clobber=False):
        Logger.info("sync called; cloudEventID="+str(self.cloudEventID))
        if clobber:
            self.signInList=[]
        if self.cloudEventID:
            request=UrlRequest(self.cloudServer+"/api/v1/events/"+str(self.cloudEventID),
                    on_success=self.on_syncToCloud_success,
                    on_failure=self.on_syncToCloud_error,
                    on_error=self.on_syncToCloud_error)
            Logger.info("asynchronous request sent to "+str(request.url))
            self.topbar.ids.syncButtonImage.source=self.syncCloudDownloadStartIconFileName
        else:
            self.loadFromDB(sdbGetEvent(self.localEventID))

    # this function name may change - right now it is intended to grab the entire table
    #  from the server using http api
#     def sync(self,clobber=False):
#         Logger.info("sync called")
#         if self.cloudEventID:
#             request=UrlRequest(self.cloudServer+"/api/v1/events/"+str(self.cloudEventID),
#                     on_success=self.on_sync_success,
#     #                 self.on_sync_redirect,
#                     on_failure=self.on_sync_failure,
#                     on_error=self.on_sync_error)
#             Logger.info("asynchronous request sent:"+str(request))
#             self.topbar.ids.syncButtonImage.source=self.syncCloudDownloadStartIconFileName
#         else:
#             Logger.info("  no cloudEventID specfiied - nothing to sync")
    
    def on_syncToCloud_success(self,request,result):
        Logger.info("on_sync_success called")
        Logger.info(str(result))
        # fix #55: result could be html text, i.e. the login page on a guest wifi
        #  https://stackoverflow.com/a/1952655/3577105
#         try:
#             i=iter(result)
#         except TypeError:
#             print("result is not iterable")
#             self.topbar.ids.syncButtonImage.source=self.syncNoneIconFileName
#         else:
#             for d in result:
#                 Logger.info("  entry dict:"+str(d))
#                 entry=[d[k] for k in self.columns]
#                 Logger.info("  entry list:"+str(entry))
#                 if entry not in self.signInList: # do not add duplicates
#                     self.signInList.append(entry)
#             self.topbar.ids.syncButtonImage.source=self.syncCloudIconFileName
#             self.updateHeaderCount()
#         for d in result:
#             Logger.info("  entry dict:"+str(d))
#             entry=[d[k] for k in self.columns]
#             Logger.info("  entry list:"+str(entry))
#             if entry not in self.signInList: # do not add duplicates
#                 self.signInList.append(entry)
        self.loadFromDB(result)
        self.topbar.ids.syncButtonImage.source=self.syncCloudIconFileName
#         self.updateHeaderCount()

#     def on_sync_failure(self,request,result):
#         Logger.info("on_sync_failure called:")
#         Logger.info("  request="+str(request))
#         Logger.info("    request body="+str(request.req_body))
#         Logger.info("    request headers="+str(request.req_headers))
#         Logger.info("  result="+str(result))
#         self.topbar.ids.syncButtonImage.source=self.syncNoneIconFileName
        
    def on_syncToCloud_error(self,request,result):
        Logger.info("on_syncToCloud_error called:")
        Logger.info("  request="+str(request))
        Logger.info("    request body="+str(request.req_body))
        Logger.info("    request headers="+str(request.req_headers))
        Logger.info("  result="+str(result))
        self.topbar.ids.syncButtonImage.source=self.syncNoneIconFileName

    def loadFromDB(self,result):
        Logger.info("loadFromDB called; signInList:"+str(self.signInList))
        for d in result:
#             Logger.info("  entry dict:"+str(d))
            entry=[d[k] for k in self.columns]
            Logger.info("  entry list:"+str(entry))
            if entry not in self.signInList: # do not add duplicates
                Logger.info("    adding")
                self.signInList.append(entry)
#                 d=dict(zip(self.columns,entry))
                # if we are copying the record directly from the cloud, then,
                #  that record has been synced by definition
                d["Synced"]=self.cloudEventID
                sdbAddOrUpdate(self.localEventID,d) # local db
            self.updateHeaderCount()

#     def sync(self,clobber=False):
#         Logger.info("sync called")
#         try:
#             r=requests.get(url=self.cloudServer+"/api/v1/events/current")
#         except Exception as e:
#             Logger.info("error during GET request:\n"+str(e))
#             return -1
#         # the response json entries are unordered; need to put them in the right
#         #  order to store in the internal list of lists
#         try:
#             rj=r.json() # r.json() returns a list of dictionaries
#         except:
#             Logger.info("reponse error: GET response has no json:\n"+str(r))
#             return -1
#         else:
#             if clobber:
#                 self.signInList=[]
#             for d in rj:
#                 Logger.info("  entry dict:"+str(d))
#                 entry=[d[k] for k in self.columns]
#                 Logger.info("  entry list:"+str(entry))
#                 if entry not in self.signInList: # do not add duplicates
#                     self.signInList.append(entry)
#         self.updateHeaderCount()
    
    def keyDown(self,text,fromLookup=False):
        Logger.info("keyDown: text="+text)
        if len(text)<3: # number or code; it must be from the keypad
            # process the button text
            if text=='bs':
                if len(self.typed)>0:
                    self.typed=self.typed[:-1]
                    self.show()
                if len(self.typed)==0:
                    self.hide()
                if self.adminMode:
                    self.exitAdminMode()
            elif text=='lu':
                Logger.info("lookup table requested")
                self.showLookup()
            else:
                if self.typed=="" and self.localEventID is not None: # this is the first char; do a fresh sync
                    self.sync()
                self.typed+=text
                self.show()
            Logger.info("  typed="+self.typed)
            
            if self.typed=="":
                self.keypad.ids.topLabel.text=""
            else:
#                 self.keypad.ids.statusLabel.text="[size={small}]Keep typing.\n[/size][size={large}]TAP YOUR NAME\n[/size][size={small}]when you see it.[/size]"
                big=int(self.keypad.height*0.05)
                small=int(big*0.4)
                self.keypad.ids.topLabel.text="[size="+str(small)+"]Keep typing.\n[/size][size="+str(big)+"][i]TAP YOUR NAME[/i][/size][size="+str(small)+"]\nwhen you see it.[/size]"
#                 self.setTextToFit(self.keypad.ids.statusLabel,"Keep typing. Tap your name when you see it.")
#                 self.keypad.ids.statusLabel.text="Keep typing. Tap your name when you see it."
                
            # do the lookup
            if self.typed in self.roster: # there is a match
#                 self.keypad.ids.nameButton.text=self.roster[self.typed][0]
#                 # for long names, reduce font size until it fits in its widget
#                 m=self.defaultTextHeightMultiplier
#                 self.keypad.ids.nameButton.font_size=self.keypad.ids.nameButton.height*m
#                 self.keypad.ids.nameButton.texture_update()
#                 while m>0.3 and self.keypad.ids.nameButton.texture_size[0]>self.keypad.ids.nameButton.width:
#                     m=m-0.05
#                     self.keypad.ids.nameButton.font_size=self.keypad.ids.nameButton.height*m
#                     self.keypad.ids.nameButton.texture_update()
                self.setTextToFit(self.keypad.ids.nameButton,self.roster[self.typed][0])
                self.keypad.ids.nameButton.background_color=(0,0.5,0,1)
#                 self.signin.ids.nameLabel.text=self.roster[self.typed][0]
#                 self.signout.ids.nameLabel.text=self.roster[self.typed][0]
            else: # no match
                if len(self.typed)==0:
                    self.hide()
                else:
                    self.show()
                    self.keypad.ids.nameButton.background_color=(0,0,0,0)
                    self.keypad.ids.nameButton.text=""
                if self.typed==self.adminCode:
                    self.enterAdminMode()
                else:
                    if self.adminMode and self.sm.current is not 'details':
                        self.exitAdminMode()
        elif text=="Admin Mode":
            self.exitAdminMode()
        elif text=='Back':
            self.sm.transition.direction='right'
            if self.sm.current_screen.fromLookup:
                self.sm.current='lookup'
            else:
                self.sm.current='keypad'
        elif self.typed!="": # a different button, with a non-blank typed value
            id=self.typed
            Logger.info("  other key pressed.  id="+str(id))
#             idText=str(id)
#             if id.isdigit():
#                 idText="SAR "+str(id)
#             name=self.roster.get(id,"")[0]
            name=self.getName(id)
            Logger.info("lookup: id="+id+"  name="+name)
            ii=[j for j,x in enumerate(self.signInList) if x[0]==id] # list of indices for the typed ID
            i=-1
            entry=[]
            if len(ii)>0:
                i=ii[-1] # index of the most recent entry for the typed ID
            if i>=0:
                entry=self.signInList[i] # the actual most recent entry
            if text==name:
                self.sm.transition.direction='left'
                if entry==[]: # not yet signed in (or out)
                    self.showSignIn(id,fromLookup)
#                     self.signin.ids.nameLabel.text=name
#                     self.signin.ids.idLabel.text=idText
#                     self.signin.fromLookup=fromLookup
#                     certs=self.getCerts(id)
#                     self.signin.ids.certBox.clear_widgets()
#                     for cert in certs:
#                         Logger.info("adding certification question for "+cert)
#                         certLayout=BoxLayout(orientation='horizontal',size_hint=(1,0.1))
#                         certLabel=Label(text='Are you ready to deploy as '+cert+'?')
#                         certSwitch=Switch()
#                         certSwitch.cert=cert # pass the cert name as a property of the switch
# #                         certSwitch.bind(active=self.certSwitchCB)
#                         certLayout.add_widget(certLabel)
#                         certLayout.add_widget(certSwitch)
#                         self.signin.ids.certBox.add_widget(certLayout)
# #                         buttonsLayout=BoxLayout(orientation='horizontal',size_hint=(1,0.1))
# #                         self.viewSwitchButton=Button(text='View List\nD.d : 0\nDM.m : 0\nDMS.s : 0')
# #                 #         self.viewSwitchButton.bind(on_press=self.viewSwitch)
# #                         buttonsLayout.add_widget(self.viewSwitchButton)
# #                         goButton=Button(text='Create Markers')
# #                         goButton.bind(on_press=self.createMarkers)
# #                         buttonsLayout.add_widget(goButton)
# #                         self.layout.add_widget(buttonsLayout)
#                     self.sm.current='signin'
                elif entry[8]==0: # signed in but not signed out
                    self.setTextToFit(self.signout.ids.nameLabel,self.getName(id))
                    # fit the text again after the transition is done, since the widget
                    #  size (and therefore the text height) is wacky until the screen has
                    #  been displayed for the first time
                    self.signout.on_enter=self.signOutNameTextUpdate
                    self.signout.ids.idLabel.text=self.getIdText(id)
                    self.signout.ids.statusLabel.text="Signed in at "+self.timeStr(entry[4])
                    self.signout.fromLookup=fromLookup
                    self.sm.current='signout'
                else: # already signed out
                    text=""
                    for k in ii: # build the full string of all previous sign-in / sign-out pairs
                        text=text+"In: "+self.timeStr(self.signInList[k][5])+"   Out: "+self.timeStr(self.signInList[k][6])+"   Total: "+self.timeStr(self.signInList[k][7])+"\n"
#                     self.alreadysignedout.ids.nameLabel.text=self.getName(id)
                    self.setTextToFit(self.alreadysignedout.ids.nameLabel,self.getName(id))
                    # fit the text again after the transition is done, since the widget
                    #  size (and therefore the text height) is wacky until the screen has
                    #  been displayed for the first time
                    self.alreadysignedout.on_enter=self.alreadySignedOutNameTextUpdate
                    self.alreadysignedout.ids.idLabel.text=self.getIdText(id)
                    self.alreadysignedout.fromLookup=fromLookup
                    self.alreadysignedout.ids.statusLabel.text="You are already signed out:\n"+text
                    self.sm.current='alreadysignedout'
#             elif text=='Back':
#                 self.sm.transition.direction='right'
#                 if self.sm.current_screen.fromLookup:
#                     self.sm.current='lookup'
#                 else:
#                     self.sm.current='keypad'
            elif text=='Sign In Again':
                self.showSignIn(id)
            elif text=='Sign In Now':
                name=self.getName(id)
                # temporary hardcodes 8-16-19
                agency="NCSSAR"
#                 cellNum=self.getCell(id)
                cellNum="123-456-7890" # use fake numbers for security while db is public on the web
                status="SignedIn"
                idText=self.getIdText(id)
#                 self.sm.current='signintype'
                t=round(time.time(),2) # round to hundredth of a second to aid database comparison
                # get the list of on/enabled ready-to-deploy-as switches
                #  since objects are always inserted to the front of the children list,
                #  the actual switch will be .children[0] as long as it was the
                #  last widget inserted to its certLayout
                certsNoPrompt=self.getCerts(id)[0]
                certsPromptedYes=[certLayout.children[0].cert for certLayout in self.signin.ids.certBox.children if certLayout.children[0].active] 
                certs=certsPromptedYes+certsNoPrompt
                s=id+" "+name+" signed in"
                if self.details.eventType=="Search":
                    s+="and is ready to deploy as "+str(certs)
                Logger.info(s)
                entry=[id,name,agency,','.join(certs),self.timeStr(t),"--","--",t,0.0,0.0,cellNum,status,'']
                self.signInList.append(entry)
                self.sendAction(entry)
                self.thankyou.ids.statusLabel.text="Signed in at "+self.timeStr(t)
#                 self.thankyou.ids.nameLabel.text=self.getName(id)
                self.setTextToFit(self.thankyou.ids.nameLabel,self.getName(id),initialFontSize=self.thankyou.height*0.1)
                # fit the text again after the transition is done, since the widget
                #  size (and therefore the text height) is wacky until the screen has
                #  been displayed for the first time
                self.thankyou.on_enter=self.thankyouNameTextUpdate                
                self.thankyou.ids.idLabel.text=self.getIdText(id)
                self.sm.current='thankyou'
#                 Logger.info(str(self.signInList))
#                 self.exportList=copy.deepcopy(self.signInList)
#                 self.writeCSV()
                Clock.schedule_once(self.switchToBlankKeypad,2)
#             elif 'in and out' in text:
#                 t=time.time()
#                 self.signInList.append([id,name,t,t,1])
#                 self.thankyou.ids.statusLabel.text="Signed in and out at "+self.timeStr(t)
#                 self.thankyou.ids.nameLabel.text=name
#                 self.thankyou.ids.idLabel.text=idText
#                 self.sm.current='thankyou'
#                 self.exportList=copy.deepcopy(self.signInList)
#                 self.writeCSV()
#                 Clock.schedule_once(self.switchToBlankKeypad,2)
            elif 'Sign Out Now' in text or 'change my latest sign-out time to right now' in text:
                #temporary hardcode 8-16-19
                status="SignedOut"
                inTime=entry[7]
                outTime=round(time.time(),2) # round to hundredth of a second to aid database comparison
                totalTime=round(outTime-inTime)
                entry[5]=self.timeStr(outTime)
                entry[6]=self.timeStr(totalTime)
                entry[8]=outTime
                entry[9]=totalTime
                entry[11]=status
                self.sendAction(entry)
                self.thankyou.ids.statusLabel.text="Signed in at "+self.timeStr(inTime)+"\nSigned out at "+self.timeStr(outTime)+"\nTotal time: "+self.timeStr(totalTime)
#                 self.thankyou.ids.nameLabel.text=self.getName(id)
                self.setTextToFit(self.thankyou.ids.nameLabel,self.getName(id),initialFontSize=self.thankyou.height*0.1)
                # fit the text again after the transition is done, since the widget
                #  size (and therefore the text height) is wacky until the screen has
                #  been displayed for the first time
                self.thankyou.on_enter=self.thankyouNameTextUpdate
                self.thankyou.ids.idLabel.text=self.getIdText(id)
                self.sm.current='thankyou'
#                 self.exportList=copy.deepcopy(self.signInList)
#                 self.writeCSV()
                Clock.schedule_once(self.switchToBlankKeypad,3)
            Logger.info(str(self.signInList))
#             Logger.info(str([{'text':str(x)} for entry in self.signInList for x in entry]))
    
    
    # from https://pastebin.com/5e7ymKTU            
    def on_request_close(self, *args, **kwargs):
        Logger.info("on_request_close called")
        if self.adminMode:
            self.textpopup(title='Exit', text='Are you sure?', buttonText='Yes', size_hint=(0.5,0.2))
            return True
        else:
            return True
 
    def newEventPopup(self,text='Fill out the form to create a new event:'):
        Logger.info("newEventPopup called")
#         box=BoxLayout(orientation='vertical')
#         box.add_widget(Label(text=text))
#         popup=Popup(title='New Event',content=box,size_hint=(None, None),size=(600, 300))
#         button=Button(text='Create New Event',size_hint=(1,0.25))
#         box.add_widget(button)
#         button.bind(on_release=popup.dismiss)
#         button.bind(on_release=self.newEvent)
#         popup.open()
        
    def on_new_event(self, *args, **kwargs):
        Logger.info("on_new_event called")
        self.sm.current='newevent'
        
    def textpopup(self, title='', text='', buttonText='OK', on_release=None, size_hint=(0.8,0.25)):
        Logger.info("textpopup called; on_release="+str(on_release))
        box = BoxLayout(orientation='vertical')
        box.add_widget(Label(text=text))
        if buttonText is not None:
            mybutton = Button(text=buttonText, size_hint=(1, 0.3))
            box.add_widget(mybutton)
#         popup = Popup(title=title, content=box, size_hint=(None, None), size=(600, 300))
        popup = Popup(title=title, content=box, size_hint=size_hint)
        if not on_release:
            on_release=self.stop
        if buttonText is not None:
            mybutton.bind(on_release=popup.dismiss)
            mybutton.bind(on_release=on_release)
        popup.open()
        return popup # so that the calling code cand close the popup
# 
#     def eventStartDateTouch(self,*args,**kwargs):
#         Logger.info("eventStartDateTouch called")
#         a=DatePicker()
        
# from https://kivy.org/doc/stable/api-kivy.uix.recycleview.htm and http://danlec.com/st4k#questions/47309983

# prevent keyboard on selection by getting rid of FocusBehavior from inheritance list
class SelectableRecycleGridLayout(LayoutSelectionBehavior,
                                  RecycleGridLayout):
    ''' Adds selection and focus behaviour to the view. '''

# class ButtonWithImage(Button):
#     pass

class ButtonWithFourImages(Button):
    pass

class SelectableLabel(RecycleDataViewBehavior, Label):
    ''' Add selection support to the Label '''
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)
    bg=ListProperty([0,0,0,0])

    def refresh_view_attrs(self, rv, index, data):
        ''' Catch and handle the view changes '''
        self.index = index
        return super(SelectableLabel, self).refresh_view_attrs(
            rv, index, data)

    def on_touch_down(self, touch):
        ''' Add selection on touch down '''
        if super(SelectableLabel, self).on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos) and self.selectable:
            if theApp.sm.current=='theList':
                colCount=theApp.theList.ids.theGridLayout.cols
                Logger.info("List item tapped: index="+str(self.index)+":"+str(theApp.theList.ids.theGrid.data[self.index]))
                rowNum=int(self.index/colCount)
                bg=theApp.theList.ids.theGrid.data[self.index]['bg']
                if bg[1]==0:
                    newBg=(0,0.8,0.1,0.7)
                else:
                    newBg=(0,0,0,0)
                for i in list(range(rowNum*colCount,(rowNum+1)*colCount)):
                    theApp.theList.ids.theGrid.data[i]['bg']=newBg
                theApp.theList.ids.theGrid.refresh_from_data()
                return True
            else:
                return self.parent.select_with_touch(self.index, touch)

    def apply_selection(self, rv, index, is_selected):
        ''' Respond to the selection of items in the view. '''
        self.selected = is_selected
        if is_selected:
            Logger.info("selection changed to {0}".format(rv.data[index]))
            [name,id]=rv.data[index]['text'].split(" : ")
            theApp.keyDown(id[-1]) # mimic the final character of the ID, to trigger the lookup
            theApp.typed=id
            theApp.keyDown(name,fromLookup=True) # mimic the name being tapped from the keypad screen
            Clock.schedule_once(self.clear_selection,0.5) # aesthetic - to prepare for the next lookup
    
    def clear_selection(self,*args):
        self.parent.clear_selection()


# clock credit to Yoav Glazner https://stackoverflow.com/a/48850796/3577105
class ClockText(Label):
    def update(self,*args):
        self.text=time.strftime('%H:%M')

class TopBar(BoxLayout):
    pass

class YesNoSwitch(Switch):
    pass

class KeypadScreen(Screen):
    pass

class SignInScreen(Screen):
    fromLookup=BooleanProperty(False) # so that 'back' will go to lookup screen

# class SignInTypeScreen(Screen):
#     pass

class SignOutScreen(Screen):
    fromLookup=BooleanProperty(False) # so that 'back' will go to lookup screen


class AlreadySignedOutScreen(Screen):
    fromLookup=BooleanProperty(False) # so that 'back' will go to lookup screen


class ThankyouScreen(Screen):
    pass


class ListScreen(Screen):
    idList=ListProperty(["id"])
    nameList=ListProperty(["name"])
    timeInList=ListProperty([])
    timeOutList=ListProperty(["out"])
    totalTimeList=ListProperty(["total"])
    bigList=ListProperty([])


class LookupScreen(Screen):
    fromLookup=BooleanProperty(False) # so that 'back' will go to keypad screen
    rosterList=ListProperty(["id"])


# class NewEventPopup(BoxLayout):
class NewEventScreen(Screen):
    eventType=StringProperty("")
    eventName=StringProperty("")
    eventStartDate=StringProperty(today_date())
    eventStartTime=StringProperty(datetime.datetime.now().strftime("%H:%M"))
    eventLocation=StringProperty("")
    rosterFileName=StringProperty("")
    
    
class DetailsScreen(Screen):
    eventType=StringProperty("")
    eventName=StringProperty("")
    eventStartDate=StringProperty(today_date())
    eventStartTime=StringProperty(datetime.datetime.now().strftime("%H:%M"))
    eventLocation=StringProperty("")
    rosterFileName=StringProperty("")


class ComboEdit(TextInput):
    options = ListProperty(('', ))
    def __init__(self, **kw):
        ddn = self.drop_down = DropDown()
        ddn.bind(on_select=self.on_select)
#         self.focus=True
        super(ComboEdit, self).__init__(**kw)

#     def show_keyboard(self,*args):
#         self.focus=True
        
    def on_options(self, instance, value):
        Logger.info("ComboEdit.on_options called:"+str(instance)+":"+str(value))
        ddn = self.drop_down
        ddn.clear_widgets()
        for option in value:
            Logger.info("creating button for "+option)
            b=Button(text=option,size_hint_y=None,height=Window.height/20,font_size=Window.height/25)
            b.bind(on_release=lambda btn: ddn.select(btn.text))
            ddn.add_widget(b)

    def on_select(self, *args):
        self.text = args[1]
        try:
            [name,id]=self.text.split(" : ")
        except:
            [name,id]=[self.text,theApp.getId(self.text)]
        theApp.keyDown(id[-1]) # mimic the final character of the ID, to trigger the lookup
        theApp.typed=id
        Logger.info("calling keyDown: typed="+theApp.typed+"  name="+name+"  id="+id)
        theApp.keyDown(name,fromLookup=True) # mimic the name being tapped from the keypad screen
        Clock.schedule_once(self.clear_selection,0.5) # aesthetic - to prepare for the next lookup
 
    def clear_selection(self,*args):
        self.text=''
        ddn=self.drop_down
        ddn.clear_widgets()
#         theApp.typed='' # not sure why this was needed;
        #but it causes action buttons to fail because they depend on id at action-button-press time!
    
    def on_touch_up(self, touch):
        Logger.info("ComboEdit.on_touch_up called")
        if touch.grab_current == self:
            self.drop_down.open(self)
        return super(ComboEdit, self).on_touch_up(touch)

    def on_text(self,instance,value):
        Logger.info("ComboEdit.on_text called:"+str(instance)+":"+str(value))
        self.text=value
        if value!="":
            instance.options=[x for x in self.parent.parent.rosterList if x.lower().startswith(value.lower())]

        else:
            instance.options=[]
#             self.clear_selection()
        Logger.info("options:"+str(instance.options))
        return True
        
#     def on_focus(self,instance,value):
#         Logger.info("on_focus called:instance="+str(instance)+":value="+str(value))
        

if __name__ == '__main__':
    theApp=signinApp()
    theApp.run()
#     signinApp().run()
    