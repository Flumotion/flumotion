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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 
import ConfigParser
import optparse
import os
import signal
import sys
import warnings
import string

warnings.filterwarnings('ignore', category=FutureWarning)

from flumotion.twisted import gstreactor
gstreactor.install()

from twisted.internet import reactor
from twisted.web import server, resource

from flumotion import errors
from flumotion.server import controller
from flumotion.server.converter import Converter
from flumotion.server.producer import Producer
from flumotion.server.streamer import Streamer, StreamingResource
from flumotion.utils import log, gstutils

class Launcher:
    def __init__(self, controller_port):
        self.children = []
        self.controller_pid = None
        self.controller_port = controller_port
        
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
                pass
            
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
    
def get_options_for(kind, args):
    if kind == 'producer':
        need_pipeline = True
        need_sources = False
    elif kind == 'converter':
        need_pipeline = True
        need_sources = True
    elif kind == 'streamer':
        need_pipeline = False
        need_sources = True
    else:
        raise AssertionError
    
    parser = optparse.OptionParser()
    parser.add_option('-c', '--controller-host',
                      action="store", type="string", dest="host",
                      default="localhost",
                      help="Controller to connect to [default localhost]")
    parser.add_option('', '--controller-port',
                      action="store", type="int", dest="port",
                      default=8890,
                      help="Controller port to connect to [default 8890]")
    parser.add_option('-n', '--name',
                      action="store", type="string", dest="name",
                      default=None,
                      help="Name of component")
    if need_pipeline:
        parser.add_option('-p', '--pipeline',
                          action="store", type="string", dest="pipeline",
                          default=None,
                          help="Pipeline to run")
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="Be verbose")

    if need_sources:
        parser.add_option('-s', '--sources',
                          action="store", type="string", dest="sources",
                          default="",
                          help="Host sources to get data from, separated by ,")

    if kind == 'streamer':
        parser.add_option('-p', '--protocol',
                          action="store", type="string", dest="protocol",
                          default="http",
                          help="Protocol to use [default http]")
        parser.add_option('-o', '--listen-port',
                          action="store", type="int", dest="listen_port",
                          default=8080,
                          help="Port to bind to [default 8080]")
        
    options, args = parser.parse_args(args)

    if options.name is None:
        raise errors.OptionError, 'Need a name'
    elif need_pipeline and options.pipeline is None:
        raise errors.OptionError, 'Need a pipeline'
    elif need_sources and options.sources is None:
        raise OptionError, 'Need a source'
    elif kind == 'streamer':
        if not options.protocol:
            raise errors.OptionError, 'Need a protocol'
        elif not options.listen_port:
            raise errors.OptionError, 'Need a listen_port'
            return 2
        
    if options.verbose:
        log.startLogging(sys.stdout)

    if need_sources:
        if ',' in  options.sources:
            options.sources = options.sources.split(',')
        else:
            options.sources = [options.sources]
    else:
        options.sources = []
        
    return options

def run_launcher(config_file):
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="Be verbose")
    parser.add_option('-c', '--controller-port',
                      action="store", type="int", dest="port",
                      help="Controller port", default=8890)

    options, args = parser.parse_args(args)

    if options.verbose:
        log.startLogging(sys.stderr)

    launcher = Launcher(options.port)

    if not gstutils.is_port_free(options.port):
        launcher.msg('Controller is already started')
    else:
        launcher.start_controller(options.port)
        
    launcher.load_config(config_file)
        
    launcher.run()

def run_component(name, args):
    try:
        options = get_options_for(name, args)
    except errors.OptionError, e:
        print 'ERROR:', e
        raise SystemExit

    if name == 'producer':
        klass = Producer
        args = (options.name, options.sources, options.pipeline)
    elif name == 'converter':
        klass = Converter
        args = (options.name, options.sources, options.pipeline)
    elif name == 'streamer':
        klass = Streamer
        args = (options.name, options.sources)
    else:
        raise AssertionError
        
    try:
        component = klass(*args)
    except errors.PipelineParseError, e:
        print 'Bad pipeline: %s' % e
        raise SystemExit
    
    reactor.connectTCP(options.host, options.port, component.factory)
    
    if name == 'streamer':
        if options.protocol == 'http':
            web_factory = server.Site(resource=StreamingResource(component))
        else:
            print 'Only http protcol supported right now'
            return
        
        reactor.listenTCP(options.listen_port, web_factory)
    
    reactor.run()

def run_controller(port=8890):
    log.msg('controller', 'Starting at port %d' % port)
    factory = controller.ControllerServerFactory()
    reactor.listenTCP(port, factory)
    reactor.run()

    return 0
    
def main(args):
    if len(args) < 2:
        print 'Usage: flumotion [config file or component] .'
        raise SystemExit

    name = args[1]
    if name in 'controller':
        return run_controller()
    elif name in ['producer', 'converter', 'streamer']:
        return run_component(args[1], args[2:])
    elif os.path.exists(args[1]):
        return run_launcher(args[1])
    else:
        raise AssertionError

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
