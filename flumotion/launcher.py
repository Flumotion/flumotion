# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo

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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 
import ConfigParser
import optik
import os
import signal
import sys
import warnings
import string

warnings.filterwarnings('ignore', category=FutureWarning)

if __name__ == '__main__':
    import gstreactor
    gstreactor.install()

from twisted.internet import reactor
from twisted.python import log
from twisted.web import server, resource

import gstutils

class Launcher:
    def __init__(self, controller_port):
        self.children = []
        self.controller_pid = None
        self.controller_port = controller_port
        
        #signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)

    def msg(self, *args):
        log.msg('[launcher] %s' % string.join(args))

    def start_controller(self, port):
        pid = os.fork()
        if not pid:
            from controller import ControllerServerFactory
            self.controller = reactor.listenTCP(port, ControllerServerFactory())
            try:
                reactor.run(False)
            except KeyboardInterrupt:
                reactor.stop()
            raise SystemExit
        self.controller_pid = pid

    def signal_handler(self, *args):
        for pid in self.children:
            try:
                os.kill(0, pid)
                os.waitpid(pid, 0)
            except OSError:
                pass

    def spawn(self, component):
        pid = os.getpid()
        def exit_cb(*args):
            component.pipeline_stop()
            raise SystemExit

        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        signal.signal(signal.SIGINT, exit_cb)
        reactor.connectTCP('localhost', self.controller_port,
                           component.factory)
        
        try:
            reactor.run(False)
        except KeyboardInterrupt:
            pass
        component.pipeline_stop()

    def start(self, component):
        pid = os.fork()
        if not pid:
            self.spawn(component)
            raise SystemExit
        else:
            self.msg('Starting %s (%s) on pid %d' %
                    (component.component_name,
                     component.getKind(),
                     pid))
            self.children.append(pid)

    def start_streamer(self, component, factory, port):
        pid = os.fork()
        if not pid:
            reactor.listenTCP(port, factory)
            self.spawn(component)
            raise SystemExit
        else:
            self.msg('Starting %s (%s) on pid %d' %
                    (component.component_name,
                     component.getKind(),
                     pid))
            self.children.append(pid)
        
    def run(self):
        while self.children:
            for pid in self.children:
                try:
                    os.kill(pid, 0)
                except OSError:
                    self.children.remove(pid)
                    
            if not self.children:
                continue
            
            try:
                pid = os.waitpid(self.children[0], 0)
                self.children.remove(pid)
                self.msg('%d is dead pid' % pid)
            except (KeyboardInterrupt, OSError):
                pass
            
        if self.controller_pid:
            try:
                os.kill(self.controller_pid, signal.SIGINT)
            except OSError:
                pass
        
        self.msg('Shutting down reactor')
        reactor.stop()

        raise SystemExit

    def load_config(self, filename):
        from producer import Producer
        from converter import Converter
        from streamer import Streamer, StreamingResource

        c = ConfigParser.ConfigParser()
        c.read(filename)

        components = {}
        for section in c.sections():
            name = section
            if not c.has_option(section, 'kind'):
                raise AssertionError
            kind = c.get(section, 'kind')
            if not kind in ('producer', 'converter', 'streamer'):
                raise AssertionError
            
            # XXX: Throw nice warnings
            if kind == 'producer' or kind == 'converter':
                assert c.has_option(section, 'pipeline')
                pipeline = c.get(section, 'pipeline')
            else:
                pipeline = None
                
            if kind == 'converter' or kind == 'streamer':
                assert (c.has_option(section, 'source') or
                        c.has_option(section, 'sources'))
                if c.has_option(section, 'source'):
                    sources = [c.get(section, 'source')]
                else:
                    sources = c.get(section, 'sources').split(',')
            else:
                sources = []
                
            if kind == 'streamer':
                assert c.has_option(section, 'port')
                port = c.getint(section, 'port')

            if kind == 'producer':
                self.start(Producer(name, sources, pipeline))
            elif kind == 'converter':
                self.start(Converter(name, sources, pipeline))
            elif kind == 'streamer':
                component = Streamer(name, sources)
                resource = StreamingResource(component)
                factory = server.Site(resource=resource)
                self.start_streamer(component, factory, port)
            else:
                raise AssertionError
    
def main(args):
    parser = optik.OptionParser()
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="Be verbose")
    parser.add_option('-c', '--controller-port',
                      action="store", type="int", dest="port",
                      help="Controller port")

    options, args = parser.parse_args(args)
    if len(args) < 2:
        print 'Need a config file.'
        raise SystemExit

    if options.verbose:
        log.startLogging(sys.stderr)

    launcher = Launcher(options.port)

    if not gstutils.is_port_free(options.port):
        launcher.msg('Controller is already started')
    else:
        launcher.start_controller(options.port)
        
    launcher.load_config(args[1])
    
    launcher.run()

if __name__ == '__main__':
    sys.exit(main(sys.argv))
