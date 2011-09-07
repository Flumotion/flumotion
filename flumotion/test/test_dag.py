# -*- Mode: Python; test-case-name: flumotion.test.test_dag -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

from flumotion.common import dag
from flumotion.common import testsuite


class TestDAG(testsuite.TestCase):

    def testSort(self):
        nodes = ['a', 'b',
                 'c', 'd',
                 'e', 'f']
        edges = [('a', 'f'),
                 ('a', 'd'),
                 ('f', 'e'),
                 ('e', 'c'),
                 ('d', 'b')]
        orderings = [['a', 'f', 'e', 'c'],
                     ['a', 'd', 'b']]
        sorted = dag.topological_sort(nodes, edges)

        for order in orderings:
            positions = [sorted.index(x) for x in order]
            positions_sorted = list(positions)
            positions_sorted.sort()
            self.failUnless(positions == positions_sorted)

    def testBible(self):
        graph = dag.DAG()

        # first line
        graph.addNode('adam')
        graph.addNode('eve')

        self.assertRaises(KeyError, graph.addNode, 'adam')
        self.assertRaises(KeyError, graph.removeNode, 'abraham')

        self.failUnless(graph.isFloating('adam'))

        # second line
        graph.addNode('cain')
        graph.addNode('abel')
        graph.addNode('seth')

        graph.addEdge('adam', 'cain')
        graph.addEdge('adam', 'abel')
        graph.addEdge('adam', 'seth')
        graph.addEdge('eve', 'cain')
        graph.addEdge('eve', 'abel')
        graph.addEdge('eve', 'seth')

        self.assertRaises(KeyError, graph.addEdge, 'adam', 'cain')
        self.assertRaises(KeyError, graph.addEdge, 'abraham', 'cain')

        self.failIf(graph.isFloating('adam'))
        self.failIf(graph.isFloating('abel'))

        c = graph.getChildren('adam')
        self.failUnless('cain' in c)
        self.failUnless('abel' in c)
        self.failUnless('seth' in c)

        c = graph.getChildren('abel')
        self.failIf(c)

        p = graph.getParents('cain')
        self.failUnless('adam' in p)
        self.failUnless('eve' in p)

        p = graph.getParents('adam')
        self.failIf(p)

        # create a cycle
        graph.addEdge('cain', 'adam')
        self.assertRaises(dag.CycleError, graph.sort)

        # remove cycle
        graph.removeEdge('cain', 'adam')

        # test offspring
        offspring = graph.getOffspring('adam')
        self.assertEquals(len(offspring), 3)
        self.failUnless('cain' in offspring)
        self.failUnless('abel' in offspring)
        self.failUnless('seth' in offspring)

        offspring = graph.getOffspring('cain')
        self.assertEquals(len(offspring), 0)

        # add third line
        graph.addNode('enoch')
        graph.addEdge('cain', 'enoch')

        graph.addNode('irad')
        graph.addEdge('enoch', 'irad')

        graph.addNode('enosh')
        graph.addEdge('seth', 'enosh')

        graph.addNode('kenan')
        graph.addEdge('enosh', 'kenan')

        offspring = graph.getOffspring('adam')
        self.assertEquals(len(offspring), 7)
        for n in ['abel', 'cain', 'enoch', 'irad', 'seth', 'enosh', 'kenan']:
            self.failUnless(n in offspring)

        offspring = graph.getOffspring('cain')
        self.assertEquals(len(offspring), 2)
        for n in ['enoch', 'irad']:
            self.failUnless(n in offspring)

        ancestors = graph.getAncestors('irad')
        self.assertEquals(len(ancestors), 4)
        for n in ['enoch', 'cain', 'adam', 'eve']:
            self.failUnless(n in ancestors)

    def testUniqueChildren(self):
        # test whether we get a list of unique children even through
        # common ancestry
        graph = dag.DAG()

        # first line
        graph.addNode('A')
        graph.addNode('B1')
        graph.addNode('B2')
        graph.addNode('B3')
        graph.addNode('C')

        graph.addEdge('A', 'B1')
        graph.addEdge('A', 'B2')
        graph.addEdge('A', 'B3')
        graph.addEdge('B1', 'C')
        graph.addEdge('B2', 'C')
        graph.addEdge('B3', 'C')

        offspring = graph.getOffspring('A')
        # make sure we have only one C and the three B's
        self.assertEquals(len(offspring), 4)

