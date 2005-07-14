# -*- Mode: Python; test-case-name: flumotion.test.test_http -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

# Headers in this file shall remain intact.

from twisted.internet import defer
from twisted.python import components
from twisted.trial import unittest
from twisted.web import server

from flumotion.component.consumers.httpstreamer import resources
from flumotion.common import interfaces

# From twisted/test/proto_helpers.py
import fcntl
import os

try:
    from twisted.web import http
except ImportError:
    #T1.3
    from twisted.protocols import http

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
        self.data = ""

        self.user = "fakeuser"
        self.passwd = "fakepasswd"
        self.ip = "255.255.255.255"
        
    def setResponseCode(self, code):
        self.response = code
        
    def setHeader(self, field, value):
        self.headers[field] = value
            
    def write(self, text): self.data = self.data + text
    def finish(self): pass

    getUser = lambda s: s.user
    getPassword = lambda s: s.passwd
    getClientIP = lambda s: s.ip

class FakeStreamer:
    caps = None
    mime = 'application/octet-stream'
    
    def __init__(self):
        self.medium = FakeMedium()

    def get_content_type(self): return self.mime
    def add_client(self, fd): pass
    def connect(self, *args): pass
    def debug(self, *args): pass
    def getName(self): return "fakestreamer"

class FakeMedium:
    # this medium just pretends that all authentication requests fail
    def authenticate(self, bouncerName, keycard): return defer.succeed(None)

class TestHTTPStreamingResource(unittest.TestCase):
    def testRenderNotReady(self):
        streamer = FakeStreamer()
        resource = resources.HTTPStreamingResource(streamer)
        self.failIf(resource.isReady())
        status = resource.render(FakeRequest(ip=''))
        self.assertEquals(status,  server.NOT_DONE_YET)

    def testRenderReachedMaxClients(self):
        streamer = FakeStreamer()
        resource = resources.HTTPStreamingResource(streamer)
        self.failIf(resource.isReady())
        streamer.caps = True
        self.failUnless(resource.isReady())
        
        #assert resource.maxAllowedClients() == 974
        resource._requests = ' ' * (resource.maxAllowedClients() + 1)
        
        self.failUnless(resource.reachedMaxClients())
        
        request = FakeRequest(ip='127.0.0.1')
        data = resource.render(request)
        error_code = http.SERVICE_UNAVAILABLE
        self.assertEquals(request.headers.get('content-type', ''), 'text/html')
        self.assertEquals(request.headers.get('server', ''),
            resources.HTTP_VERSION)
        self.assertEquals(request.response, error_code)

        expected = resources.ERROR_TEMPLATE % {
            'code': error_code,
            'error': http.RESPONSES[error_code]}
        self.assertEquals(data,  expected)

    def testRenderUnauthorized(self):
        streamer = FakeStreamer()
        resource = resources.HTTPStreamingResource(streamer)
        resource.setBouncerName('fakebouncer')
        resource.setDomain('FakeDomain')
        
        streamer.caps = True
        self.failUnless(resource.isReady())
        
        request = FakeRequest(ip='127.0.0.1')
        d = resource.authenticate(request)
        d.addCallback(resource._authenticatedCallback, request)
        keycard = unittest.deferredResult(d)
        # keycard should be False if not authed
        self.failIf(keycard)

        error_code = http.UNAUTHORIZED
        self.assertEquals(request.headers.get('content-type', ''), 'text/html')
        self.assertEquals(request.headers.get('server', ''),
            resources.HTTP_VERSION)
        self.assertEquals(request.response, error_code)
        
        expected = resources.ERROR_TEMPLATE % {
            'code': error_code,
            'error': http.RESPONSES[error_code]}
        self.assertEquals(request.data, expected)
    
    def testRenderNew(self):
        streamer = FakeStreamer()
        resource = resources.HTTPStreamingResource(streamer)
        streamer.caps = True
        streamer.mime = 'application/x-ogg'
        
        request = FakeRequest(ip='127.0.0.1')
        data = resource.render(request)
        self.failUnless(server.NOT_DONE_YET)
        
        #assert request.headers['Server'] == HTTP_VERSION
        #assert request.headers['Date'] == 'FakeDate'
        #assert request.headers['Content-Type'] == 'application/x-ogg'
