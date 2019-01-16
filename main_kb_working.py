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
from kivy.base import runTouchApp
from kivy.lang import Builder

KV='''
<MyButton@Button>:
    text: 'My Button'
    font_size: '24pt'
    on_press: app.keyDown(self.text)

BoxLayout:
    orientation: 'vertical'
    Label:
        id: theLabel
        text: app.defaultLabelText
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
            text: '4'
        MyButton:
            text: '5'
        MyButton:
            text: '6'
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
            text: 'S'
        MyButton:
            text: '0'
        MyButton:
            text: 'bs'
        
'''
  
class signinApp(App):
    def build(self):
        self.defaultLabelText='Enter your SAR number'
        self.labelText=self.defaultLabelText
        self.main_widget=Builder.load_string(KV)
        return self.main_widget
        
    def keyDown(self,text):
        # if default label text was previously shown, replace it with the button text
        if self.labelText==self.defaultLabelText:
            self.labelText=''
        
        # process the button text
        if text=='bs':
            if len(self.labelText)>0:
                self.labelText=self.labelText[:-1]
            if len(self.labelText)==0:
                self.labelText=self.defaultLabelText
        else:    
            self.labelText+=text
        
        # show it
        self.main_widget.ids.theLabel.text=self.labelText


if __name__ == '__main__':
    signinApp().run()
    