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
import pwd

try:
    warnings.filterwarnings('ignore', category=FutureWarning)
except:
    pass

sys_argv = sys.argv
sys.argv = sys_argv[:1]
import gst
sys.argv = sys_argv

from flumotion.twisted import gstreactor
gstreactor.install()


from twisted.internet import reactor
from twisted.web import server, resource

from flumotion import errors, twisted
from flumotion.server.controller import ControllerServerFactory
from flumotion.server.converter import Converter
from flumotion.server.producer import Producer
from flumotion.server import streamer
from flumotion.utils import log, gstutils

def set_proc_text(text):
    return

    i = 0
    for item in proc:
        n = len(item)
        if not text:
            value = '\0'
        elif len(text) > n:
            value = text[:n+1] 
            text = text[n:]
        else:
            value = text + '\0'
            text = None

        print '%d = %r' % (i, value)
        proc[i] = value
        i += 1
        
    #print len(proc)
    #proc[0] = 'flumotion - laun'
    #proc[1] = 'cher\0'
    #proc[2] = '\0'
    #proc[3] = '\0'
    #proc[4] = '\0'
    
class Launcher:
    def __init__(self, host, port):
        self.children = []
        self.controller_pid = None
        self.uid = None
        self.controller_host = host
        self.controller_port = port
        
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        signal.signal(signal.SIGSEGV, self.segv_handler)
        
        set_proc_text('flumotion [launcher]')
        
    def setup_uid(self, name):
        if self.uid is not None:
            try:
                os.setuid(self.uid)
                self.msg('uid set to %d for %s' % (self.uid, name))
            except OSError, e:
                self.msg('failed to set uid: %s' % str(e))

    def msg(self, *args):
        log.msg('launcher', *args)

    def set_nice(self, nice, name):
        if nice:
            try:
                os.nice(nice)
            except OSError, e:
                self.msg('Failed to set nice level: %s' % str(e))
            else:
                self.msg('Nice level set to %d' % nice)

        self.setup_uid(name)
        
    def start_controller(self):
        pid = os.fork()
        self.msg('Starting controller')
        if not pid:
            self.setup_uid('controller')
            set_proc_text('flumotion [controller]')
            factory = ControllerServerFactory()
            self.controller = reactor.listenTCP(self.controller_port,
                                                factory)
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

    def segv_handler(self, *args):
        print args
        
    def spawn(self, component):
        pid = os.getpid()
        def exit_cb(*args):
            print 'EXIT'
            component.pipeline_stop()
            raise SystemExit

        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        signal.signal(signal.SIGINT, exit_cb)
        reactor.connectTCP(self.controller_host,
                           self.controller_port,
                           component.factory)
        
        try:
            reactor.run(False)
        except KeyboardInterrupt:
            pass
        component.pipeline_stop()

    def start(self, component, nice, func=None, *args):
        pid = os.fork()
        if not pid:
            if func:
                func(*args)
            self.set_nice(nice, component.component_name)
            set_proc_text('flumotion [%s]' % component.component_name)
            self.spawn(component)
            raise SystemExit
        else:
            self.msg('Starting %s (%s) on pid %d' %
                    (component.component_name,
                     component.getKind(),
                     pid))
            self.children.append(pid)

    def run(self):
        self.setup_uid('launcher')
        
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

    def parse_globals(self, conf):
        if conf.has_option('global', 'username'):
            username = conf.get('global', 'username')
            entry = pwd.getpwnam(username)
            self.uid = entry[2]
        
    def load_config(self, filename):
        c = ConfigParser.ConfigParser()
        self.msg('Loading configuration file `%s\'' % filename)
        c.read(filename)

        components = {}
        for section in c.sections():
            if section == 'global':
                self.parse_globals(c)
                continue
            
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
                if c.has_option(section, 'feeds'):
                    feeds = c.get(section, 'feeds').split(',')
                else:
                    feeds = ['default']
            else:
                feeds = []
                pipeline = ''
                
            if kind == 'converter' or kind == 'streamer':
                assert (c.has_option(section, 'source') or
                        c.has_option(section, 'sources'))
                if c.has_option(section, 'source'):
                    sources = [c.get(section, 'source')]
                else:
                    sources = c.get(section, 'sources').split(',')
            else:
                sources = []

            if c.has_option(section, 'nice'):
                nice = c.getint(section, 'nice')
            else:
                nice = 0
                
            if kind == 'producer':
                self.start(Producer(name, sources, feeds, pipeline), nice)
            elif kind == 'converter':
                self.start(Converter(name, sources, feeds, pipeline), nice)
            elif kind == 'streamer':
                assert c.has_option(section, 'protocol')
                protocol = c.get(section, 'protocol')
                
                if protocol == 'http':
                    assert c.has_option(section, 'port')
                    port = c.getint(section, 'port')
                    if c.has_option(section, 'logfile'):
                        logfile = c.get(section, 'logfile')
                    else:
                        logfile = None

                    def setup(port, component):
                        resource = streamer.HTTPStreamingResource(component, logfile)
                        factory = server.Site(resource=resource)
                        reactor.listenTCP(port, factory)
                        
                    component = streamer.MultifdSinkStreamer(name, sources)
                    self.msg('Starting http factory at port %d' % port)
                    self.start(component, nice, setup, port, component)
                elif protocol == 'file':
                    assert c.has_option(section, 'location')
                    location = c.get(section, 'location')
                    if c.has_option(section, 'port'):
                        port = c.getint(section, 'port')
                    else:
                        port = None
                    def setup(port, component):
                        factory = component.create_admin()
                        reactor.listenTCP(port, factory)
                        
                    component = streamer.FileSinkStreamer(name, sources, location)
                    self.start(component, nice, setup, port, component)
                else:
                    raise AssertionError, "unknown protocol: %s" % protocol
            else:
                raise AssertionError, "unknown component kind: %s" % kind
    
