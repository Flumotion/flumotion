# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

import os
import glob
import time

from flumotion.configure import configure
from flumotion.common import common, errors, log

class Servicer(log.Loggable):
    logCategory = 'servicer'

    def __init__(self, configDir):
        self.configDir = configDir
        self.managersDir = os.path.join(self.configDir, 'managers')
        self.workersDir = os.path.join(self.configDir, 'workers')

    def _parseManagersWorkers(self, command, args):
        # parse the given args and return two lists;
        # one of manager names to act on and one of worker names
        managers = []
        workers = []

        if not args:
            managers = self.getManagers().keys()
            workers = self.getWorkers()
            return (managers, workers)

        which = args[0]
        if which not in ['manager', 'worker']:
            raise errors.SystemError, 'Please specify either manager or worker'
            
        if len(args) < 2:
            raise errors.SystemError, 'Please specify which %s to %s' % (
                which, command)

        name = args[1]
        if which == 'manager':
            managers = self.getManagers()
            if not managers.has_key(name):
                raise errors.SystemError, 'No manager "%s"' % name
            managers = [name, ]
        elif which == 'worker':
            workers = self.getWorkers()
            if not name in workers:
                raise errors.SystemError, 'No worker with name %s' % name
            workers = [name, ]
            
        return (managers, workers)

    def getManagers(self):
        """
        @returns: a dictionary of manager names -> flow names
        """
        managers = {}

        self.log('getManagers()')
        if not os.path.exists(self.managersDir):
            return managers

        for managerDir in glob.glob(os.path.join(self.managersDir, '*')):
            flows = [] # names of flows
            # find flow files
            flowsDir = os.path.join(managerDir, 'flows')
            if os.path.exists(flowsDir):
                flowFiles = glob.glob(os.path.join(flowsDir, '*.xml'))
                for flowFile in flowFiles:
                    filename = os.path.split(flowFile)[1]
                    name = filename.split(".xml")[0]
                    flows.append(name)
            managerName = os.path.split(managerDir)[1]
            self.log('Adding flows %r to manager %s' % (flows, managerName))
            managers[managerName] = flows
        self.log('returning managers: %r' % managers)
        return managers

    def getWorkers(self):
        """
        @returns: a list of worker names
        """
        workers = []

        if not os.path.exists(self.workersDir):
            return workers

        for workerFile in glob.glob(os.path.join(self.workersDir, '*.xml')):
            filename = os.path.split(workerFile)[1]
            name = filename.split(".xml")[0]
            workers.append(name)
        return workers

    def start(self, args):
        """
        Start processes as given in the args.

        If nothing specified, start all managers and workers.
        If first argument is "manager", start given manager,
        or all if none specified.
        If first argument is "worker", start given worker,
        or all if none specified.

        Returns: an exit value
        """
        (managers, workers) = self._parseManagersWorkers('start', args)
        self.debug("Start managers %r and workers %r" % (managers, workers))
        managersDict = self.getManagers()
        exitvalue = 0

        for name in managers:
            if not self.startManager(name, managersDict[name]):
                exitvalue += 1
        for name in workers:
            if not self.startWorker(name):
                exitvalue += 1

        return exitvalue

    def stop(self, args):
        """
        Stop processes as given in the args.

        If nothing specified, stop all managers and workers.
        If first argument is "manager", stop given manager,
        or all if none specified.
        If first argument is "worker", stop given worker,
        or all if none specified.
        """
        (managers, workers) = self._parseManagersWorkers('stop', args)
        self.debug("Stop managers %r and workers %r" % (managers, workers))

        exitvalue = 0

        for name in workers:
            if not self.stopWorker(name):
                exitvalue += 1
        for name in managers:
            if not self.stopManager(name):
                exitvalue += 1
            
        return exitvalue

    def status(self, args):
        """
        Give status on processes as given in the args.
        """
        (managers, workers) = self._parseManagersWorkers('status', args)
        self.debug("Status managers %r and workers %r" % (managers, workers))
        for type, list in [('manager', managers), ('worker', workers)]:
            for name in list:
                pid = common.getPid(type, name)
                if not pid:
                    print "%s %s not running" % (type, name)
                    continue
                if common.checkPidRunning(pid):
                    print "%s %s is running with pid %d" % (type, name, pid)
                else:
                    print "%s %s dead (stale pid %d)" % (type, name, pid)

    def clean(self, args):
        """
        Clean up dead processes as given in the args.
        """
        (managers, workers) = self._parseManagersWorkers('clean', args)
        self.debug("Clean managers %r and workers %r" % (managers, workers))
        for type, list in [('manager', managers), ('worker', workers)]:
            for name in list:
                pid = common.getPid(type, name)
                if not pid:
                    continue
                if not common.checkPidRunning(pid):
                    self.debug("Cleaning up stale pid %d for %s %s" % (
                        pid, type, name))
                    common.deletePidFile(type, name)
 
    def startManager(self, name, flowNames):
        """
        Start the manager as configured in the manager directory for the given
        manager name, together with the given flows.

        @returns: whether or not the manager daemon started
        """
        self.info("Starting manager %s" % name)
        self.debug("Starting manager with flows %r" % flowNames)
        managerDir = os.path.join(self.managersDir, name)
        planetFile = os.path.join(managerDir, 'planet.xml')
        if not os.path.exists(planetFile):
            raise errors.SystemError, \
                "Planet file %s does not exist" % planetFile
        self.info("Loading planet %s" % planetFile)

        flowsDir = os.path.join(managerDir, 'flows')
        flowFiles = []
        for flowName in flowNames:
            flowFile = os.path.join(flowsDir, "%s.xml" % flowName)
            if not os.path.exists(flowFile):
                raise errors.SystemError, \
                    "Flow file %s does not exist" % flowFile
            flowFiles.append(flowFile)
            self.info("Loading flow %s" % flowFile)

        pid = common.getPid('manager', name)
        if pid:
            if common.checkPidRunning(pid):
                raise errors.SystemError, \
                    "Manager %s is already running (with pid %d)" % (name, pid)
            else:
                raise errors.SystemError, \
                    "Manager %s is dead (stale pid %d)" % (name, pid)
            
        command = "flumotion-manager -D -n %s %s %s" % (
            name, planetFile, " ".join(flowFiles))
        self.debug("starting process %s" % command)
        retval = self.startProcess(command)

        if retval == 0:
            self.debug("Waiting for pid for manager %s" % name)
            pid = common.waitPidFile('manager', name)
            if pid:
                self.info("Started manager %s with pid %d" % (name, pid))
                return True
            else:
                self.warning("manager %s could not start" % name)
                return False

        self.warning("manager %s could not start (return value %d)" % (
            name, retval))
        return False

    def startWorker(self, name):
        """
        Start the worker as configured in the worker directory for the given
        worker name.

        @returns: whether or not the manager daemon started
        """
        self.info("Starting worker %s" % name)
        workerFile = os.path.join(self.workersDir, "%s.xml" % name)
        if not os.path.exists(workerFile):
            raise errors.SystemError, \
                "Worker file %s does not exist" % workerFile

        pid = common.getPid('worker', name)
        if pid:
            if common.checkPidRunning(pid):
                raise errors.SystemError, \
                    "Worker %s is already running (with pid %d)" % (name, pid)
            else:
                raise errors.SystemError, \
                    "Worker %s is dead (stale pid %d)" % (name, pid)
            
        self.info("Loading worker %s" % workerFile)

        command = "flumotion-worker -D -n %s %s" % (name, workerFile)
        retval = self.startProcess(command)

        if retval == 0:
            self.debug("Waiting for pid for worker %s" % name)
            pid = common.waitPidFile('worker', name)
            if pid:
                self.debug("worker %s started with pid %d" % (name, pid))
                return True
            else:
                self.warning("worker %s could not start" % name)
                return False

        return False

    def startProcess(self, command):
        """
        Start the given process and block.
        Returns the exit status of the process, or -1 in case of another error.
        """
        status = os.system(command)
        if os.WIFEXITED(status):
            retval = os.WEXITSTATUS(status)
            return retval

        # definately something wrong
        return -1

    def stopManager(self, name):
        """
        Stop the given manager if it is running.
        """
        self.info("Stopping manager %s" % name)
        pid = common.getPid('manager', name)
        if not pid:
            return True

        # FIXME: ensure a correct process is running this pid
        if not common.checkPidRunning(pid):
            self.info("Manager %s is dead (stale pid %d)" % (name, pid))
            return False

        self.debug('Stopping manager %s with pid %d' % (name, pid))
        if not self.stopProcess(pid):
            return False

        self.info('Stopped manager %s with pid %d' % (name, pid))
        return True

    def stopWorker(self, name):
        """
        Stop the given worker if it is running.
        """
        self.info("Stopping worker %s" % name)
        pid = common.getPid('worker', name)
        if not pid:
            self.info("worker %s was not running" % name)
            return True

        # FIXME: ensure a correct process is running this pid
        if not common.checkPidRunning(pid):
            self.info("Worker %s is dead (stale pid %d)" % (name, pid))
            return False

        self.debug('Stopping worker %s with pid %d' % (name, pid))
        if not self.stopProcess(pid):
            return False

        self.info('Stopped worker %s with pid %d' % (name, pid))
        return True

    def stopProcess(self, pid):
        """
        Stop the process with the given pid.
        Wait until the pid has disappeared.
        """
        startClock = time.clock()
        termClock = startClock + configure.processTermWait
        killClock = termClock + configure.processKillWait

        self.debug('stopping process with pid %d' % pid)
        if not common.termPid(pid):
            self.warning('No process with pid %d' % pid)
            return False

        # wait for the kill
        while (common.checkPidRunning(pid)):
            if time.clock() > termClock:
                self.warning("Process with pid %d has not responded to TERM " \
                    "for %d seconds, killing" % (pid,
                        configure.processTermWait))
                common.killPid(pid)
                termClock = killClock + 1.0 # so it does not get triggered again

            if time.clock() > killClock:
                self.warning("Process with pid %d has not responded to KILL " \
                    "for %d seconds, stopping" % (pid,
                        configure.processKillWait))
                return False

            # busy loop until kill is done

        return True
  
    def list(self):
        """
        List all service parts managed.
        """
        managers = self.getManagers()
        for name in managers.keys():
            flows = managers[name]
            print "manager %s" % name
            if flows:
                for flow in flows:
                   print "        flow %s" % flow

        workers = self.getWorkers()
        for worker in workers:
            print "worker  %s" % worker

