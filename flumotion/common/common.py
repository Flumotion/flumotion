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

"""
small common functions used by all processes
"""

import os
import time

# Note: This module is loaded very early on, so
#       don't add any extra flumotion imports unless you
#       really know what you're doing.
from flumotion.common import log
from flumotion.common.python import makedirs
from flumotion.configure import configure

__version__ = "$Rev$"

def version(binary):
    """
    Print a version block for the flumotion binaries.

    @arg binary: name of the binary
    @type binary: string
    """

    block = []
    block.append("%s %s" % (binary, configure.version))
    block.append("part of Flumotion - a streaming media server")
    block.append("(C) Copyright 2004,2005,2006,2007 Fluendo")
    return "\n".join(block)

def mergeImplements(*classes):
    """
    Merge the __implements__ tuples of the given classes into one tuple.
    """
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

def ensureDir(dir, description):
    """
    Ensure the given directory exists, creating it if not.
    Raises a SystemError if this fails, including the given description.
    """
    if not os.path.exists(dir):
        try:
            makedirs(dir)
        except OSError, e:
            from flumotion.common import errors
            raise errors.SystemError(
                "could not create %s directory %s: %s" % (
                description, dir, str(e)))


# FIXME: fix epydoc to correctly spell deprecated
def componentPath(componentName, parentName):
    """
    Create a path string out of the name of a component and its parent.

    @depreciated: Use @componentId instead
    """
    return '/%s/%s' % (parentName, componentName)

def componentId(parentName, componentName):
    """
    Create a C{componentId} based on the C{parentName} and C{componentName}.

    A C{componentId} uniquely identifies a component within a planet.

    @since: 0.3.1

    @rtype: str
    """
    return '/%s/%s' % (parentName, componentName)

def parseComponentId(componentId):
    """
    Parses a component id ("/flowName/componentName") into its parts.

    @since: 0.3.1

    @rtype:  tuple of (str, str)
    @return: tuple of (flowName, componentName)
    """
    list = componentId.split("/")
    assert len(list) == 3, \
        "componentId %s should have exactly two components" % componentId
    assert list[0] == '', \
        "componentId %s should start with /" % componentId
    return (list[1], list[2])

def feedId(componentName, feedName):
    """
    Create a C{feedId} based on the C{componentName} and C{feedName}.

    A C{feedId} uniquely identifies a feed within a flow or atmosphere.
    It identifies the feed from a feeder to an eater.

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
    assert not feedId.startswith('/'), \
           "feedId must not start with '/': %s" % feedId
    list = feedId.split(":")
    assert len(list) == 2, "feedId %s should contain exactly one ':'" % feedId
    return (list[0], list[1])

def fullFeedId(flowName, componentName, feedName):
    """
    Create a C{fullFeedId} based on the C{flowName}, C{componentName} and
    C{feedName}.

    A C{fullFeedId} uniquely identifies a feed within a planet.

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

