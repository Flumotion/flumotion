# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

"""
Servicer object used in service scripts
"""

import os
import glob
import time

from flumotion.configure import configure
from flumotion.common import errors, log
from flumotion.common.python import makedirs
from flumotion.common.process import checkPidRunning, deletePidFile, getPid, \
     killPid, termPid, waitPidFile

__version__ = "$Rev$"


class Servicer(log.Loggable):
    """
    I manage running managers and workers on behalf of a service script.
    """

    logCategory = 'servicer'

    def __init__(self, configDir=None, logDir=None, runDir=None):
        """
        @type  configDir: string
        @param configDir: overridden path to the configuration directory.
        @type  logDir:    string
        @param logDir:    overridden path to the log directory.
        @type  runDir:    string
        @param runDir:    overridden path to the run directory.
        """
        self.managersDir = os.path.join(configure.configdir, 'managers')
        self.workersDir = os.path.join(configure.configdir, 'workers')
        self._overrideDir = {
            'logdir': logDir,
            'rundir': runDir,
        }

    def _parseManagersWorkers(self, command, args):
        # parse the given args and return two sorted lists;
        # one of manager names to act on and one of worker names
        managers = []
        workers = []

        if not args:
            managers = self.getManagers().keys()
            managers.sort()
            workers = self.getWorkers()
            workers.sort()
            return (managers, workers)

        which = args[0]
        if which not in ['manager', 'worker']:
            raise errors.FatalError, 'Please specify either manager or worker'

        if len(args) < 2:
            raise errors.FatalError, 'Please specify which %s to %s' % (
                which, command)

        name = args[1]
        if which == 'manager':
            managers = self.getManagers()
            if not name in managers:
                raise errors.FatalError, 'No manager "%s"' % name
            managers = [name, ]
        elif which == 'worker':
            workers = self.getWorkers()
            if not name in workers:
                raise errors.FatalError, 'No worker with name %s' % name
            workers = [name, ]

        return (managers, workers)

    def _getDirOptions(self):
        """
        Return a list of override directories for configure.configure
        suitable for appending to a command line.
        """
        args = []
        for key, value in self._overrideDir.items():
            if value:
                args.append('--%s=%s' % (key, value))
        return " ".join(args)

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
            name = name.split("-disabled")[0]
            workers.append(name)
        workers.sort()
        return workers

    def start(self, args):
        """
        Start processes as given in the args.

        If nothing specified, start all managers and workers.
        If first argument is "manager", start given manager.
        If first argument is "worker", start given worker.

        @returns: an exit value reflecting the number of processes that failed
                  to start
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
        If first argument is "manager", stop given manager.
        If first argument is "worker", stop given worker.

        @returns: an exit value reflecting the number of processes that failed
                  to stop
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
        for kind, names in [('manager', managers), ('worker', workers)]:
            for name in names:
                pid = getPid(kind, name)
                if not pid:
                    if self.checkDisabled(kind, name):
                        print "%s %s is disabled" % (kind, name)
                    else:
                        print "%s %s not running" % (kind, name)
                    continue
                if checkPidRunning(pid):
                    print "%s %s is running with pid %d" % (kind, name, pid)
                else:
                    print "%s %s dead (stale pid %d)" % (kind, name, pid)

    def clean(self, args):
        """
        Clean up dead process pid files as given in the args.
        """
        (managers, workers) = self._parseManagersWorkers('clean', args)
        self.debug("Clean managers %r and workers %r" % (managers, workers))
        for kind, names in [('manager', managers), ('worker', workers)]:
            for name in names:
                pid = getPid(kind, name)
                if not pid:
                    # may be a file that contains bogus data
                    try:
                        deletePidFile(kind, name)
                        print "deleted bogus pid file for %s %s" % (kind, name)
                    except OSError:
                        print ("failed to delete pid file for %s %s "
                               "- ignoring" % (kind, name))
                    continue
                if not checkPidRunning(pid):
                    self.debug("Cleaning up stale pid %d for %s %s" % (
                        pid, kind, name))
                    print "deleting stale pid file for %s %s" % (kind, name)
                    deletePidFile(kind, name)

    def condrestart(self, args):
        """
        Restart running processes as given in the args.

        If nothing specified, condrestart all managers and workers.
        If first argument is "manager", condrestart given manager.
        If first argument is "worker", condrestart given worker.

        @returns: an exit value reflecting the number of processes that failed
                  to start
        """
        (managers, workers) = self._parseManagersWorkers('condrestart', args)
        self.debug("condrestart managers %r and workers %r" % (
            managers, workers))
        managersDict = self.getManagers()
        exitvalue = 0

        for kind, names in [('manager', managers), ('worker', workers)]:
            for name in names:
                pid = getPid(kind, name)
                if not pid:
                    continue
                if checkPidRunning(pid):
                    if kind == 'manager':
                        if not self.stopManager(name):
                            exitvalue += 1
                            continue
                        if not self.startManager(name, managersDict[name]):
                            exitvalue += 1
                    elif kind == 'worker':
                        if not self.stopWorker(name):
                            exitvalue += 1
                            continue
                        if not self.startWorker(name):
                            exitvalue += 1
                else:
                    print "%s %s dead (stale pid %d)" % (kind, name, pid)

        return exitvalue

    def create(self, args):
        # TODO: Andy suggested we should be able to customize the
        # configuration this generates.
        # For that we maybe first want to use the Command class way of
        # writing the service script.
        """
        Create a default manager or worker config.
        """
        if len(args) == 0:
            raise errors.FatalError, \
                "Please specify 'manager' or 'worker' to create."
        kind = args[0]
        if len(args) == 1:
            raise errors.FatalError, \
                "Please specify name of %s to create." % kind
        name = args[1]

        port = 7531
        if len(args) == 3:
            port = int(args[2])

        if kind == 'manager':
            self.createManager(name, port)
        elif kind == 'worker':
            self.createWorker(name, managerPort=port, randomFeederports=True)
        else:
            raise errors.FatalError, \
                "Please specify 'manager' or 'worker' to create."

    def createManager(self, name, port=7531):
        """
        Create a sample manager.

        @returns: whether or not the config was created.
        """
        self.info("Creating manager %s" % name)
        managerDir = os.path.join(self.managersDir, name)
        if os.path.exists(managerDir):
            raise errors.FatalError, \
                "Manager directory %s already exists" % managerDir
        makedirs(managerDir)

        planetFile = os.path.join(managerDir, 'planet.xml')

        # create a default.pem file if it doesn't exist yet
        pemFile = os.path.join(configure.configdir, 'default.pem')
        if not os.path.exists(pemFile):
            # files in datadir are usually not executable, so call through sh
            retval = os.system("sh %s %s" % (
                os.path.join(configure.datadir, 'make-dummy-cert'), pemFile))

            # If we couldn't generate the file, it means that we probably
            # don't have openssl installed. If so, don't include the complete
            # to the pemfile which means that the the default pem file which
            # is shipped with flumotion will be used instead.
            if retval != 0:
                pemFile = 'default.pem'

        # generate the file
        handle = open(planetFile, 'w')
        handle.write("""<planet>
  <manager>
    <debug>4</debug>
    <host>localhost</host>
    <port>%(port)d</port>
    <transport>ssl</transport>
    <!-- certificate path can be relative to $sysconfdir/flumotion,
         or absolute -->
    <certificate>%(pemFile)s</certificate>
    <component name="manager-bouncer" type="htpasswdcrypt-bouncer">
      <property name="data"><![CDATA[
user:PSfNpHTkpTx1M
]]></property>
    </component>
  </manager>
