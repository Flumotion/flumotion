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
main for flumotion-nagios
"""

from twisted.internet import reactor, defer

from flumotion.common import common, errors, planet, log
from flumotion.admin.connections import parsePBConnectionInfoRecent
from flumotion.admin import  admin

from flumotion.monitor.nagios import util, process, stream, log as nlog

__version__ = "$Rev$"


class Mood(util.LogCommand):
    description = "Check the mood of a component."
    usage = "mood [mood options] [component id]"

    def addOptions(self):
        default = "hungry"
        self.parser.add_option('-w', '--warning',
            action="store", dest="warning",
            help="moods to give a warning for (defaults to %s)" % (default),
            default=default)
        default = "sleeping,lost,sad"
        self.parser.add_option('-c', '--critical',
            action="store", dest="critical",
            help="moods to give a critical for (defaults to %s)" % (default),
            default=default)

    def handleOptions(self, options):
        self._warning = options.warning.split(',')
        self._critical = options.critical.split(',')

    def do(self, args):
        if not args:
            self.stderr.write(
                'Please specify a component to check the mood of.\n.')
            return 3

        self._component = args[0]
        # call our callback after connecting
        self.parentCommand.managerDeferred.addCallback(self._callback)

    def _callback(self, result):
        d = self.parentCommand.adminModel.callRemote('getPlanetState')

        def gotPlanetStateCb(result):
            self.debug('gotPlanetStateCb')
            c = util.findComponent(result, self._component)
            if not c:
                return util.unknown('Could not find component %s' %
                    self._component)

            moodValue = c.get('mood')
            moodName = planet.moods.get(moodValue).name

            if moodName in self._critical:
                return util.critical('Component %s is %s' % (self._component,
                    moodName))

            if moodName in self._warning:
                return util.warning('Component %s is %s' % (self._component,
                    moodName))

            return util.ok('Component %s is %s' % (self._component,
                moodName))

        d.addCallback(gotPlanetStateCb)
        d.addCallback(lambda e: setattr(reactor, 'exitStatus', e))
        return d

# Because we run a reactor and use deferreds, the flow is slightly different
# from the usual Command flow.

# Manager will first create a managerDeferred instance variable, which will
# allow subcommands to hook into the connection and schedule callbacks.

# Manager will then parse the command line, allowing all subcommands to
# hook into this step with their respective handleOptions/parse/do methods.

# Subcommands are expected to use the ok/warning/critical methods to report
# a message and set the exit state.

# The Manager root command will take care of stopping the reactor and returning
# the exit value.


class Manager(util.LogCommand):
    usage = "manager [-m manager-string] %command"
    description = "Run Nagios checks on Flumotion manager."

    managerDeferred = None # deferred that fires upon connection
    adminModel = None      # AdminModel connected to the manager

    subCommandClasses = [Mood, ]

    def addOptions(self):
        default = "user:test@localhost:7531"
        self.parser.add_option('-m', '--manager',
            action="store", type="string", dest="manager",
            help="the manager connection string, " \
                 "in the form [username[:password]@]host:port " \
                 "(defaults to %s)" % default,
            default=default)
        self.parser.add_option('-T', '--transport',
            action="store_true", dest="transport",
            help="transport protocol to use (tcp/ssl) [default ssl]",
            default="ssl")

    def parse(self, argv):
        # instantiated here so our subcommands can chain to it
        self.managerDeferred = defer.Deferred()

        self.debug('parse: chain up')
        # chain up to parent first
        # all subcommands will have a chance to chain up to the deferred
        ret = util.LogCommand.parse(self, argv)
        self.debug('parse: chained up')

        if ret is None:
            self.debug('parse returned None, help/usage printed')
            return ret

        if ret:
            self.debug('parse returned %r' % ret)
            return ret

        if self.parser.help_printed or self.parser.usage_printed:
            return 0

        # now connect
        self.debug('parse: connect')
        self.connect(self.options)

        # chain up an exit after our child commands have had the chance.

        def cb(result):
            self.debug('parse: cb: done')
            reactor.callLater(0, reactor.stop)

        def eb(failure):
            self.debug(
                'parse: eb: failure %s' % log.getFailureMessage(failure))
            # Nagios exceptions have already got their feedback covered
            if not failure.check(util.NagiosException):
                util.unknown(log.getFailureMessage(failure))
            reactor.callLater(0, reactor.stop)
        self.managerDeferred.addCallback(cb)
        self.managerDeferred.addErrback(eb)

        # now run the reactor
        self.debug('parse: run the reactor')
        self.run()
        self.debug('parse: ran the reactor')

        return reactor.exitStatus

    def run(self):
        """
        Run the reactor.

        Resets .exitStatus, and returns its value after running the reactor.
        """
        # run the reactor

        self.debug('running reactor')
        # We cheat by putting the exit code in the reactor.
        reactor.exitStatus = 0
        reactor.run()
        self.debug('ran reactor')

        return reactor.exitStatus

    def connect(self, options):
        connection = parsePBConnectionInfoRecent(options.manager,
                                                 options.transport == 'ssl')

        # platform-3/trunk compatibility stuff to guard against
        # gratuitous changes
        try:
            # platform-3
            self.adminModel = admin.AdminModel(connection.authenticator)
            self.debug("code is platform-3")
        except TypeError:
            # trunk
            self.adminModel = admin.AdminModel()
            self.debug("code is trunk")

        if hasattr(self.adminModel, 'connectToHost'):
            # platform-3
            d = self.adminModel.connectToHost(connection.host,
                connection.port, not connection.use_ssl)
        else:
            d = self.adminModel.connectToManager(connection)

        d.addCallback(self._connectedCb)
        d.addErrback(self._connectedEb)

    def _connectedCb(self, result):
        self.debug('Connected to manager.')
        self.managerDeferred.callback(result)

    def _connectedEb(self, failure):
        if failure.check(errors.ConnectionFailedError):
            util.unknown("Unable to connect to manager.")
        if failure.check(errors.ConnectionRefusedError):
            util.critical("Manager refused connection.")
        self.managerDeferred.errback(failure)


class Stream(util.LogCommand):
    description = "Run checks on streams."
    usage = "stream %command"

    subCommandClasses = [stream.Check]


class Nagios(util.LogCommand):
    usage = "%prog %command"
    description = "Run Flumotion-related Nagios checks."

    subCommandClasses = [Manager, Stream, process.ProcessCommand, nlog.Log]

    def addOptions(self):
        self.parser.add_option('-v', '--version',
            action="store_true", dest="version",
            help="show version information")

    def handleOptions(self, options):
        self.debug('Nagios: handleOptions')
        if options.version:
            print common.version("flumotion-nagios")
            return 0


def main(args):
    c = Nagios()
    ret = c.parse(args[1:])

    return ret
