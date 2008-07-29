# -*- Mode: Python; test-case-name: flumotion.test.test_common -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

"""utilities for interacting with processes"""

import errno
import os
import signal
import sys
import time

from flumotion.common import log
from flumotion.common.common import ensureDir
from flumotion.configure import configure

__version__ = "$Rev: 6690 $"


def startup(processType, processName, daemonize=False, daemonizeTo='/'):
    """
    Prepare a process for starting, logging appropriate standarised messages.
    First daemonizes the process, if daemonize is true.
    """
    log.info(processType, "Starting %s '%s'", processType, processName)

    if daemonize:
        _daemonizeHelper(processType, daemonizeTo, processName)

    log.info(processType, "Started %s '%s'", processType, processName)

    def shutdownStarted():
        log.info(processType, "Stopping %s '%s'", processType, processName)
    def shutdownEnded():
        log.info(processType, "Stopped %s '%s'", processType, processName)

    # import inside function so we avoid affecting startup
    from twisted.internet import reactor
    reactor.addSystemEventTrigger('before', 'shutdown',
                                  shutdownStarted)
    reactor.addSystemEventTrigger('after', 'shutdown',
                                  shutdownEnded)

def daemonize(stdin='/dev/null', stdout='/dev/null', stderr='/dev/null',
              directory='/'):
    '''
    This forks the current process into a daemon.
    The stdin, stdout, and stderr arguments are file names that
    will be opened and be used to replace the standard file descriptors
    in sys.stdin, sys.stdout, and sys.stderr.
    These arguments are optional and default to /dev/null.

    The fork will switch to the given directory.
    
    Used by external projects (ft).
    '''
    # Redirect standard file descriptors.
    si = open(stdin, 'r')
    os.dup2(si.fileno(), sys.stdin.fileno())
    try:
        log.outputToFiles(stdout, stderr)
    except IOError, e:
        if e.errno == errno.EACCES:
            log.error('common', 'Permission denied writing to log file %s.',
                e.filename)

    # first fork
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)   # exit first parent
    except OSError, e:
        sys.stderr.write("Failed to fork: (%d) %s\n" % (e.errno, e.strerror))
        sys.exit(1)

    # decouple from parent environment
    try:
        os.chdir(directory)
    except OSError, e:
        from flumotion.common import errors
        raise errors.FatalError, "Failed to change directory to %s: %s" % (
            directory, e.strerror)
    os.umask(0)
    os.setsid()

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)   # exit second parent
    except OSError, e:
        sys.stderr.write("Failed to fork: (%d) %s\n" % (e.errno, e.strerror))
        sys.exit(1)

    # Now I am a daemon!
    # don't add stuff here that can fail, because from now on the program
    # will keep running regardless of tracebacks

def _daemonizeHelper(processType, daemonizeTo='/', processName=None):
    """
    Daemonize a process, writing log files and PID files to conventional
    locations.

    @param processType: The process type, for example 'worker'. Used
    as part of the log file and PID file names.
    @type  processType: str
    @param daemonizeTo: The directory that the daemon should run in.
    @type  daemonizeTo: str
    @param processName: The service name of the process. Used to
    disambiguate different instances of the same daemon.
    @type  processName: str
    """

    ensureDir(configure.logdir, "log dir")
    ensureDir(configure.rundir, "run dir")
    ensureDir(configure.cachedir, "cache dir")
    ensureDir(configure.registrydir, "registry dir")

    pid = getPid(processType, processName)
    if pid:
        raise SystemError(
            "A %s service named '%s' is already running with pid %d"
            % (processType, processName or processType, pid))

    log.debug(processType, "%s service named '%s' daemonizing",
        processType, processName)

    if processName:
        logPath = os.path.join(configure.logdir,
                               '%s.%s.log' % (processType, processName))
    else:
        logPath = os.path.join(configure.logdir,
                               '%s.log' % (processType,))
    log.debug(processType, 'Further logging will be done to %s', logPath)

    pidFile = _acquirePidFile(processType, processName)

    # here we daemonize; so we also change our pid
    daemonize(stdout=logPath, stderr=logPath, directory=daemonizeTo)

    log.debug(processType, 'Started daemon')

    # from now on I should keep running until killed, whatever happens
    path = writePidFile(processType, processName, file=pidFile)
    log.debug(processType, 'written pid file %s', path)

    # import inside function so we avoid affecting startup
    from twisted.internet import reactor
    def _deletePidFile():
        log.debug(processType, 'deleting pid file')
        deletePidFile(processType, processName)
    reactor.addSystemEventTrigger('after', 'shutdown',
                                  _deletePidFile)


