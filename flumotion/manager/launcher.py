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
import resource
import signal
import sys

import gobject

from twisted.internet import reactor
from twisted.internet.protocol import ClientCreator, Factory
from twisted.protocols.basic import NetstringReceiver

from flumotion import config
from flumotion.manager import manager, component
from flumotion.manager.config import FlumotionConfigXML
from flumotion.manager.registry import registry
from flumotion.utils import log, gstutils

class MiniProtocol(NetstringReceiver):
    def stringReceived(self, line):
        if line == 'STOP':
            reactor.stop()
            self.manager.shutdown()
            
class Launcher(log.Loggable):
    logCategory = 'launcher'
    def __init__(self, host, port):
        self.children = []
        self.manager_pid = None
        self.manager_host = host
        self.manager_port = port
        self.uid = None
        
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        
    def restore_uid(self, name):
        if self.uid is not None:
            try:
                os.setuid(self.uid)
                log.debug(name, 'uid set to %d' % (self.uid))
            except OSError, e:
                log.warning(name, 'failed to set uid: %s' % str(e))

    def set_nice(self, name, nice):
        if nice:
            try:
                os.nice(nice)
            except OSError, e:
                log.warning(name, 'Failed to set nice level: %s' % str(e))
            else:
                log.debug(name, 'Nice level set to %d' % nice)

    def enable_core_dumps(self, name):
        soft, hard = resource.getrlimit(resource.RLIMIT_CORE)
        if hard != resource.RLIM_INFINITY:
            log.warning(name, 'Could not set ulimited core dump sizes, setting to %d instead' % hard)
        else:
            log.debug(name, 'Enabling core dumps of ulimited size')
            
        resource.setrlimit(resource.RLIMIT_CORE, (hard, hard))
        
    def start_manager(self, logging=False):
        self.debug('Starting manager')
        
        pid = os.fork()
        if pid:
            self.manager_pid = pid
            return
        
        if logging:
            log.setFluDebug("*:4")
            
        signal.signal(signal.SIGINT, signal.SIG_IGN)
                
        self.restore_uid('manager')
        factory = manager.ManagerServerFactory()
        log.debug('manager', 'listening on TCP port %d' % self.manager_port)
        reactor.listenTCP(self.manager_port, factory)
        f = Factory()
        f.protocol = MiniProtocol
        f.protocol.manager = factory.manager
        reactor.listenUNIX('/tmp/flumotion.%d' % os.getpid(), f)

        reactor.run(False)
            
        raise SystemExit
        
    def stop_manager(self):
        if not self.manager_pid:
            return
        
        filename = '/tmp/flumotion.%d' % self.manager_pid
        c = ClientCreator(reactor, MiniProtocol)
        defered = c.connectUNIX(filename)
        def cb_Stop(protocol):
            self.debug('Telling manager to shutdown')
            protocol.sendString('STOP')
            self.debug('Shutting down launcher')
            reactor.callLater(0, reactor.stop)
        defered.addCallback(cb_Stop)

        # We need to run the reactor again, so we can process
        # the last events, need to tell the manager to shutdown
        reactor.run()
        
    def run(self):
        self.restore_uid('launcher')

        reactor.run() # don't fucking dare setting it to False.

        self.stop_manager()

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
        
        component_name = config.getName()

        log.debug(component_name, 'Starting on pid %d of type %s' %
                   (os.getpid(), config.getType()))

        signal.signal(signal.SIGINT, signal.SIG_IGN)
        self.threads_init()
        self.restore_uid(component_name)
        self.set_nice(component_name, config.nice)
        self.enable_core_dumps(component_name)
        
        log.debug(component_name, 'Configuration dictionary is: %r' % (
            config.getConfigDict()))
        comp = config.getComponent()
        factory = component.ComponentFactory(comp)
        factory.login(component_name)
        
        reactor.connectTCP(self.manager_host, self.manager_port, factory)
        
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
                      help="Manager port", default=8890)
    parser.add_option('', '--host',
                      action="store", type="string", dest="host",
                      help="Manager host", default="localhost")

    options, args = parser.parse_args(args)

    if len(args) < 3:
        print 'Need a configuration file'
        return -1

    launcher = Launcher(options.host, options.port)

    if options.host == 'localhost':
        if not gstutils.is_port_free(options.port):
            launcher.error('Manager is already started')
        else:
            launcher.start_manager(options.verbose)

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
        launcher.stop_manager()
        return
    
    if options.verbose:
        log.setFluDebug("*:4")

    launcher.run()

    return 0

def run_manager(args):
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="Be verbose")
    group = optparse.OptionGroup(parser, "Manager options")
    group.add_option('-p', '--port',
                     action="store", type="int", dest="port",
                     default=8890,
                     help="Port to listen on [default 8890]")
    parser.add_option_group(group)
    
    options, args = parser.parse_args(args)

    if options.verbose:
        log.setFluDebug("*:4")

    factory = manager.ManagerServerFactory()
    
    log.debug('manager', 'Starting at port %d' % options.port)
    reactor.listenTCP(options.port, factory)
    reactor.run()

    return 0

def usage():
    print 'Usage: flumotion command [command-options-and-arguments]'
    
def show_commands():
    print 'Flumotion commands are:'
    print '\tlauncher      Component launcher'
    print '\tmanager    Component manager'
    print
    print '(Specify the --help option for a list of other help options)'

def main(args):
    if len(args) < 2:
        usage()
        return -1

    args = [arg for arg in args if not arg.startswith('--gst')]
    
    name = args[1]
    if name == 'manager':
        return run_manager(args)
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
