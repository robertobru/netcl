import networkx as nx
G = nx.MultiGraph([(1, 2), (1, 2), (2, 3), (3, 4)])

for e in G.edges(data=True):
    print(type(e))
