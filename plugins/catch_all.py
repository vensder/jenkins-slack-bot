from rtmbot.core import Plugin

class CatchAllPlugin(Plugin):
    def catch_all(self, data):
        if data['type'] != 'pong':  #  exclude ofter repeated messages with type 'pong'
            print("CATCH_ALL:", data, flush=True)
