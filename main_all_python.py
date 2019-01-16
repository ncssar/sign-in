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

import kivy
kivy.require('1.9.1')

from kivy.app import App
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button

from kivy.core.window import Window
from kivy.uix.widget import Widget


class Keypad(FloatLayout):
    pass
#     def keyCB(self,text):
#         print("Button pressed: {}".format(text))
#         self.ids.textArea.text=text    
        
#     def __init__(self,**kwargs):
#         super(Keypad,self).__init__(**kwargs)
#         self.cols=4
#         self.add_widget(Label(text='1'))
#         self.add_widget(Label(text='2'))
#         self.add_widget(Label(text='3'))
#         self.add_widget(Label(text='4'))
#         self.add_widget(Label(text='5'))
#         self.add_widget(Label(text='6'))
#         self.add_widget(Label(text='7'))
#         self.add_widget(Label(text='8'))
#         b1=Button(text='1')
#         self.add_widget(b1)
#         b2=Button(text='2')
#         self.add_widget(b2)
#         b3=Button(text='3')
#         self.add_widget(b3)
#         b4=Button(text='4')
#         self.add_widget(b4)
#         b5=Button(text='5')
#         self.add_widget(b5)
#         b6=Button(text='6')
#         self.add_widget(b6)
#         b7=Button(text='7')
#         self.add_widget(b7)
#         b8=Button(text='8')
#         self.add_widget(b8)
         
class signinApp(App):
    def keyCB(self,text):
        print("Button pressed: {}".format(text))
        self.v+=text
        self.keypad.ids.typingArea.text=self.v
        if self.v in self.roster.keys():
            self.keypad.ids.nameArea.text=self.roster[self.v]
        else:
            self.keypad.ids.nameArea.text="tap your name when it appears here"          
   
    def keyClear(self):
        self.v=""
        self.keypad.ids.typingArea.text=self.v          
   
    def build(self):
        self.title='SAR Sign-in'
        self.v=""
        self.roster={
            '35':'joe',
            '28':'steve',
            '122':'ross',
            '1':'Del'
        }
        self.layout=BoxLayout(orientation='vertical')
        self.numField=Label(text='number',size_hint_y=0.2)
        self.nameField=Label(text='name',size_hint_y=0.15)
        self.yesRowLayout=BoxLayout(orientation='horizontal',size_hint_y=0.15)
        self.isThisYouField=Label(text='Is this you?')
        self.keepTypingField=Label(text='(if not, keep typing)')
        self.yesButton=Button(text='Yes')
        self.yesRowLayout.add_widget(self.isThisYouField)
        self.yesRowLayout.add_widget(self.yesButton)
        self.layout.add_widget(self.numField)
        self.layout.add_widget(self.nameField)
        self.layout.add_widget(self.yesRowLayout)
        self.b0=Button(text='0')
        self.b1=Button(text='1')
        self.b2=Button(text='2')
        self.b3=Button(text='3')
        self.b4=Button(text='4')
        self.b5=Button(text='5')
        self.b6=Button(text='6')
        self.b7=Button(text='7')
        self.b8=Button(text='8')
        self.b9=Button(text='9')
        self.backspace=Button(text='bs')
        self.bs=Button(text='S')
        self.row7=BoxLayout(orientation='horizontal')
        self.row7.add_widget(self.b7)
        self.row7.add_widget(self.b8)
        self.row7.add_widget(self.b9)
        self.row4=BoxLayout(orientation='horizontal')
        self.row4.add_widget(self.b4)
        self.row4.add_widget(self.b5)
        self.row4.add_widget(self.b6)
        self.row1=BoxLayout(orientation='horizontal')
        self.row1.add_widget(self.b1)
        self.row1.add_widget(self.b2)
        self.row1.add_widget(self.b3)
        self.row0=BoxLayout(orientation='horizontal')
        self.row0.add_widget(self.bs)
        self.row0.add_widget(self.b0)
        self.row0.add_widget(self.backspace)
        self.keypad=BoxLayout(orientation='vertical')
        self.keypad.add_widget(self.row7)
        self.keypad.add_widget(self.row4)
        self.keypad.add_widget(self.row1)
        self.keypad.add_widget(self.row0)
        self.layout.add_widget(self.keypad)
        
        return self.layout
        
if __name__ == '__main__':
    signinApp().run()