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
manager commands
"""

import os

from twisted.spread import flavors

from flumotion.common import errors, log
from flumotion.monitor.nagios import util

from flumotion.admin.command import common

__version__ = "$Rev: 6562 $"


class Invoke(common.AdminCommand):
    usage = "[method-name] [arguments]"
    summary = "invoke a method on a manager"
    description = """Invoke a method on a manager.
%s
For a list of methods that can be invoked, see the admin's avatar class
in flumotion.manager.admin and its perspective_* methods.

Note that not all of them can be invoked if you have no way of passing the
needed arguments (for example, componentStart needs a componentState)

Examples: getConfiguration, getVersions
""" % common.ARGUMENTS_DESCRIPTION

    def doCallback(self, args):
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

        d = self.getRootCommand().medium.callRemote(
            methodName, *args)

        def cb(result):
            import pprint
            self.stdout.write("Invoking '%s' on manager returned:\n%s\n" % (
                methodName, pprint.pformat(result)))

        def eb(failure):
            # FIXME
            if failure.check(errors.NoMethodError) \
                or failure.check(flavors.NoSuchMethod):
                common.errorRaise("No method '%s' on manager." % methodName)
            elif failure.check(errors.RemoteRunError):
                common.errorRaise(log.getFailureMessage(failure))
            else:
                common.errorRaise(log.getFailureMessage(failure))

        d.addCallback(cb)
        d.addErrback(eb)

        return d


class Load(common.AdminCommand):
    usage = "[configuration-file]"
    summary = "load a configuration onto the manager."

    def doCallback(self, args):
        try:
            filePath = args[0]
        except IndexError:
            common.errorRaise('Please specify a configuration file')

        if not os.path.exists(filePath):
            common.errorRaise("'%s' does not exist." % filePath)

        d = self.getRootCommand().medium.callRemote('loadConfiguration',
            open(filePath).read())

        def eb(failure):
            common.errorRaise(log.getFailureMessage(failure))

        d.addErrback(eb)

        return d


class Manager(util.LogCommand):
    description = "Act on manager."

    subCommandClasses = [Invoke, Load]
