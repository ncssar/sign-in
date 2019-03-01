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
# Config.set('kivy','keyboard_mode','system')
Config.set('kivy','log_dir','log')
Config.set('kivy','log_enable',1)
Config.set('kivy','log_level','info')
Config.set('kivy','log_maxfiles',5)

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
from kivy.properties import BooleanProperty, ListProperty, StringProperty, ObjectProperty,NumericProperty
from kivy.clock import Clock
from kivy.utils import platform

from kivy.logger import Logger

from jnius import cast
from jnius import autoclass

class signinApp(App):
    def build(self):
        Logger.info("build starting...")
        self.gui=Builder.load_file('main.kv')
        self.adminCode='925'
        self.adminMode=False
        self.possibleCerts=["K9A","K9T","M","S","K9","DR"]
        self.roster={}
        self.signInList=[]
        self.exportList=[]
#         self.csvFileName="C:\\Users\\caver\\Downloads\\sign-in.csv"
        if platform in ('windows'):
            self.downloadDir=os.path.join(os.path.expanduser('~'),"Downloads")
            self.rosterDir=self.downloadsDir
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
        self.details=self.sm.get_screen('details')
        self.defaultNameButtonText='Enter your SAR #'
        self.exitAdminMode()
        self.typed=''
        self.finalized='NO'
        self.details.rosterFileName=self.rosterFileName
        self.readRoster()
#         self.setupAlphaGrouping()
        self.startTime=time.time()
        self.clocktext=self.keypad.ids.clocktext
        Clock.schedule_interval(self.clocktext.update,1)
        self.sm.current='details'
        return self.sm

    def exitAdminMode(self):
        Logger.info("Exiting admin mode")
        self.keypad.ids.listbutton.opacity=0
        self.keypad.ids.listbutton.disabled=True
        self.keypad.ids.detailsbutton.opacity=0
        self.keypad.ids.detailsbutton.disabled=True
        self.typed=""
        self.keypad.ids.statusLabel.text=""
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
        self.keypad.ids.statusLabel.text="(tap above to exit)"
        self.keypad.ids.topLabel.text=""
        self.adminMode=True
    
    def hide(self):
        self.keypad.ids.topLabel.opacity=0
        self.keypad.ids.topLabel.height=0
        self.keypad.ids.nameButton.text=self.defaultNameButtonText
        self.keypad.ids.nameButton.background_color=(0,0,0,0)

    def show(self):
        self.keypad.ids.topLabel.opacity=1
        self.keypad.ids.topLabel.height=100
        self.keypad.ids.topLabel.text="You entered: "+self.typed

