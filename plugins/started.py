from rtmbot.core import Plugin
import os

class StartedPlugin(Plugin):
    def process_hello(self, data):
        print('CANARY STARDED. DATA:', data, flush=True)
        #print(os.getcwd(), flush=True)
        #print(os.listdir('plugins'))
        #print(os.listdir('config'))


