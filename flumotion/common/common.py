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
import glob
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

def _listDirRecursively(path):
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
            retval += _listDirRecursively(os.path.join(path, f))

    if glob.glob(os.path.join(path, '*.py*')):
        retval.append(path)
            
    return retval

def _listPyFileRecursively(path):
    """
    I'm similar to os.listdir, but I work recursively and only return
    files representing python non-package modules.
    
    @param path: the path
    @type  path: string

    @rtype:      list
    @returns:    list of files underneath the given path containing python code
    """
    retval = []

    # get all the dirs containing python code
    dirs = _listDirRecursively(path)

    for dir in dirs:
        pyfiles = glob.glob(os.path.join(dir, '*.py*'))
        dontkeep = glob.glob(os.path.join(dir, '*__init__.py*'))
        for f in dontkeep:
            if f in pyfiles:
                pyfiles.remove(f)

        retval.extend(pyfiles)

    return retval

def _findPackageCandidates(path, prefix='flumotion.'):
    """
    I take a directory and return a list of candidate python packages.
    A package is a module containing modules; typically the directory
    with the same name as the package contains __init__.py

    @param path: the path
    @type  path: string
    """
    # this function also "guesses" candidate packages when __init__ is missing
    # so a bundle with only a subpackage is also detected
    dirs = _listDirRecursively(path)
    if path in dirs:
        dirs.remove(path)

    # chop off the base path to get a list of "relative" bundlespace paths
    bundlePaths = [x[len(path) + 1:] for x in dirs]

    # remove some common candidates, like .svn subdirs, or containing -
    isNotSvn = lambda x: x.find('.svn') == -1
    bundlePaths = filter(isNotSvn, bundlePaths)
    isNotDashed = lambda x: x.find('-') == -1
    bundlePaths = filter(isNotDashed, bundlePaths)

    # convert paths to module namespace
    bundlePackages = [".".join(x.split(os.path.sep)) for x in bundlePaths]

    # remove all not starting with prefix
    isInPrefix = lambda x: x.startswith(prefix)
    bundlePackages = filter(isInPrefix, bundlePackages)

    # sort them so that depending packages are after higher-up packages
    bundlePackages.sort()
        
    return bundlePackages

def _findEndModuleCandidates(path, prefix='flumotion.'):
    """
    I take a directory and return a list of candidate end python modules.
    These are non-package modules.

    @param path: the path
    @type  path: string
    """
    files = _listPyFileRecursively(path)
    #print "THOMAS: pyfiles in path %s: %r" % (path, files)

    # chop off the base path to get a list of "relative" bundlespace paths
    bundlePaths = [x[len(path) + 1:] for x in files]

    # remove some common candidates, like .svn subdirs, or containing -
    isNotSvn = lambda x: x.find('.svn') == -1
    bundlePaths = filter(isNotSvn, bundlePaths)
    isNotDashed = lambda x: x.find('-') == -1
    bundlePaths = filter(isNotDashed, bundlePaths)

    # convert paths to module namespace
    bundleModules = [pathToModuleName(x) for x in bundlePaths]

    # remove all not starting with prefix
    isInPrefix = lambda x: x.startswith(prefix)
    bundleModules = filter(isInPrefix, bundleModules)

    # sort them so that depending packages are after higher-up packages
    bundleModules.sort()

    # make unique
    res = {}
    for b in bundleModules: res[b] = 1

    return res.keys()