# self.roster is a dictionary: key=ID, val=[name,certifications]
#  where 'certs' is a string of the format "K9,M,DR," etc as specified in the
#  master roster document; relevant certifications will result in questions
#   "are you ready to deploy as <cert>?" during sign-in
    def readRoster(self):
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
#                     Logger.info("row:"+str(row[0])+":"+row[1])
                    # if the first token has any digits, add it to the roster
                    if any(i.isdigit() for i in row[0]):
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
        
    def getIdText(self,id):
        idText=str(id)
        if id.isdigit():
            idText="SAR "+str(id)
        return idText
    
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
        Environment=autoclass('android.os.Environment')
        PythonActivity=autoclass('org.kivy.android.PythonActivity')
        mActivity=PythonActivity.mActivity
        Context=autoclass('android.content.Context')
        DownloadManager=autoclass('android.app.DownloadManager')
        try:
            shutil.copy(filename,path)
        except PermissionError as ex:
            Logger.warning("Could not write file "+path+":")
            Logger.warning(ex)
            PythonActivity.toastError("File not written: Permission denied\n\nPlease add Storage permission for this app using your device's Settings menu, then try again.\n\nYou should not need to restart the app.")
            PythonActivity.toastError("File not written: "+str(ex))
        except Exception as ex:
            Logger.warning("Could not write file "+path+":")
            Logger.warning(ex)
            PythonActivity.toastError("File not written: "+str(ex))
        else:
            Logger.info("Download successful")
            DownloadService=mActivity.getSystemService(Context.DOWNLOAD_SERVICE)
            DownloadService.addCompletedDownload(path,path,True,mimetype,path,os.stat(path).st_size,True)    
            PythonActivity.toastError("File created successfully:\n\n"+path+"\n\nCheck your 'download' notifications for single-tap access.")
        
    def writeCSV(self,rotate=True,download=False):
        # rotate first, since it moves the base file to .bak1
        Logger.info("writeCSV called")
        if rotate and os.path.isfile(self.csvFileName):
            self.rotateCSV()
        with open(self.csvFileName,'w') as csvFile:
            Logger.info("csv file "+self.csvFileName+" opened")
            csvWriter=csv.writer(csvFile)
            csvWriter.writerow(["## NCSSAR Sign-in Sheet"])
            csvWriter.writerow(["## Event Date and Start Time: "+time.strftime("%a %b %#d %Y %H:%M:%S",time.localtime(self.startTime))])
            csvWriter.writerow(["## Event Name: "+self.details.ids.eventNameField.text])
            csvWriter.writerow(["## Event Type: "+self.details.eventType])
            csvWriter.writerow(["## Event Location: "+self.details.eventLocation])
            csvWriter.writerow(["## File written "+time.strftime("%a %b %#d %Y %H:%M:%S")])
            csvWriter.writerow(["ID","Name","Resource","In","Out","Total"])
            for entry in self.exportList:
                # copy in, out, and total seconds to end of list
                entry.append(entry[3])
                entry.append(entry[4])
                entry.append(entry[5])
                # change entries 2,3,4 to human-readable in case the csv is
                #  imported to a spreadsheet
                entry[3]=self.timeStr(entry[3])
                entry[4]=self.timeStr(entry[4])
                entry[5]=self.timeStr(entry[5])
                # csv apparently knows to wrap the string in quotes only if the
                #  same character used as the delimiter appears in the string
                csvWriter.writerow(entry)
            csvWriter.writerow(["## end of list; FINALIZED: "+self.finalized])
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
        self.writeCSV(download=True)
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
    def importCSV(self):
        pass
    
    def sync(self):
        pass
    
    def timeStr(self,sec):
#         Logger.info("calling timeStr:"+str(sec))
        if isinstance(sec,str): # return strings as-is
            return sec
        if sec==0:
            return "--"
        if sec<1e6: # assume it's an elapsed / total time
            t=time.gmtime(sec)
            if t.tm_hour==0:
                return time.strftime("%#M min",t)
            if t.tm_hour==1:
                return time.strftime("%#H hr %#M min",t)
            return time.strftime("%#H hrs %#M min",t)
        return time.strftime("%H:%M",time.localtime(sec))
    
    def switchToBlankKeypad(self,*args):
        self.keypad.ids.headerLabel.text=self.details.eventType+": "+self.details.ids.eventNameField.text+"  In:"+str(self.getCurrentlySignedInCount())+" Total:"+str(self.getTotalAttendingCount())
        self.typed=''
        self.hide()
        self.sm.current='keypad'
    
    def getCurrentlySignedInCount(self,*args):
        # get the number of entries in signInList that are not signed out
        return len([x for x in self.signInList if x[4]==0])
    
    def getTotalAttendingCount(self,*Args):
        # get the number of unique IDs in signInList
        return len(list(set([x[0] for x in self.signInList])))
         
    def showList(self,*args):
        self.theList.ids.listHeadingLabel.text=self.details.eventType+": "+self.details.ids.eventNameField.text+"  Currently here: "+str(self.getCurrentlySignedInCount())+"   Total: "+str(self.getTotalAttendingCount())
        self.theList.bigList=[str(x) for entry in self.exportList for x in entry[0:6]]
        self.sm.transition.direction='up'
        self.sm.current='theList'
        self.sm.transition.direction='down'
        if self.adminMode:
            self.exitAdminMode()

    def showDetails(self,*args):
        self.sm.transition.direction='up'
        self.sm.current='details'
        self.sm.transition.direction='down'
        if self.adminMode:
            self.exitAdminMode()
        
    def showLookup(self,*args):
        self.lookup.rosterList=sorted([str(val[0])+" : "+str(key) for key,val in self.roster.items()])
