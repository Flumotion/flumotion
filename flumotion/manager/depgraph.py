# -*- Mode: Python; test-case-name: flumotion.test.test_manager_depgraph -*-
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

"""
A dependency graph for the manager.

The purpose of this code is to make sure that the multi-stage component
start process proceeds in order, and that components do not start before
their clock master (if any).

The strategy used by the code is to model each dependency as a node in
the graph, with a boolean state, and a callable to attempt to make that
state true.

When a node changes its state to False, all offspring (children,
childrens' children, etc) of that node are marked as False.[1]

When a node changes its state to True, all children (the direct
dependencies only) are examined to see if they can "start". A node can
start when all nodes that it depends on are True, and if the node itself
is False. In that case, the node's callable is called, which is code
external to this file that should attempt to make that node True.

For example, DepGraph.addClockMaster() marks a component as being a
clock master, with a callable to start that component's clock. All
components with that clock master will be marked as children of the
master component's "CLOCKMASTER" node, which in turn is a child of the
master component's "COMPONENTSETUP" node. So when the master component
has been set up ("COMPONENTSETUP" == True), the setupClockMasterCallable
will be called, which at some point will mark "CLOCKMASTER" == True,
which will allow other components to be started.

Components also are marked as depending on the components that feed
them.[2]

In reality, the only interesting feature of the depgraph is the
clockmaster dependency, because otherwise a deferred from calling
setup() could be directly chained to start() in all cases[3].

[1] It is unclear if this recursive behavior is actually what you want.
Specifically, if a worker pings out, it doesn't mean that the component
will go away, or that you should do anything different.

[2] This is BS, and will be changed soon (accompanied with comments).

[3] This only really works in the case in which all components have been
added to the depgraph, then the clock master is marked, and no more
components are added to the depgraph. Also, all components must have
been added to the depgraph. There are numerous places in
flumotion/manager files that do not complete these requirements. Perhaps
if the clock master strategy were changed, then this entire file would
be unnecessary; it seems to introduce concepts needlessly, causing
needless complexity and brittleness.
"""

from flumotion.common import dag, log, registry, errors, common
from flumotion.common.planet import moods

