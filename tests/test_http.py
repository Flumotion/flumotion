import common
import unittest

from twisted.protocols import http as twisted_http
from twisted.python import components
from twisted.web import server

from flumotion.component.http import http
from flumotion.common import interfaces

# From twisted/test/proto_helpers.py
import fcntl
import os

class PipeTransport:
    def __init__(self):
        self.rfd, self.wfd = os.pipe()
        fcntl.fcntl(self.rfd, fcntl.F_SETFL, os.O_NONBLOCK)

    def fileno(self): return self.wfd
    def write(self, data): os.write(self.wfd, data)
    def read(self, len=4096): return os.read(self.rfd, len)

    def readall(self):
        data = ''
        while 1:
            try:
                data += self.read()
            except OSError:
                break
        return data
        
class FakeRequest:
    transport = PipeTransport()
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.headers = {}
        self.response = -1
        
    def setResponseCode(self, code):
        self.response = code
        
    def setHeader(self, field, value):
        self.headers[field] = value
            
    getUser = lambda s: s.user
    getPassword = lambda s: s.passwd
    getClientIP = lambda s: s.ip

class FakeStreamer:
    caps = None
    mime = 'application/octet-stream'
    
    def get_content_type(self): return self.mime
    def add_client(self, fd): pass
    def connect(self, *args): pass
    def debug(self, *args): pass

class FakeAuth:
    def __init__(self, response):
        self.response = response
    def authenticate(self, *args): return self.response
    def getDomain(self): return 'FakeDomain'
    
class TestHTTPClientKeycard(unittest.TestCase):
    def testCreate(self):
        keycard = http.HTTPClientKeycard(None)
        assert components.implements(keycard, interfaces.IClientKeycard)

    def testParms(self):
        fake = FakeRequest(user='username',
                           passwd='password',
                           ip='127.0.0.1')
        keycard = http.HTTPClientKeycard(fake)
        assert keycard.request == fake
        assert keycard.getUsername() == 'username'
        assert keycard.getPassword() == 'password'
        assert keycard.getIP() == '127.0.0.1'

class TestHTTPStreamingResource(unittest.TestCase):
    def testRenderNotReady(self):
        streamer = FakeStreamer()
        resource = http.HTTPStreamingResource(streamer)
        assert not resource.isReady()
        status = resource.render(FakeRequest(ip=''))
        assert status == server.NOT_DONE_YET

    def testRenderReachedMaxClients(self):
        streamer = FakeStreamer()
        resource = http.HTTPStreamingResource(streamer)
        assert not resource.isReady()
        streamer.caps = True
        assert resource.isReady()
        
        #assert resource.maxAllowedClients() == 974
        resource.request_hash = ' ' * (resource.maxAllowedClients() + 1)
        
        assert resource.reachedMaxClients()
        
        request = FakeRequest(ip='127.0.0.1')
        data = resource.render(request)
        error_code = twisted_http.SERVICE_UNAVAILABLE
        assert request.headers.get('content-type', '') == 'text/html'
        assert request.headers.get('server', '') == http.HTTP_VERSION
        assert request.response == error_code

        expected = http.ERROR_TEMPLATE % {'code': error_code,
                                          'error': twisted_http.RESPONSES[error_code]}
        assert data == expected

    def testRenderUnauthorized(self):
        streamer = FakeStreamer()
        resource = http.HTTPStreamingResource(streamer)
        resource.setAuth(FakeAuth(False))
        
        streamer.caps = True
        assert resource.isReady()
        
        request = FakeRequest(ip='127.0.0.1')
        data = resource.render(request)

        error_code = twisted_http.UNAUTHORIZED
        assert request.headers.get('content-type', '') == 'text/html'
        assert request.headers.get('server', '') == http.HTTP_VERSION
        assert request.response == error_code
        
        expected = http.ERROR_TEMPLATE % {'code': error_code,
                                          'error': twisted_http.RESPONSES[error_code]}
        assert data == expected

    def testRenderNew(self):
        streamer = FakeStreamer()
        resource = http.HTTPStreamingResource(streamer)
        streamer.caps = True
        streamer.mime = 'application/x-ogg'
        
        request = FakeRequest(ip='127.0.0.1')
        data = resource.render(request)
        assert server.NOT_DONE_YET
        
        #assert request.headers['Server'] == HTTP_VERSION
        #assert request.headers['Date'] == 'FakeDate'
        #assert request.headers['Content-Type'] == 'application/x-ogg'
        
if __name__ == '__main__':
    unittest.main()
