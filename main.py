import os
import csv
import readline
import traceback
import json as js
import networkx as nx
from time import sleep
from datetime import datetime
from termcolor import cprint, colored
from threading import Thread, Semaphore, Lock

logs = []
links = []
routers = []
commands = []
monitor = False
graph = nx.Graph()
log_lock = Lock()


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
    def __init__(self, ip: str):
        self.ip = ip
        self.router = None
        # dict.__init__(self, ip=self.ip, router=self.router)
        # dict.__init__(self)


class Router:
    def __init__(self, n: int):
        self.id = n
        self.sec = 0
        self.neighbors = {}
        self.LSDB = nx.Graph()
        self.LSDB.add_node(self.id, object=self, typ='router')
        self.routing_table = {}

        self.inp = []
        self.inp_sem = Semaphore(value=0)
        self.rcv_trd = Thread(target=self.receive, daemon=True)
        self.rcv_trd.start()

        self.nbr_in = None
        self.nbr_sem = Semaphore(value=0)
        # dict.__init__(self, id=n, sec=self.sec, neighbors=self.neighbors, routing_table=self.routing_table)
        # dict.__init__(self)

    def neighboring(self, dst, starter=False):
        def non_blocking():
            # down
            if starter:
                self.send(Packet({'id': self.id, 'neighbors': self.neighbors.keys()}, 'hello', self, dst, nbr=True))
                self.nbr_sem.acquire()
                self.neighbors[self.nbr_in.msg['id']] = self.sec
                # 2_way
                self.send(Packet({'id': self.id, 'neighbors': self.neighbors.keys()}, 'hello', self, dst, nbr=True))
                sleep(.1)
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
            self.dijkstra()
            self.flood(Packet(self.LSDB, 'lsa', self, self, lsdb=True), [dst.id])
            # full

        Thread(target=non_blocking, daemon=True).start()

    def dijkstra(self):
        self.routing_table = {}
        dijkstra = nx.single_source_dijkstra_path(self.LSDB, self.id, weight='weight')  # TODO check if weight based
        for k, v in dijkstra.items():
            if type(k) == str:
                self.routing_table[k] = v[1]

    def give(self, pkt):
        self.inp.append(pkt)
        self.inp_sem.release()

    def send(self, pkt):
        submit_log(self.id, False, pkt)
        graph.edges.get((self.id, pkt.receiver.id))['object'].deliver(pkt)

    def receive(self):
        while True:
            self.inp_sem.acquire()
            pkt = self.inp.pop()
            submit_log(self.id, True, pkt)
            if monitor:
                print('%d:' % self.id, pkt)

            if pkt.nbr:
                self.nbr_in = pkt
                self.nbr_sem.release()

            elif pkt.type == 'hello':
                if pkt.sender.id not in self.neighbors.keys():
                    self.LSDB.add_edge(pkt.sender.id, pkt.receiver.id,
                                       weight=graph.edges[pkt.sender.id, pkt.receiver.id]['weight'],
                                       object=graph.edges[pkt.sender.id, pkt.receiver.id]['object'])
                    self.flood(Packet((self.id, pkt.sender.id, True), 'lsa', self, self))
                    self.dijkstra()
                self.neighbors[pkt.sender.id] = self.sec
                if not self.LSDB.has_edge(pkt.sender.id, self.id):
                    self.LSDB.add_edge(self.id, pkt.sender.id, object=graph.edges[self.id, pkt.sender.id]['object'],
                                       weight=graph.edges[self.id, pkt.sender.id]['weight'])
                    self.flood(Packet(self.LSDB, 'lsa', self, self, lsdb=True))
                    self.dijkstra()

            elif pkt.type.lower() == 'lsa':
                if pkt.lsdb:
                    if pkt.msg.nodes == self.LSDB.nodes and pkt.msg.edges == self.LSDB.edges:
                        continue
                    self.LSDB.update(pkt.msg)
                    self.dijkstra()
                    self.flood(Packet(self.LSDB, 'lsa', self, self, lsdb=True), [pkt.sender.id])
                else:
                    a, b, add = pkt.msg
                    if not add and self.LSDB.has_edge(a, b):
                        self.LSDB.remove_edge(a, b)
                        self.dijkstra()
                    elif add and not self.LSDB.has_edge(a, b):
                        self.LSDB.add_edge(a, b, weight=graph.edges[a, b]['weight'], object=graph.edges[a, b]['object'])
                        self.dijkstra()
                    else:
                        continue
                    self.flood(Packet(pkt.msg, 'lsa', self, self), [pkt.sender.id, pkt.msg[0], pkt.msg[1]])


            elif pkt.type.lower() == 'ping':
                print(colored(self.id, 'yellow'), end=" ")
                try:
                    dst = self.routing_table[pkt.msg]
                except KeyError:
                    cprint("invalid", 'red')
                    continue
                if type(dst) == int:
                    pkt.sender, pkt.receiver = self, self.LSDB.nodes[dst]['object']
                    rcvd = graph.edges.get((self.id, dst))['object'].deliver(pkt)
                    if not rcvd:
                        cprint("unreachable", 'red')
                else:
                    print(colored(dst, 'yellow'))

    def sec_passed(self):
        self.sec += 1

        # send hello to neighbors
        if self.sec % 10 == 0:
            for k in self.neighbors.keys():
                self.send(Packet({'id': self.id, 'neighbors': self.neighbors.keys()}, 'hello', self,
                                 graph.nodes.get(k)['object']))

        # check other neighbors
        # deleted_idx = []
        for k, v in self.neighbors.items():
            if self.sec - v == 30 and self.LSDB.has_edge(self.id, k):
                if monitor:
                    cprint("%d is going to remove (%d, %d)" % (self.id, self.id, k), 'blue')
                self.LSDB.remove_edge(self.id, k)
                # deleted_idx.append(k)
                self.dijkstra()
                self.flood(Packet((self.id, k, False), 'lsa', self, self), [k])
        # for k in deleted_idx:
        #     del self.neighbors[k]

    def flood(self, pkt, ex=[]):
        for d, _ in self.neighbors.items():
            if d in ex:
                continue
            pkt.receiver = graph.nodes.get(d)['object']
            self.send(pkt)


