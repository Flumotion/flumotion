# -*- Mode: Python; test-case-name: flumotion.test.test_dag -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

"""directed acyclic graph implementation.
Directed Acyclic Graph class and functionality
"""
from flumotion.common import log

__version__ = "$Rev$"


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

class DAG(log.Loggable):
    """
    I represent a Directed Acyclic Graph.

    You can add objects to me as Nodes and then express dependency by
    adding edges.
    """
    def __init__(self):
        self._nodes = {} # map of (object, type) -> NodeX
        self._tainted = False # True after add/remove and no cycle check done

        # topological sort stuff
        self._count = 0
        self._begin = {} # node -> begin count
        self._end = {} # node -> end count
        self._hasZeroEnd = [] # list of nodes that have end set to zero

    def _assertExists(self, object, type=0):
        if not self.hasNode(object, type):
            raise KeyError("No node for object %r, type %r" % (object, type))

    def addNode(self, object, type=0):
        """
        I add a node to the DAG.

        @param object: object to put in the DAG
        @param type:   optional type for the object
        """
        if self.hasNode(object, type):
            raise KeyError("Node for %r already exists with type %r" % (
                object, type))

        n = Node(object, type)
        self._nodes[(object, type)] = n

    def hasNode(self, object, type=0):
        """
        I check if a node exists in the DAG.

        @param object: The object to check existence of.
        @param type: An optional type for the object to check.
        @type type: Integer

        @rtype: Boolean
        """
        if (object, type) in self._nodes.keys():
            return True
        return False

    def removeNode(self, object, type=0):
        """
        I remove a node that exists in the DAG.  I also remove any edges
        pointing to this node.

        @param object: The object to remove.
        @param type: The type of object to remove (optional).
        """
        if not self.hasNode(object, type):
            raise KeyError("Node for %r with type %r does not exist" % (
                object, type))
        node = self._getNode(object, type)
        self.debug("Removing node (%r, %r)" % (object, type))
        # go through all the nodes and remove edges that end in this node
        for somenodeobj, somenodetype in self._nodes:
            somenode = self._nodes[(somenodeobj, somenodetype)]
            if node in somenode.children:
                self.removeEdge(somenodeobj, object, somenodetype, type)

        del self._nodes[(object, type)]

    def _getNode(self, object, type=0):
        value = self._nodes[(object, type)]
        return value


    def addEdge(self, parent, child, parenttype=0, childtype=0):
        """
        I add an edge between two nodes in the DAG.

        @param parent: The object that is to be the parent.
        @param child: The object that is to be the child.
        @param parenttype: The type of the parent object (optional).
        @param childtype: The type of the child object (optional).
        """
        self._assertExists(parent, parenttype)
        self._assertExists(child, childtype)
        np = self._getNode(parent, parenttype)
        nc = self._getNode(child, childtype)

        if nc in np.children:
            raise KeyError(
                "%r of type %r is already a child of %r of type %r" % (
                    child, childtype, parent, parenttype))

        self._tainted = True
        np.children.append(nc)
        nc.parents.append(np)

    def removeEdge(self, parent, child, parenttype=0, childtype=0):
        """
        I remove an edge between two nodes in the DAG.

        @param parent: The object that is the parent,
        @param child: The object that is the child.
        @param parenttype: The type of the parent object (optional).
        @param childtype: The type of the child object (optional).
        """
        self._assertExists(parent, parenttype)
        self._assertExists(child, childtype)
        np = self._nodes[(parent, parenttype)]
        nc = self._nodes[(child, childtype)]

        if nc not in np.children:
            raise KeyError("%r is not a child of %r" % (child, parent))
        self.debug("Removing edge (%r ,%r) -> (%r, %r)" % (parent, parenttype,
            child, childtype))
        self._tainted = True
        np.children.remove(nc)
        self.log("Children now: %r" % np.children)
        nc.parents.remove(np)

    def getChildrenTyped(self, object, objtype=0, types=None):
        """
        I return a list of (object, type) tuples that are direct children of
        this object,objtype.

        @param  object:  object to return children of
        @param  objtype: type of object (optional)
        @param  types:   a list of types of children that you want.
                         None means all.
        @type   types:   list

        @rtype: list of (object, object)
        """
        self._assertExists(object, objtype)
        node = self._getNode(object, objtype)

        l = node.children
        if types:
            l = [n for n in l if n.type in types]

        return [(n.object, n.type) for n in l]

    def getChildren(self, object, objtype=0, types=None):
        """
        I return a list of objects that are direct children of this
        object,objtype.

        @param object: object to return children of.
        @param objtype: type of object (optional).
        @type objtype: Integer
        @param types: a list of types of children that you want.
            None means all.
        @type types: list of Integers

        @rtype: list of objects
        """
        typedchildren = self.getChildrenTyped(object, objtype, types)

        ret = [n[0] for n in typedchildren]
        return ret

    def getParentsTyped(self, object, objtype=0, types=None):
        """
        I return a list of (object, type) tuples that are direct parents of
        this object, objtype.

        @param object:  object to return parents of
        @param objtype: type of object (optional)
        @param types:   A list of types of parents that you want.
                        None means all.
        @type  types:   list or None

        @rtype: list of (object, object)
        """
        self._assertExists(object, objtype)
        node = self._getNode(object, objtype)

        l = node.parents
        if types:
            l = [n for n in l if n.type in types]

        return [(n.object, n.type) for n in l]

    def getParents(self, object, objtype=0, types=None):
        """
        I return a list of objects that are direct parents of this
        object, objtype.

        @param object:  object to return parents of.
        @param objtype: type of object (optional)
        @param types:   List of types of parents that you want. None means all.
        @type  types:   list

        @rtype: list of (object, object)
        """
        typedparents = self.getParentsTyped(object, objtype, types)
        ret = [n[0] for n in typedparents]
        return ret


    def getOffspringTyped(self, object, objtype=0, *types):
        """
        I return a list of (object, type) tuples that are offspring of
        this object,objtype.

        @param object: object to return children of.
        @param objtype: type of object (optional).
        @type objtype: Integer
        @param types: a list of types of children that you want.
            None means all.
        @type types: list of Integers

        @rtype: list of (object,Integer)
        """
        self._assertExists(object, objtype)
        node = self._getNode(object, objtype)
        self.log("Getting offspring for (%r, %r)" % (object, objtype))
        # if we don't have children, don't bother trying
        if not node.children:
            self.log("Returning nothing")
            return []

        # catches CycleError as well
        sortedNodes = self._sortPreferred()

        # start by adding our node to our to be expanded list
        nodeList = [node]
        offspring = []
        expand = True
        # as long as we need to expand, loop over all offspring ...
        while expand:
            expand = False
            for n in nodeList:
                if n.children:
                    # .. and for every item add all of its children
                    # which triggers requiring further expansion
                    expand = True
                    nodeList.remove(n)
                    nodeList.extend(n.children)
                    offspring.extend(n.children)

        # filter offspring by types
        if types:
            offspring = [n for n in offspring if n.type in types]

        # now that we have all offspring, return a sorted list of them
        ret = []
        for n in sortedNodes:
            if n in offspring:
                ret.append((n.object, n.type))

        for node in ret:
            self.log("Offspring: (%r, %r)" % (node[0], node[1]))
        return ret

    def getOffspring(self, object, objtype=0, *types):
        """
        I return a list of objects that are offspring of this
        object,objtype.

        @param object: object to return children of.
        @param objtype: type of object (optional).
        @type objtype: Integer
        @param types: types of children that you want offspring returned of.

        @rtype: list of objects
        """

        typedoffspring = self.getOffspringTyped(object, objtype, *types)

        ret = []
        ret = [n[0] for n in typedoffspring]

        return ret


    def getAncestorsTyped(self, object, objtype=0, *types):
        """
        I return a list of (object, type) tuples that are ancestors of
        this object,objtype.

        @param object: object to return ancestors of.
        @param objtype: type of object (optional).
        @type objtype: Integer
        @param types: types of ancestors that you want ancestors of.

        @rtype: list of (object,Integer)
        """
        self._assertExists(object, objtype)
        node = self._getNode(object, objtype)

        # if we don't have children, don't bother trying
        if not node.parents:
            return []

        # catches CycleError as well
        sortedNodes = self._sortPreferred()

        # start by adding our node to our to be expanded list
        nodeList = [node]
        ancestors = []
        expand = True
        # as long as we need to expand, loop over all offspring ...
        while expand:
            expand = False
            for n in nodeList:
                if n.parents:
                    # .. and for every item add all of its children
                    # which triggers requiring further expansion
                    expand = True
                    nodeList.remove(n)
                    nodeList.extend(n.parents)
                    ancestors.extend(n.parents)

        # filter offspring by types
        if types:
            ancestors = [n for n in ancestors if n.type in types]

        # now that we have all offspring, return a sorted list of them
        ret = []
        for n in sortedNodes:
            if n in ancestors:
                ret.append((n.object, n.type))

        return ret

    def getAncestors(self, object, objtype=0, *types):
        """
        I return a list of objects that are ancestors of this object,objtype.

        @param object: object to return ancestors of.
        @param objtype: type of object (optional).
        @type objtype: Integer
        @param types: types of ancestors that you want returned.

        @rtype: list of objects
        """
        typedancestors = self.getAncestorsTyped(object, objtype, *types)

        ret = []
        ret = [n[0] for n in typedancestors]

        return ret


    def isFloating(self, object, objtype=0):
        """
        I return whether the object is floating: no parents and no children.

        @param object: object to check if floating.
        @param objtype: type of object (optional).
        @type objtype: Integer

        @rtype: Boolean
        """
        self._assertExists(object, objtype)
        node = self._getNode(object, objtype)

        return node.isFloating()

    def hasCycle(self):
        """
        I return whether or not the graph has a cycle.

        If it has, some operations on it will fail and raise CycleError.
        """
        self._sortPreferred()

    def sort(self):
        """
        I return a topologically sorted list of objects.

        @rtype: list of (object, type)
        """
        return [(node.object, node.type) for node in self._sortPreferred()]

    def _sortPreferred(self, list=None, clearState=True):
        """
        I return a topologically sorted list of nodes, using list as a
        preferred order for the algorithm.

        @param list: a list of (object, type) tuples in preference order
        @type list: list of (object, type)

        @rtype: list of {Node}
        """
        self._count = 0
        for n in self._nodes.values():
            self._begin[n] = 0
            self._end[n] = 0
            if list:
                assert (n.object, n.type) in list
        if list:
            self._hasZeroEnd = [self._nodes[(n[0], n[1])] for n in list]
        else:
            self._hasZeroEnd = self._nodes.values()

        while self._hasZeroEnd:
            node = self._hasZeroEnd[0]
            self._dfs(node)

        # get a list of dictionary keys sorted in decreasing value order
        l = []
        for node, count in self._end.items():
            l.append([count, node])

        l.sort()
        l.reverse()
        if clearState:
            self._begin = {}
            self._end = {}
            self._hasZeroEnd = []
        return [node for count, node in l]

    def _dfs(self, node):
        # perform depth first search

        self._count += 1

        self._begin[node] = self._count

        # 2.3
        # 2.3.b: detect cycle
        nodes = [n for n in node.children
                       if self._begin[n] > 0 and self._end[n] == 0]
        if nodes:
            raise CycleError('nodes %r' % nodes)

        # 2.3.a: perform dfs
        # don't get a list of zerobegins first; do it step by step

        for n in node.children:
            if self._begin[n] > 0:
                continue
            self._dfs(n)

        self._count += 1
        self._end[node] = self._count
        if node in self._hasZeroEnd:
            self._hasZeroEnd.remove(node)

    def getAllNodesByType(self, type):
        """
        I return all the objects with node type specified by type

        @rtype: list of object
        """
        ret = []
        for node in self._nodes.keys():
            if node[1] == type:
                ret.append(self._nodes[node].object)

        return ret


def topological_sort(items, partial_order):
    """
    Perform topological sort.

    @param items: list of items
    @param partial_order: list of pairs. If pair (a,b) is in it, it
    means that item a should appear before item b.
    @returns: list of the items in one of the possible orders. Raises
    DAG.CycleError if partial_order contains a loop.
    """

    graph = DAG()
    for v in items:
        graph.addNode(v)
    for a, b in partial_order:
        graph.addEdge(a, b)

    return [v for v, t in graph.sort()]
