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
A set of common functions.
"""

import os 
import sys

from twisted.python import reflect

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

def argRepr(args=(), kwargs={}):
    assert (type(args) is tuple or
            type(args) is list)
    assert type(kwargs) is dict
    
    args = list(args)

    s = ''
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

def _listRecursivly(path):
    """
    I'm similar to os.listdir, but I work recursivly
    
    @param path: the path
    @type  path: string
    """

    
    retval = []
    if not os.path.isdir(path):
        return retval

    try:
        files = os.listdir(path)
    except OSError:
        pass
    else:
        for f in files:
            retval += _listRecursivly(os.path.join(path, f))

    if os.path.exists(os.path.join(path, '__init__.py')):
        retval.append(path)
            
    return retval

def _findPackages(path):
    """
    I take a directory and returns a list of python packages
    @param path: the path
    @type  path: string
    """

    dirs = _listRecursivly(path)
    if path in dirs:
        dirs.remove(path)
        
    packageNames = map(reflect.filenameToModuleName, dirs)
    
    # if os.path.exists(os.path.join(path, '__init__.py'))
    #    packageNames = map(lambda n: '.'.join(n.split('.')[1:]), packageNames)
    
    return packageNames

def addPackagePath(packagePath):
    """
    Add a package path so we can import stuff that's already partly present
    @param packagePath: path to add
    @type packagePath:  string
    """

    # First add the root to sys.path, so we can import stuff from it,
    # probably a good idea to live it there, if we want to do
    # fancy stuff later on.
    sys.path.append(os.path.abspath(packagePath))

    # Find the packages in the path and sort them,
    # the following algorithm only works if they're sorted.
    # By sorting the list we can ensure that a parent package
    # is always processed before one of its childrens
    packageNames = _findPackages(packagePath)
    packageNames.sort()

    if not packageNames:
        return

    # Since the list is sorted, the top module is the first item
    toplevelName = packageNames[0]
    
    # Append the bundle to the __path__ of the toplevel directory
    package = reflect.namedAny(toplevelName)
    package.__path__.append(os.path.join(packagePath, toplevelName))
    
    for packageName in packageNames[1:]:
        package = sys.modules.get(packageName, None)
        
        # If the package fails to import from our bundle, it means
        # That its funknown at the moment, import it from the package dir
        # (eg non bundle)
        if not package:
            package = reflect.namedAny(packageName)

        # Append ourselves to the packages __path__, this is all
        # magic that's required
        subPath = os.path.join(packagePath,
                               packageName.replace('.', os.sep))
        package.__path__.insert(0, subPath)

