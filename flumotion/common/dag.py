# -*- Mode: Python; test-case-name: flumotion.test.test_dag -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.GPL" in the source distribution for more information.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

"""
Direct Acyclic Graph class and functionality
"""

class CycleError(Exception):
    """
    A cycle was detected during execution of a function.
    """

class Node:
    """
    I represent a Node in a Graph.

    I am private to the Graph.
    """
    def __init__(self, object, type=0):
        self.object = object
        self.type = type
        self.parents = []   # FIXME: could be weakrefs to avoid cycles ?
        self.children = []

    def isFloating(self):
        """
        Returns whether the node is floating: no parents and no children.
        """
        count = len(self.children) + len(self.parents)
        if count:
            return False

        return True

class DAG:
    """
    I represent a Direct Acyclic Graph.

    You can add objects to me as Nodes and then express dependency by
    adding edges.
    """
    def __init__(self):
        self.nodes = {} # map of object -> Node
        self._tainted = False # True after add/remove and no cycle check done

        # topological sort stuff
        self._count = 0
        self._begin = {} # node -> begin count
        self._end = {} # node -> end count
        self._hasZeroEnd = [] # list of nodes that have end set to zero

    def _assertExists(self, object):
        if not self.hasObject(object):
            raise KeyError("No node for %r" % object)

    def addNode(self, object, type=0):
        if self.hasObject(object):
            raise KeyError("Node for %r already exists" % object)

        n = Node(object, type)
        self.nodes[object] = n

    def hasObject(self, object):
        return object in self.nodes.keys()

    def removeNode(self, object):
        if not self.hasObject(object):
            raise KeyError("Node for %r does not exist" % object)

        # FIXME: implement
        pass
    
    def addEdge(self, parent, child):
        self._assertExists(parent)
        self._assertExists(child)
        np = self.nodes[parent]
        nc = self.nodes[child]
        
        if nc in np.children:
            raise KeyError("%r is already a child of %r" % (child, parent))

        self._tainted = True
        np.children.append(nc)
        nc.parents.append(np)

    def removeEdge(self, parent, child):
        self._assertExists(parent)
        self._assertExists(child)
        np = self.nodes[parent]
        nc = self.nodes[child]
        
        if nc not in np.children:
            raise KeyError("%r is not a child of %r" % (child, parent))

        self._tainted = True
        np.children.remove(nc)
        nc.parents.remove(np)

    def getChildren(self, object, types=None):
        """
        Return a list of objects that are direct children of this object.

        @rtype: list of object
        """
        self._assertExists(object)
        node = self.nodes[object]

        l = node.children
        if types:
            l = filter(lambda n: n.type in types, l)

        return [n.object for n in l]

    def getParents(self, object, types=None):
        self._assertExists(object)
        node = self.nodes[object]
        
        l = node.parents
        if types:
            l = filter(lambda n: n.type in types, l)

        return [n.object for n in l]
        
    def getOffspring(self, object, *types):
        self._assertExists(object)
        node = self.nodes[object]

        # if we don't have children, don't bother trying
        if not node.children:
            return []

        # catches CycleError as well
        sorted = self._sortPreferred()

        # start by adding our node to our to be expanded list
        list = [node]
        offspring = []
        expand = True
        # as long as we need to expand, loop over all offspring ...
        while expand:
            expand = False
            for n in list:
                if n.children:
                    # .. and for every item add all of its children
                    # which triggers requiring further expansion
                    expand = True
                    list.remove(n)
                    list.extend(n.children)
                    offspring.extend(n.children)

        # filter offspring by types
        if types:
            offspring = filter(lambda n: n.type in types, offspring)

        # now that we have all offspring, return a sorted list of them
        ret = []
        for n in sorted:
            if n in offspring:
                ret.append(n.object)

        return ret

    def getAncestors(self, object):
        pass

    def isFloating(self, object):
        """
        Returns whether the object is floating: no parents and no children.
        """
        self._assertExists(object)
        node = self.nodes[object]

        return node.isFloating()

    def hasCycle(self):
        """
        Returns whether or not the graph has a cycle.

        If it has, some operations on it will fail and raise CycleError.
        """
        self._sortPreferred()

    def sort(self):
        """
        Return a topologically sorted list of objects.

        @rtype: list of object
        """
        return [node.object for node in self._sortPreferred()]
        
    def _sortPreferred(self, list=None):
        """
        Return a topologically sorted list of nodes, using list as a
        preferred order for the algorithm.

        @rtype: list of L{Node}
        """

        self._count = 0
        for n in self.nodes.values():
            self._begin[n] = 0
            self._end[n] = 0
            if list: assert n.object in list
        if list:
            self._hasZeroEnd = [self.nodes[object] for object in list]
        else:
            self._hasZeroEnd = self.nodes.values()

        while self._hasZeroEnd:
            node = self._hasZeroEnd[0]
            #print "working on node %r for object %r" % (node, node.object)
            self._dfs(node)

        # get a list of dictionary keys sorted in decreasing value order
        l = []
        for node, count in self._end.items():
            l.append([count, node])

        l.sort()
        l.reverse()
        return [node for count, node in l]

    def _dfs(self, node):
        # perform depth first search

        #print "doing _dfs for object %r" % node.object
        self._count += 1
        
        self._begin[node] = self._count
        
        # 2.3
        # 2.3.b: detect cycle
        hasCycle = lambda n: self._begin[n] > 0 and self._end[n] == 0
        nodes = filter(hasCycle, node.children)
        if nodes:
            raise CycleError('nodes %r' % nodes)
            
        # 2.3.a: perform dfs
        # don't get a list of zerobegins first; do it step by step

        for n in node.children:
            if self._begin[n] > 0:
                continue
            #print "calling _dfs for object %r because beginzero" % n.object
            self._dfs(n)
            #print "called _dfs for object %r" % n.object
            
        self._count += 1
        self._end[node] = self._count
        if node in self._hasZeroEnd:
            #print "removing for object %r" % node.object
            self._hasZeroEnd.remove(node)

        #print "done _dfs for object %r" % node.object