class DepGraph(log.Loggable):
    """
    I am a dependency graph for components.  I also maintain boolean state
    for each of the nodes.

    I contain a DAG to help with resolving dependencies.
    """
    logCategory = "depgraph"
    
    typeNames = ("WORKER", "JOB", "COMPONENTSETUP", "CLOCKMASTER",
        "COMPONENTSTART")

    def __init__(self):
        # Each node in the DAG is an object (and has a given type, corresponding
        # to some action that must be taken to progress through the DAG). The
        # objects are states - componentState, jobState, workerState.
        self._dag = dag.DAG()

        # (object,type) -> (callable, boolean) mapping. 
        # The boolean is true if the action needed at this node has completed.
        # The callable should take some action to (eventually) set the state to
        # True so we can progress further through the depgraph.
        self._state = {}

    def _addNode(self, component, type, callable):
        # type: str
        self.debug("Adding node %r of type %s" % (component, type))
        self._dag.addNode(component, type)
        self._state[(component, type)] = (callable, False)

    def _removeNode(self, component, type):
        self.debug("Removing node %r of type %s" % (component, type))
        self._dag.removeNode(component, type)

    def _addEdge(self, parent, child, parentType, childType):
        self.debug("Adding edge %r of type %s to %r of type %s" % (
            parent, parentType, child, childType))
        self._dag.addEdge(parent, child, parentType, childType)

    def _removeEdge(self, parent, child, parentType, childType):
        self.debug("Removing edge %r of type %s to %r of type %s" % (
            parent, parentType, child, childType))
        self._dag.removeEdge(parent, child, parentType, childType)

    def addClockMaster(self, component, setupClockMasterCallable):
        """
        I set a component to be the clock master in the dependency
        graph.  This component must have already been added to the
        dependency graph.

        @param component: the component to set as the clock master
        @type  component: L{flumotion.manager.component.ComponentAvatar}
        """
        if self._dag.hasNode(component, "JOB"):
            self._addNode(component, "CLOCKMASTER", setupClockMasterCallable)
            self._addEdge(component, component, "COMPONENTSETUP",
                "CLOCKMASTER")
        
            # now go through all the component starts and make them dep on the
            # clock master
            startnodes = self._dag.getAllNodesByType("COMPONENTSTART")
            for start in startnodes:
                # only add if they share the same parent flow
                if start.get('parent') == component.get('parent'):
                    self._addEdge(component, start, "CLOCKMASTER", 
                        "COMPONENTSTART")
        else:
            raise KeyError("Component %r has not been added" % component)

    def addComponent(self, component, setupCallable, startCallable):
        """
        I add a component to the dependency graph.
        This includes adding the worker (if not already added), the job,
        the feeders and the eaters.

        Requirement: worker must already be assigned to component

        @param component: component object to add
        @type  component: L{flumotion.common.planet.ManagerComponentState}
        """
        if self._dag.hasNode(component, "JOB"):
            self.debug('component %r already in depgraph, ignoring',
                       component)
            return
        
        self.debug('adding component %r to depgraph' % component)
        # Starting jobs is handled elsewhere, not by the depgraph, so we don't
        # need a function to do anything in particular.
        self._addNode(component, "JOB", lambda x: None)
        self._addNode(component, "COMPONENTSTART", startCallable)
        self._addNode(component, "COMPONENTSETUP", setupCallable)
        self._addEdge(component, component, "JOB", "COMPONENTSETUP")
        workername = component.get('workerRequested')
        if workername:
            self.addWorker(workername)
            self.setComponentWorker(component, workername)
        self._addEdge(component, component, "COMPONENTSETUP", 
            "COMPONENTSTART")

    def addWorker(self, worker):
        """
        I add a worker to the dependency graph.

        @param worker: the worker to add
        @type  worker: str
        """
        self.debug('adding worker %s' % worker)
        if not self._dag.hasNode(worker, "WORKER"):
            # Workers only get started explicitly externally to the manager.
            # So we don't need a function here.
            self._addNode(worker, "WORKER", lambda x: None)

    def removeComponent(self, component):
        """
        I remove a component in the dependency graph, this includes removing
        the JOB, COMPONENTSETUP, COMPONENTSTART, CLOCKMASTER.

        @param component: the component to remove
        @type component:  L{flumotion.manager.component.ComponentAvatar}
        """
        self.debug('removing component %r from depgraph' % component)
        for type in self.typeNames:
            if self._dag.hasNode(component, type):
                self._removeNode(component, type)
                del self._state[(component, type)]

    def removeWorker(self, worker):
        """
        I remove a worker from the dependency graph.

        @param worker: the worker to remove
        @type  worker: str
        """
        self.debug('removing worker %s' % worker)
        if self._dag.hasNode(worker, "WORKER"):
            self._dag.removeNode(worker, "WORKER")
            del self._state[(worker, "WORKER")]

    def setComponentWorker(self, component, worker):
        """
        I assign a component to a specific worker.

        @param component: the component
        @type  component: L{flumotion.common.planet.ManagerComponentState}
        @param worker:    the worker to set it to
        @type  worker:    str
        """
        if self._dag.hasNode(worker, "WORKER") and (
            self._dag.hasNode(component, "JOB")):
            self._addEdge(worker, component, "WORKER", "JOB")
        else:
            raise KeyError("Worker %s or Component %r not in dependency graph" %
                (worker, component))

    # TODO: This is nasty: it goes and touches anything in the graph, not just
    # the newly added things. Unfortunately, we don't enforce adding things in
    # the right order, so doing it correctly otherwise looks hard.
    def mapEatersToFeeders(self):
        """
        I am called once a piece of configuration has been added,
        so I can add edges to the DAG for each feed from the
        feeding component to the eating component.

        @raise errors.ComponentConfigError: if a component is
                                            misconfigured and eats from
                                            a non-existant component
        """
        toSetup = self._dag.getAllNodesByType("COMPONENTSETUP")
        
        for eatingComponent in toSetup:
            # for this component setup, go through all the feeders in it
            config = eatingComponent.get('config')

            if not config.has_key('eater'):
                # no eaters
                self.debug("Component %r has no eaters" % eatingComponent)
            else:
                # eater is a dict of eaterName -> list of componentName[:feedName]
                # with feedName defaulting to default
                eaters = config['eater']

                for eater in eaters:
                    for feed, alias in eaters[eater]:
                        feederFound = False
                        feederComponentName = feed.split(':')[0]
                        # find the feeder
                        for feedingComponent in toSetup:
                            if feedingComponent.get("name") == feederComponentName:
                                feederFound = True
                                try:
                                    self._addEdge(feedingComponent, eatingComponent,
                                        "COMPONENTSETUP", "COMPONENTSETUP")
                                except KeyError:
                                    # it is possible for a component to have
                                    # two eaters, each eating from feeders on
                                    # one other component
                                    pass
                                try:
                                    self._addEdge(feedingComponent, eatingComponent,
                                        "COMPONENTSTART", "COMPONENTSTART")
                                except KeyError:
                                    pass

                        if not feederFound:
                            raise errors.ComponentConfigError(eatingComponent,
                                "No feeder exists feeding %s to eater"
                                " %s on component %s" % (
                                feed, eater, eatingComponent))

    def _setState(self, object, type, value):
        self.doLog(log.DEBUG, -2, "Setting state of (%r, %s) to %d" % (
            object, type, value))
        (callable, oldstate) = self._state[(object,type)]
        self._state[(object,type)] = (callable, value)

        # if making state False, should make its offspring False
        # if the object is the same
        if not value:
            self.debug("Setting state of all (%r, %s)'s offspring to %d" %
                (object, type, value))
            offspring = self._dag.getOffspringTyped(object, type)
            for kid in offspring:
                self.debug("Setting state of offspring (%r) to %d", kid, value)
                if kid[0] == object:
                    (callable, oldstate) = self._state[kid]
                    self._state[kid] = (callable, False)
        else:
            # We set this to true. So perhaps we can progress!
            kids = self._dag.getChildrenTyped(object, type)
            for (kid, kidtype) in kids:
                # Skip this for things already True.
                if self._state[(kid,kidtype)][1]:
                    continue
                # For each of these we need to check that ALL the parents are
                # now true before we can go further
                if reduce(lambda x,y: x and self._state[y][1], 
                        self._dag.getParentsTyped(kid, kidtype), True):
                    self.debug("Calling callable %r", 
                        self._state[(kid, kidtype)][0])
                    self._state[(kid,kidtype)][0](kid)

    def setComponentStarted(self, component):
        """
        Set a COMPONENTSTART node to have state of True

        @param component: the component to set COMPONENTSTART to True for
        @type  component: L{flumotion.common.planet.ManagerComponentState}
        """
        self._setState(component, "COMPONENTSTART", True)

    def setComponentNotStarted(self, component):
        """
        Set a COMPONENTSTART node to have state of False

        @param component: the component to set COMPONENTSTART to False for
        @type  component: L{flumotion.common.planet.ManagerComponentState}
        """

        self._setState(component, "COMPONENTSTART", False)

    def setComponentSetup(self, component):
        """
        Set a COMPONENTSETUP node to have state of True

        @param component: the component to set COMPONENTSETUP to True for
        @type  component: L{flumotion.common.planet.ManagerComponentState}
        """

        self._setState(component, "COMPONENTSETUP", True)

    def setComponentNotSetup(self, component):
        """
        Set a COMPONENTSETUP node to have state of False

        @param component: the component to set COMPONENTSETUP to True for
        @type  component: L{flumotion.common.planet.ManagerComponentState}
        """

        self._setState(component, "COMPONENTSETUP", False)


    def setJobStarted(self, component):
        """
        Set a JOB node to have state of True

        @param component: the component to set JOB to True for
        @type  component: L{flumotion.common.planet.ManagerComponentState}
        """
        self._setState(component, "JOB", True)

    def setJobStopped(self, component):
        """
        Set a JOB node to have state of False

        @param component: the component to set JOB to False for
        @type  component: L{flumotion.common.planet.ManagerComponentState}
        """
        self.doLog(log.DEBUG, -2, "Setting component's job %r to FALSE" %
            component)
        self._setState(component, "JOB", False)

    def setWorkerStarted(self, worker):
        """
        Set a WORKER node to have state of True

        @param worker: the component to set WORKER to True for
        @type  worker: str
        """
        self._setState(worker, "WORKER", True)

    def setWorkerStopped(self, worker):
        """
        Set a WORKER node to have state of False

        @param worker: the component to set WORKER to False for
        @type  worker: str
        """
        self._setState(worker, "WORKER", False)
    
    def setClockMasterStarted(self, component):
        """
        Set a CLOCKMASTER node to have state of True

        @param component: the component to set CLOCKMASTER to True for
        @type  component: {flumotion.common.planet.ManagerComponentState}
        """
        self._setState(component, "CLOCKMASTER", True)

    def setClockMasterStopped(self, component):
        """
        Set a CLOCKMASTER node to have state of False

        @param component: the component to set CLOCKMASTER to True for
        @type  component: {flumotion.common.planet.ManagerComponentState}
        """
        self._setState(component, "CLOCKMASTER", False)

    def isAClockMaster(self, component):
        """
        Checks if component has a CLOCKMASTER node

        @param component: the component to check if CLOCKMASTER node exists
        @type component: {flumotion.common.planet.ManagerComponentState}
        """
        return self._dag.hasNode(component, "CLOCKMASTER")
