# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.
 
import optparse
import os
import signal
import sys

import gobject

from twisted.internet import reactor
from twisted.internet.protocol import ClientCreator, Factory
from twisted.protocols.basic import NetstringReceiver

from flumotion import config
from flumotion.server import controller, component
from flumotion.server.config import FlumotionConfigXML
from flumotion.server.registry import registry
from flumotion.utils import log, gstutils

class MiniProtocol(NetstringReceiver):
    def stringReceived(self, line):
        if line == 'STOP':
            reactor.stop()
            self.controller.shutdown()
            
class Launcher:
    def __init__(self, host, port):
        self.children = []
        self.controller_pid = None
        self.controller_host = host
        self.controller_port = port
        self.uid = None
        
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        
    debug = lambda s, *a: log.debug('launcher', *a)
    warning = lambda s, *a: log.warning('launcher', *a)
    error = lambda s, *a: log.error('launcher', *a)

    def restore_uid(self):
        if self.uid is not None:
            try:
                os.setuid(self.uid)
                self.debug('uid set to %d' % (self.uid))
            except OSError, e:
                self.warning('failed to set uid: %s' % str(e))

    def set_nice(self, nice):
        if nice:
            try:
                os.nice(nice)
            except OSError, e:
                self.warning('Failed to set nice level: %s' % str(e))
            else:
                self.debug('Nice level set to %d' % nice)

    def start_controller(self, logging=False):
        self.debug('Starting controller')
        
        pid = os.fork()
        if pid:
            self.controller_pid = pid
            return
        
        if logging:
            log.enableLogging()
            
        signal.signal(signal.SIGINT, signal.SIG_IGN)
                
        self.restore_uid()
        factory = controller.ControllerServerFactory()
        reactor.listenTCP(self.controller_port, factory)
        f = Factory()
        f.protocol = MiniProtocol
        f.protocol.controller = factory.controller
        reactor.listenUNIX('/tmp/flumotion.%d' % os.getpid(), f)

        reactor.run(False)
            
        raise SystemExit
        
    def stop_controller(self):
        if not self.controller_pid:
            return
        
        filename = '/tmp/flumotion.%d' % self.controller_pid
        c = ClientCreator(reactor, MiniProtocol)
        defered = c.connectUNIX(filename)
        def cb_Stop(protocol):
            self.debug('Telling controller to shutdown')
            protocol.sendString('STOP')
            self.debug('Shutting down launcher')
            reactor.callLater(0, reactor.stop)
        defered.addCallback(cb_Stop)

        # We need to run the reactor again, so we can process
        # the last events, need to tell the controller to shutdown
        reactor.run()
        
    def run(self):
        self.restore_uid()

        reactor.run() # don't fucking dare setting it to False.

        self.stop_controller()

    def threads_init(self):
        try:
            gobject.threads_init()
        except AttributeError:
            print '** WARNING: OLD PyGTK detected **'
        except RuntimeError:
            print '** WARNING: PyGTK with threading disabled detected **'
        
    def launch_component(self, config):
        if not config.startFactory():
            return
        
        pid = os.fork()
        if pid:
            self.children.append(pid)
            return

        signal.signal(signal.SIGINT, signal.SIG_IGN)
        self.restore_uid()
        self.threads_init()
        self.set_nice(config.nice)

        comp = config.getComponent()
        component_name = config.getName()
        self.debug('Starting %s (%s) on pid %d' %
                   (component_name, config.getType(), pid))
        factory = component.ComponentFactory(comp)
        factory.login(component_name)
        
        reactor.connectTCP(self.controller_host, self.controller_port, factory)
        
        reactor.run(False)
        raise SystemExit

    def load_config(self, filename):
        conf = FlumotionConfigXML(filename)

        for name in conf.entries.keys():
            self.debug('Starting component: %s' % name)
            self.launch_component(conf.getEntry(name))
    
def run_launcher(args):
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="Be verbose")
    parser.add_option('-c', '--port',
                      action="store", type="int", dest="port",
                      help="Controller port", default=8890)
    parser.add_option('', '--host',
                      action="store", type="string", dest="host",
                      help="Controller host", default="localhost")

    options, args = parser.parse_args(args)

    if len(args) < 3:
        print 'Need a configuration file'
        return -1

    filename = os.path.join(config.datadir, 'registry', 'basecomponents.xml')
    registry.addFromFile(filename)

    launcher = Launcher(options.host, options.port)

    if options.host == 'localhost':
        if not gstutils.is_port_free(options.port):
            launcher.error('Controller is already started')
        else:
            launcher.start_controller(options.verbose)

    try:
        launcher.load_config(args[2])
    except SystemExit:
        return
    except Exception, e:
        import traceback
        print 'Traceback caught during configuration loading:'
        print '='*79
        traceback.print_exc(file=sys.stdout)
        print '='*79
        launcher.stop_controller()
        return
    
    if options.verbose:
        log.enableLogging()

    launcher.run()

    return 0

def run_controller(args):
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="Be verbose")
    group = optparse.OptionGroup(parser, "Controller options")
    group.add_option('-p', '--port',
                     action="store", type="int", dest="port",
                     default=8890,
                     help="Port to listen on [default 8890]")
    parser.add_option_group(group)
    
    options, args = parser.parse_args(args)

    if options.verbose:
        log.enableLogging()

    factory = controller.ControllerServerFactory()
    
    log.debug('controller', 'Starting at port %d' % options.port)
    reactor.listenTCP(options.port, factory)
    reactor.run()

    return 0

def usage():
    print 'Usage: flumotion command [command-options-and-arguments]'
    
def show_commands():
    print 'Flumotion commands are:'
    print '\tlauncher      Component launcher'
    print '\tcontroller    Component controller'
    print
    print '(Specify the --help option for a list of other help options)'

def main(args):
    if len(args) < 2:
        usage()
        return -1

    args = [arg for arg in args if not arg.startswith('--gst')]
    
    name = args[1]
    if name == 'controller':
        return run_controller(args)
    elif name == 'launcher':
        return run_launcher(args)
    else:
        print "Unknown command: `%s'" % name
        print
        show_commands()
        return -1

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
