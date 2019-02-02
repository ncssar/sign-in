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

import kivy
kivy.require('1.9.1')

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.recyclegridlayout import RecycleGridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.properties import ListProperty
from kivy.clock import Clock

KV='''
<MyButton@Button>:
    text: 'My Key'
    font_size: 32
    on_press: app.keyDown(self.text)

<MyRV@RecycleView>:
    viewclass: 'Label'
    RecycleGridLayout:
        cols: 1
        default_size: None, dp(26)
        default_size_hint: 1, None
        size_hint_y: None
        height: self.minimum_height
        orientation: 'vertical'

<ClockText>:

<KeypadScreen>:
    BoxLayout:
        orientation: 'vertical'
        BoxLayout:
            height:20
            ClockText:
                id: clocktext
            Button:
                size_hint: None, None
                height:64
                width:64
                background_normal: 'images/list_64x64_white.png'
                on_press:app.showList()
        Label:
            id: topLabel
            font_size:28
        Label:
            id: nameLabel
            font_size:36
        Label:
            id: statusLabel
        BoxLayout:
            id: buttonRow
            orientation: 'horizontal'
            BoxLayout:
                orientation: 'vertical'
                Label:
                    id: isThisYouLabel
                    font_size: 32
                    text: 'Is this you?'
                Label:
                    id: ifNotLabel
                    text: '(if not, keep typing)'
            MyButton:
                id: yesButton
                background_color: (0,0,5,1)
                markup: True
#                 text: '[size=28][b]  YES[/b][/size]\\n[size=18]Sign me in.[/size]'
                text: 'YES'
        BoxLayout:
            orientation: 'horizontal'
            MyButton:
                text: '1'
            MyButton:
                text: '2'
            MyButton:
                text: '3'
        BoxLayout:
            orientation: 'horizontal'
            MyButton:
                text: '4'
            MyButton:
                text: '5'
            MyButton:
                text: '6'
        BoxLayout:
            orientation: 'horizontal'
            MyButton:
                text: '7'
            MyButton:
                text: '8'
            MyButton:
                text: '9'
        BoxLayout:
            orientation: 'horizontal'
            MyButton:
                text: 'S'
            MyButton:
                text: '0'
            MyButton:
                text: 'bs'
<SignInScreen>:
    BoxLayout:
        orientation: 'vertical'
        Label:
            id: nameLabel
            font_size:36
        Label:
            id: statusLabel
        MyButton:
            text: 'Sign In Now'
        MyButton:
            text: 'Sign In 30min Ago'
            opacity: 0.2
        MyButton:
            text: 'Sign In 60min Ago'
            opacity: 0.2
        MyButton:
            text: 'Back'
<SignOutScreen>:
    BoxLayout:
        orientation: 'vertical'
        Label:
            id: nameLabel
            font_size:36
        Label:
            id: statusLabel
        MyButton:
            text: 'Sign Out Now'
        MyButton:
            text: 'Sign Out 30min From Now'
            opacity: 0.2
        MyButton:
            text: 'Sign Out 60min From Now'
            opacity: 0.2
        MyButton:
            text: 'Back'
<AlreadySignedOutScreen>:
    BoxLayout:
        orientation: 'vertical'
        Label:
            id: nameLabel
            font_size:36
        Label:
            id: statusLabel
        MyButton:
            text: 'That must be a mistake; sign me in and out right now.'
            font_size:18
        MyButton:
            text: 'Sign In Again Now'
        MyButton:
            text: 'Back'
<ThankyouScreen>:
    BoxLayout:
        orientation: 'vertical'
        Label:
            font_size: 24
            text: 'Thank You'
        Label:
            id: nameLabel
            font_size: 36
        Label:
            id: statusLabel
            font_size: 18
<ListScreen>:
    BoxLayout:
        orientation: 'vertical'
        BoxLayout:
            size_hint_y: 0.1
            Button:
                size_hint: None, None
                height:64
                width:64
                background_normal: 'images/keypad_64x64_white.png'
                on_press:app.switchToBlankKeypad()
        BoxLayout:
            size_hint_y: 0.9
            MyRV:
                size_hint_x: 0.1
                # app.idList (etc) does not seem to work; use root. instead
                data: [{'text':str(x)} for x in root.idList]
            MyRV:
                size_hint_x: 0.45
                data: [{'text':str(x)} for x in root.nameList]
            MyRV:
                size_hint_x: 0.15
                data: [{'text':x} for x in root.timeInList]
                
            MyRV:
                size_hint_x: 0.15
                data: [{'text':x} for x in root.timeOutList]
            MyRV:
                size_hint_x: 0.15
                data: [{'text':x} for x in root.totalTimeList]

'''