# example as shown in
# http://www.cs.cornell.edu/courses/cs312/2004fa/lectures/lecture15.htm

    def testExample(self):
        graph = dag.DAG()

        for i in range(1, 10):
            graph.addNode(i)

        graph.addEdge(1, 2)
        graph.addEdge(1, 4)
        graph.addEdge(2, 3)
        graph.addEdge(4, 3)
        graph.addEdge(4, 6)
        graph.addEdge(5, 8)
        graph.addEdge(6, 5)
        graph.addEdge(6, 8)
        graph.addEdge(9, 8)

        # check result of sort, using a preferred order chosen to match
        # the example
        # even though multiple answers are possible, the preferred order
        # makes sure we get the one result we want
        nodes = graph._sortPreferred([
            (1, 0), (2, 0), (3, 0), (4, 0),
            (5, 0), (6, 0), (9, 0), (8, 0),
            (7, 0)], clearState=False)
        sorted = [node.object for node in nodes]
        self.assertEquals(sorted, [7, 9, 1, 4, 6, 5, 8, 2, 3])

        # poke at internal counts to see if the algorithm was done right
        # reference begin and end value for each item - see example
        counts = [(1, 14), (2, 5), (3, 4), (6, 13), (8, 11), (7, 12),
                  (17, 18), (9, 10), (15, 16)]
        for i in range(1, 10):
            n = graph._nodes[(i, 0)]
            begin, end = counts[i - 1]
            self.failUnless(n in graph._begin,
                "n %r not in graph._begin %r" % (n, graph._begin))
            self.assertEquals(graph._begin[n], begin)
            self.assertEquals(graph._end[n], end)

        # add an edge that introduces a cycle
        graph.addEdge(5, 4)
        self.assertRaises(dag.CycleError, graph.sort)


class FakeDep:

    def __init__(self, name):
        self.name = name


class FakeFeeder(FakeDep):
    pass


class FakeEater(FakeDep):
    pass


class FakeWorker(FakeDep):
    pass


class FakeKid(FakeDep):
    pass


class FakeComponent(FakeDep):
    pass

(feeder, eater, worker, kid, component) = range(0, 5)


class TestPlanet(testsuite.TestCase):

    def testPlanet(self):
        graph = dag.DAG()

        weu = FakeWorker('europe')
        wus = FakeWorker('america')

        graph.addNode(weu, worker)
        graph.addNode(wus, worker)

        # producer
        kpr = FakeKid('producer')
        cpr = FakeComponent('producer')
        fau = FakeFeeder('audio')
        fvi = FakeFeeder('video')

        graph.addNode(kpr, kid)
        graph.addNode(cpr, component)
        graph.addNode(fau, feeder)
        graph.addNode(fvi, feeder)

        graph.addEdge(weu, kpr, worker, kid)
        graph.addEdge(kpr, fau, kid, feeder)
        graph.addEdge(kpr, fvi, kid, feeder)
        graph.addEdge(fau, cpr, feeder, component)
        graph.addEdge(fvi, cpr, feeder, component)

        kcv = FakeKid('converter')
        ccv = FakeComponent('converter')
        fen = FakeFeeder('encoded')
        evi = FakeEater('video')

        graph.addNode(kcv, kid)
        graph.addNode(ccv, component)
        graph.addNode(evi, eater)
        graph.addNode(fen, feeder)

        graph.addEdge(weu, kcv, worker, kid)
        graph.addEdge(kcv, fen, kid, feeder)
        graph.addEdge(kcv, evi, kid, eater)
        graph.addEdge(fen, ccv, feeder, component)
        graph.addEdge(evi, ccv, eater, component)

        # link from producer to converter
        graph.addEdge(fvi, evi, feeder, eater)

        # consumer
        kcs = FakeKid('consumer')
        ccs = FakeComponent('consumer')
        een = FakeEater('encoded')

        graph.addNode(kcs, kid)
        graph.addNode(ccs, component)
        graph.addNode(een, eater)

        graph.addEdge(wus, kcs, worker, kid)
        graph.addEdge(kcs, een, kid, eater)
        graph.addEdge(een, ccs, eater, component)

        # link from converter to consumer
        graph.addEdge(fen, een, feeder, eater)
        # tester
        kte = FakeKid('tester')
        cte = FakeComponent('tester')

        graph.addNode(kte, kid)
        graph.addNode(cte, component)

        graph.addEdge(ccs, cte, component, component)

        # test offspring filtered

        # all components depend on the european worker
        list = graph.getOffspringTyped(weu, worker, component)
        self.assertEquals(len(list), 4)
        for c in [(cpr, component), (ccv, component),
                  (ccs, component), (cte, component)]:
            self.failUnless(c in list)

        # only streamer and tester depend on the us worker
        list = graph.getOffspringTyped(wus, worker, component)
        self.assertEquals(len(list), 2)
        for c in [(ccs, component), (cte, component)]:
            self.failUnless(c in list)
