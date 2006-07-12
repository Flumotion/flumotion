# -*- Mode: Python; test-case-name: flumotion.test.test_common -*-
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
small common functions used by all processes
"""

import errno
import os 
import socket
import sys
import time
import signal

from twisted.python import reflect, rebuild, components
from twisted.internet import address
import twisted.copyright

from flumotion.common import log

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
    block.append("(C) Copyright 2004,2005,2006 Fluendo")
    return "\n".join(block)
             
def mergeImplements(*classes):
    """
    Merge the __implements__ tuples of the given classes into one tuple.
    """
    if twisted.copyright.version[0] < '2':
        allYourBase = []
        for clazz in classes:
            allYourBase += getattr(clazz, '__implements__', ())
        return tuple(allYourBase)
    else:
        allYourBase = ()
        for clazz in classes:
            try:
                interfaces = [i for i in clazz.__implemented__]
            except AttributeError:
                # with twisted 2.0.1, we get AttributeError with a simple
                # class C: pass
                # which does not have C.__implemented__
                interfaces = []
            for interface in interfaces:
                allYourBase += (interface,)
        return allYourBase

def daemonize(stdin='/dev/null', stdout='/dev/null', stderr='/dev/null',
              directory='/'):
    '''
    This forks the current process into a daemon.
    The stdin, stdout, and stderr arguments are file names that
    will be opened and be used to replace the standard file descriptors
    in sys.stdin, sys.stdout, and sys.stderr.
    These arguments are optional and default to /dev/null.
    Note that stderr is opened unbuffered, so
    if it shares a file with stdout then interleaved output
    may not appear in the order that you expect.

    The fork will switch to the given directory.
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
    try:
        os.chdir(directory) 
    except OSError, e: 
        from flumotion.common import errors
        raise errors.SystemError, "Failed to change directory to %s: %s" % (
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
            from flumotion.common import errors
            raise errors.SystemError, "could not create %s directory %s" % (
                description, dir)

def getPidPath(type, name=None):
    """
    Get the full path to the pid file for the given process type and name.
    """
    if name:
        return os.path.join(configure.rundir, '%s.%s.pid' % (type, name))
    else:
        return os.path.join(configure.rundir, '%s.pid' % type)
 
def writePidFile(type, name=None):
    """
    Write a pid file in the run directory, using the given process type
    and process name for the filename.
    """
    ensureDir(configure.rundir, "rundir")
    pid = os.getpid()
    file = open(getPidPath(type, name), 'w')
    file.write("%d\n" % pid)
    file.close()
 
def deletePidFile(type, name=None):
    """
    Delete the pid file in the run directory, using the given process type
    and process name for the filename.
    """
    os.unlink(getPidPath(type, name))
 
def getPid(type, name=None):
    """
    Get the pid from the pid file in the run directory, using the given
    process type and process name for the filename.
    
    @returns: pid of the process, or None if not running or file not found.
    """
    
    pidPath = getPidPath(type, name)
    log.log('common', 'pidfile for %s %s is %s' % (type, name, pidPath))
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

    @deprecated Use @componentId instead
    """
    return '/%s/%s' % (parentName, componentName)

def componentId(parentName, componentName):
    """
    Create a componentId based on the parentName and componentName.

    @since: 0.3.1

    @rtype: str
    """
    return '/%s/%s' % (parentName, componentName)

def parseComponentId(componentId):
    """
    @since: 0.3.1

    @rtype:  tuple of (str, str)
    @return: tuple of (flowName, componentName)
    """
    list = componentId.split("/")
    assert len(list) == 3
    assert list[0] == ''
    return (list[1], list[2])

def feedId(componentName, feedName):
    """
    Create a feedId based on the componentName and feedName.

    @since: 0.3.1

    @rtype: str
    """
    return "%s:%s" % (componentName, feedName)

def parseFeedId(feedId):
    """
    @since: 0.3.1

    @rtype:  tuple of (str, str)
    @return: tuple of (componentName, feedName)
    """
    list = feedId.split(":")
    assert len(list) == 2
    return (list[0], list[1])

