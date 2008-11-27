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

#
# FIXME: Everything here should be removed and be placed in
# modules which have more meaningful names.
#
# *********************************************************
# DO NOT ADD NEW SYMBOLS HERE, ADD THEM TO OTHER MODULES OR
# CREATE NEW ONES INSTEAD
# *********************************************************
#

import os

# Note: This module is loaded very early on, so
#       don't add any extra flumotion imports unless you
#       really know what you're doing.
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
    block.append("(C) Copyright 2004,2005,2006,2007,2008 Fluendo")
    return "\n".join(block)


def ensureDir(directory, description):
    """
    Ensure the given directory exists, creating it if not.

    @raise errors.FatalError: if the directory could not be created.
    """
    if not os.path.exists(directory):
        try:
            makedirs(directory)
        except OSError, e:
            from flumotion.common import errors
            raise errors.FatalError(
                "could not create %s directory %s: %s" % (
                description, directory, str(e)))


def componentPath(componentName, parentName):
    # FIXME: fix epydoc to correctly spell deprecated
    # F0.6
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
    assert componentId is not None, "componentId should not be None"
    l = componentId.split("/")
    assert len(l) == 3, \
        "componentId %s should have exactly two parts" % componentId
    assert l[0] == '', \
        "componentId %s should start with /" % componentId
    return (l[1], l[2])


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
    parts = feedId.split(":")
    assert len(parts) == 2, "feedId %s should contain exactly one ':'" % feedId
    return (parts[0], parts[1])


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
    parts = fullFeedId.split(":")
    assert len(parts) == 2, "%r should have exactly one colon" % fullFeedId
    flowName, componentName = parseComponentId(parts[0])
    return (flowName, componentName, parts[1])


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


def versionStringToTuple(versionString):
    """
    Converts a 3- or 4-number version string to a 4-tuple.

    @since: 0.5.3

    @type versionString: str

    @rtype: tuple of int
    """
    t = tuple(map(int, versionString.split('.')))
    if len(t) < 4:
        t = t + (0, )

    return t


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


#
# *********************************************************
# DO NOT ADD NEW SYMBOLS HERE, ADD THEM TO OTHER MODULES OR
# CREATE NEW ONES INSTEAD
# *********************************************************
#
