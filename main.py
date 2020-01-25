import readline
from termcolor import cprint, colored
import networkx as nx


graph = nx.Graph()
routers = []
links = []


class MyCompleter(object):

    def __init__(self, options):
        self.options = sorted(options)

    def complete(self, text, state):
        if state == 0:  # on first trigger, build possible matches
            if text:  # cache matches (entries that start with entered text)
                self.matches = [s for s in self.options 
                                    if s and s.startswith(text)]
            else:  # no text entered, all matches possible
                self.matches = self.options[:]

        # return match indexed by state
        try: 
            return self.matches[state]
        except IndexError:
            return None


class Packet:
    def __init__(self, msg, sender, receiver):
        self.msg = msg
        self.sender = sender
        self.receiver = receiver


class Client:
    ids = 0

    @staticmethod
    def get_id():
        Client.ids += 1
        return Client.ids

    def __init__(self):
        self.id = Client.get_id()


class Router:
    def __init__(self, n):
        self.id = n
        self.neighbors = None       # not implemented
        self.LSDB = None            # not implemented
        self.routing_table = None   # not implemented


class Link:
    def __init__(self, s1, s2, bw):
        self.sides = [s1, s2]
        self.bw = bw
        self.up = True


class Functions:
    @staticmethod
    def sec(cmd):
        pass

    @staticmethod
    def add(cmd):
        pass

    @staticmethod
    def connect(cmd):
        pass

    @staticmethod
    def link(cmd):
        pass

    @staticmethod
    def ping(cmd):
        pass

    @staticmethod
    def monitor(cmd):
        pass


if __name__ == '__main__':
    completer = MyCompleter(["sec ", "add router ", "connect ", "link ", "ping ", "monitor"])
    readline.set_completer(completer.complete)
    readline.parse_and_bind('tab: complete')

    while True:
        inp = input(colored(">>> ", 'green'))
        if inp == '':
            continue
        try:
            getattr(Functions, inp.split()[0])
        except AttributeError:
            cprint("no function %s" % inp.split()[0], 'red')
        except Exception as e:
            cprint(e.__cause__)
            cprint(e.__traceback__)

