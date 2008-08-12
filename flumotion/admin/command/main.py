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
main for flumotion-command
"""

import sys

from twisted.internet import reactor, defer

from flumotion.common import errors, log
from flumotion.admin import connections, admin

from flumotion.monitor.nagios import util

from flumotion.admin.command import component, manager, worker, common

from flumotion.common.common import version

__version__ = "$Rev: 6562 $"

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


class Command(util.LogCommand):
    usage = "%prog %command"
    description = "Run commands on Flumotion manager."

    managerDeferred = None # deferred that fires upon connection
    adminModel = None      # AdminModel connected to the manager

    subCommandClasses = [component.Component, manager.Manager, worker.Worker]

    def addOptions(self):
        self.parser.add_option('-v', '--version',
            action="store_true", dest="version",
            help="show version information")
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

    def handleOptions(self, options):
        self.debug('command: handleOptions')
        if options.version:
            print version("flumotion-admin-command")
            return 0

    def parse(self, argv):
        # instantiated here so our subcommands can chain to it
        self.managerDeferred = defer.Deferred()

        self.debug('parse: chain up')
        # chain up to parent first
        # all subcommands will have a chance to chain up to the deferred
        ret = util.LogCommand.parse(self, argv)

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
            self.debug('parse: eb: failure %s' %
                log.getFailureMessage(failure))
            if failure.check(common.Exited):
                sys.stderr.write(failure.value.msg + '\n')
                reactor.exitStatus = failure.value.code
            else:
                sys.stderr.write(log.getFailureMessage(failure) + '\n')
                reactor.exitStatus = 1

            reactor.callLater(0, reactor.stop)
            return

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
        connection = connections.parsePBConnectionInfo(options.manager,
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
            sys.stderr.write("Unable to connect to manager.\n")
        if failure.check(errors.ConnectionRefusedError):
            sys.stderr.write("Manager refused connection.\n")
        self.managerDeferred.errback(failure)


def main(args):
    c = Command()
    try:
        ret = c.parse(args[1:])
    except common.Exited, e:
        ret = e.code
        if ret == 0:
            sys.stdout.write(e.msg + '\n')
        else:
            sys.stderr.write(e.msg + '\n')

    return ret
