import readline
import networkx as nx
from threading import Thread, Semaphore
from termcolor import cprint, colored

graph = nx.Graph()
routers = []
links = []
monitor = False


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
        self.sec = 0
        self.neighbors = {}  # not implemented
        self.LSDB = nx.Graph()  # not implemented
        self.routing_table = {}  # not implemented

        self.inp = []
        self.inp_sem = Semaphore(value=0)
        self.rcv_trd = Thread(target=self.receive, daemon=True)
        self.rcv_trd.start()

        self.nbr_in = None
        self.nbr_sem = Semaphore(value=0)

    def neighboring(self, dst, starter=False):
        # down
        if starter:
            self.send(Packet({'id': self.id, 'neighbors': self.neighbors.keys()}, 'hello', self, dst, nbr=True))
            self.nbr_sem.acquire()
            self.neighbors[self.nbr_in.msg['id']] = self.sec
            # 2_way
            self.send(Packet({'id': self.id, 'neighbors': self.neighbors.keys()}, 'hello', self, dst, nbr=True))
        else:
            self.nbr_sem.acquire()
            self.neighbors[self.nbr_in.msg['id']] = self.sec
            # init
            self.send(Packet({'id': self.id, 'neighbors': self.neighbors.keys()}, 'hello', self, dst, nbr=True))
            self.nbr_sem.acquire()
            # 2_way

        self.send(Packet(self.LSDB, 'DBD', self, dst, nbr=True))
        self.nbr_sem.acquire()
        self.LSDB.update(self.nbr_in.msg)
        # full

    def give(self, pkt):
        self.inp.append(pkt)
        self.inp_sem.release()

    def send(self, pkt):
        graph.edges.get((self.id, pkt.receiver))['object'].deliver(pkt)

    def receive(self):
        self.inp_sem.acquire()
        pkt = self.inp.pop()
        if pkt.nbr:
            self.nbr_in = pkt
            self.nbr_in.release()
        else:
            pass  # not implemented

    def sec_passed(self):
        self.sec += 1
        if self.sec % 10 == 0:
            for k in self.neighbors.keys():
                self.send(Packet({'id': self.id, 'neighbors': self.neighbors.keys()}, 'hello', self,
                                 graph.nodes.get(k)['object']))
        if self.sec % 30 == 1:
            for k, v in self.neighbors.items():
                if self.sec - v > 30:
                    for d in self.neighbors.items():
                        if k == d:
                            continue
                        self.send(Packet(None, 'lsa', self, graph.nodes.get(d)['object']))

class Packet:
    def __init__(self, msg, typ: str, sender: Router, receiver: Router, nbr=False):
        self.msg = msg
        self.type = typ
        self.sender = sender
        self.receiver = receiver
        self.nbr = nbr


class Link:
    def __init__(self, s1: Router, s2: Router, bw: int):
        self.sides = [s1, s2]
        self.bw = bw
        self.up = True

    def deliver(self, pkt: Packet):
        if not self.up:
            return
        if pkt.receiver.id == self.sides[0].id:
            self.sides[0].give(pkt)
        elif pkt.receiver.id == self.sides[1].id:
            self.sides[1].give(pkt)
        else:
            raise Exception("not valid destination for this link")


class Functions:
    @staticmethod
    def sec(cmd: str):
        pass  # not implemented

    @staticmethod
    def add(cmd: str):
        _, _, n = cmd.split()
        n = int(n)
        if graph.has_node(n):
            cprint("router %d exists" % n, 'red')
            return
        graph.add_node(n, object=Router(n))
        # todo check remained

    @staticmethod
    def connect(cmd: str):
        _, s1, s2, bw = cmd.split()
        s1, s2, bw = int(s1), int(s2), int(bw)
        router1 = graph.nodes.get(s1)['object']
        router2 = graph.nodes.get(s2)['object']

        if graph.edges.get((s1, s2)):
            cprint("link already exists between %d and %d." % (s1, s2), 'yellow')
            return

        if len(graph.neighbors(s1)) >= 10 or len(graph.neighbors(s2)) >= 10:
            cprint("no empty interface found on router.", 'yellow')
            return

        link = Link(router1, router2, bw)
        graph.add_edge(s1, s2, weight=bw, object=link)

        # todo neighboring process
        # todo check remained

    @staticmethod
    def link(cmd: str):
        _, s1, s2, en = cmd.split()
        s1, s2, en = int(s1), int(s2), en == 'e'
        graph.edges.get((s1, s2))['object'].up = en

    @staticmethod
    def ping(cmd: str):
        pass  # not implemented

    @staticmethod
    def monitor(cmd: str):
        global monitor
        en = cmd.split()[1] == 'e'
        if en:
            monitor = True
        else:
            monitor = False


if __name__ == '__main__':
    completer = MyCompleter(["sec ", "add router ", "connect ", "link ", "ping ", "monitor e", "monitor d"])
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
