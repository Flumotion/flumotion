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

def err(string):
    sys.stderr.write('Error: ' + string + '\n')
    sys.exit(1)

def warn(string):
    sys.stderr.write('Warning: ' + string + '\n')

def type_chk(type):
    return lambda x: isinstance(x, type)

def item_chk(checker):
    def ret(x):
        for i in x:
            if not checker(i):
                return False
        return True
    return ret

# function intersection
def fint(*procs):
    def ret(x):
        for f in procs:
            if not f(x):
                return False
        return True
    return ret

# command-list := (command-spec, command-spec...)
# command-spec := (command-name, arguments)
# command-name := str
# arguments := (arg-spec, arg-spec...)
# arg-spec := (arg-name, arg-predicate)
# arg-name := str
# arg-predicate := f(x) -> True or False

commands = (('getprop', (('component-path', type_chk(str)),
                         ('property-name', type_chk(str)))))

def setup_reactor(options):
    # We do the import here so gettext has been set up and class strings
    # from greeter are translated
    from flumotion.admin.gtk import greeter
    g = thegreeter or greeter.Greeter()
    state = g.run()
    if not state:
        reactor.callLater(0, reactor.stop)
        return
    g.set_sensitive(False)

    model = AdminModel(state['user'], state['passwd'])
    d = model.connectToHost(state['host'], state['port'], state['use_insecure'])

    def connected(model, greeter):
        greeter.destroy()
        Window(model).show()

    def refused(failure, greeter):
        failure.trap(errors.ConnectionRefusedError)
        dialogs.connection_refused_modal_message(state['host'],
                                                 greeter.window)
        _runInterface(None, None, greeter)

    def failed(failure, greeter):
        failure.trap(errors.ConnectionFailedError)
        message = "".join(failure.value.args)
        dialogs.connection_failed_modal_message(message, greeter.window)
        _runInterface(None, None, greeter)

    d.addCallback(connected, g)
    d.addErrback(refused, g)
    d.addErrback(failed, g)

pat = re.compile('^(([^:@]*)(:([^:@]+))?@)?([^:@]+)(:([0-9]+))?$')

def parse_connection(manager_string, use_insecure):
    recent = connections.get_recent_connections()

    if manager_string:
        matched = pat.match(manager_string)
        if not matched:
            err('invalid manager string: %s '
                '(looking for [user[:pass]@]host[:port])'
                % manager_string)

        ret = {}
        for k, v in (('user', 1),
                     ('passwd', 3),
                     ('host', 4),
                     ('port', 6)):
            ret[k] = matched[v]
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
                if compatible(ret, c, 'host', 'port', 'use_insecure'):
                    ret['user'] = c['user']
                    ret['passwd'] = c['passwd']
                    break
        elif not ret['passwd']:
            for c in recent:
                if compatible(ret, c, 'host', 'port', 'use_insecure', 'user'):
                    ret['passwd'] = c['passwd']
                    break
        if not (ret['user'] and ret['passwd']):
            err('You are connecting to %s for the first time; please '
                'specify a user and password (e.g. user:test@%s).'
                % (manager_string, manager_string))

        for k, v in ret.items():
            assert v is not None, '%s unset, internal error' % k

        return ret
    elif recent:
        return recent[0]
    else:
        err('Missing --manager, and no recent connections to use.')

def main(args):
    parser = optparse.OptionParser()
    parser.add_option('-d', '--debug',
                      action="store", type="string", dest="debug",
                      help="set debug levels")
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

    if not args[1:]:
        #usage
        print 'here is how to use this thing'
        sys.exit(0)

    connection = parse_connection(options.manager)
    print connection

    #thunk = parse_commands(args)
    #quit = lambda: reactor.callLater(0, reactor.stop)

    #d = setup_reactor()

    #d.addCallback(lambda result: thunk(quit))

    #reactor.run()
