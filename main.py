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
    def __init__(self, n: int):
        self.id = n
        self.neighbors = None  # not implemented
        self.LSDB = None  # not implemented
        self.routing_table = None  # not implemented


class Link:
    def __init__(self, s1: Router, s2: Router, bw: int):
        self.sides = [s1, s2]
        self.bw = bw
        self.up = True


class Functions:
    @staticmethod
    def sec(cmd: str):
        pass

    @staticmethod
    def add(cmd: str):
        _, _, n = cmd.split()
        n = int(n)
        if graph.has_node(n):
            cprint("router %d exists" % n, 'red')
            return
        routers.append(Router(n))
        graph.add_node(n)
        # todo check remained

    @staticmethod
    def connect(cmd: str):
        _, s1, s2, bw = cmd.split()
        s1, s2, bw = int(s1), int(s2), int(bw)
        router1 = list(map(lambda q: q.id == s1, routers))[0]
        router2 = list(map(lambda q: q.id == s2, routers))[0]
        # fixme don't add duplicate links
        if len(graph.neighbors(s1)) >= 10 or len(graph.neighbors(s2)) >= 10:
            cprint("no empty interface found on router.")
            return

        links.append(Link(router1, router2, bw))
        graph.add_weighted_edges_from([(s1, s2, bw)])

        # todo neighboring process
        # todo check remained

    @staticmethod
    def link(cmd: str):
        _, s1, s2, d = cmd.split()
        s1, s2, d = int(s1), int(s2), d == 'd'

        link = list(map(lambda q: s1 in q.sides and s2 in q.sides, links))[0]
        link.up = d

    @staticmethod
    def ping(cmd: str):
        pass

    @staticmethod
    def monitor(cmd: str):
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
            getattr(Functions, inp.split()[0]).__call__(inp)
        except AttributeError:
            cprint("no function %s" % inp.split()[0], 'red')
        except Exception as e:
            cprint(e.__cause__)
            cprint(e.__traceback__)
