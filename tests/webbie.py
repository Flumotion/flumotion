import sys
sys.path.append('..')

from flumotion.twisted import gstreactor
gstreactor.install()

from twisted.web import server, resource
from twisted.internet import reactor
from twisted.python import log

from flumotion.utils import gstutils

import gobject
import gst

class Streamer(resource.Resource):
    def __init__(self, pipeline, mime):
        resource.Resource.__init__(self)
        self.mime = mime
        self.pipeline = gst.parse_launch('%s ! multifdsink name=sink' % pipeline)
        self.pipeline.connect('deep-notify', gstutils.verbose_deep_notify_cb, self)
        self.pipeline.connect('state-change', self.state_change_cb)
        self.pipeline.set_state(gst.STATE_PLAYING)
        gobject.idle_add(self.pipeline.iterate)
        
        self.caps = None

    def state_change_cb(self, element, old, state):
        self.msg('state-changed %s %s' % (element.get_path_string(),
                                          gst.element_state_get_name(state)))

    def add_client(self, fd):
        print 'client added', fd
        sink = self.get_sink()
        sink.emit('add', fd)

    def remove_client(self, fd):
        print 'client removed', fd
        sink = self.get_sink()
        sink.emit('remove', fd)
        
    def get_sink(self):
        assert self.pipeline, 'Pipeline not created'
        sink = self.pipeline.get_by_name('sink')
        assert sink, 'No sink element in pipeline'
        assert isinstance(sink, gst.Element)
        return sink

    def lost(self, obj, fd, ip):
        self.remove_client(fd)
        self.msg('client from %s disconnected' % ip)

    def isReady(self):
        sink = self.get_sink()
        if sink:
            return True
        
        return False
        
    def getChild(self, path, request):
        return self

    def msg(self, msg):
        print msg
        
    def render(self, request):
        ip = request.getClientIP()
        self.msg('client from %s connected' % ip)
    
        if not self.isReady():
            self.msg('Not sending data, it\'s not ready')
            return server.NOT_DONE_YET

        self.msg('setting Content-type to %s' % self.mime)
        request.setHeader('Content-type', self.mime)
        
        fd = request.transport.fileno()
        self.msg('adding client %r' % fd)
        self.add_client(fd)
        request.notifyFinish().addBoth(self.lost, fd, ip)
        
        request.write('')
        
        return server.NOT_DONE_YET

#log.startLogging(sys.stderr)

s = Streamer(sys.argv[1], sys.argv[2])
print 'Listening on 8080'
reactor.listenTCP(8080, server.Site(resource=s))
reactor.run()
