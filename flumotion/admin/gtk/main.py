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
import sys

from twisted.internet import reactor

from flumotion.admin.admin import AdminModel
from flumotion.admin.gtk.greeter import Greeter
from flumotion.admin.gtk.client import Window
from flumotion.common import log
from flumotion.configure import configure

def _model_connected_cb(model, greeter, ids):
    map(model.disconnect, ids)
    greeter.destroy()
    win = Window(model)
    win.show()

def _model_refused_cb(model, host, port, use_insecure, greeter, ids):
    map(model.disconnect, ids)
    print '\n\nconnection refused, try again'
    print 'FIXME: make a proper errbox'
    _runInterface(None, None, greeter, False)

def _runInterface(conf_file, options, greeter=None, run=True):
    if conf_file:
        # load the conf file here
        raise NotImplementedError()

    g = greeter or Greeter()
    state = g.run()
    if not state:
        sys.exit(0)
    g.set_sensitive(False)

    model = AdminModel(state['user'], state['passwd'])
    model.connectToHost(state['host'], state['port'], state['use_insecure'])

    ids = []
    ids.append(model.connect('connected', _model_connected_cb, g, ids))
    ids.append(model.connect('connection-refused', _model_refused_cb, g, ids))

    if run:
        reactor.run()

def main(args):
    parser = optparse.OptionParser()
    parser.add_option('-d', '--debug',
                      action="store", type="string", dest="debug",
                      help="set debug levels")
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="be verbose")
    parser.add_option('', '--version',
                      action="store_true", dest="version",
                      default=False,
                      help="show version information")
    
    options, args = parser.parse_args(args)

    if options.version:
        from flumotion.common import common
        print common.version("flumotion-admin")
        return 0

    if options.verbose:
        log.setFluDebug("*:3")

    if options.debug:
        log.setFluDebug(options.debug)

    conf_files = args[1:]

    if conf_files and len(conf_files) > 1:
        w = sys.stderr.write
        w('flumotion-admin: too many configuration files: %r' % conf_files)
    elif conf_files:
        _runInterface(conf_files[0], options)
    else:
        _runInterface(None, options)