</planet>
""" % locals())
        handle.close()

        return True

    def createWorker(self, name, managerPort=7531, randomFeederports=False):
        """
        Create a sample worker.

        @returns: whether or not the config was created.
        """
        makedirs(self.workersDir)
        self.info("Creating worker %s" % name)
        workerFile = os.path.join(self.workersDir, "%s.xml" % name)
        if os.path.exists(workerFile):
            raise errors.FatalError, \
                "Worker file %s already exists." % workerFile

        feederports = "  <!-- <feederports>8600-8639</feederports> -->"
        if randomFeederports:
            feederports = '  <feederports random="True" />'
        # generate the file
        handle = open(workerFile, 'w')
        handle.write("""<worker>

    <debug>4</debug>

  <manager>
    <host>localhost</host>
    <port>%(managerPort)s</port>
  </manager>

  <authentication type="plaintext">
    <username>user</username>
    <password>test</password>
  </authentication>

%(feederports)s

</worker>
""" % locals())
        handle.close()

        return True

    def startManager(self, name, flowNames):
        """
        Start the manager as configured in the manager directory for the given
        manager name, together with the given flows.

        @returns: whether or not the manager daemon started
        """
        self.info("Starting manager %s" % name)

        if self.checkDisabled('manager', name):
            print "manager %s is disabled, cannot start" % name
            return

        self.debug("Starting manager with flows %r" % flowNames)
        managerDir = os.path.join(self.managersDir, name)
        planetFile = os.path.join(managerDir, 'planet.xml')
        if not os.path.exists(planetFile):
            raise errors.FatalError, \
                "Planet file %s does not exist" % planetFile
        self.info("Loading planet %s" % planetFile)

        flowsDir = os.path.join(managerDir, 'flows')
        flowFiles = []
        for flowName in flowNames:
            flowFile = os.path.join(flowsDir, "%s.xml" % flowName)
            if not os.path.exists(flowFile):
                raise errors.FatalError, \
                    "Flow file %s does not exist" % flowFile
            flowFiles.append(flowFile)
            self.info("Loading flow %s" % flowFile)

        pid = getPid('manager', name)
        if pid:
            if checkPidRunning(pid):
                raise errors.FatalError, \
                    "Manager %s is already running (with pid %d)" % (name, pid)
            else:
                # there is a stale PID file, warn about it, remove it and
                # continue
                self.warning("Removing stale pid file %d for manager %s",
                             pid, name)
                deletePidFile('manager', name)

        dirOptions = self._getDirOptions()
        command = "flumotion-manager %s -D --daemonize-to %s " \
            "--service-name %s %s %s" % (
            dirOptions, configure.daemondir, name, planetFile,
            " ".join(flowFiles))
        self.debug("starting process %s" % command)
        retval = self.startProcess(command)

        if retval == 0:
            self.debug("Waiting for pid for manager %s" % name)
            pid = waitPidFile('manager', name)
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

        @returns: whether or not the worker daemon started
        """
        self.info("Starting worker %s" % name)

        if self.checkDisabled('worker', name):
            print "worker %s is disabled, cannot start" % name
            return

        workerFile = os.path.join(self.workersDir, "%s.xml" % name)
        if not os.path.exists(workerFile):
            raise errors.FatalError, \
                "Worker file %s does not exist" % workerFile

        pid = getPid('worker', name)
        if pid:
            if checkPidRunning(pid):
                raise errors.FatalError, \
                    "Worker %s is already running (with pid %d)" % (name, pid)
            else:
                # there is a stale PID file, warn about it, remove it and
                # continue
                self.warning("Removing stale pid file %d for worker %s",
                             pid, name)
                deletePidFile('worker', name)

        # we are sure the worker is not running and there's no pid file
        self.info("Loading worker %s" % workerFile)

        dirOptions = self._getDirOptions()
        command = "flumotion-worker %s -D --daemonize-to %s " \
            "--service-name %s %s" % (
                dirOptions, configure.daemondir, name, workerFile)
        self.debug("Running %s" % command)
        retval = self.startProcess(command)

        if retval == 0:
            self.debug("Waiting for pid for worker %s" % name)
            pid = waitPidFile('worker', name)
            if pid:
                self.info("Started worker %s with pid %d" % (name, pid))
                return True
            else:
                self.warning("worker %s could not start" % name)
                return False

        self.warning("worker %s could not start (return value %d)" % (
            name, retval))
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
        pid = getPid('manager', name)
        if not pid:
            return True

        # FIXME: ensure a correct process is running this pid
        if not checkPidRunning(pid):
            self.info("Manager %s is dead (stale pid %d), "
                      "cleaning up" % (name, pid))
            deletePidFile('manager', name)
            return False

        self.debug('Stopping manager %s with pid %d' % (name, pid))

        ret = self.stopProcess(pid)

        # we may need to remove the pid file ourselves, in case the process
        # failed to do it
        deletePidFile('manager', name, force=True)

        if ret:
            self.info('Stopped manager %s with pid %d' % (name, pid))
        return ret

    def stopWorker(self, name):
        """
        Stop the given worker if it is running.
        """
        self.info("Stopping worker %s" % name)
        pid = getPid('worker', name)
        if not pid:
            self.info("worker %s was not running" % name)
            return True

        # FIXME: ensure a correct process is running this pid
        if not checkPidRunning(pid):
            self.info("Worker %s is dead (stale pid %d), "
                      "cleaning up" % (name, pid))
            deletePidFile('worker', name)
            return False

        self.debug('Stopping worker %s with pid %d' % (name, pid))

        ret = self.stopProcess(pid)

        # we may need to remove the pid file ourselves, in case the process
        # failed to do it
        deletePidFile('worker', name, force=True)

        if ret:
            self.info('Stopped worker %s with pid %d' % (name, pid))
        return ret

    def stopProcess(self, pid):
        """
        Stop the process with the given pid.
        Wait until the pid has disappeared.
        """
        startClock = time.clock()
        termClock = startClock + configure.processTermWait
        killClock = termClock + configure.processKillWait

        self.debug('stopping process with pid %d' % pid)
        if not termPid(pid):
            self.warning('No process with pid %d' % pid)
            return False

        # wait for the kill
        while (checkPidRunning(pid)):
            if time.clock() > termClock:
                self.warning("Process with pid %d has not responded to TERM " \
                    "for %d seconds, killing" % (pid,
                        configure.processTermWait))
                killPid(pid)
                # so it does not get triggered again
                termClock = killClock + 1.0

            if time.clock() > killClock:
                self.warning("Process with pid %d has not responded to KILL " \
                    "for %d seconds, stopping" % (pid,
                        configure.processKillWait))
                return False

            # busy loop until kill is done

        return True

    def enable(self, args):
        if len(args) < 1:
            raise errors.FatalError, 'Please specify what to enable'

        which = args[0]
        if which not in ['manager', 'worker']:
            raise errors.FatalError, 'Please specify either manager or worker'

        if len(args) < 2:
            raise errors.FatalError, 'Please specify which %s to %s' % (
                which, 'enable')

        name = args[1]
        if which == 'manager':
            managers = self.getManagers()
            if not name in managers:
                raise errors.FatalError, 'No manager "%s"' % name
            self.enableManager(name)
        elif which == 'worker':
            workers = self.getWorkers()
            if not name in workers:
                raise errors.FatalError, 'No worker with name %s' % name
            self.enableWorker(name)
        return

    def disable(self, args):
        if len(args) < 1:
            raise errors.FatalError, 'Please specify what to disable'

        which = args[0]
        if which not in ['manager', 'worker']:
            raise errors.FatalError, 'Please specify either manager or worker'

        if len(args) < 2:
            raise errors.FatalError, 'Please specify which %s to %s' % (
                which, 'enable')

        name = args[1]
        if which == 'manager':
            managers = self.getManagers()
            if not name in managers:
                raise errors.FatalError, 'No manager "%s"' % name
            pid = getPid('manager', name)
            if pid:
                if checkPidRunning(pid):
                    raise errors.FatalError, "Manager %s is running" % name
            self.disableManager(name)
        elif which == 'worker':
            workers = self.getWorkers()
            if not name in workers:
                raise errors.FatalError, 'No worker with name %s' % name
            pid = getPid('worker', name)
            if pid:
                if checkPidRunning(pid):
                    raise errors.FatalError, "Worker %s is running" % name
            self.disableWorker(name)
        return

    def enableManager(self, name):
        self.debug("Enabling manager %s" % name)
        managerDir = os.path.join(self.managersDir, name)
        planetDisabledFile = os.path.join(managerDir, 'planet-disabled.xml')
        planetFile = os.path.join(managerDir, 'planet.xml')
        if not os.path.exists(planetDisabledFile):
            if not os.path.exists(planetFile):
                raise errors.FatalError, \
                    "Planet file %s does not exist" % planetFile
            else:
                print "manager %s already enabled" % name
                return
        else:
            os.rename(planetDisabledFile, planetFile)
            print "manager %s enabled" %name

    def enableWorker(self, name):
        self.debug("Disabling worker %s" % name)
        workerFile = os.path.join(self.workersDir, "%s.xml" % name)
        workerDisFile = os.path.join(self.workersDir, "%s-disabled.xml" % name)
        if not os.path.exists(workerDisFile):
            if not os.path.exists(workerFile):
                raise errors.FatalError, \
                    "Worker file %s does not exist" % workerFile
            else:
                print "worker %s already enabled" % name
        else:
            os.rename(workerDisFile, workerFile)
            print "worker %s enabled" % name

    def disableManager(self, name):
        self.debug("Disabling manager %s" % name)
        managerDir = os.path.join(self.managersDir, name)
        planetDisabledFile = os.path.join(managerDir, 'planet-disabled.xml')
        planetFile = os.path.join(managerDir, 'planet.xml')
        if not os.path.exists(planetFile):
            if not os.path.exists(planetDisabledFile):
                raise errors.FatalError, \
                    "Planet file %s does not exist" % planetFile
            else:
                print "manager %s already disabled" % name
                return
        else:
            os.rename(planetFile, planetDisabledFile)
            print "manager %s disabled" %name

    def disableWorker(self, name):
        self.debug("Disabling worker %s" % name)
        workerFile = os.path.join(self.workersDir, "%s.xml" % name)
        workerDisFile = os.path.join(self.workersDir, "%s-disabled.xml" % name)
        if not os.path.exists(workerFile):
            if not os.path.exists(workerDisFile):
                raise errors.FatalError, \
                    "Worker file %s does not exist" % workerFile
            else:
                print "worker %s already disabled" % name
        else:
            os.rename(workerFile, workerDisFile)
            print "worker %s disabled" % name

    def checkDisabled(self, type, name):
        if type == 'manager':
            managerDir = os.path.join(self.managersDir, name)
            planetDisFile = os.path.join(managerDir, 'planet-disabled.xml')
            planetFile = os.path.join(managerDir, 'planet.xml')
            if not os.path.exists(planetFile):
                if os.path.exists(planetDisFile):
                    return True
            return False
        elif type == 'worker':
            workerFile = os.path.join(self.workersDir, "%s.xml" % name)
            wkDisFile = os.path.join(self.workersDir, "%s-disabled.xml" % name)
            if not os.path.exists(workerFile):
                if os.path.exists(wkDisFile):
                    return True
            return False

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
