import simulator

from time import sleep
from threading import Thread
from termcolor import cprint
from random import choice, randint, choices, random
from ipaddress import IPv4Address as ip


def do(cmd):
    simulator.Functions.parse_command(cmd)
    sleep(.01)


def random_topology(n: int, e: int, c: int, bw_min=1, bw_max=10):
    nodes = []
    edges = []
    clients = []
    if n < 1:
        cprint("number of nodes should be bigger than 1", 'red')
    elif e < n - 1:
        cprint("number of edges should be bigger than #nodes - 1", 'red')
    elif e > n * (n-1) / 2:
        cprint("number of edges should be smaller", 'red')
    else:
        nodes = [0]
        candidate_edges = [(i, j) for i in range(n) for j in range(i+1, n)]
        for i in range(1, n):
            edge = (i, choice(nodes))
            nodes.append(i)
            edges.append(edge + (randint(bw_min, bw_max),))
            try:
                candidate_edges.remove(edge)
            except ValueError:
                candidate_edges.remove((edge[1], edge[0]))
        for _ in range(e - n + 1):
            edge = choice(candidate_edges)
            candidate_edges.remove(edge)
            edges.append(edge + (randint(bw_min, bw_max),))
        for i in range(c):
            clients.append((str(ip(0) + i), choice(nodes), randint(bw_min, bw_max)))
    return nodes, edges, clients


def apply_topology(nodes, edges, clients):
    for n in nodes:
        do("add router " + str(n))
    for s1, s2, w in edges:
        do("connect %d %d %d" % (s1, s2, w))
    for c, r, w in clients:
        do("add client %s" % c)
        do("connect %s %d %d" % (c, r, w))


def random_pings(clients, ping_no=1):
    if len(clients) == 0:
        return []
    return ["ping %s %s" % tuple(map(lambda q: q[0], choices(clients, k=2))) for _ in range(ping_no)]


disabled_links = []


def apply_pings(pings, edges):
    for p in pings:
        Thread(target=do, args=(p,)).start()
        rnd = random()
        if rnd < 0.02:
            s1, s2, _ = choice(edges)
            # do("link %d %d d" % (s1, s2))
            Thread(target=do, args=("link %d %d d" % (s1, s2),)).start()
            disabled_links.append((s1, s2))
        elif rnd < 0.4:
            Thread(target=do, args=("sec 1",)).start()
            # do("sec 1")

        elif rnd > (1 - 0.005 * len(disabled_links)):
            s1, s2 = choice(disabled_links)
            # do("link %d %d e" % (s1, s2))
            Thread(target=do, args=("link %d %d e" % (s1, s2),)).start()
            disabled_links.remove((s1, s2))


if __name__ == '__main__':
    nn, ne, nc, bwm, bwM, n_ping = 8, 10, 10, 10, 20, 100

    r_nodes, r_edges, r_clients = random_topology(nn, ne, nc, bwm, bwM)
    apply_topology(r_nodes, r_edges, r_clients)
    do("dump graph logs/graph.png")
    do("dump topology logs/topology.txt")
    for r in range(20):
        r_pings = random_pings(r_clients, n_ping)
        for i in range(50):
            print("iteration no. %d:%d" % (r, i))
            apply_pings(r_pings, r_edges)
            sleep(0.5)
            do("restart time")
    do("accumulate_all logs/cumulative_count.csv")
    do("dump log 1 0 1")