#         Logger.info(str(self.lookup.rosterList))
        self.sm.transition.direction='left'
        self.sm.current='lookup'
        self.sm.transition.direction='right'

    def showSignIn(self,id,fromLookup=False):
        self.signin.ids.nameLabel.text=self.getName(id)
        self.signin.ids.idLabel.text=self.getIdText(id)
        self.signin.fromLookup=fromLookup
        certs=self.getCerts(id)
        self.signin.ids.certBox.clear_widgets()
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
    #                         buttonsLayout=BoxLayout(orientation='horizontal',size_hint=(1,0.1))
    #                         self.viewSwitchButton=Button(text='View List\nD.d : 0\nDM.m : 0\nDMS.s : 0')
    #                 #         self.viewSwitchButton.bind(on_press=self.viewSwitch)
    #                         buttonsLayout.add_widget(self.viewSwitchButton)
    #                         goButton=Button(text='Create Markers')
    #                         goButton.bind(on_press=self.createMarkers)
    #                         buttonsLayout.add_widget(goButton)
    #                         self.layout.add_widget(buttonsLayout)
        self.sm.current='signin'
#     def certSwitchCB(self,instance,value):
#         Logger.info("certSwitchCB called:"+str(instance)+":"+str(value))
#         Logger.info("  cert:"+str(instance.cert))
     
    def keyDown(self,text,fromLookup=False):
        Logger.info("keyDown: text="+text+"  typed="+self.typed)
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
            
            # do the lookup
            if self.typed in self.roster: # there is a match
                self.keypad.ids.nameButton.text=self.roster[self.typed][0]
                self.keypad.ids.nameButton.background_color=(0,0.5,0,1)
                self.signin.ids.nameLabel.text=self.roster[self.typed][0]
                self.signout.ids.nameLabel.text=self.roster[self.typed][0]
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
        else: # a different button
            id=self.typed
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
                elif entry[4]==0: # signed in but not signed out
                    self.signout.ids.nameLabel.text=self.getName(id)
                    self.signout.ids.idLabel.text=self.getIdText(id)
                    self.signout.ids.statusLabel.text="Signed in at "+self.timeStr(entry[3])
                    self.signout.fromLookup=fromLookup
                    self.sm.current='signout'
                else: # already signed out
                    text=""
                    for k in ii: # build the full string of all previous sign-in / sign-out pairs
                        text=text+"In: "+self.timeStr(self.signInList[k][3])+"   Out: "+self.timeStr(self.signInList[k][4])+"   Total: "+self.timeStr(self.signInList[k][5])+"\n"
                    self.alreadysignedout.ids.nameLabel.text=self.getName(id)
                    self.alreadysignedout.ids.idLabel.text=self.getIdText(id)
                    self.alreadysignedout.fromLookup=fromLookup
                    self.alreadysignedout.ids.statusLabel.text="You are already signed out:\n"+text
                    self.sm.current='alreadysignedout'
            elif text=='Back':
                self.sm.transition.direction='right'
                if self.sm.current_screen.fromLookup:
                    self.sm.current='lookup'
                else:
                    self.sm.current='keypad'
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
                Logger.info(id+" "+name+" signed in and is ready to deploy as "+str(certs))
                self.signInList.append([id,name,','.join(certs),t,0,0])
                self.thankyou.ids.statusLabel.text="Signed in at "+self.timeStr(t)
                self.thankyou.ids.nameLabel.text=self.getName(id)
                self.thankyou.ids.idLabel.text=self.getIdText(id)
                self.sm.current='thankyou'
#                 Logger.info(str(self.signInList))
                self.exportList=copy.deepcopy(self.signInList)
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
                inTime=entry[3]
                outTime=time.time()
                totalTime=outTime-inTime
                entry[4]=outTime
                entry[5]=totalTime
                self.thankyou.ids.statusLabel.text="Signed in at "+self.timeStr(inTime)+"\nSigned out at "+self.timeStr(outTime)+"\nTotal time: "+self.timeStr(totalTime)
                self.thankyou.ids.nameLabel.text=self.getName(id)
                self.thankyou.ids.idLabel.text=self.getIdText(id)
                self.sm.current='thankyou'
                self.exportList=copy.deepcopy(self.signInList)
                self.writeCSV()
                Clock.schedule_once(self.switchToBlankKeypad,3)
            Logger.info(str(self.signInList))
#             Logger.info(str([{'text':str(x)} for entry in self.signInList for x in entry]))
                

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
    rosterList=ListProperty(["id"])
    
class DetailsScreen(Screen):
    eventType=StringProperty("")
    eventName=StringProperty("")
    eventLocation=StringProperty("")
    rosterFileName=StringProperty("")


if __name__ == '__main__':
    theApp=signinApp()
    theApp.run()
#     signinApp().run()
    