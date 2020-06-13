import simulator

from time import sleep
from termcolor import cprint
from random import choice, randint, choices
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


def apply_pings(pings):
    for p in pings:
        do(p)


if __name__ == '__main__':
    nn, ne, nc, bwm, bwM, n_ping = 10, 15, 10, 10, 20, 50
    r_nodes, r_edges, r_clients = random_topology(nn, ne, nc, bwm, bwM)
    apply_topology(r_nodes, r_edges, r_clients)
    r_pings = random_pings(r_clients, n_ping)
    apply_pings(r_pings)
    do("dump log 1 0 1")
    do("dump topology")
    do("dump graph")
