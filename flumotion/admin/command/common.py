# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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
common functionality for flumotion-admin-command
"""

import sys

# we need to have the unjelliers registered
# FIXME: why is this not in flumotion.admin.admin ?
from flumotion.common import componentui, common

# FIXME: move
from flumotion.monitor.nagios import util

__version__ = "$Rev: 6562 $"

# explain the complicated arguments system for the invoke methods
ARGUMENTS_DESCRIPTION = """
Arguments to the method are passed using an argument list string, and the
arguments (matching the argument list string).

Example: "method ss one two" would invoke remote_method("one", "two")
"""

# code copied over from old flumotion-command


class ParseException(Exception):
    pass

# FIXME: don't print darn it


def parseTypedArgs(spec, args):

    def _readFile(filename):
        try:
            f = open(filename)
            contents = f.read()
            f.close()
            return contents
        except OSError:
            raise ParseException("Failed to read file %s" % (filename, ))

    def _doParseTypedArgs(spec, args):
        accum = []
        while spec:
            argtype = spec.pop(0)
            parsers = {'i': int, 's': str, 'b': common.strToBool,
                'F': _readFile}
            if argtype == ')':
                return tuple(accum)
            elif argtype == '(':
                accum.append(_doParseTypedArgs(spec, args))
            elif argtype == '}':
                return dict(accum)
            elif argtype == '{':
                accum.append(_doParseTypedArgs(spec, args))
            elif argtype == ']':
                return accum
            elif argtype == '[':
                accum.append(_doParseTypedArgs(spec, args))
            elif argtype not in parsers:
                raise ParseException('Unknown argument type: %r'
                                     % argtype)
            else:
                parser = parsers[argtype]
                try:
                    arg = args.pop(0)
                except IndexError:
                    raise ParseException('Missing argument of type %r'
                                         % parser)
                try:
                    accum.append(parser(arg))
                except Exception, e:
                    raise ParseException('Failed to parse %s as %r: %s'
                                         % (arg, parser, e))

    spec = list(spec) + [')']
    args = list(args)

    try:
        res = _doParseTypedArgs(spec, args)
    except ParseException, e:
        print e.args[0]
        return None

    if args:
        print 'Left over arguments:', args
        return None
    else:
        return res

# helper subclass for leaf commands


class AdminCommand(util.LogCommand):

    def do(self, args):
        # call our callback after connecting
        self.getRootCommand().loginDeferred.addCallback(self._callback, args)

    def _callback(self, result, args):
        self.debug('invoking doCallback with args %r', args)
        return self.doCallback(args)

    def doCallback(self, args):
        """
        Subclasses should implement this as an alternative to the normal do
        method. It will be called after a connection to the manager is made.

        Don't forget to return a deferred you create to properly chain
        execution.
        """
        raise NotImplementedError(
            "subclass %r should implement doCallback" % self.__class__)


class Exited(Exception):
    """
    Raised when the code wants the program to exit with a return value and
    a message.
    """

    def __init__(self, code, msg=None):
        self.args = (code, msg)
        self.code = code
        self.msg = msg


def errorRaise(msg):
    raise Exited(1, "ERROR: " + msg)


def errorReturn(msg):
    sys.stderr.write("ERROR: " + msg + '\n')
    return 1
