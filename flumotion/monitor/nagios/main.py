# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

"""
main for flumotion-nagios
"""

import sys

from twisted.internet import reactor, defer
from twisted.internet.defer import failure

from flumotion.common import common, errors, log
from flumotion.admin import admin

# registers serializables
from flumotion.common import planet

from flumotion.monitor.nagios import util, process, stream, component
from flumotion.monitor.nagios import log as nlog

from flumotion.admin.connections import parsePBConnectionInfoRecent

__version__ = "$Rev$"


# Because we run a reactor and use deferreds, the flow is slightly different
# from the usual Command flow.

# Nagios will first create a managerDeferred instance variable, which will
# allow subcommands to hook into the connection and schedule callbacks.

# Nagios will then parse the command line, allowing all subcommands to
# hook into this step with their respective handleOptions/parse/do methods.

# Subcommands are expected to use the ok/warning/critical methods to report
# a message and set the exit state.

# The Nagios root command will take care of stopping the reactor and returning
# the exit value.


class Manager(util.LogCommand):
    usage = "manager [-m manager-string] %command"
    description = "Run Nagios checks on Flumotion manager."

    managerDeferred = None # deferred that fires upon connection
    adminModel = None      # AdminModel connected to the manager

    subCommandClasses = [component.Mood, component.FlipFlop]

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

        def eb(f):
            self.debug(
                'parse: eb: failure %s' % log.getFailureMessage(f))
            # Nagios exceptions have already got their feedback covered
            if not f.check(util.NagiosException):
                util.unknown(log.getFailureMessage(f))
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

    def _connectedEb(self, f):
        if f.check(errors.ConnectionFailedError):
            # switch the failure and return an UNKNOWN status
            msg = "Unable to connect to manager."
            f = failure.Failure(util.NagiosUnknown(msg))
            util.unknown(msg)
        if f.check(errors.ConnectionRefusedError):
            # switch the failure and return a CRITICAL status
            msg = "Manager refused connection."
            f = failure.Failure(util.NagiosCritical(msg))
            util.critical(msg)
        # all other failures get forwarded to the managerDeferred errback as-is
        self.managerDeferred.errback(f)


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
    try:
        ret = c.parse(args[1:])
    except util.NagiosException, e:
        sys.stderr.write('%s\n' % e.message)
        return e.exitStatus


    return ret