# FIXME: an extra key argument (used for bundle) might help in keeping
# track of old paths
# ie, it would ensure that only one packagePath per key is registered
def registerPackagePath(packagePath, prefix='flumotion'):
    """
    Register a given path as a path that can be imported from.
    Used to support partition of bundled code or import code from various
    uninstalled location.

    sys.path will also be changed to include this, and remove references
    to older packagePath's for the same bundle.

    @param packagePath: path to add under which the module namespaces live,
                        (ending in an md5sum, for flumotion purposes)
    @type  packagePath: string
    @param prefix:      prefix of the packages to be considered
    @type  prefix:      string
    """

    # FIXME: this should potentially also clean up older registered package
    # paths for the same bundle ?
    # This would involve us keeping track of what has been registered before,
    # and would probably involve creating an object to keep track of this state

    # First add the root to sys.path, so we can import stuff from it,
    # probably a good idea to live it there, if we want to do
    # fancy stuff later on.
    packagePath = os.path.abspath(packagePath)
    if not os.path.exists(packagePath):
        log.warning('bundle', 'registering a non-existing package path %s' %
            packagePath)

    log.log('bundle', 'registering packagePath %s' % packagePath)

    # check if a packagePath for this bundle was already registered
    # by stripping off the last part, which is the md5sum
    oneup = os.path.split(packagePath)[0]
    if oneup:
        paths = sys.path
        targets = [x for x in paths if x.startswith(oneup) and x != packagePath]

    for path in targets:
        log.log('bundle', 'removing old packagePath %s from sys.path' % path)
        sys.path.remove(path)

    # put packagePath at the top of sys.path if not in there
    if not packagePath in sys.path:
        log.log('bundle', 'adding packagePath %s to sys.path' % packagePath)
        sys.path.insert(0, packagePath)

    # Find the packages in the path and sort them,
    # the following algorithm only works if they're sorted.
    # By sorting the list we can ensure that a parent package
    # is always processed before one of its children
    print "THOMAS: packagePath: %s" % packagePath
    packageNames = _findPackageCandidates(packagePath, prefix)
    print "THOMAS: modules: %r" % packageNames
    packageNames.sort()

    if not packageNames:
        log.log('bundle', 'packagePath %s does not have package candidates' %
            packagePath)
        return

    log.log('bundle', 'package candidates %r' % packageNames)
    # Since the list is sorted, the top module is the first item
    log.log('bundle', 'packagePath %s has packageNames %r' % (
        packagePath, packageNames)) 

    toplevelName = packageNames[0]
    
    # Insert or move the bundle's absolute path to the top of __path__ of
    # each of its higher-level packages, so reload() will take the new path

    # FIXME: for complete correctness, it'd be good to remove the path
    # for the previous bundle if there is a previous bundle
    partials = []
    for partial in toplevelName.split("."):
        partials.append(partial)
        name = ".".join(partials)
        try:
            package = reflect.namedAny(name)
        #except ValueError: # Empty module name, ie. subdir has no __init__
        #    continue
        except:
            print "ERROR: could not reflect name %s" % name
            raise
        path = os.path.join(packagePath, name.replace('.', os.sep))
        if path in package.__path__:
            package.__path__.remove(path)
        package.__path__.insert(0, path)
        
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

        # insert at front because FLU_REGISTRY_PATH paths should override
        # base components, and because subsequent reload() should prefer
        # the latest registered path
        # FIXME: we might eventually want to remove old paths for the same
        # bundle   
        if subPath in package.__path__:
            log.log('bundle', 'moving subPath %s to top for package %r' % (
                subPath, package))
            package.__path__.remove(subPath)
            package.__path__.insert(0, subPath)
        else:
            log.log('bundle', 'inserting subPath %s for package %r' % (
                subPath, package))
            package.__path__.insert(0, subPath)

    # now rebuild all non-package modules in this packagePath
    print "THOMAS: packagePath: %s" % packagePath
    moduleNames = _findEndModuleCandidates(packagePath)
    print "THOMAS: modules: %r" % moduleNames
    for name in moduleNames:
        if name in sys.modules:
            print "THOMAS: rebuilding %s" % name
            module = reflect.namedAny(name)
            rebuild.rebuild(module)

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
    Get the port number of an IPv4 address.

    @type a: L{twisted.internet.address.IPv4Address}
    """
    assert(isinstance(a, address.IPv4Address))
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
    """
    if path.endswith('.pyc'): path = path[:-4]
    if path.endswith('.py'): path = path[:-3]
    if path.endswith('__init__'): path = path[:-9]

    return ".".join(path.split(os.path.sep))


