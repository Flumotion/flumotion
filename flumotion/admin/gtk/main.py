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

import gtk
from twisted.internet import reactor

from flumotion.admin.admin import AdminModel
from flumotion.admin.gtk import greeter
from flumotion.admin.gtk.client import Window
from flumotion.configure import configure
from flumotion.common import log
from flumotion.wizard import wizard

FIRST_TIME_FILE = os.path.join(os.environ['HOME'], '.flumotion',
                               'default.xml')

def _write_default(configuration): 
    directory = os.path.split(FIRST_TIME_FILE)[0]
    if not os.path.exists(directory):
        os.makedirs(directory)
        
    filename = os.path.join(directory, 'default.xml')
    fd = file(filename, 'w')
    fd.write(configuration)

def _read_default():
    directory = os.path.split(FIRST_TIME_FILE)[0]
    filename = os.path.join(directory, 'default.xml')
    fd = file(filename)
    return fd.read()

def _wizard_finished_cb(wizard, configuration, window):
    wizard.hide()
    _write_default(configuration)
    window.admin.loadConfiguration(configuration)
    window.show()
    
def _window_connected_cb(window, options):
    if not window.admin.getComponents() and not os.path.exists(FIRST_TIME_FILE):
        workers = window.admin.getWorkerHeavenState()
        if not workers:
            print >> sys.stderr, "ERROR: No workers connected"
            reactor.stop()
        wiz = wizard.Wizard(window.admin)
        wiz.connect('finished', _wizard_finished_cb, window)
        wiz.load_steps()
        wiz.run(not options.debug, workers, main=False)
        return

    if True:
        window.show()
    else:
        wiz = window.runWizard()
        wiz.connect('finished', lambda w, c: sys.stdout.write(c))
        wiz.window.connect('delete-event', gtk.main_quit)
        
def _runWizardAndDump():
    wiz = wizard.Wizard()
    wiz.load_steps()
    wiz.run(True, ['localhost'], False)
    wiz.printOut()

def _runInterface(conf_file, options):
    if conf_file:
        # load the conf file here
        raise NotImplementedError()

    state = greeter.Greeter().run()
    if not state:
        exit (0)

    model = AdminModel(state['user'], state['passwd'])
    model.connectToHost(state['host'], state['port'], state['use_insecure'])
    win = Window(model)

    win.connect('connected', _window_connected_cb, options)
    reactor.run()

def main(args):
    #defaultSSLPort = configure.defaultSSLManagerPort
    #defaultTCPPort = configure.defaultTCPManagerPort
    
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
