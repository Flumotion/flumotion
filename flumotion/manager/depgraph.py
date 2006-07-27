# -*- Mode: Python; test-case-name: flumotion.test.test_manager_depgraph -*-
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

from flumotion.common import dag, log, registry
from flumotion.common.planet import moods

import string

class Feeder:
    """
    I am an object representing a feeder in the DepGraph
    """
    def __init__(self, feederName, component):
        self.feederName = feederName
        self.component = component
        self.feederData = None
        
class Eater:
    """
    I am an object representing an eater in the DepGraph
    """
    def __init__(self, eaterName, component):
        # feeder attribute is a reference to the Feeder object
        # that this eater eats from
        self.eaterName = eaterName
        self.component = component
        self.feeder = None

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
        self._dag = dag.DAG()
        self._state = {}

    def _addNode(self, component, type):
        # type: str
        self.debug("Adding node %r of type %s" % (component, type))
        self._dag.addNode(component, type)
        self._state[(component, type)] = False

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

    def addClockMaster(self, component):
        """
        I set a component to be the clock master in the dependency
        graph.  This component must have already been added to the
        dependency graph.

        @param component: the component to set as the clock master
        @type  component: L{flumotion.manager.component.ComponentAvatar}
        """
        if self._dag.hasNode(component, "JOB"):
            self._addNode(component, "CLOCKMASTER")
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

    def addComponent(self, component):
        """
        I add a component to the dependency graph.
        This includes adding the worker (if not already added), the job,
        the feeders and the eaters.

        Requirement: worker must already be assigned to component

        @param component: component object to add
        @type  component: L{flumotion.common.planet.ManagerComponentState}
        """
        self.debug('adding component %r to depgraph' % component)
        self._addNode(component, "JOB")
        self._addNode(component, "COMPONENTSTART")
        self._addNode(component, "COMPONENTSETUP")
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
            self._addNode(worker, "WORKER")

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
    

    def mapEatersToFeeders(self):
        """
        I am called once whole flow has been added so I can add edges to the
        dag between eaters and feeders.
        """
        compsetups = self._dag.getAllNodesByType("COMPONENTSETUP")
        #eaters = self._dag.getAllNodesByType(self.EATER)
        
        for eatercomp in compsetups:
            # for this component setup, go through all the feeders in it
            dict = eatercomp.get('config')

            if not dict.has_key('source'):
            # no eaters
                self.debug("Component %r has no eaters" % eatercomp)
            else:
                # source entries are componentName[:feedName]
                # with feedName defaulting to default
        
                list = dict['source']

                # FIXME: there's a bug in config parsing - sometimes this gives
                # us one string, and sometimes a list of one string, and
                # sometimes a list
                if isinstance(list, str):
                    list = [list, ]
                for eater in list:
                    feederfound = False
                    name = string.split(eater,':')
                    # name[0] is the name of the feeder component
                    # find the feeder
                    for feedercomp in compsetups:
                        #name = "%s:default" % eater
                        #self.debug("eater %s being added with name %s" % (eater,name))
                        #eat = Eater(name, component)
                        #self._addNode(eat, self.EATER)
                        #self._addEdge(eat, component, self.EATER, 
                        #    self.COMPONENTREADY)
                        if feedercomp.get("name") == name[0]:
                            try:
                                self._addEdge(feedercomp, eatercomp, 
                                    "COMPONENTSETUP", "COMPONENTSETUP")
                            except KeyError:
                                # this happens when edge is already there, 
                                # possible to have 2 feeders on one component
                                # go to 2 eaters on another component
                                pass
                            feederfound = True
                            try:
                                self._addEdge(feedercomp, eatercomp,
                                    "COMPONENTSTART", "COMPONENTSTART")
                            except KeyError:
                                pass
                    if not feederfound:
                        raise KeyError("Eater %s has no mapped feeder" % 
                            eater)

    def whatShouldBeStarted(self):
        """
        I return a list of things that can and should be started now.

        @return: a list of nodes that should be started, in order
        @rtype:  list of (object, str)
        """
        # A bit tricky because workers can't be started by manager,
        # and jobs are started automatically when worker is attached
        # So we get all the stuff sorted by depgraph,
        # then remove ones that are already have state of True,
        # then remove ones that are workers who are False, and their offspring,
        # then remove ones that are jobs who are False, and their offspring,
        # and also remove eaters whose feeders haven't started.
        toBeStarted = self._dag.sort()
        # we want to loop over all objects, so we loop over a copy
        for obj in toBeStarted[:]:
            if obj in toBeStarted:
                self.log("toBeStarted: checking if (%r, %r) needs starting",
                    obj[0], obj[1])
                if self._state[obj]:
                    toBeStarted.remove(obj)
                elif obj[1] == "WORKER":
                    # This is a worker not started.
                    # Let's remove it and its offspring
                    worker_offspring = self._dag.getOffspringTyped(
                        obj[0], obj[1])
                    for offspring in worker_offspring:
                        if offspring in toBeStarted:
                            toBeStarted.remove(offspring)
                    toBeStarted.remove(obj)
                elif obj[1] == "JOB":
                    job_offspring = self._dag.getOffspringTyped(obj[0], obj[1])
                    for offspring in job_offspring:
                        if offspring in toBeStarted:
                            toBeStarted.remove(offspring)
                    toBeStarted.remove(obj)
        
        return toBeStarted

    def _setState(self, object, type, value):
        self.doLog(log.DEBUG, -2, "Setting state of (%r, %s) to %d" % (
            object, type, value))
        self._state[(object,type)] = value
        # if making state False, should make its offspring False
        # if the object is the same
        if not value:
            self.debug("Setting state of all (%r, %s)'s offspring to %d" %
                (object, type, value))
            offspring = self._dag.getOffspringTyped(object, type)
            for kid in offspring:
                self.debug("Setting state of offspring (%r) to %d", kid, value)
                # FIXME: what does this do ?
                # a) why compare kid[0] to object ?
                # b) why does the state get set to False, not value ?
                # c) why does the debug line lie about what's done ?
                if kid[0] == object:
                    self._state[kid] = False

                # if COMPONENTSTART state on offspring is set to FALSE,
                # and the component is happy, then we set it to hungry;
                # that is what will happen soon enough anyway
                if kid[1] == "COMPONENTSTART" and kid[0] != object:
                    if kid[0].get('mood') == moods.happy.value:
                        self.debug('Setting downstream component %r to hungry' %
                            kid[0])
                        kid[0].set('mood', moods.hungry.value)

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
