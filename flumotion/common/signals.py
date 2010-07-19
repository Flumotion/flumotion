# -*- Mode: Python; test-case-name: flumotion.test.test_common_signals -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2007 Fluendo, S.L. (www.fluendo.com).
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

"""synchronous message passing between python objects
"""

import warnings

from flumotion.common import log

__version__ = "$Rev$"


class SignalMixin(object):
    __signals__ = ()

    __signalConnections = None
    __signalId = 0

    def __ensureSignals(self):
        if self.__signalConnections is None:
            self.__signalConnections = {}

    def connect(self, signalName, proc, *args, **kwargs):
        self.__ensureSignals()

        if signalName not in self.__signals__:
            raise ValueError('Unknown signal for object of type %r: %s'
                             % (type(self), signalName))

        sid = self.__signalId
        self.__signalConnections[sid] = (signalName, proc, args, kwargs)
        self.__signalId += 1
        return sid

    def disconnect(self, signalId):
        self.__ensureSignals()

        if signalId not in self.__signalConnections:
            raise ValueError('Unknown signal ID: %s' % (signalId, ))

        del self.__signalConnections[signalId]

    def disconnectByFunction(self, function):
        self.__ensureSignals()

        for signalId, conn in self.__signalConnections.items():
            name, proc, args, kwargs = conn
            if proc == function:
                break
        else:
            raise ValueError(
                'No signal connected to function: %r' % (function, ))

        del self.__signalConnections[signalId]

    def emit(self, signalName, *args):
        self.__ensureSignals()
        if signalName not in self.__signals__:
            raise ValueError('Emitting unknown signal %s' % signalName)

        connections = self.__signalConnections
        for name, proc, pargs, pkwargs in connections.values():
            if name == signalName:
                try:
                    proc(self, *(args + pargs), **pkwargs)
                except Exception, e:
                    log.warning("signalmixin", "Exception calling "
                                "signal handler %r: %s", proc,
                                log.getExceptionMessage(e))
