# -*- Mode: Python; test-case-name: flumotion.test.test_common -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/common/common.py: common functionality
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
import sys
import time
import signal

from twisted.python import reflect, rebuild
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
    block.append("(C) Copyright 2004 Fluendo")
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

def _listRecursively(path):
    """
    I'm similar to os.listdir, but I work recursively and only return
    directories containing python code.
    
    @param path: the path
    @type  path: string
    """
    retval = []
    # files are never returned, only directories
    if not os.path.isdir(path):
        return retval

    try:
        files = os.listdir(path)
    except OSError:
        pass
    else:
        for f in files:
            # this only adds directories since files are not returned
            retval += _listRecursively(os.path.join(path, f))

    import glob
    if glob.glob(os.path.join(path, '*.py*')):
        retval.append(path)
            
    return retval

def _findPackageCandidates(path):
    """
    I take a directory and returns a list of candidate python packages.

    @param path: the path
    @type  path: string
    """
    # this function also "guesses" candidate packages when __init__ is missing
    # so a bundle with only a subpackage is also detected
    dirs = _listRecursively(path)
    if path in dirs:
        dirs.remove(path)

    # chop off the base path to get a list of "relative" bundlespace paths
    bundlePaths = [x[len(path) + 1:] for x in dirs]
    bundlePackages = [".".join(x.split(os.path.sep)) for x in bundlePaths]

    # sort them so that depending packages are after higher-up packages
    bundlePackages.sort()
        
    return bundlePackages

def registerPackagePath(packagePath):
    """
    Register a given path as a path that can be imported from.
    Used to support partition of bundled code.

    @param packagePath: path to add
    @type  packagePath: string
    """

    # FIXME: this should potentially also clean up older registered package
    # paths for the same bundle ?
    # This would involve us keeping track of what has been registered before,
    # and would probably involve creating an object to keep track of this state

    # First add the root to sys.path, so we can import stuff from it,
    # probably a good idea to live it there, if we want to do
    # fancy stuff later on.
    abs = os.path.abspath(packagePath)
    if not abs in sys.path:
        sys.path.append(abs)

    # Find the packages in the path and sort them,
    # the following algorithm only works if they're sorted.
    # By sorting the list we can ensure that a parent package
    # is always processed before one of its childrens
    packageNames = _findPackageCandidates(packagePath)
    packageNames.sort()

    if not packageNames:
        return

    # Since the list is sorted, the top module is the first item
    log.log('bundle', 'packagePath %s has packageNames %r' % (
        packagePath, packageNames)) 

    toplevelName = packageNames[0]
    
    # Append the bundle's absolute path to the __path__ of
    # each of its higher-level packages
    partials = []
    for partial in toplevelName.split("."):
        partials.append(partial)
        name = ".".join(partials)
        try:
            package = reflect.namedAny(name)
        except:
            print "ERROR: could not reflect name %s" % name
            raise
        path = os.path.join(packagePath, name.replace('.', os.sep))
        if not path in package.__path__:
            package.__path__.append(path)
        
    for packageName in packageNames[1:]:
        package = sys.modules.get(packageName, None)
        
        # If the package fails to import from our bundle, it means
        # that it's unknown at the moment, import it from the package dir
        # (eg non bundle)
        if not package:
            package = reflect.namedAny(packageName)

        # Append ourselves to the packages __path__, this is all
        # magic that's required
        subPath = os.path.join(packagePath,
                               packageName.replace('.', os.sep))

        # rebuild the package
        rebuild.rebuild(package)

        if not subPath in package.__path__:
            # insert because FLU_REGISTRY_PATH paths should override
            # base components
            package.__path__.insert(0, subPath)

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

 
def writePidFile(type, name):
    """
    Write a pid file in the run directory, using the given process type
    and process name for the filename.
    """
    
    ensureDir(configure.rundir, "rundir")
    pid = os.getpid()
    pidPath = os.path.join(configure.rundir, '%s.%s.pid' % (type, name))
    file = open(pidPath, 'w')
    file.write("%d\n" % pid)
    file.close()
 
def deletePidFile(type, name):
    """
    Delete the pid file in the run directory, using the given process type
    and process name for the filename.
    """
    
    pidPath = os.path.join(configure.rundir, '%s.%s.pid' % (type, name))
    os.unlink(pidPath)
 
def getPid(type, name):
    """
    Get the pid from the pid file in the run directory, using the given
    process type and process name for the filename.
    
    @returns: pid of the process, or None.
    """
    
    pidPath = os.path.join(configure.rundir, '%s.%s.pid' % (type, name))
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
    Wait for the given process type and name to have started.
    Return the pid if it started successfully, or None if it didn't.
    """
    
    mtime = os.stat(configure.rundir)[8]
    pid = getPid(type, name)
    if pid:
        return pid
         
    while os.stat(configure.rundir)[8] == mtime:
        pid = getPid(type, name)
        #if pid:
        #    return pid
        time.sleep(0.1)
 
    pid = getPid(type, name)
    return pid
 
def waitForKill():
    """
    Wait until we get killed by someone else.
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

# moods
class Moods: pass
moods = Moods()
moods.HAPPY = 0
moods.SAD = 1
moods.LOST = 2
moods.HUNGRY = 3
moods.WAKING = 4
moods.SLEEPING = 5
