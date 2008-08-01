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

"""flumotion-command entry point, command line parsing and invokation"""

import re
import sys

from twisted.internet import reactor

from flumotion.admin.admin import AdminModel
from flumotion.admin.command.commands import commands
from flumotion.admin.connections import parsePBConnectionInfoRecent
from flumotion.common import log, errors
# make Message proxyable
from flumotion.common import messages
from flumotion.common.options import OptionParser

__version__ = "$Rev$"


def err(string):
    sys.stderr.write('Error: ' + string + '\n')
    sys.exit(1)


def warn(string):
    sys.stderr.write('Warning: ' + string + '\n')


def command_usage():
    for name, desc, argspecs, proc in commands:
        sys.stdout.write('  %s -- %s\n' % (name, desc))
        sys.stdout.write('    usage: %s' % name)
        for spec in argspecs:
            if len(spec) > 2:
                sys.stdout.write(' [%s]' % spec[0].upper())
            else:
                sys.stdout.write(' %s' % spec[0].upper())
        sys.stdout.write('\n')


def usage(args, exitval=0):
    print 'usage: %s [OPTIONS] -m MANAGER COMMAND COMMAND-ARGS...' % args[0]
    print ''
    print 'Available commands:'
    print ''
    command_usage()
    print ''
    print 'See %s -h for help on the available options.' % args[0]
    sys.exit(exitval)


def parse_commands(args):
    op = args[1]
    matching = [x for x in commands if x[0] == op]
    if not matching:
        print 'Error: Unknown command: %s' % op
        usage(args, exitval=1)
    commandspec = matching[0]

    argspecs = commandspec[2]
    reqspecs = [spec for spec in argspecs if len(spec) < 3]
    nreq = len(reqspecs)
    optspecs = [spec for spec in argspecs if len(spec) == 3 or \
        len(spec) > 3 and not spec[3]]
    nopt = len(optspecs)

    vararg = [spec for spec in argspecs if len(spec) > 3 and spec[3]]

    # pop off argv[0] and the command name
    cargs = args[2:]

    if len(cargs) < nreq or len(cargs) > nreq + nopt and not vararg:
        print 'Error: Invalid arguments to operation %s: %r' % (op, cargs)
        usage(args, exitval=1)

    vals = []
    for name, parse in reqspecs:
        arg = cargs.pop(0)
        try:
            vals.append(parse(arg))
        except Exception:
            err('Error: Operation %s\'s arg %s="%s" could not be '
                'parsed as type "%s"'
                % (op, name, arg, parse.__name__))
    for name, parse, default in optspecs:
        if cargs:
            arg = cargs.pop(0)
            try:
                vals.append(parse(arg))
            except Exception:
                err('Error: Operation %s\'s arg %s="%s" could not be '
                    'parsed as type "%s"'
                    % (op, name, arg, parse.__name__))
        else:
            vals.append(default)

    if vararg:
        vals.extend(cargs)

    proc = commandspec[3]

    def command(model, quit):

        def print_traceback(failure):
            import traceback
            warn('Operation %s failed:' % op)
            traceback.print_exc()
            return failure
        d = proc(model, quit, *vals)
        d.addErrback(print_traceback)
        return d

    return command


def setup_reactor(info):
    model = AdminModel()
    d = model.connectToManager(info)

    def failed(failure):
        if failure.check(errors.ConnectionRefusedError):
            print >> sys.stderr, \
                  "Manager refused connection. Check your user and password."
        elif failure.check(errors.ConnectionFailedError):
            message = "".join(failure.value.args)
            print >> sys.stderr, "Connection to manager failed: %s" % message
        else:
            print >> sys.stderr, ("Exception while connecting to manager: %s"
                   % log.getFailureMessage(failure))
        return failure

    d.addErrback(failed)

    return d

pat = re.compile('^(([^:@]*)(:([^:@]+))?@)?([^:@]+)(:([0-9]+))?$')


def main(args):
    parser = OptionParser(domain="flumotion-command")
    parser.add_option('-u', '--usage',
                      action="store_true", dest="usage",
                      help="show a usage message")
    parser.add_option('-m', '--manager',
                      action="store", type="string", dest="manager",
                      help="the manager to connect to, e.g. localhost:7531")
    parser.add_option('', '--no-ssl',
                      action="store_true", dest="no_ssl",
                      help="disable encryption when connecting to the manager")

    options, args = parser.parse_args(args)

    if options.usage or not args[1:]:
        usage(args)

    connection = parsePBConnectionInfoRecent(options.manager,
                                             not options.no_ssl)

    command = parse_commands(args)
    quit = lambda: reactor.callLater(0, reactor.stop)

    reactor.exitStatus = 0

    d = setup_reactor(connection)

    d.addCallback(lambda model: command(model, quit))
    # assume that whatever raised the error already printed -- this is a
    # bit geto

    def errback(failure):
        reactor.exitStatus = 1
        quit()
    d.addErrback(errback)

    reactor.run()
    return reactor.exitStatus
