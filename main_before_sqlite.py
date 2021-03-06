# #############################################################################
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

# # from kivy.garden import datetimepicker
# # DatePicker from https://github.com/Skucul/datepicker
# from datepicker import DatePicker
# # TimePicker from https://github.com/Skucul/timepicker
# from timepicker import TimePicker

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

def sortSecond(val):
    return val[1]

def toast(text):
    if platform in ('android'):
        PythonActivity.toastError(text)
    else:
        Logger.info("TOAST:"+text)

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
        self.possibleCerts=["K9A","K9T","M","S","K9","DR"]
        self.roster={}
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
            self.rosterDir=self.csvDir # need to get permision to read local files, then use a file browser
        self.rosterFileName=os.path.join(self.rosterDir,"roster.csv")
        self.csvFileName=os.path.join(self.csvDir,"sign-in.csv")
        self.printLogoFileName="images/logo.jpg"
        self.agencyNameForPrint="NEVADA COUNTY SHERIFF'S SEARCH AND RESCUE"
        self.sm=ScreenManager()
        self.sm.add_widget(KeypadScreen(name='keypad'))
        self.sm.add_widget(SignInScreen(name='signin'))
#         self.sm.add_widget(SignInTypeScreen(name='signintype'))
        self.sm.add_widget(SignOutScreen(name='signout'))
        self.sm.add_widget(AlreadySignedOutScreen(name='alreadysignedout'))
        self.sm.add_widget(ThankyouScreen(name='thankyou'))
        self.sm.add_widget(ListScreen(name='theList'))
        self.sm.add_widget(LookupScreen(name='lookup'))
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
        self.startTime=time.time()
        self.readRoster()
#         self.setupAlphaGrouping()
        self.clocktext=self.keypad.ids.clocktext
        Clock.schedule_interval(self.clocktext.update,1)
        self.sm.current='details'
        self.recoverIfNeeded()
        Logger.info("Valid roster files:"+str(self.scanForRosters()))
        return self.sm

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
        # 1. check for files in the data dir with modification date within 24 hours
        # 2. of those, check to see which are not finalized
        # 3. if just one is not finalized, and it's the most recent one, load it
        # 4. if more than one is not finalized, show a pick box to let user
        #      select which one to restore
        # 5. if everything within the last 24 hours is finalized, do not load anything
        
        Logger.info("entering recoverIfNeeded")
        csvList=self.scanForCSV()
        Logger.info("Valid CSV files:"+str(csvList))
#         each sublist is [<filename>,<file_time>,<event_name>,<header_time>,<finalized>]
        csvCandidates=[x for x in csvList if self.startTime-x[1]<86400 and not x[4]]
        csvCandidates.sort(key=sortSecond)
        csvCandidates.reverse() # most recent first, i.e. descending order
        Logger.info("Candidates for recover:"+str(csvCandidates))
        if len(csvCandidates)>>0:
            Logger.info("Reading "+csvCandidates[0][0])
            self.readCSV(csvCandidates[0][0])
            self.switchToBlankKeypad()
            toast("Automatically recovering:\n"+csvCandidates[0][2]+"\nEvent started:"+str(csvCandidates[0][3]))
    
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
        self.keypad.ids.listbutton.opacity=0
        self.keypad.ids.listbutton.disabled=True
        self.keypad.ids.detailsbutton.opacity=0
        self.keypad.ids.detailsbutton.disabled=True
        self.typed=""
        self.keypad.ids.topLabel.text=""
        self.hide()
        self.adminMode=False
    
    def enterAdminMode(self):
        Logger.info("Entering admin mode")
        self.keypad.ids.listbutton.opacity=1
        self.keypad.ids.listbutton.disabled=False
        self.keypad.ids.detailsbutton.opacity=1
        self.keypad.ids.detailsbutton.disabled=False
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
        
# self.roster is a dictionary: key=ID, val=[name,certifications]
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
                for row in csvReader:
                    # critera for adding a row to the roster:
                    #  row[7] (DOE = Date Of Entry) must be non-blank
                    #  so if row[0] (ID) is blank, assign a unique ID here 
                    #   to allow the rest of this app to work.  Start with 'X1'.
#                     Logger.info("row:"+str(row[0])+":"+row[1])
                    # if the first token has any digits, add it to the roster
                    if row[7] not in ("","DOE"): # skip blanks and the header
