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

from controller import ControllerServerFactory
from producer import Producer
from converter import Converter
from streamer import Streamer, StreamingResource


def disable_stderr(suffix):
    #print 'disable', suffix
    fd = file('/tmp/stderr-%d' % suffix, 'w+')
                   
    sys.stderr = os.fdopen(os.dup(2), 'w')
    os.close(2)
    os.dup(fd.fileno())

    return fd

def enable_stderr(fd, suffix):
    os.close(2)
    try:
        os.dup(sys.stderr.fileno())
    except OSError:
        return []

    #print 'seeking', suffix
    fd.seek(0, 0)
    data = fd.read()
    #print 'closing', suffix
    fd.close()
    os.remove('/tmp/stderr-%d' % suffix)

    return [line for line in data.split('\n')]

CONTROLLER_PORT = 9802
class Launcher:
    streaming_port = 8080
    def __init__(self):
        self.children = []

        #signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)

        pid = os.fork()
        if not pid:
            self.controller = reactor.listenTCP(CONTROLLER_PORT,
                                                ControllerServerFactory())
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
            fd = disable_stderr(pid)
            for line in enable_stderr(fd, pid):
                if line.find('(null)') != -1:
                    continue
                if line.find('Interrupted system call') != -1:
                    continue
                if line:
                    print line
            component.stop()
            raise SystemExit

        #fd = disable_stderr(pid)
        signal.signal(signal.SIGINT, exit_cb)
        reactor.connectTCP('localhost', CONTROLLER_PORT, component.factory)
        try:
            reactor.run(False)
        except KeyboardInterrupt:
            pass
        component.stop()
        print 'Leaving spawn()'

    def start(self, component):
        pid = os.fork()
        if not pid:
            self.spawn(component)
            raise SystemExit
        else:
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
                print pid, 'is dead'
            except (KeyboardInterrupt, OSError):
                pass
            
        #print >> sys.stderr, '**** WAITING FOR CONTROLLER'
        try:
            os.kill(self.controller_pid, signal.SIGINT)
        except OSError:
            pass
        
        print '*** STOPPING MAINLOOP'
        reactor.stop()


        raise SystemExit
    
PRODUCER_PIPELINE = 'videotestsrc ! video/x-raw-yuv,width=160,height=120,framerate=15.0,format=(fourcc)I420'
PRODUCER2_PIPELINE = 'sinesrc'
CONVERTER_PIPELINE = '{ @producer1 ! ffmpegcolorspace ! jpegenc quality=50 ! queue name=video max-size-buffers=0 max-size-bytes=0 max-size-time=2000000000 } ' + \
                     '{ @producer2 ! audioconvert ! queue name=audio max-size-buffers=0 max-size-bytes=0 max-size-time=2000000000 } ' + \
                     'video.src ! multipartmux name=muxer audio.src ! muxer. muxer.'

def is_port_free(port):
    import socket
    fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        fd.bind(('', port))
    except socket.error:
        return False
    return True

if __name__ == '__main__':
    #log.startLogging(file('all.log', 'w'), False)
    log.startLogging(sys.stderr)

    if not is_port_free(CONTROLLER_PORT):
        log.msg('Port %d is already used.' % CONTROLLER_PORT)
        raise SystemExit
    
    launcher = Launcher()
    
    launcher.start(Producer('producer1', [], PRODUCER_PIPELINE))
    launcher.start(Producer('producer2', [], PRODUCER2_PIPELINE))
    launcher.start(Converter('converter', ['producer1', 'producer2'], CONVERTER_PIPELINE))
    
    streamer = Streamer('streamer', ['converter'])
    reactor.listenTCP(8081,
                      server.Site(resource=StreamingResource(streamer)))
    launcher.start(streamer)
    
    launcher.run()