def get_options_for(kind, args):
    if kind == 'producer':
        need_sources = False
        need_pipeline = True
    elif kind == 'converter':
        need_sources = True
        need_pipeline = True
    elif kind == 'streamer':
        need_sources = True
        need_pipeline = False
    else:
        raise AssertionError

    usage = "usage: flumotion %s [options]" % kind
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="Be verbose")
    
    group = optparse.OptionGroup(parser, '%s%s options' % (kind[0].upper(),
                                                           kind[1:]))
    group.add_option('-n', '--name',
                     action="store", type="string", dest="name",
                     default=None,
                     help="Name of component")
    if need_pipeline:
        group.add_option('-p', '--pipeline',
                         action="store", type="string", dest="pipeline",
                         default=None,
                         help="Pipeline to run")
        group.add_option('-f', '--feeds',
                         action="store", type="string", dest="feeds",
                         default=[],
                         help="Feeds to provide")

    if need_sources:
        group.add_option('-s', '--sources',
                         action="store", type="string", dest="sources",
                         default="",
                         help="Host sources to get data from, separated by ,")

    if kind == 'streamer':
        group.add_option('-p', '--protocol',
                         action="store", type="string", dest="protocol",
                         default="http",
                         help="Protocol to use [default http]")
        group.add_option('-o', '--listen-port',
                         action="store", type="int", dest="listen_port",
                         default=8080,
                         help="Port to bind to [default 8080]")
    parser.add_option_group(group)
    
    group = optparse.OptionGroup(parser, "Controller options")
    group.add_option('-c', '--controller-host',
                     action="store", type="string", dest="host",
                     default="localhost",
                     help="Controller to connect to [default localhost]")
    group.add_option('', '--controller-port',
                     action="store", type="int", dest="port",
                     default=8890,
                     help="Controller port to connect to [default 8890]")
    parser.add_option_group(group)

    options, args = parser.parse_args(args)

    if options.name is None:
        raise errors.OptionError, 'Need a name'
    elif need_pipeline:
        if options.pipeline is None:
            raise errors.OptionError, 'Need a pipeline'
        if options.feeds is None:
            raise errors.OptionError, 'Need feeds'
        else:
            options.feeds = options.feeds.split(',')
    elif need_sources and options.sources is None:
        raise OptionError, 'Need a source'
    elif kind == 'streamer':
        if not options.protocol:
            raise errors.OptionError, 'Need a protocol'
        elif not options.listen_port:
            raise errors.OptionError, 'Need a listen_port'
            return 2

    if options.verbose:
        log.enableLogging()

    if need_sources:
        if ',' in  options.sources:
            options.sources = options.sources.split(',')
        else:
            options.sources = [options.sources]
    else:
        options.sources = []
        
    return options

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
    
    if options.verbose:
        log.enableLogging()

    launcher = Launcher(options.host, options.port)
    launcher.load_config(args[2])

    if options.host == 'localhost':
        if not gstutils.is_port_free(options.port):
            launcher.msg('Controller is already started')
        else:
            launcher.start_controller()

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

    factory = ControllerServerFactory()
    
    log.msg('controller', 'Starting at port %d' % options.port)
    reactor.listenTCP(options.port, factory)
    reactor.run()

    return 0

def run_component(name, args):
    try:
        options = get_options_for(name, args)
    except errors.OptionError, e:
        print 'ERROR:', e
        raise SystemExit

    if name == 'producer':
        klass = Producer
        args = (options.name, options.sources, options.feeds, options.pipeline)
    elif name == 'converter':
        klass = Converter
        args = (options.name, options.sources, options.feeds, options.pipeline)
    elif name == 'streamer':
        # IGNORE THIS
        if options.protocol == 'http':
            web_factory = server.Site(resource=streamer.StreamingResource(component))
            reactor.listenTCP(options.listen_port, web_factory)
            klass = streamer.FakeSinkStreamer
            args = (options.name, options.sources)
        elif options.protocol == 'file':
            klass = streamer.FileStreamer
            args = (options.name, options.sources, options.location)
        else:
            print 'Only http and file protcol supported right now'
            return
    else:
        raise AssertionError
        
    try:
        print klass, args
        component = klass(*args)
    except twisted.errors.PipelineParseError, e:
        print 'Bad pipeline: %s' % e
        raise SystemExit
    
    reactor.connectTCP(options.host, options.port, component.factory)
    
    reactor.run()

def usage():
    print 'Usage: flumotion command [command-options-and-arguments]'
    
def show_commands():
    print 'Flumotion commands are:'
    print '\tlauncher      Component launcher'
    print '\tcontroller    Component controller'
    print '\tproducer      Producer component'
    print '\tconverter     Converter component'
    print '\tstreamer      Streamer component'
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
    if name in ['producer', 'converter', 'streamer']:
        return run_component(args[1], args[2:])
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
