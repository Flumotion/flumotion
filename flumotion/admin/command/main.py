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

import optparse
import sys
import re

from twisted.internet import reactor

from flumotion.admin.admin import AdminModel
from flumotion.admin import connections
from flumotion.common import log, errors
# make Message proxyable
from flumotion.common import messages
from flumotion.configure import configure
from flumotion.twisted import pb as fpb

from flumotion.admin.command.commands import commands

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

    vararg = filter(lambda spec: len(spec) > 3 and spec[3], argspecs)

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
        proc(model, quit, *vals)

    return command

def setup_reactor(info):
    model = AdminModel(info.authenticator)
    d = model.connectToHost(info.host, info.port, not info.use_ssl)

    def failed(failure):
        if failure.check(errors.ConnectionRefusedError):
            print "Manager refused connection. Check your user and password."
        elif failure.check(errors.ConnectionFailedError):
            message = "".join(failure.value.args)
            print "Connection to manager failed: %s" % message
        else:
            print ("Exception while connecting to manager: %s"
                   % log.getFailureMessage(failure))
        return failure

    d.addErrback(failed)

    return d

pat = re.compile('^(([^:@]*)(:([^:@]+))?@)?([^:@]+)(:([0-9]+))?$')

def main(args):
    parser = optparse.OptionParser()
    parser.add_option('-d', '--debug',
                      action="store", type="string", dest="debug",
                      help="set debug levels")
    parser.add_option('-u', '--usage',
                      action="store_true", dest="usage",
                      help="show a usage message")
    parser.add_option('-m', '--manager',
                      action="store", type="string", dest="manager",
                      help="the manager to connect to, e.g. localhost:7531")
    parser.add_option('', '--no-ssl',
                      action="store_true", dest="no_ssl",
                      help="disable encryption when connecting to the manager")
    parser.add_option('', '--version',
                      action="store_true", dest="version",
                      default=False,
                      help="show version information")
    
    options, args = parser.parse_args(args)

    if options.version:
        from flumotion.common import common
        print common.version("flumotion-command")
        return 0

    if options.debug:
        log.setFluDebug(options.debug)

    if options.usage or not args[1:]:
        usage(args)

    connection = connections.parsePBConnectionInfo(options.manager,
                                                   not options.no_ssl)

    command = parse_commands(args)
    quit = lambda: reactor.callLater(0, reactor.stop)

    d = setup_reactor(connection)

    d.addCallback(lambda model: command(model, quit))
    # assume that whatever raised the error already printed -- this is a
    # bit geto
    d.addErrback(lambda failure: quit())

    reactor.run()
