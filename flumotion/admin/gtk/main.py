# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/admin/gtk/main.py: GTK+-based admin client
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

import optparse
import os
import sys

from flumotion.admin.gtk.client import Window
from flumotion.configure import configure
from flumotion.wizard import wizard
from twisted.internet import reactor

FIRST_TIME_FILE = os.path.join(os.environ['HOME'], '.flumotion',
                               'default.xml')

def _write_default(configuration): 
    directory = os.path.split(FIRST_TIME_FILE)[0]
    if not os.path.exists(directory):
        os.makedirs(directory)
        
    filename = os.path.join(directory, 'default.xml')
    print 'Saving configuration to', filename
    fd = file(filename, 'w')
    fd.write(configuration)

def _read_default():
    directory = os.path.split(FIRST_TIME_FILE)[0]
    filename = os.path.join(directory, 'default.xml')
    print 'Loading configuration from', filename
    fd = file(filename)
    return fd.read()

def _wizard_finished_cb(wizard, configuration, window):
    wizard.hide()
    _write_default(configuration)
    window.admin.loadConfiguration(configuration)
    window.show()

def _window_connected_cb(window, options):
    if not os.path.exists(FIRST_TIME_FILE):
        workers = window.admin.getWorkers()
        if not workers:
            print >> sys.stderr, "ERROR: No workers connected"
            reactor.stop()
        wiz = wizard.Wizard()
        wiz.connect('finished', _wizard_finished_cb, window)
        wiz.load_steps()
        wiz.run(not options.debug, workers, main=False)
    elif not window.admin.getComponents():
        configuration = _read_default()
        window.admin.loadConfiguration(configuration)
        window.show()
    else:
        print 'There are already components connected, not sending configuration'
        window.show()
        
def _runWizard(debug):
    wiz = wizard.Wizard()
    wiz.load_steps()
    wiz.run(not debug, ['localhost'])
    if debug:
        wiz.printOut()
    
def _runInterface(options):
    win = Window(options.host, options.port, options.transport,
                 options.username, options.password)

    win.connect('connected', _window_connected_cb, options)
    reactor.run()

def main(args):
    defaultSSLPort = configure.defaultSSLManagerPort
    defaultTCPPort = configure.defaultTCPManagerPort
    
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="be verbose")
    parser.add_option('', '--version',
                      action="store_true", dest="version",
                      default=False,
                      help="show version information")
    
    parser.add_option('-H', '--host',
                     action="store", type="string", dest="host",
                     default='localhost',
                     help="manager host to connect to [default localhost]")
    parser.add_option('-P', '--port',
                     action="store", type="int", dest="port",
                     default=None,
                     help="port to listen on [default %d (ssl) or %d (tcp)]" % (defaultSSLPort,
                                                                                defaultTCPPort))
    parser.add_option('-T', '--transport',
                      action="store", type="string", dest="transport",
                      default="ssl",
                      help="transport protocol to use (tcp/ssl) [default: ssl]")
    parser.add_option('-u', '--username',
                      action="store", type="string", dest="username",
                      default="",
                      help="username to use")
    parser.add_option('-p', '--password',
                      action="store", type="string", dest="password",
                      default="",
                      help="password to use, - for interactive")

    parser.add_option('', '--wizard',
                     action="store_true", dest="wizard",
                     help="run the wizard")
    parser.add_option('', '--debug',
                      action="store_true", dest="debug",
                      default=False,
                      help="run in debug")

    options, args = parser.parse_args(args)

    if options.version:
        from flumotion.common import common
        print common.version("flumotion-admin")
        return 0

    if options.verbose:
        log.setFluDebug("*:4")

    if not options.port:
        if options.transport == "tcp":
            options.port = defaultTCPPort
        elif options.transport == "ssl":
            options.port = defaultSSLPort

    if options.wizard:
        _runWizard(options.debug)
    else:
        _runInterface(options)
