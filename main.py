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

import kivy
kivy.require('1.9.1')

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.recyclegridlayout import RecycleGridLayout
from kivy.uix.boxlayout import BoxLayout
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
        
<KeypadScreen>:
    BoxLayout:
        orientation: 'vertical'
        BoxLayout:
            height:20
            Button:
                text:'a'
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
        MyButton:
            text: 'Sign In 60min Ago'
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
        MyButton:
            text: 'Sign Out 60min From Now'
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
            height:20
            Button:
                text:'a'
                on_press:app.switchToBlankKeypad()
        BoxLayout:
            MyRV:
                size_hint_x: 0.1
                # app.idList (etc) does not seem to work; use root. instead
                data: [{'text':str(x)} for x in root.idList]
            MyRV:
                size_hint_x: 0.45
                data: [{'text':str(x)} for x in root.nameList]
            MyRV:
                size_hint_x: 0.15
                data: [{'text':str(x)} for x in root.timeInList]
            MyRV:
                size_hint_x: 0.15
                data: [{'text':str(x)} for x in root.timeOutList]
            MyRV:
                size_hint_x: 0.15
                data: [{'text':str(x)} for x in root.totalTimeList]

'''
  
class signinApp(App):
    def build(self):
        self.defaultNameLabelText='Enter your SAR #'
        self.typed=''
        self.roster={}
        self.roster["35"]="Tom Grundy"
        self.roster["1S9"]="Sgt. Mike Sullivan"
        self.roster["1"]="Del Clement"
        sm.current='keypad'
        return sm

    def hide(self):
#         keypad=sm.get_screen(keypad)
        keypad.ids.topLabel.opacity=0
        keypad.ids.topLabel.height=0
        keypad.ids.buttonRow.opacity=0
        keypad.ids.buttonRow.height=0
        keypad.ids.nameLabel.text=self.defaultNameLabelText

    def show(self):
#         keypad=sm.get_screen(keypad)
        keypad.ids.topLabel.opacity=1
        keypad.ids.topLabel.height=100
        keypad.ids.buttonRow.opacity=1
        keypad.ids.buttonRow.height=100
        keypad.ids.topLabel.text="You entered: "+self.typed
#         self.main_widget.ids.yesLabel2.text="Sign me in."

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
        for key in signInDict.keys():
            print("key="+key+"  item="+str(signInDict[key]))
            theList.idList.append(key)
            theList.nameList.append(signInDict[key][0])
            theList.timeInList.append(signInDict[key][1])
            theList.timeOutList.append(signInDict[key][2])
            theList.totalTimeList.append(signInDict[key][3])
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
            if self.typed in self.roster:
                keypad.ids.nameLabel.text=self.roster[self.typed]
                signin.ids.nameLabel.text=self.roster[self.typed]
                signout.ids.nameLabel.text=self.roster[self.typed]
            else:
                if len(self.typed)==0:
                    self.hide()
    #                 self.main_widget.ids.nameLabel.text=self.defaultNameLabelText
                else:
                    self.show()
                    keypad.ids.nameLabel.text=""
        else: # a different button
            if text=='YES':
                sm.transition.direction='left'
                # not yet signed in (or out):
                if self.typed not in signInDict:
                    sm.current='signin'
                # signed in but not yet signed out:
                if self.typed in signInDict and signInDict[self.typed][1]!=0 and signInDict[self.typed][2]==0:
                    signout.ids.statusLabel.text="Signed in at "+time.strftime("%H:%M",time.localtime(signInDict[self.typed][1]))
                    sm.current='signout'
            elif text=='Back':
                sm.transition.direction='right'
                sm.current='keypad'
            elif text=='Sign In Now':
                # not yet signed in (or out):
                if self.typed not in signInDict:
                    signInDict[self.typed]=[self.roster[self.typed],time.time(),0,0]
                    thankyou.ids.statusLabel.text="Signed in at "+time.strftime("%H:%M",time.localtime(signInDict[self.typed][1]))
                    thankyou.ids.nameLabel.text=self.roster[self.typed]
                    sm.current='thankyou'
                    Clock.schedule_once(self.switchToBlankKeypad,2)
            elif text=='Sign Out Now':
                # signed in but not yet signed out:
                if self.typed in signInDict and signInDict[self.typed][2]==0:
                    inTime=signInDict[self.typed][1]
                    outTime=time.time()
                    totalTime=outTime-inTime
                    signInDict[self.typed][2]=outTime
                    signInDict[self.typed][3]=totalTime
                    thankyou.ids.statusLabel.text="Signed in at "+time.strftime("%H:%M",time.localtime(inTime))+"\nSigned out at "+time.strftime("%H:%M",time.localtime(outTime))+"\nTotal time:"+time.strftime("%h hours %m minutes",time.localtime(totalTime))
                    thankyou.ids.nameLabel.text=self.roster[self.typed]
                    sm.current='thankyou'
            print(str(signInDict))
                
                
class KeypadScreen(Screen):
    pass

class SignInScreen(Screen):
    pass

class SignOutScreen(Screen):
    pass

class ThankyouScreen(Screen):
    pass

class ListScreen(Screen):
    idList=ListProperty(["id"])
    nameList=ListProperty(["name"])
    timeInList=ListProperty(["in"])
    timeOutList=ListProperty(["out"])
    totalTimeList=ListProperty(["total"])

Builder.load_string(KV)
sm=ScreenManager()
sm.add_widget(KeypadScreen(name='keypad'))
sm.add_widget(SignInScreen(name='signin'))
sm.add_widget(SignOutScreen(name='signout'))
sm.add_widget(ThankyouScreen(name='thankyou'))
sm.add_widget(ListScreen(name='theList'))
keypad=sm.get_screen('keypad')
signin=sm.get_screen('signin')
signout=sm.get_screen('signout')
thankyou=sm.get_screen('thankyou')
theList=sm.get_screen('theList')
signInDict={}

if __name__ == '__main__':
    signinApp().run()
    