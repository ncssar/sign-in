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
from kivy.uix.checkbox import CheckBox
from kivy.properties import BooleanProperty, ListProperty, StringProperty, ObjectProperty,NumericProperty
from kivy.clock import Clock

from kivy.logger import Logger

class signinApp(App):
    def build(self):
        self.gui=Builder.load_file('main.kv')
        self.adminCode='925'
        self.adminMode=False
        self.roster={}
        self.signInList=[]
        self.csvFileName="C:\\Users\\caver\\Downloads\\sign-in.csv"
        self.sm=ScreenManager()
        self.sm.add_widget(KeypadScreen(name='keypad'))
        self.sm.add_widget(SignInScreen(name='signin'))
        self.sm.add_widget(SignOutScreen(name='signout'))
        self.sm.add_widget(AlreadySignedOutScreen(name='alreadysignedout'))
        self.sm.add_widget(ThankyouScreen(name='thankyou'))
        self.sm.add_widget(ListScreen(name='theList'))
        self.sm.add_widget(LookupScreen(name='lookup'))
        self.sm.add_widget(DetailsScreen(name='details'))
        self.keypad=self.sm.get_screen('keypad')
        self.signin=self.sm.get_screen('signin')
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
        self.details.rosterFileName="C:\\Users\\caver\\Downloads\\roster.csv"
        self.readRoster()
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

    def readRoster(self):
        self.roster={}
        try:
            with open(self.details.rosterFileName,'r') as rosterFile:
                self.details.ids.rosterTimeLabel.text=time.strftime("%a %b %#d %Y %H:%M:%S",time.localtime(os.path.getmtime(self.details.rosterFileName))) # need to use os.stat(path).st_mtime on linux
                csvReader=csv.reader(rosterFile)
                for row in csvReader:
    #                 print("row:"+str(row[0])+":"+row[1])
                    # if the first token has any digits, add it to the roster
                    if any(i.isdigit() for i in row[0]):
    #                     print("  adding")
                        self.roster[row[0]]=row[1]
                self.details.ids.rosterStatusLabel.text=str(len(self.roster))+" roster entries have been loaded."
        except Exception as e:
            self.details.ids.rosterStatusLabel.text="Specified roster file is not valid."
            self.details.ids.rosterTimeLabel.text=""
            Logger.warning(str(e))

    def writeCsv(self,rotate=True):
        # rotate first, since it moves the base file to .bak1
        if rotate and os.path.isfile(self.csvFileName):
            self.rotateCsv()
        with open(self.csvFileName,'w') as csvFile:
            csvWriter=csv.writer(csvFile)
            csvWriter.writerow(["## NCSSAR Sign-in Sheet"])
            csvWriter.writerow(["## Event Date and Start Time: "+time.strftime("%a %b %#d %Y %H:%M:%S",time.localtime(self.startTime))])
            csvWriter.writerow(["## Event Name: "+self.details.ids.eventNameField.text])
            csvWriter.writerow(["## Event Type: "+self.details.eventType])
            csvWriter.writerow(["## Event Location: "+self.details.eventLocation])
            csvWriter.writerow(["## File written "+time.strftime("%a %b %#d %Y %H:%M:%S")])
            csvWriter.writerow(["ID","Name","In","Out","Total"])
            for entry in self.exportList:
                # copy in, out, and total seconds to end of list
                entry.append(entry[2])
                entry.append(entry[3])
                entry.append(entry[4])
                # change entries 2,3,4 to human-readable in case the csv is
                #  imported to a spreadsheet
                entry[2]=self.timeStr(entry[2])
                entry[3]=self.timeStr(entry[3])
                entry[4]=self.timeStr(entry[4])
                csvWriter.writerow(entry)
            csvWriter.writerow(["## end of list; FINALIZED: "+self.finalized])

    def rotateCsv(self,depth=5):
        # move e.g. 4 to 5, then 3 to 4, then 2 to 3, then 1 to 2, then <base> to 1
        for n in range(depth-1,0,-1):
            name1=self.csvFileName.replace('.csv','.bak'+str(n)+'.csv')
            name2=self.csvFileName.replace('.csv','.bak'+str(n+1)+'.csv')
            if os.path.isfile(name1):
                shutil.move(name1,name2) # shutil.move will overwrite; os.rename will not
        shutil.move(self.csvFileName,name1)
                
    def finalize(self):
        pass
    
    def export(self):
        pass
    
    def importCsv(self):
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
        return len([x for x in self.signInList if x[3]==0])
    
    def getTotalAttendingCount(self,*Args):
        # get the number of unique IDs in signInList
        return len(list(set([x[0] for x in self.signInList])))
         
    def showList(self,*args):
        self.theList.ids.listHeadingLabel.text=self.details.eventType+": "+self.details.ids.eventNameField.text+"  Currently here: "+str(self.getCurrentlySignedInCount())+"   Total: "+str(self.getTotalAttendingCount())
        self.theList.bigList=[str(x) for entry in self.exportList for x in entry[0:5]]
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
        self.lookup.rosterList=sorted([str(val)+" : "+str(key) for key,val in self.roster.items()])