#                     if any(i.isdigit() for i in row[0]):
                        if row[0]=="":
                            row[0]="X"+str(self.nextXID)
                            Logger.info("  no ID exists for "+row[1]+": assigning ID "+row[0])
                            self.nextXID=self.nextXID+1
                        self.roster[row[0]]=[row[1],row[5]]
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
            print("letter:"+letter+" n:"+str(n)+" list:"+str(len(alphaDict.get(letter,[])))+":"+str(alphaDict.get(letter,[])))
            alphaGroupList[n]=len(alphaDict.get(letter,[]))
        print("alphaGroupList:"+str(alphaGroupList))
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
        certs=[]
        if self.roster[id]:
            # parse the certifications field, using either space or comma as delimiter,
            #  removing blank strings due to back-to-back delimiters due to loose syntax
            idCerts=[x for x in self.roster[id][1].replace(' ',',').split(',') if x]
            Logger.info("roster certs for "+id+":"+str(idCerts)+"  (raw="+str(self.roster[id][1])+")")
            for possibleCert in self.possibleCerts:
                if possibleCert in idCerts:
                    certs.append(possibleCert)
        Logger.info("Certifications for "+id+":"+str(certs))
        return certs

    def downloadFile(self,filename,mimetype):
        path=self.downloadDir+"/"+os.path.basename(filename)
        Logger.info("Downloading i.e. copying from "+filename+" to "+path)
        try:
            shutil.copy(filename,path)
        except PermissionError as ex:
            Logger.warning("Could not write file "+path+":")
            Logger.warning(ex)
            toast("File not written: Permission denied\n\nPlease add Storage permission for this app using your device's Settings menu, then try again.\n\nYou should not need to restart the app.")
            toast("File not written: "+str(ex))
        except Exception as ex:
            Logger.warning("Could not write file "+path+":")
            Logger.warning(ex)
            toast("File not written: "+str(ex))
        else:
            Logger.info("Download successful")
            if platform in ('android'):
                DownloadService=mActivity.getSystemService(Context.DOWNLOAD_SERVICE)
                DownloadService.addCompletedDownload(path,path,True,mimetype,path,os.stat(path).st_size,True)    
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
                    row[6]=float(row[6]) # use the epoch sec for time-in
                    row[7]=float(row[7]) # use the epoch sec for time-out
                    row[8]=float(row[8]) # use the number of sec for total time
                    self.signInList.append(row)
                elif row[0].startswith("## Event Date and Start Time:"):
                    pass
                elif row[0].startswith("## Event Name:"):
                    self.eventName=row[0].split(':')[1]
                elif row[0].startswith("## Event Type:"):
                    self.eventType=row[0].split(':')[1]
                elif row[0].startswith("## Event Location:"):
                    self.eventLocation=row[0].split(':')[1]
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
        
    def writeCSV(self,rotate=True,download=False):
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
            csvWriter.writerow(["ID","Name","Resource","In","Out","Total"])
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
        if download and os.path.isfile(self.csvFileName):
            self.downloadFile(self.csvFileName,"text/csv")

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
        self.writeCSV(download=True,rotate=False)
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
    def sync(self):
        pass
    
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
#         self.keypad.ids.headerLabel.text=self.details.eventType+": "+self.details.ids.eventNameField.text+"  In:"+str(self.getCurrentlySignedInCount())+" Total:"+str(self.getTotalAttendingCount())
        self.keypad.ids.headerLabel.text=" Total: "+str(self.getTotalAttendingCount())+"   Here: "+str(self.getCurrentlySignedInCount())
        self.typed=''
        self.hide()
        self.sm.current='keypad'
        if self.adminMode:
            self.exitAdminMode()
        if self.getCurrentlySignedInCount()<1:
            self.keypad.ids.topLabel.text="READY TO FINALIZE"
            self.keypad.ids.topLabel.background_color=(0,0,0.5,1)
        else:
            self.keypad.ids.topLabel.text=""

    
    def getCurrentlySignedInCount(self,*args):
        # get the number of entries in signInList that are not signed out
        Logger.info("Getting signed-in count.  Current signInList:"+str(self.signInList))
        return len([x for x in self.signInList if x[4]==0 or x[4]=='--'])
    
    def getTotalAttendingCount(self,*Args):
        # get the number of unique IDs in signInList
        return len(list(set([x[0] for x in self.signInList])))
         
    def showList(self,*args):
        Logger.info("showList called")
        self.theList.ids.listHeadingLabel.text=self.details.eventType+": "+self.details.ids.eventNameField.text+"  Currently here: "+str(self.getCurrentlySignedInCount())+"   Total: "+str(self.getTotalAttendingCount())
        # recycleview needs a single list of strings; it divides into rows every nth element
#         self.theList.bigList=[str(x) for entry in self.signInList for x in entry[0:6]]
        self.theList.bigList=[]
        for entry in self.signInList:
            row=copy.deepcopy(entry[0:6])
            # show blank ID for X# entries (folks without assigned ID in the roster)
            if str(row[0]).startswith('X'):
                row[0]=""
            self.theList.bigList=self.theList.bigList+row
        self.sm.transition.direction='up'
        self.sm.current='theList'
        self.sm.transition.direction='down'

    def showDetails(self,*args):
        self.sm.transition.direction='up'
        self.sm.current='details'
        self.sm.transition.direction='down'
        
    def showLookup(self,*args):
