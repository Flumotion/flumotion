# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
import os
import sys
import re

from twisted.internet import reactor

from flumotion.admin.admin import AdminModel
from flumotion.admin import connections
from flumotion.common import log, errors
from flumotion.configure import configure

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
        for name, pred in argspecs:
            sys.stdout.write(' %s' % name.upper())
        sys.stdout.write('\n')

def usage(args, exitval=0):
    print 'usage: %s -m [OPTIONS] MANAGER COMMAND COMMAND-ARGS...' % args[0]
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
    if len(args[2:]) != len(argspecs):
        print 'Error: Invalid arguments to operation %s: %r' % (op, args[2:])
        usage(args, exitval=1)

    vals = []
    for argspec, arg in zip(argspecs, args[2:]):
        name, parse = argspec
        try:
            vals.append(parse(arg))
        except Exception:
            err('Error: Operation %s\'s arg %s="%s" could not be '
                'parsed as type "%s"'
                % (op, name, arg, parse.__name__))

    proc = commandspec[3]

    def command(model, quit):
        proc(model, quit, *vals)

    return command

def setup_reactor(connection):
    model = AdminModel(connection['user'], connection['passwd'])
    d = model.connectToHost(connection['host'], connection['port'],
                            connection['use_insecure'])

    def refused(failure):
        failure.trap(errors.ConnectionRefusedError)
        print "Manager refused connection. Check your user and password."
        raise

    def failed(failure):
        failure.trap(errors.ConnectionFailedError)
        message = "".join(failure.value.args)
        print "Connection to manager failed: %s" % message
        raise

    d.addErrback(refused)
    d.addErrback(failed)

    return d

pat = re.compile('^(([^:@]*)(:([^:@]+))?@)?([^:@]+)(:([0-9]+))?$')

def parse_connection(manager_string, use_insecure):
    recent = connections.get_recent_connections()

    if manager_string:
        matched = pat.search(manager_string)
        if not matched:
            err('invalid manager string: %s '
                '(looking for [user[:pass]@]host[:port])'
                % manager_string)

        groups = matched.groups()
        ret = {}
        for k, v in (('user', 1),
                     ('passwd', 3),
                     ('host', 4),
                     ('port', 6)):
            ret[k] = groups[v]
        ret['use_insecure'] = bool(use_insecure)
        if not ret['port']:
            if use_insecure:
                ret['port'] = configure.defaultTCPManagerPort
            else:
                ret['port'] = configure.defaultSSLManagerPort

        def compatible(d1, d2, *keys):
            for k in keys:
                if d1[k] and d1[k] != d2[k]:
                    return False
            return True

        if not ret['user']:
            for c in recent:
                state = c['state']
                if compatible(ret, state, 'host', 'port', 'use_insecure'):
                    ret['user'] = state['user']
                    ret['passwd'] = state['passwd']
                    break
        elif not ret['passwd']:
            for c in recent:
                state = c['state']
                if compatible(ret, state, 'host', 'port', 'use_insecure',
                              'user'):
                    ret['passwd'] = state['passwd']
                    break
        if not (ret['user'] and ret['passwd']):
            err('You are connecting to %s for the first time; please '
                'specify a user and password (e.g. user:test@%s).'
                % (manager_string, manager_string))

        for k, v in ret.items():
            assert v is not None, '%s unset, internal error' % k

        return ret
    elif recent:
        return recent[0]['state']
    else:
        err('Missing --manager, and no recent connections to use.')

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

    connection = parse_connection(options.manager, options.no_ssl)

    command = parse_commands(args)
    quit = lambda: reactor.callLater(0, reactor.stop)

    d = setup_reactor(connection)

    d.addCallback(lambda model: command(model, quit))
    # assume that whatever raised the error already printed -- this is a
    # bit geto
    d.addErrback(lambda failure: quit())

    reactor.run()
