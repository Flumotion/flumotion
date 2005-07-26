# -*- Mode: Python; test-case-name: flumotion.test.test_common -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
small common functions used by all processes
"""

import errno
import os 
import socket
import sys
import time
import signal

from twisted.python import reflect, rebuild, components
from twisted.spread import pb
from twisted.internet import address

from flumotion.common import errors, log

# Note: This module is loaded very early on, so
#       don't add any extra flumotion imports unless you
#       really know what you're doing.
from flumotion.configure import configure

def formatStorage(units, precision = 2):
    """
    Nicely formats a storage size using SI units.
    See Wikipedia and other sources for rationale.
    Prefixes are k, M, G, ...
    Sizes are powers of 10.
    Actual result should be suffixed with bit or byte, not b or B.

    @param units:     the unit size to format
    @type  units:     int or float
    @param precision: the number of floating point digits to use
    @type  precision: int

    @rtype: string
    @returns: value of units, formatted using SI scale and the given precision
    """

    # XXX: We might end up calling float(), which breaks
    #      when using LC_NUMERIC when it is not C
    import locale
    locale.setlocale(locale.LC_NUMERIC, "C")

    prefixes = ['E', 'P', 'T', 'G', 'M', 'k', '']

    value = float(units)
    prefix = prefixes.pop()
    while prefixes and value >= 1000:
        prefix = prefixes.pop()
        value /= 1000

    format = "%%.%df %%s" % precision
    return format % (value, prefix)

def formatTime(seconds):
    """
    Nicely format time in a human-readable format.
    Will chunks weeks, days, hours and minutes.

    @param seconds: the time in seconds to format.
    @type  seconds: int or float

    @rtype: string
    @returns: a nicely formatted time string.
    """
    chunks = []
    
    week = 60 * 60 * 24 * 7
    weeks = seconds / week
    seconds %= week

    day = 60 * 60 * 24
    days = seconds / day
    seconds %= day

    hour = 60 * 60
    hours = seconds / hour
    seconds %= hour

    minute = 60
    minutes = seconds / minute
    seconds %= minute

    if weeks > 1:
        chunks.append('%d weeks' % weeks)
    elif weeks == 1:
        chunks.append('1 week')

    if days > 1:
        chunks.append('%d days' % days)
    elif days == 1:
        chunks.append('1 day')

    chunks.append('%02d:%02d' % (hours, minutes))

    return " ".join(chunks)

def version(binary):
    """
    Print a version block for the flumotion binaries.

    @arg binary: name of the binary
    @type binary: string
    """

    block = []
    block.append("%s %s" % (binary, configure.version))
    block.append("part of Flumotion - a streaming media server")
    block.append("(C) Copyright 2004,2005 Fluendo")
    return "\n".join(block)
             
def mergeImplements(*classes):
    """
    Merge the __implements__ tuples of the given classes into one tuple.
    """
    allYourBase = []
    for clazz in classes:
        allYourBase += getattr(clazz, '__implements__', ())
    return tuple(allYourBase)


def daemonize(stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
    '''
    This forks the current process into a daemon.
    The stdin, stdout, and stderr arguments are file names that
    will be opened and be used to replace the standard file descriptors
    in sys.stdin, sys.stdout, and sys.stderr.
    These arguments are optional and default to /dev/null.
    Note that stderr is opened unbuffered, so
    if it shares a file with stdout then interleaved output
    may not appear in the order that you expect.
    '''

    # first fork
    try: 
        pid = os.fork() 
        if pid > 0:
            sys.exit(0)   # exit first parent
    except OSError, e: 
        sys.stderr.write("Failed to fork: (%d) %s\n" % (e.errno, e.strerror))
        sys.exit(1)

    # decouple from parent environment
    os.chdir("/") 
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
    
    # Redirect standard file descriptors.
    si = open(stdin, 'r')
    so = open(stdout, 'a+')
    se = open(stderr, 'a+', 0)
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

def argRepr(args=(), kwargs={}, max=-1):
    """
    Return a string representing the given args.
    """
    # FIXME: rename function
    # FIXME: implement max
    
    # check validity of input
    assert (type(args) is tuple or
            type(args) is list)
    assert type(kwargs) is dict
    
    s = ''
    args = list(args)

    if args:
        args = map(repr, args)
        s += ', '.join(args)
    
    if kwargs:
        r = [(key + '=' + repr(item))
                for key, item in kwargs.items()]

        if s:
            s += ', '
        s += ', '.join(r)
            
    return s

def ensureDir(dir, description):
    """
    Ensure the given directory exists, creating it if not.
    Raises a SystemError if this fails, including the given description.
    """
    if not os.path.exists(dir):
        try:
            os.makedirs(dir)
        except:
            raise errors.SystemError, "could not create %s directory %s" % (
                description, dir)

def getPidPath(type, name):
    """
    Get the full path to the pid file for the given process type and name.
    """
    return os.path.join(configure.rundir, '%s.%s.pid' % (type, name))
 
def writePidFile(type, name):
    """
    Write a pid file in the run directory, using the given process type
    and process name for the filename.
    """
    ensureDir(configure.rundir, "rundir")
    pid = os.getpid()
    file = open(getPidPath(type, name), 'w')
    file.write("%d\n" % pid)
    file.close()
 
def deletePidFile(type, name):
    """
    Delete the pid file in the run directory, using the given process type
    and process name for the filename.
    """
    os.unlink(getPidPath(type, name))
 
def getPid(type, name):
    """
    Get the pid from the pid file in the run directory, using the given
    process type and process name for the filename.
    
    @returns: pid of the process, or None if not running or file not found.
    """
    
    pidPath = getPidPath(type, name)
    if not os.path.exists(pidPath):
        return
    
    file = open(pidPath, 'r')
    pid = file.readline()
    file.close()
    if not pid or int(pid) == 0:
        return
 
    return int(pid)

def termPid(pid):
    """
    Send the given process a TERM signal.

    @returns: whether or not the process with the given pid was running
    """
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except OSError, e:
        if not e.errno == errno.ESRCH:
        # FIXME: unhandled error, maybe give some better info ?
            raise
        return False

def killPid(pid):
    """
    Send the given process a KILL signal.

    @returns: whether or not the process with the given pid was running
    """
    try:
        os.kill(pid, signal.SIGKILL)
        return True
    except OSError, e:
        if not e.errno == errno.ESRCH:
        # FIXME: unhandled error, maybe give some better info ?
            raise
        return False

def checkPidRunning(pid):
    """
    Check if the given pid is currently running.
    
    @returns: whether or not a process with that pid is active.
    """
    try:
        os.kill(pid, 0)
        return True
    except OSError, e:
        if e.errno is not errno.ESRCH:
            raise
    return False
 
def waitPidFile(type, name):
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

def checkPortFree(port):
    """
    Check if the given local port is free to accept on.

    @type port: int

    @rtype: boolean
    """
    assert type(port) == int
    fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        fd.bind(('', port))
    except socket.error:
        return False
    
    return True
    
def getFirstFreePort(startPort):
    """
    Get the first free port, starting from the given port.

    @type startPort: int

    @rtype: int
    """
    port = startPort
    while 1:
        if checkPortFree(port):
            return port
        port += 1

def checkRemotePort(host, port):
    """
    Check if the given remote host/port is accepting connections.

    @type port: int

    @rtype: boolean
    """
    assert type(port) == int
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, port))
    except socket.error:
        s.close()
        return False
    
    s.close()
    return True

def addressGetHost(a):
    """
    Get the host name of an IPv4 address.

    @type a: L{twisted.internet.address.IPv4Address}
    """
    if not isinstance(a, address.IPv4Address) and not isinstance(a,
        address.UNIXAddress):
        raise TypeError("object %r is not an IPv4Address or UNIXAddress" % a)
    if isinstance(a, address.UNIXAddress):
        return 'localhost'

    try:
        host = a.host
    except AttributeError:
        host = a[1]
    return host
        
def addressGetPort(a):
    """
    Get the port number of an IPv4 address.

    @type a: L{twisted.internet.address.IPv4Address}
    """
    assert(isinstance(a, address.IPv4Address))
    try:
        port = a.port
    except AttributeError:
        port = a[2]
    return port

def componentPath(componentName, parentName):
    """
    Create a path string out of the name of a component and its parent.
    """
    
    return '/%s/%s' % (parentName, componentName)

def objRepr(object):
    """
    Return a string giving the fully qualified class of the given object.
    """ 
    c = object.__class__
    return "%s.%s" % (c.__module__, c.__name__)

def pathToModuleName(path):
    """
    Convert the given (relative) path to the python module it would have to
    be imported as.

    Return None if the path is not a valid python module
    """
    # __init__ is last because it works on top of the first three
    valid = False
    suffixes = ['.pyc', '.pyo', '.py', os.path.sep + '__init__']
    for s in suffixes:
        if path.endswith(s):
            path = path[:-len(s)]
            valid = True

    # if the path still contains dots, it can't possibly be a valid module
    if not '.' in path:
        valid = True

    if not valid:
        return None

    return ".".join(path.split(os.path.sep))


