import ConfigParser
import optik
import os
import signal
import sys
import warnings

warnings.filterwarnings('ignore', category=FutureWarning)

if __name__ == '__main__':
    import gstreactor
    gstreactor.install()

from twisted.internet import reactor
from twisted.python import log
from twisted.web import server, resource

import gstutils

class Launcher:
    def __init__(self):
        self.children = []
        self.controller_pid = None
        
        #signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)

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

        signal.signal(signal.SIGINT, exit_cb)
        reactor.connectTCP('localhost', 8890, component.factory)
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
            log.msg('Starting %s (%s) on pid %d' %
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
            log.msg('Starting %s (%s) on pid %d' %
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
                log.msg('%d is dead pid' % pid)
            except (KeyboardInterrupt, OSError):
                pass
            
        if self.controller_pid:
            try:
                os.kill(self.controller_pid, signal.SIGINT)
            except OSError:
                pass
        
        log.msg('Shutting down reactor')
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

    options, args = parser.parse_args(args)
    if len(args) < 2:
        print 'Need a config file.'
        raise SystemExit

    if options.verbose:
        log.startLogging(sys.stderr)

    launcher = Launcher()

    if not gstutils.is_port_free(8890):
        log.msg('Controller is already started')
    else:
        launcher.start_controller(8890)
        
    launcher.load_config(args[1])
    
    launcher.run()

if __name__ == '__main__':
    sys.exit(main(sys.argv))