#         Logger.info(str(self.lookup.rosterList))
        self.sm.transition.direction='left'
        self.sm.current='lookup'
        self.sm.transition.direction='right'
        
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
                self.keypad.ids.nameButton.text=self.roster[self.typed]
                self.keypad.ids.nameButton.background_color=(0,0.5,0,1)
                self.signin.ids.nameLabel.text=self.roster[self.typed]
                self.signout.ids.nameLabel.text=self.roster[self.typed]
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
            idText=str(id)
            if id.isdigit():
                idText="SAR "+str(id)
            name=self.roster.get(id,"")
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
                    self.signin.ids.nameLabel.text=name
                    self.signin.ids.idLabel.text=idText
                    self.signin.fromLookup=fromLookup
                    self.sm.current='signin'
                elif entry[3]==0: # signed in but not signed out
                    self.signout.ids.nameLabel.text=name
                    self.signout.ids.idLabel.text=idText
                    self.signout.ids.statusLabel.text="Signed in at "+self.timeStr(entry[2])
                    self.signout.fromLookup=fromLookup
                    self.sm.current='signout'
                else: # already signed out
                    text=""
                    for k in ii: # build the full string of all previous sign-in / sign-out pairs
                        text=text+"In: "+self.timeStr(self.signInList[k][2])+"   Out: "+self.timeStr(self.signInList[k][3])+"   Total: "+self.timeStr(self.signInList[k][4])+"\n"
                    self.alreadysignedout.ids.nameLabel.text=name
                    self.alreadysignedout.ids.idLabel.text=idText
                    self.alreadysignedout.fromLookup=fromLookup
                    self.alreadysignedout.ids.statusLabel.text="You are already signed out:\n"+text
                    self.sm.current='alreadysignedout'
            elif text=='Back':
                self.sm.transition.direction='right'
                if self.sm.current_screen.fromLookup:
                    self.sm.current='lookup'
                else:
                    self.sm.current='keypad'
            elif text=='Sign In Now' or text=='Sign In Again Now':
                t=time.time()
                self.signInList.append([id,name,t,0,0])
                self.thankyou.ids.statusLabel.text="Signed in at "+self.timeStr(t)
                self.thankyou.ids.nameLabel.text=name
                self.thankyou.ids.idLabel.text=idText
                self.sm.current='thankyou'
                Logger.info(str(self.signInList))
                self.exportList=copy.deepcopy(self.signInList)
                self.writeCsv()
                Clock.schedule_once(self.switchToBlankKeypad,2)
            elif 'in and out' in text:
                t=time.time()
                self.signInList.append([id,name,t,t,1])
                self.thankyou.ids.statusLabel.text="Signed in and out at "+self.timeStr(t)
                self.thankyou.ids.nameLabel.text=name
                self.thankyou.ids.idLabel.text=idText
                self.sm.current='thankyou'
                self.exportList=copy.deepcopy(self.signInList)
                self.writeCsv()
                Clock.schedule_once(self.switchToBlankKeypad,2)
            elif 'Sign Out Now' in text or 'change my latest sign-out time to right now' in text:
                inTime=entry[2]
                outTime=time.time()
                totalTime=outTime-inTime
                entry[3]=outTime
                entry[4]=totalTime
                self.thankyou.ids.statusLabel.text="Signed in at "+self.timeStr(inTime)+"\nSigned out at "+self.timeStr(outTime)+"\nTotal time: "+self.timeStr(totalTime)
                self.thankyou.ids.nameLabel.text=name
                self.thankyou.ids.idLabel.text=idText
                self.sm.current='thankyou'
                self.exportList=copy.deepcopy(self.signInList)
                self.writeCsv()
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
                colCount=5
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
            
class KeypadScreen(Screen):
    pass

class SignInScreen(Screen):
    fromLookup=BooleanProperty(False)

class SignOutScreen(Screen):
    fromLookup=BooleanProperty(False)

class AlreadySignedOutScreen(Screen):
    fromLookup=BooleanProperty(False)

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
    