def checkVersionsCompat(version, against):
    """Checks if two versions are compatible.

    Versions are compatible if they are from the same minor release. In
    addition, unstable (odd) releases are treated as compatible with
    their subsequent stable (even) releases.

    @param version: version to check
    @type  version: tuple of int
    @param against: version against which we are checking. For versions
                    of core Flumotion, this may be obtained by
                    L{flumotion.configure.configure.version}.
    @type  against: tuple of int
    @returns: True if a configuration from version is compatible with
              against.
    """
    if version == against:
        return True
    elif version > against:
        # e.g. config generated against newer flumotion than what is
        # running
        return False
    elif len(version) < 2 or len(against) < 2:
        return False
    elif version[0] != against[0]:
        return False
    else:
        round2 = lambda x: ((x + 1) // 2) * 2
        return round2(version[1]) == round2(against[1])

def versionTupleToString(versionTuple):
    """
    Converts a version tuple to a string.  If the tuple has a zero nano number,
    it is dropped from the string.

    @since: 0.4.1

    @type versionTuple: tuple

    @rtype: str
    """
    if len(versionTuple) == 4 and versionTuple[3] == 0:
        versionTuple = versionTuple[:3]

    return ".".join([str(i) for i in versionTuple])

def _uniq(l, key=lambda x: x):
    """
    Filters out duplicate entries in a list.
    """
    out = []
    for x in l:
        if key(x) not in [key(y) for y in out]:
            out.append(x)
    return out

def get_all_methods(obj, method, subclass_first):
    mro = type(obj).__mro__
    if not subclass_first:
        # do a list() so as to copy the mro, we reverse the list in
        # place so as to start with the base class
        mro = list(mro)
        mro.reverse()
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
    return _uniq(procs, lambda proc: proc.im_func)

def call_each_method(obj, method, *args, **kwargs):
    """
    Invoke all implementations of a method on an object.

    Searches for method implementations in the object's class and all of
    the class' superclasses. Calls the methods in method resolution
    order, which goes from subclasses to superclasses.
    """
    for proc in get_all_methods(obj, method, True):
        proc(obj, *args, **kwargs)

def call_each_method_reversed(obj, method, *args, **kwargs):
    """
    Invoke all implementations of a method on an object.

    Like call_each_method, but calls the methods in reverse method
    resolution order, from superclasses to subclasses.
    """
    for proc in get_all_methods(obj, method, False):
        proc(obj, *args, **kwargs)

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

def strToBool(string):
    """
    @type  string: str

    @return: True if the string represents a value we interpret as true.
    """
    if string in ('True', 'true', '1', 'yes'):
        return True

    return False

def assertSSLAvailable():
    """Assert that twisted has support for SSL connections.
    """
    from twisted.internet import posixbase
    from flumotion.common import errors

    if not posixbase.sslEnabled:
        raise errors.NoSSLError()

class Poller(object, log.Loggable):
    """
    A class representing a cancellable, periodic call to a procedure,
    which is robust in the face of exceptions raised by the procedure.

    The poller will wait for a specified number of seconds between
    calls. The time taken for the procedure to complete is not counted
    in the timeout. If the procedure returns a deferred, rescheduling
    will be performed after the deferred fires.

    For example, if the timeout is 10 seconds and the procedure returns
    a deferred which fires 5 seconds later, the next invocation of the
    procedure will be performed 15 seconds after the previous
    invocation.
    """

    def __init__(self, proc, timeout, immediately=False, start=True):
        """
        @param proc:        a procedure of no arguments
        @param timeout:     float number of seconds to wait between calls
        @param immediately: whether to immediately call proc, or to wait
                            until one period has passed
        @param start:       whether to start the poller (defaults to True)
        """
        from twisted.internet import reactor
        from twisted.internet import defer

        self._callLater = reactor.callLater
        self._maybeDeferred = defer.maybeDeferred

        self.proc = proc
        self.logName = 'poller-%s' % proc.__name__
        self.timeout = timeout

        self._dc = None
        self.running = False

        if start:
            self.start(immediately)

    def start(self, immediately=False):
        """Start the poller.

        This procedure is called during __init__, so it is normally not
        necessary to call it. It will ensure that the poller is running,
        even after a previous call to stop().

        @param immediately: whether to immediately invoke the poller, or
        to wait until one period has passed
        """
        if self.running:
            self.debug('already running')
        else:
            self.running = True
            self._reschedule(immediately)

    def _reschedule(self, immediately=False):
        assert self._dc is None
        if self.running:
            if immediately:
                self.run()
            else:
                self._dc = self._callLater(self.timeout, self.run)
        else:
            self.debug('shutting down, not rescheduling')

    def run(self):
        """Run the poller immediately, regardless of when it was last
        run.
        """
        def reschedule(v):
            self._reschedule()
            return v

        if self._dc and self._dc.active():
            # we don't get here in the normal periodic case, only for
            # explicit run() invocations
            self._dc.cancel()
        self._dc = None

        d = self._maybeDeferred(self.proc)
        d.addBoth(reschedule)

    def stop(self):
        """Stop the poller.

        This procedure ensures that the poller is stopped. It may be
        called multiple times.
        """
        if self._dc:
            self._dc.cancel()
            self._dc = None
        self.running = False

def strftime(format, t):
    """A version of time.strftime that can handle unicode formats."""
    out = []
    percent = False
    for c in format:
        if percent:
            out.append(time.strftime('%'+c, t))
            percent = False
        elif c == '%':
            percent = True
        else:
            out.append(c)
    if percent:
        out.append('%')
    return ''.join(out)
