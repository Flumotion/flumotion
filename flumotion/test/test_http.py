# -*- Mode: Python; test-case-name: flumotion.test.test_http -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_http.py: regression test for HTTP component
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from twisted import protocols
from twisted.python import components
from twisted.trial import unittest
from twisted.web import server

from flumotion.component.consumers.httpstreamer import resources
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
    method = 'GET'
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.headers = {}
        self.response = -1

        self.user = "fakeuser"
        self.passwd = "fakepasswd"
        self.ip = "255.255.255.255"
        
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
    def get_name(self): return "fakestreamer"

class FakeAuth:
    def __init__(self, response):
        self.response = response
    def authenticate(self, *args): return self.response
    def getDomain(self): return 'FakeDomain'

class TestHTTPStreamingResource(unittest.TestCase):
    def testRenderNotReady(self):
        streamer = FakeStreamer()
        resource = resources.HTTPStreamingResource(streamer)
        assert not resource.isReady()
        status = resource.render(FakeRequest(ip=''))
        assert status == server.NOT_DONE_YET

    def testRenderReachedMaxClients(self):
        streamer = FakeStreamer()
        resource = resources.HTTPStreamingResource(streamer)
        assert not resource.isReady()
        streamer.caps = True
        assert resource.isReady()
        
        #assert resource.maxAllowedClients() == 974
        resource._requests = ' ' * (resource.maxAllowedClients() + 1)
        
        assert resource.reachedMaxClients()
        
        request = FakeRequest(ip='127.0.0.1')
        data = resource.render(request)
        error_code = protocols.http.SERVICE_UNAVAILABLE
        assert request.headers.get('content-type', '') == 'text/html'
        assert request.headers.get('server', '') == resources.HTTP_VERSION
        assert request.response == error_code

        expected = resources.ERROR_TEMPLATE % {'code': error_code,
                                               'error': protocols.http.RESPONSES[error_code]}
        assert data == expected

    def testRenderUnauthorized(self):
        streamer = FakeStreamer()
        resource = resources.HTTPStreamingResource(streamer)
        resource.setAuth(FakeAuth(False))
        
        streamer.caps = True
        assert resource.isReady()
        
        request = FakeRequest(ip='127.0.0.1')
        data = resource.render(request)

        error_code = protocols.http.UNAUTHORIZED
        assert request.headers.get('content-type', '') == 'text/html'
        assert request.headers.get('server', '') == resources.HTTP_VERSION
        assert request.response == error_code
        
        expected = resources.ERROR_TEMPLATE % {'code': error_code,
                                               'error': protocols.http.RESPONSES[error_code]}
        assert data == expected
    testRenderUnauthorized.skip = "Thomas needs to update this"
    
    def testRenderNew(self):
        streamer = FakeStreamer()
        resource = resources.HTTPStreamingResource(streamer)
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