#         self.lookup.rosterList=sorted([str(val[0])+" : "+str(key) for key,val in self.roster.items()])
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
        certs=self.getCerts(id)
        self.signin.ids.certBox.clear_widgets()
        if self.details.eventType=="Search":
            for cert in certs:
                Logger.info("adding certification question for "+cert)
                certLayout=BoxLayout(orientation='horizontal',size_hint=(1,0.1))
                certLabel=Label(text='Are you ready to deploy as '+cert+'?')
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
                    if self.adminMode:
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
                elif entry[7]==0: # signed in but not signed out
                    self.setTextToFit(self.signout.ids.nameLabel,self.getName(id))
                    # fit the text again after the transition is done, since the widget
                    #  size (and therefore the text height) is wacky until the screen has
                    #  been displayed for the first time
                    self.signout.on_enter=self.signOutNameTextUpdate
                    self.signout.ids.idLabel.text=self.getIdText(id)
                    self.signout.ids.statusLabel.text="Signed in at "+self.timeStr(entry[3])
                    self.signout.fromLookup=fromLookup
                    self.sm.current='signout'
                else: # already signed out
                    text=""
                    for k in ii: # build the full string of all previous sign-in / sign-out pairs
                        text=text+"In: "+self.timeStr(self.signInList[k][3])+"   Out: "+self.timeStr(self.signInList[k][4])+"   Total: "+self.timeStr(self.signInList[k][5])+"\n"
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
                idText=self.getIdText(id)
#                 self.sm.current='signintype'
                t=time.time()
                # get the list of on/enabled ready-to-deploy-as switches
                #  since objects are always inserted to the front of the children list,
                #  the actual switch will be .children[0] as long as it was the
                #  last widget inserted to its certLayout
                certs=[certLayout.children[0].cert for certLayout in self.signin.ids.certBox.children if certLayout.children[0].active] 
                s=id+" "+name+" signed in"
                if self.details.eventType=="Search":
                    s+="and is ready to deploy as "+str(certs)
                Logger.info(s)
                self.signInList.append([id,name,','.join(certs),self.timeStr(t),"--","--",t,0,0])
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
                self.writeCSV()
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
                inTime=entry[6]
                outTime=time.time()
                totalTime=outTime-inTime
                entry[4]=self.timeStr(outTime)
                entry[5]=self.timeStr(totalTime)
                entry[7]=outTime
                entry[8]=totalTime
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
                self.writeCSV()
                Clock.schedule_once(self.switchToBlankKeypad,3)
            Logger.info(str(self.signInList))
#             Logger.info(str([{'text':str(x)} for entry in self.signInList for x in entry]))
    
    
    # from https://pastebin.com/5e7ymKTU            
    def on_request_close(self, *args, **kwargs):
        Logger.info("on_request_close called")
        if self.adminMode:
            self.textpopup(title='Exit', text='Are you sure?')
            return True
        else:
            return True
 
    def textpopup(self, title='', text=''):
        """Open the pop-up with the name.
 
        :param title: title of the pop-up to open
        :type title: str
        :param text: main text of the pop-up to open
        :type text: str
        :rtype: None
        """
        box = BoxLayout(orientation='vertical')
        box.add_widget(Label(text=text))
        mybutton = Button(text='OK', size_hint=(1, 0.25))
        box.add_widget(mybutton)
        popup = Popup(title=title, content=box, size_hint=(None, None), size=(600, 300))
        mybutton.bind(on_release=self.stop)
        popup.open()
# 
#     def eventStartDateTouch(self,*args,**kwargs):
#         Logger.info("eventStartDateTouch called")
#         a=DatePicker()
        
# from https://kivy.org/doc/stable/api-kivy.uix.recycleview.htm and http://danlec.com/st4k#questions/47309983

# prevent keyboard on selection by getting rid of FocusBehavior from inheritance list
class SelectableRecycleGridLayout(LayoutSelectionBehavior,
                                  RecycleGridLayout):
    ''' Adds selection and focus behaviour to the view. '''


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
            print("selection changed to {0}".format(rv.data[index]))
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

    
class DetailsScreen(Screen):
    eventType=StringProperty("")
    eventName=StringProperty("")
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
        Logger.info("on_options called:"+str(instance)+":"+str(value))
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
        Logger.info("on_touch_up called")
        if touch.grab_current == self:
            self.drop_down.open(self)
        return super(ComboEdit, self).on_touch_up(touch)

    def on_text(self,instance,value):
        Logger.info("on_text called:"+str(instance)+":"+str(value))
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
    