class signinApp(App):
    def build(self):
        self.defaultNameLabelText='Enter your SAR #'
        self.typed=''
        self.readRoster()
        sm.current='keypad'
        self.switchToBlankKeypad()
        clocktext=keypad.ids.clocktext
        Clock.schedule_interval(clocktext.update,1)
        return sm

    def hide(self):
#         keypad=sm.get_screen(keypad)
        keypad.ids.topLabel.opacity=0
        keypad.ids.topLabel.height=0
        self.hideButtonRow()
#         keypad.ids.buttonRow.opacity=0
#         keypad.ids.buttonRow.height=0
        keypad.ids.nameLabel.text=self.defaultNameLabelText

    def show(self):
#         keypad=sm.get_screen(keypad)
        keypad.ids.topLabel.opacity=1
        keypad.ids.topLabel.height=100
        self.showButtonRow()
#         keypad.ids.buttonRow.opacity=1
#         keypad.ids.buttonRow.height=100
        keypad.ids.topLabel.text="You entered: "+self.typed
#         self.main_widget.ids.yesLabel2.text="Sign me in."

    def hideButtonRow(self):
        print("hideButtonRow called")
        keypad.ids.buttonRow.opacity=0
        keypad.ids.buttonRow.height=0
        
    def showButtonRow(self):
        print("showButtonRow called")
        keypad.ids.buttonRow.opacity=1
        keypad.ids.buttonRow.height=100
        
    def readRoster(self):
        self.roster={}
        rosterFileName="C:\\Users\\caver\\Downloads\\roster.csv"
        with open(rosterFileName,'r') as rosterFile:
            csvReader=csv.reader(rosterFile)
            for row in csvReader:
                print("row:"+str(row[0])+":"+row[1])
                # if the first token has any digits, add it to the roster
                if any(i.isdigit() for i in row[0]):
                    print("  adding")
                    self.roster[row[0]]=row[1]

