# -*- Mode: Python -*-
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

"""spawn a local manager and worker"""

import gettext
import os
import shutil
import tempfile

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.error import ProcessDone
from twisted.internet.protocol import ProcessProtocol

from flumotion.common.signals import SignalMixin
from flumotion.configure import configure

__version__ = "$Rev$"
_ = gettext.gettext


class GreeterProcessProtocol(ProcessProtocol):

    def __init__(self):
        # no parent init
        self.deferred = Deferred()

    def processEnded(self, failure):
        if failure.check(ProcessDone):
            self.deferred.callback(None)
        else:
            self.deferred.callback(failure)


class LocalManagerSpawner(SignalMixin):
    """I am a class which can start a local manager and a worker which
    connects to it.
    It's mainly used by the greeter in a debug mode and by the testsuite
    """
    __signals__ = ['description-changed',
                   'error',
                   'finished',
                   ]

    def __init__(self, port):
        self._path = tempfile.mkdtemp(suffix='.flumotion')
        self._confDir = os.path.join(self._path, 'etc')
        self._logDir = os.path.join(self._path, 'var', 'log')
        self._runDir = os.path.join(self._path, 'var', 'run')
        self._port = port

    # Public

    def getPort(self):
        return self._port

    def getConfDir(self):
        return self._confDir

    def getLogDir(self):
        return self._logDir

    def getRunDir(self):
        return self._runDir

    def start(self):
        # We need to run 4 commands in a row, and each of them can fail
        d = Deferred()

        def chain(args, description, failMessage):
            d.addCallback(self._spawnProcess, args, description, failMessage)

        for serviceName in ['manager', 'worker']:
            chain(["flumotion",
                   "-C", self._confDir,
                   "-L", self._logDir,
                   "-R", self._runDir,
                   "create", serviceName,
                   "admin", str(self._port)],
                  _('Creating %s ...') % serviceName,
                  _("Could not create %s." % serviceName))
            chain(["flumotion",
                   "-C", self._confDir,
                   "-L", self._logDir,
                   "-R", self._runDir,
                   "start", serviceName, "admin"],
                  _('Starting %s ...' % serviceName),
                  _("Could not start %s." % serviceName))

        d.addErrback(lambda f: None)

        def done(result):
            self._finished()
        d.addCallback(done)

        # start chain
        d.callback(None)

        return d

    def stop(self, cleanUp=False):
        d = Deferred()

        def chain(args, description, failMessage):
            d.addCallback(self._spawnProcess, args, description, failMessage)

        for serviceName in [_('manager'), _('worker')]:
            chain(["flumotion",
                   "-C", self._confDir,
                   "-L", self._logDir,
                   "-R", self._runDir,
                   "stop", serviceName, "admin"], '', '')

        def done(result):
            if cleanUp:
                self._cleanUp()
        d.addCallback(done)

        # start chain
        d.callback(None)
        return d

    # Private

    def _finished(self):
        self.emit('finished')

    def _error(self, failure, failMessage, args):
        self.emit('error', failure, failMessage, args)

    def _setDescription(self, description):
        self.emit('description-changed', description)

    def _spawnProcess(self, result, args, description, failMessage):
        self._setDescription(description)
        args[0] = os.path.join(configure.sbindir, args[0])
        protocol = GreeterProcessProtocol()
        env = os.environ.copy()
        paths = env['PATH'].split(os.pathsep)
        if configure.bindir not in paths:
            paths.insert(0, configure.bindir)
        env['PATH'] = os.pathsep.join(paths)
        reactor.spawnProcess(protocol, args[0], args, env=env)

        def error(failure, failMessage):
            self._error(failure, failMessage, args)
            return failure
        protocol.deferred.addErrback(error, failMessage)
        return protocol.deferred

    def _cleanUp(self):
        shutil.rmtree(self._path)