def _getPidPath(type, name=None):
    """
    Get the full path to the pid file for the given process type and name.
    """
    path = os.path.join(configure.rundir, '%s.pid' % type)
    if name:
        path = os.path.join(configure.rundir, '%s.%s.pid' % (type, name))
    log.debug('common', 'getPidPath for type %s, name %r: %s' % (
        type, name, path))
    return path

def writePidFile(type, name=None, file=None):
    """
    Write a pid file in the run directory, using the given process type
    and process name for the filename.

    @rtype:   str
    @returns: full path to the pid file that was written
    """
    # don't shadow builtin file
    pidFile = file
    if pidFile is None:
        ensureDir(configure.rundir, "rundir")
        filename = _getPidPath(type, name)
        pidFile = open(filename, 'w')
    else:
        filename = pidFile.name
    pidFile.write("%d\n" % (os.getpid(),))
    pidFile.close()
    os.chmod(filename, 0644)
    return filename

def _acquirePidFile(type, name=None):
    """
    Open a PID file for writing, using the given process type and
    process name for the filename. The returned file can be then passed
    to writePidFile after forking.

    @rtype:   str
    @returns: file object, open for writing
    """
    ensureDir(configure.rundir, "rundir")
    path = _getPidPath(type, name)
    return open(path, 'w')

def deletePidFile(type, name=None):
    """
    Delete the pid file in the run directory, using the given process type
    and process name for the filename.

    @rtype:   str
    @returns: full path to the pid file that was written
    """
    path = _getPidPath(type, name)
    os.unlink(path)
    return path

def getPid(type, name=None):
    """
    Get the pid from the pid file in the run directory, using the given
    process type and process name for the filename.

    @returns: pid of the process, or None if not running or file not found.
    """

    pidPath = _getPidPath(type, name)
    log.log('common', 'pidfile for %s %s is %s' % (type, name, pidPath))
    if not os.path.exists(pidPath):
        return

    pidFile = open(pidPath, 'r')
    pid = pidFile.readline()
    pidFile.close()
    if not pid or int(pid) == 0:
        return

    return int(pid)

def signalPid(pid, signum):
    """
    Send the given process a signal.

    @returns: whether or not the process with the given pid was running
    """
    try:
        os.kill(pid, signum)
        return True
    except OSError, e:
        # see man 2 kill
        if e.errno == errno.EPERM:
            # exists but belongs to a different user
            return True
        if e.errno == errno.ESRCH:
            # pid does not exist
            return False
        raise

def termPid(pid):
    """
    Send the given process a TERM signal.

    @returns: whether or not the process with the given pid was running
    """
    return signalPid(pid, signal.SIGTERM)

def killPid(pid):
    """
    Send the given process a KILL signal.

    @returns: whether or not the process with the given pid was running
    """
    return signalPid(pid, signal.SIGKILL)

def checkPidRunning(pid):
    """
    Check if the given pid is currently running.

    @returns: whether or not a process with that pid is active.
    """
    return signalPid(pid, 0)

def waitPidFile(type, name=None):
    """
    Wait for the given process type and name to have started and created
    a pid file.

    Return the pid.
    """
    # getting it from the start avoids an unneeded time.sleep
    pid = getPid(type, name)

    while not pid:
        time.sleep(0.1)
        pid = getPid(type, name)

    return pid

def waitForTerm():
    """
    Wait until we get killed by a TERM signal (from someone else).
    """

    class Waiter:
        def __init__(self):
            self.sleeping = True
            import signal
            self.oldhandler = signal.signal(signal.SIGTERM,
                                            self._SIGTERMHandler)

        def _SIGTERMHandler(self, number, frame):
            self.sleeping = False

        def sleep(self):
            while self.sleeping:
                time.sleep(0.1)

    waiter = Waiter()
    waiter.sleep()