class Packet:
    def __init__(self, msg, typ: str, sender, receiver, nbr=False, lsdb=False):
        self.msg = msg
        self.type = typ
        self.sender = sender
        self.receiver = receiver
        self.nbr = nbr
        self.lsdb = lsdb

    def __str__(self):
        return colored("%s %s (from %s)" % (
            self.type, str(self.msg), self.sender.id if type(self.sender) == Router else self.sender.ip), 'magenta')


class Link:
    def __init__(self, s1, s2, bw: int):
        self.sides = [s1, s2]
        self.bw = bw
        self.up = True
        # dict.__init__(self, sides=self.sides, bw=self.bw, up=self.up)
        # dict.__init__(self)

    def deliver(self, pkt: Packet):
        if not self.up:
            return False
        if pkt.receiver.id == self.sides[0].id:
            self.sides[0].give(pkt)
        elif pkt.receiver.id == self.sides[1].id:
            self.sides[1].give(pkt)
        else:
            raise Exception("not valid destination for this link")
        return True


def submit_log(router_id: int, is_in: bool, pkt: Packet):
    log_lock.acquire()
    writer.writerow(
        dict(zip(headers, [(datetime.now() - start_time).__str__(), router_id, is_in,
                           pkt.sender.id if type(pkt.sender) == Router else pkt.sender.ip,
                           pkt.receiver.id if type(pkt.receiver) == Router else pkt.receiver.ip, pkt.type, pkt.nbr,
                           pkt.lsdb, pkt.msg])))
    log_lock.release()