#     def writeCsv(self):
#         csvFileName="C:\\Users\\caver\\Downloads\\sign-in.csv"
#         with open(csvFileName,'w') as csvFile:
#             csvWriter=csv.writer(csvFile)
#             csvWriter.writerow(["## Event: test"])
#             csvWriter.writerow(["## File written "+time.strftime("%a %b %d %Y %H:%M:%S")])
#             csvWriter.writeRow(["ID","Name",""
#             for entry in self.signInList:
#                 csvWriter.writerow(row)
#             csvWriter.writerow(["## end"])

    def timeStr(self,sec):
        print("calling timeStr:"+str(sec))
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
        self.typed=''
        self.hide()
        sm.current='keypad'
        
    def showList(self,*args):
        theList.idList=["ID"]
        theList.nameList=["Name"]
        theList.timeInList=["In"]
        theList.timeOutList=["Out"]
        theList.totalTimeList=["Total"]
        for entry in signInList:
            print("entry="+str(entry))
            theList.idList.append(entry[0])
            theList.nameList.append(entry[1])
            theList.timeInList.append(self.timeStr(entry[2]))
            theList.timeOutList.append(self.timeStr(entry[3]))
            theList.totalTimeList.append(self.timeStr(entry[4]))
        sm.transition.direction='up'
        sm.current='theList'
                    
    def keyDown(self,text):
        print("keyDown called: text="+text)
        if len(text)<3: # number or code; it must be from the keypad
            # process the button text
            if text=='bs':
                if len(self.typed)>0:
                    self.typed=self.typed[:-1]
                    self.show()
                if len(self.typed)==0:
                    self.hide()
            else:    
                self.typed+=text
                self.show()
                        
            # do the lookup
            if self.typed in self.roster: # there is a match
                keypad.ids.nameLabel.text=self.roster[self.typed]
                signin.ids.nameLabel.text=self.roster[self.typed]
                signout.ids.nameLabel.text=self.roster[self.typed]
                self.showButtonRow()
            else: # no match
                if len(self.typed)==0:
                    self.hide()
    #                 self.main_widget.ids.nameLabel.text=self.defaultNameLabelText
                else:
                    self.show()
                    self.hideButtonRow()
                    keypad.ids.nameLabel.text=""
        else: # a different button
            id=self.typed
            name=self.roster[id]
            ii=[j for j,x in enumerate(signInList) if x[0]==id] # list of indices for the typed ID
            i=-1
            entry=[]
            if len(ii)>0:
                i=ii[-1] # index of the most recent entry for the typed ID
            if i>=0:
                entry=signInList[i] # the actual most recent entry
            if text=='YES':
                sm.transition.direction='left'
                if entry==[]: # not yet signed in (or out)
                    sm.current='signin'
                elif entry[3]==0: # signed in but not signed out
                    signout.ids.statusLabel.text="Signed in at "+self.timeStr(entry[2])
                    sm.current='signout'
                else: # already signed out
                    text=""
                    for k in ii: # build the full string of all previous sign-in / sign-out pairs
                        text=text+"In: "+self.timeStr(signInList[k][2])+"   Out: "+self.timeStr(signInList[k][3])+"   Total: "+self.timeStr(signInList[k][4])+"\n"
                    alreadysignedout.ids.nameLabel.text=name
                    alreadysignedout.ids.statusLabel.text=text
                    sm.current='alreadysignedout'
            elif text=='Back':
                sm.transition.direction='right'
                sm.current='keypad'
            elif text=='Sign In Now' or text=='Sign In Again Now':
                t=time.time()
                signInList.append([id,name,t,0,0])
                thankyou.ids.statusLabel.text="Signed in at "+self.timeStr(t)
                thankyou.ids.nameLabel.text=name
                sm.current='thankyou'
                Clock.schedule_once(self.switchToBlankKeypad,2)
            elif 'in and out' in text:
                t=time.time()
                signInList.append([id,name,t,t,1])
                thankyou.ids.statusLabel.text="Signed in and out at "+self.timeStr(t)
                thankyou.ids.nameLabel.text=name
                sm.current='thankyou'
                Clock.schedule_once(self.switchToBlankKeypad,2)
            elif text=='Sign Out Now':
                if entry[3]==0: # signed in but not signed out
                    inTime=entry[2]
                    outTime=time.time()
                    totalTime=outTime-inTime
                    entry[3]=outTime
                    entry[4]=totalTime
                    thankyou.ids.statusLabel.text="Signed in at "+self.timeStr(inTime)+"\nSigned out at "+self.timeStr(outTime)+"\nTotal time: "+self.timeStr(totalTime)
                    thankyou.ids.nameLabel.text=name
                    sm.current='thankyou'
                    Clock.schedule_once(self.switchToBlankKeypad,3)
            print(str(signInList))
                

# clock credit to Yoav Glazner https://stackoverflow.com/a/48850796/3577105
class ClockText(Label):
    def update(self,*args):
        self.text=time.strftime('%H:%M')
            
class KeypadScreen(Screen):
    pass

class SignInScreen(Screen):
    pass

class SignOutScreen(Screen):
    pass

class AlreadySignedOutScreen(Screen):
    pass

class ThankyouScreen(Screen):
    pass

class ListScreen(Screen):
    idList=ListProperty(["id"])
    nameList=ListProperty(["name"])
    timeInList=ListProperty([])
    timeOutList=ListProperty(["out"])
    totalTimeList=ListProperty(["total"])
    

Builder.load_string(KV)
sm=ScreenManager()
sm.add_widget(KeypadScreen(name='keypad'))
sm.add_widget(SignInScreen(name='signin'))
sm.add_widget(SignOutScreen(name='signout'))
sm.add_widget(AlreadySignedOutScreen(name='alreadysignedout'))
sm.add_widget(ThankyouScreen(name='thankyou'))
sm.add_widget(ListScreen(name='theList'))
keypad=sm.get_screen('keypad')
signin=sm.get_screen('signin')
signout=sm.get_screen('signout')
alreadysignedout=sm.get_screen('alreadysignedout')
thankyou=sm.get_screen('thankyou')
theList=sm.get_screen('theList')
signInList=[]

if __name__ == '__main__':
    signinApp().run()
    