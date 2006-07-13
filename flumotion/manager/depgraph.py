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

from flumotion.common import dag, log, registry

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

    (WORKER, JOB, COMPONENTSETUP, CLOCKMASTER, COMPONENTSTART) = range(0,5)
    
    def __init__(self):
        self._dag = dag.DAG()
        self._state = {}

    def _addNode(self, component, type):
        self._dag.addNode(component, type)
        self._state[(component,type)] = False
        self.debug("Adding node %r of type %d" % (component, type))

    def addComponent(self, component):
        """
        I add a component to the dependency graph.
        This includes adding the worker (if not already added), the job,
        the feeders and the eaters.

        Requirement: worker must already be assigned to component

        @param component: component object to add
        @type component: L{flumotion.common.planet.ManagerComponentState}
        """
        self._addNode(component, self.JOB)
        self._addNode(component, self.COMPONENTSTART)
        self._addNode(component, self.COMPONENTSETUP)
        self._dag.addEdge(component, component, self.JOB, self.COMPONENTSETUP)
        workername = component.get('workerRequested')
        if workername:
            self.addWorker(workername)
            self.setComponentWorker(component, workername)
        self._dag.addEdge(component, component, self.COMPONENTSETUP, 
            self.COMPONENTSTART)

    def addClockMaster(self, component):
        """
        I set a component to be the clock master in the dependency
        graph.  This component must have already been added to the
        dependency graph.

        @param component: the component to set as the clock master
        @type component: L{flumotion.manager.component.ComponentAvatar}
        """
        if self._dag.hasNode(component, self.JOB):
            self._addNode(component, self.CLOCKMASTER)
            self._dag.addEdge(component, component, self.COMPONENTSETUP, 
                self.CLOCKMASTER)
        
            # now go through all the component starts and make them dep on the
            # clock master
            startnodes = self._dag.getAllNodesByType(self.COMPONENTSTART)
            for start in startnodes:
                # only add if they share the same parent flow
                if start.get('parent') == component.get('parent'):
                    self._dag.addEdge(component, start, self.CLOCKMASTER, 
                        self.COMPONENTSTART)
        else:
            raise KeyError("Component %r has not been added" % component)

    def addWorker(self, worker):
        """
        I add a worker to the dependency graph.

        @param worker: the worker to add
        @type worker: String
        """
        if not self._dag.hasNode(worker, self.WORKER):
            self._addNode(worker, self.WORKER)

    def removeWorker(self, worker):
        """
        I remove a worker from the dependency graph.

        @param worker: the worker to remove
        @type worker: String
        """
        if self._dag.hasNode(worker, self.WORKER):
            self._dag.removeNode(worker, self.WORKER)

    def removeComponent(self, component):
        """
        I remove a component in the dependency graph, this includes removing
        the JOB, COMPONENTSETUP, COMPONENTSTART, CLOCKMASTER.

        @param component: the component to remove
        @type component:  L{flumotion.manager.component.ComponentAvatar}
        """
        if self._dag.hasNode(component, self.CLOCKMASTER):
            self._dag.removeNode(component, self.CLOCKMASTER)
        if self._dag.hasNode(component, self.COMPONENTSTART):
            self._dag.removeNode(component, self.COMPONENTSTART)
        if self._dag.hasNode(component, self.COMPONENTSETUP):
            self._dag.removeNode(component, self.COMPONENTSETUP)
        if self._dag.hasNode(component, self.JOB):
            self._dag.removeNode(component, self.JOB)

    def setComponentWorker(self, component, worker):
        """
        I assign a component to a specific worker.

        @param component: the component
        @type component: L{flumotion.common.planet.ManagerComponentState}
        @param worker: the worker to set it to
        @type worker: String
        """
        if self._dag.hasNode(worker, self.WORKER) and (
            self._dag.hasNode(component, self.JOB)):
            self._dag.addEdge(worker, component, self.WORKER, self.JOB)
        else:
            raise KeyError("Worker %s or Component %r not in dependency graph" %
                (worker, component))
    

    def mapEatersToFeeders(self):
        """
        I am called once whole flow has been added so I can add edges to the
        dag between eaters and feeders.
        """
        compsetups = self._dag.getAllNodesByType(self.COMPONENTSETUP)
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

                # FIXME: there's a bug in config parsing - sometimes this gives us
                # one string, and sometimes a list of one string, and sometimes
                # a list
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
                        #self._dag.addEdge(eat, component, self.EATER, 
                        #    self.COMPONENTREADY)
                        if feedercomp.get("name") == name[0]:
                            try:
                                self._dag.addEdge(feedercomp, eatercomp, 
                                    self.COMPONENTSETUP, self.COMPONENTSETUP)
                            except KeyError:
                                # this happens when edge is already there, 
                                # possible to have 2 feeders on one component
                                # go to 2 eaters on another component
                                pass
                            feederfound = True
                            try:
                                self._dag.addEdge(feedercomp, eatercomp,
                                    self.COMPONENTSTART, self.COMPONENTSTART)
                            except KeyError:
                                pass
                    if not feederfound:
                        raise KeyError("Eater %s has no mapped feeder" % 
                            eater)

    def whatShouldBeStarted(self):
        """
        I return a list of things that can and should be started now
        @rtype: List of (object,type)
        @returns a list of nodes that should be started, in order
        """
        # a bit tricky because workers cant be started by manager
        # and jobs are started automatically when worker is attached
        # so we get all the stuff sorted by depgraph
        # then remove ones that are already have state of True
        # then remove ones that are workers who are False, and their offspring
        # then remove ones that are jobs who are False, and their offspring
        # also remove eaters who's feeders havent started
        tobestarted_temp = self._dag.sort()
        tobestarted = tobestarted_temp[:]
        for obj in tobestarted_temp:
            if obj in tobestarted:
                if self._state[obj]:
                    del tobestarted[tobestarted.index(obj)]
                elif obj[1] == self.WORKER:
                    # this is a worker not started
                    # lets remove it and its 
                    # offspring
                    worker_offspring = self._dag.getOffspringTyped(obj[0], obj[1])
                    for offspring in worker_offspring:
                        if offspring in tobestarted:
                            del tobestarted[tobestarted.index(offspring)]
                    del tobestarted[tobestarted.index(obj)]
                elif obj[1] == self.JOB:
                    job_offspring = self._dag.getOffspringTyped(obj[0], obj[1])
                    for offspring in job_offspring:
                        if offspring in tobestarted:
                            del tobestarted[tobestarted.index(offspring)]
                    del tobestarted[tobestarted.index(obj)]
        
        return tobestarted

    def _setState(self, object, type, value):
        self.debug("Setting state of (%r,%d) to %d" % (object, type, value))
        self._state[(object,type)] = value
        # if making state False, should make its offspring False
        # if the object is the same
        if not value:
            self.debug("Setting state of (%r,%d) offspring to %d" %
                (object, type, value))
            offspring = self._dag.getOffspringTyped(object, type)
            for kid in offspring:
                if kid[0] == object:
                    self._state[kid] = False

    def setComponentStarted(self, component):
        """
        Set a COMPONENTSTART node to have state of True

        @param component: the component to set COMPONENTSTART to True for
        @type component: L{flumotion.common.planet.ManagerComponentState}
        """
        self._setState(component, self.COMPONENTSTART, True)

    def setComponentNotStarted(self, component):
        """
        Set a COMPONENTSTART node to have state of False

        @param component: the component to set COMPONENTSTART to False for
        @type component: L{flumotion.common.planet.ManagerComponentState}
        """

        self._setState(component, self.COMPONENTSTART, False)

    def setComponentSetup(self, component):
        """
        Set a COMPONENTSETUP node to have state of True

        @param component: the component to set COMPONENTSETUP to True for
        @type component: L{flumotion.common.planet.ManagerComponentState}
        """

        self._setState(component, self.COMPONENTSETUP, True)

    def setComponentNotSetup(self, component):
        """
        Set a COMPONENTSETUP node to have state of False

        @param component: the component to set COMPONENTSETUP to True for
        @type component: L{flumotion.common.planet.ManagerComponentState}
        """

        self._setState(component, self.COMPONENTSETUP, False)


    def setJobStarted(self, component):
        """
        Set a JOB node to have state of True

        @param component: the component to set JOB to True for
        @type component: L{flumotion.common.planet.ManagerComponentState}
        """
        self._setState(component, self.JOB, True)

    def setJobStopped(self, component):
        """
        Set a JOB node to have state of False

        @param component: the component to set JOB to False for
        @type component: L{flumotion.common.planet.ManagerComponentState}
        """
        self._setState(component, self.JOB, False)

    def setWorkerStarted(self, worker):
        """
        Set a WORKER node to have state of True

        @param worker: the component to set WORKER to True for
        @type worker: String
        """
        self._setState(worker, self.WORKER, True)

    def setWorkerStopped(self, worker):
        """
        Set a WORKER node to have state of False

        @param worker: the component to set WORKER to False for
        @type worker: String
        """
        self._setState(worker, self.WORKER, False)
    
    def setClockMasterStarted(self, component):
        """
        Set a CLOCKMASTER node to have state of True

        @param component: the component to set CLOCKMASTER to True for
        @type component: {flumotion.common.planet.ManagerComponentState}
        """
        self._setState(component, self.CLOCKMASTER, True)

    def setClockMasterStopped(self, component):
        """
        Set a CLOCKMASTER node to have state of False

        @param component: the component to set CLOCKMASTER to True for
        @type component: {flumotion.common.planet.ManagerComponentState}
        """

        self._setState(component, self.CLOCKMASTER, False)