class Functions:
    @staticmethod
    def sec(cmd: str):
        _, t = cmd.split()
        t = int(t)
        for _ in range(t):
            for n in graph.nodes.values():
                if n['typ'] == 'router':
                    n['object'].sec_passed()
                    sleep(.003)

    @staticmethod
    def add_router(cmd: str):
        _, _, n = cmd.split()
        n = int(n)
        if graph.has_node(n):
            cprint("router %d exists" % n, 'red')
            return
        graph.add_node(n, object=Router(n), typ='router')
        # todo check remained

    @staticmethod
    def add_client(cmd: str):
        _, _, ip = cmd.split()
        if len(ip.split('.')) != 4:
            cprint("malformed IP address", 'red')
            return
        for i in ip.split('.'):
            if not i.isnumeric() or int(i) > 255 or int(i) < 0:
                cprint("invalid IP address %s" % ip, 'red')
        if graph.has_node(ip):
            cprint("client %s exists" % ip, 'red')
            return
        graph.add_node(ip, object=Client(ip), typ='client')

    @staticmethod
    def connect(cmd: str):
        _, s1, s2, bw = cmd.split()
        s1, s2, bw = int(s1) if s1.isnumeric() else s1, int(s2) if s2.isnumeric() else s2, int(bw)

        so1, s1t = graph.nodes.get(s1)['object'], graph.nodes.get(s1)['typ']
        so2, s2t = graph.nodes.get(s2)['object'], graph.nodes.get(s2)['typ']

        if graph.edges.get((s1, s2)):
            cprint("link already exists between %s and %s." % (str(s1), str(s2)), 'yellow')
            return

        if len(graph.adj.get(s1)) >= 10 or len(graph.adj.get(s2)) >= 10:
            cprint("no empty interface found on router.", 'yellow')
            return

        if s1t == 'router' and s2t == 'router':
            so1.LSDB.add_node(s2, object=so2, typ='router')
            so2.LSDB.add_node(s1, object=so1, typ='router')

            link = Link(so1, so2, bw)
            graph.add_edge(s1, s2, weight=bw, object=link)
            so1.LSDB.add_edge(s1, s2, weight=bw, object=link)
            so2.LSDB.add_edge(s1, s2, weight=bw, object=link)

            so1.neighboring(so2, starter=True)
            so2.neighboring(so1)

        else:
            router, client = (so1, so2) if s1t == 'router' else (so2, so1)
            if client.router:
                cprint("client already connected to router %d" % client.router.id, 'yellow')
                return
            router.LSDB.add_edge(s1, s2)
            router.dijkstra()
            router.flood(Packet(router.LSDB, 'lsa', router, router, lsdb=True))
            client.router = router
            graph.add_edge(s1, s2)

    @staticmethod
    def link(cmd: str):
        _, s1, s2, en = cmd.split()
        s1, s2, en = int(s1), int(s2), en == 'e'
        graph.edges.get((s1, s2))['object'].up = en

    @staticmethod
    def ping(cmd: str):
        _, src, dst = cmd.split()
        try:
            src, dst = graph.nodes[src]['object'], graph.nodes[dst]['object']
        except KeyError:
            cprint("invalid ips", 'red')
        cprint(colored(src.ip, 'yellow'), end=' ')
        router = graph.nodes[src.ip]['object'].router
        if not router:
            cprint("unreachable", 'red')
            return
        router.give((Packet(dst.ip, 'ping', src, dst)))

    @staticmethod
    def monitor(cmd: str):
        global monitor
        en = cmd.split()[1] == 'e'
        if en:
            monitor = True
        else:
            monitor = False

    @staticmethod
    def parse_command(cmd, normal_mode=True):
        if cmd.startswith('add') or cmd.startswith('dump') or cmd.startswith('load'):
            func = cmd.split()[0] + '_' + cmd.split()[1]
        else:
            func = cmd.split()[0]
        try:
            getattr(Functions, func).__call__(cmd)
            if normal_mode and not cmd.startswith("dump state"):
                commands.append(cmd)
            sleep(.1)
        except AttributeError:
            cprint("no function %s" % func, 'red')
        except Exception as e:
            print(e)
            print(traceback.print_exc())

    @staticmethod
    def dump_topology(cmd: str):
        try:
            path = cmd.split()[2]
        except IndexError:
            path = "topology.json"
        file = open(path, 'w')
        dump_data = nx.readwrite.adjacency_data(graph)
        # fixme: make objects serializable
        file.write(js.dumps(dump_data))
        file.close()

    @staticmethod
    def load_topology(cmd: str):
        global graph
        try:
            path = cmd.split()[2]
        except IndexError:
            path = "topology.json"
        file = open(path, 'r')
        data = js.loads(file.read())
        graph = nx.readwrite.adjacency_graph(data)
        # fixme initiate graph objects
        file.close()

    @staticmethod
    def dump_state(cmd: str):
        try:
            path = cmd.split()[2]
        except IndexError:
            path = "commands.json"
        file = open(path, 'w')
        file.write(js.dumps(commands))
        file.close()

    @staticmethod
    def load_state(cmd: str):
        global commands
        try:
            path = cmd.split()[2]
        except IndexError:
            path = "commands.json"
        file = open(path, 'r')
        commands = js.loads(file.read())
        cprint("loading state:", 'blue')
        for c in commands:
            cprint("> " + c, 'cyan')
            Functions.parse_command(c, normal_mode=False)
        file.close()

    @staticmethod
    def restart(cmd: str):
        global graph, commands, links, routers
        if input(colored("are you sure? [N/y]", 'magenta')) == 'y':
            commands = []
            links = []
            routers = []
            graph = nx.Graph()


if __name__ == '__main__':
    start_time = datetime.now()
    if not os.path.isdir("logs"):
        os.mkdir("logs")
    csv_file = open("logs/packets_log " + datetime.now().__str__() + ".csv", 'w')
    headers = ['time stamp', 'router', 'received packet?', 'sender', 'receiver', 'type', 'nbr?', 'lsdb?', 'message']
    writer = csv.DictWriter(csv_file, fieldnames=headers, extrasaction='ignore')
    writer.writeheader()

    try:
        completer = MyCompleter(
            ["sec ", "add ", "router ", "client ", "connect ", "link ", "ping ", "monitor e", "monitor d",
             "dump ", "load ", "topology", "state", "restart"])
        readline.set_completer(completer.complete)
        readline.parse_and_bind('tab: complete')

        while True:
            inp = input(colored(">>> ", 'green'))
            if inp != '':
                Functions.parse_command(inp)
    except KeyboardInterrupt:
        cprint('\nfinished.', 'cyan')
    except EOFError:
        cprint('\nfinished.', 'cyan')
    finally:
        csv_file.close()