def fullFeedId(flowName, componentName, feedName):
    """
    Create a fullFeedId based on the flowName, componentName and feedName.

    @since: 0.3.1

    @rtype: str
    """
    return feedId(componentId(flowName, componentName), feedName)

def parseFullFeedId(fullFeedId):
    """
    @since: 0.3.1

    @rtype:  tuple of (str, str, str)
    @return: tuple of (flowName, componentName, feedName)
    """
    list = fullFeedId.split(":")
    assert len(list) == 2
    flowName, componentName = parseComponentId(list[0])
    return (flowName, componentName, list[1])

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

def getLL():
    """
    Return the (at most) two-letter language code set for message translation.
    """
    # LANGUAGE is a GNU extension; it can be colon-seperated but we ignore the
    # advanced stuff. If that's not present, just use LANG, as normal.
    language = os.environ.get('LANGUAGE', None)
    if language != None:
      LL = language[:2]
    else:
      lang = os.environ.get('LANG', 'en')
      LL = lang[:2]

    return LL

def gettexter(domain):
    """
    Returns a method you can use as _ to translate strings for the given
    domain.
    """
    import gettext
    return lambda s: gettext.dgettext(domain, s)

def compareVersions(first, second):
    """
    Compares two version strings.  Returns -1, 0 or 1 if first is smaller than,
    equal to or larger than second.

    @type  first:  str
    @type  second: str

    @rtype: int
    """
    if first == second:
        return 0

    firsts = first.split(".")
    seconds = second.split(".")

    while firsts or seconds:
        f = 0
        s = 0
        try:
            f = int(firsts[0])
            del firsts[0]
        except IndexError:
            pass
        try:
            s = int(seconds[0])
            del seconds[0]
        except IndexError:
            pass

        if f < s:
            return -1
        if f > s:
            return 1

    return 0

def _uniq(l, key=lambda x: x):
    """
    Filters out duplicate entries in a list.
    """
    out = []
    for x in l:
        if key(x) not in [key(y) for y in out]:
            out.append(x)
    return out

def _call_each_method(obj, method, mro, args, kwargs):
    procs = []
    for c in mro:
        if hasattr(c, method):
            proc = getattr(c, method)
            assert callable(proc) and hasattr(proc, 'im_func'),\
                   'attr %s of class %s is not a method' % (method, c)
            procs.append(proc)

    # In a hierarchy A -> B, if A implements the method, B will inherit
    # it as well. Compare the functions implementing the methods so as
    # to avoid calling them twice.
    procs = _uniq(procs, lambda proc: proc.im_func)

    for proc in procs:
        proc(obj, *args, **kwargs)

def call_each_method(obj, method, *args, **kwargs):
    """
    Invoke all implementations of a method on an object.

    Searches for method implementations in the object's class and all of
    the class' superclasses. Calls the methods in method resolution
    order, which goes from subclasses to superclasses.
    """
    mro = type(obj).__mro__
    _call_each_method(obj, method, mro, args, kwargs)

def call_each_method_reversed(obj, method, *args, **kwargs):
    """
    Invoke all implementations of a method on an object.

    Like call_each_method, but calls the methods in reverse method
    resolution order, from superclasses to subclasses.
    """
    # do a list() so as to copy the mro, we reverse the list in
    # place so as to start with the base class
    mro = list(type(obj).__mro__)
    mro.reverse()
    _call_each_method(obj, method, mro, args, kwargs)
    
class InitMixin(object):
    """
    A mixin class to help with object initialization.

    In some class hierarchies, __init__ is only used for initializing
    instance variables. In these cases it is advantageous to avoid the
    need to "chain up" to a parent implementation of a method. Adding
    this class to your hierarchy will, for each class in the object's
    class hierarchy, call the class's init() implementation on the
    object.

    Note that the function is called init() without underscrores, and
    that there is no need to chain up to superclasses' implementations.

    Uses call_each_method_reversed() internally.
    """

    def __init__(self, *args, **kwargs):
        call_each_method_reversed(self, 'init', *args, **kwargs)
