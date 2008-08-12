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
worker commands
"""

import os
import time

from gettext import gettext as _

from twisted.python import failure

from flumotion.configure import configure
from flumotion.common import errors, log, i18n, messages
from flumotion.monitor.nagios import util

from flumotion.admin.command import common

__version__ = "$Rev: 6562 $"


class Invoke(common.AdminCommand):
    usage = "invoke [method-name] [arguments]"
    summary = "invoke a method on a worker"
    description = """Invoke a method on a worker.
%s
For a list of methods that can be invoked, see the worker's medium class
in flumotion.worker.medium and its remote_* methods.

Examples: getFeedServerPort, killJob, getComponents, getVersions

checkElements [ss] oggmux vorbisenc

checkImport s sys""" % common.ARGUMENTS_DESCRIPTION

    def doCallback(self, args):
        workerName = self.parentCommand.options.name
        if not workerName:
            common.errorRaise('Please specify a worker name with --name.')

        try:
            methodName = args[0]
        except IndexError:
            common.errorRaise('Please specify a method name.')

        if len(args) > 1:
            args = common.parseTypedArgs(args[1], args[2:])
            if args is None:
                common.errorRaise('Could not parse arguments.')
        else:
            args = []

        p = self.parentCommand
        d = self.getRootCommand().adminModel.callRemote(
            'workerCallRemote', workerName, methodName, *args)

        def cb(result):
            import pprint
            self.stdout.write("Invoking '%s' on '%s' returned:\n%s\n" % (
                methodName, workerName, pprint.pformat(result)))

        def eb(failure):
            # FIXME
            if failure.check(errors.NoMethodError):
                common.errorRaise("No method '%s' on worker '%s'." % (
                    methodName, workerName))
            elif failure.check(errors.SleepingComponentError):
                common.errorRaise("Component '%s' is sleeping." %
                    p.componentId)
            elif failure.check(errors.RemoteRunError):
                common.errorRaise(log.getFailureMessage(failure))
            else:
                common.errorRaise(log.getFailureMessage(failure))

        d.addCallback(cb)
        d.addErrback(eb)

        return d


class List(common.AdminCommand):
    description = "List workers."

    def doCallback(self, args):
        s = self.parentCommand.workerHeavenState
        workers = s.get('workers')
        if not workers:
            self.stdout.write('No workers logged in.\n')
            return

        for worker in workers:
            self.stdout.write('%s: %s\n' % (
                worker.get('name'), worker.get('host')))


class Run(common.AdminCommand):
    usage = "run [module-name] [method-name] [arguments]"
    summary = "run a method on a worker"
    description = """Run a method on a worker
%s
Any method that the worker can import can be run.
This is useful for testing worker checks.

Examples:

flumotion.worker.checks.video checkTVCard s /dev/video0

flumotion.worker.checks.audio checkMixerTracks ssi alsasrc hw:0 2
""" % common.ARGUMENTS_DESCRIPTION

    def doCallback(self, args):
        try:
            moduleName = args[0]
        except IndexError:
            common.errorRaise('Please specify a module name to invoke from.')
        try:
            methodName = args[1]
        except IndexError:
            common.errorRaise('Please specify a method name.')

        if len(args) > 2:
            args = common.parseTypedArgs(args[2], args[3:])
            if args is None:
                common.errorRaise('Could not parse arguments.')
        else:
            args = []

        p = self.parentCommand
        workerName = p.options.name
        d = self.getRootCommand().adminModel.callRemote(
            'workerCallRemote', workerName, 'runFunction',
            moduleName, methodName, *args)

        def cb(result):
            i18n.installGettext()
            # handle some results specifically, like Result
            self.stdout.write("Invoking '%s' on '%s' returned:\n" %
                    (methodName, workerName))
            import pprint
            self.stdout.write("%s\n" % pprint.pformat(result))

            if isinstance(result, messages.Result):
                _headings = {
                    messages.ERROR: _('Error'),
                    messages.WARNING: _('Warning'),
                    messages.INFO: _('Note'),
                }

                for m in result.messages:
                    translator = i18n.Translator()
                    localedir = os.path.join(configure.localedatadir, 'locale')
                    # FIXME: add locales as messages from domains come in
                    translator.addLocaleDir(configure.PACKAGE, localedir)
                    self.stdout.write('%s:\n' % _headings[m.level])
                    self.stdout.write(translator.translate(m) + '\n')
                    if hasattr(m, 'timestamp'):
                        self.stdout.write(_("\nPosted on %s.\n") %
                            time.strftime("%c", time.localtime(m.timestamp)))
                    if m.debug:
                        self.stdout.write("DEBUG:\n%s\n" % m.debug)

                if result.failed:
                    self.stdout.write('Result failed.\n')
                else:
                    self.stdout.write('Result successful:\n%s\n' %
                        pprint.pformat(result.value))

        def eb(failure):
            if failure.check(errors.NoMethodError):
                common.errorRaise("No method '%s' on worker '%s'." % (
                    methodName, workerName))
            elif failure.check(errors.SleepingComponentError):
                common.errorRaise("Component '%s' is sleeping." %
                    p.componentId)
            elif failure.check(errors.RemoteRunError):
                common.errorRaise(log.getFailureMessage(failure))
            else:
                common.errorRaise(log.getFailureMessage(failure))

        d.addCallback(cb)
        d.addErrback(eb)

        return d


class Worker(util.LogCommand):
    """
    @param workerHeavenState: the planet state; set when logged in to manager.
    @type  workerHeavenState: L{flumotion.common.state.WorkerHeavenState}
    """
    description = "Act on workers."

    subCommandClasses = [Invoke, List, Run]

    def addOptions(self):
        self.parser.add_option('-n', '--name',
            action="store", dest="name",
            help="name of the component")

    def handleOptions(self, options):
        # call our callback after connecting
        self.getRootCommand().managerDeferred.addCallback(self._callback)

    def _callback(self, result):
        d = self.parentCommand.adminModel.callRemote('getWorkerHeavenState')

        def gotWorkerHeavenStateCb(result):
            self.workerHeavenState = result
        d.addCallback(gotWorkerHeavenStateCb)
        return d
