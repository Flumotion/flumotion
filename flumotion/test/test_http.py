# -*- Mode: Python; test-case-name: flumotion.test.test_http -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

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

import common

from twisted.internet import defer
from twisted.trial import unittest
from twisted.web import server

from flumotion.component.consumers.httpstreamer import resources
from flumotion.common import interfaces, keycards, log
from flumotion.twisted.defer import defer_generator_method

# From twisted/test/proto_helpers.py
import fcntl
import os

try:
    from twisted.web import http
except ImportError:
    #T1.3
    from twisted.protocols import http

import twisted.copyright #T1.3
#T1.3
def weHaveAnOldTwisted():
    return twisted.copyright.version[0] < '2'

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
    uri = 'http://fake/'

    def __init__(self, **kwargs):
        self.headers = {}
        self.response = -1
        self.data = ""

        self.user = "fakeuser"
        self.passwd = "fakepasswd"
        self.ip = "255.255.255.255"

        # fake out request.transport.fileno
        self.fdIncoming = 3

        # copied from test_web.DummyRequest
        self.sitepath = []
        self.prepath = []
        self.postpath = ['']

        self.__dict__.update(kwargs)
        
    def setResponseCode(self, code):
        self.response = code
        
    def setHeader(self, field, value):
        self.headers[field] = value
            
    def write(self, text): self.data = self.data + text
    def finish(self): pass

    getUser = lambda s: s.user
    getPassword = lambda s: s.passwd
    getClientIP = lambda s: s.ip

# fake mediums that only do authenticate

class FakeAuthMedium:
    # this medium allows HTTP auth with fakeuser/fakepasswd
    def authenticate(self, bouncerName, keycard):
        if keycard.username == 'fakeuser' and keycard.password == 'fakepasswd':
            keycard.state = keycards.AUTHENTICATED
            return defer.succeed(keycard)

        return defer.succeed(None)

class FakeTokenMedium:
    # this medium allows HTTP auth if there is a "LETMEIN" token
    def authenticate(self, bouncerName, keycard):
        if keycard.token == 'LETMEIN':
            keycard.state = keycards.AUTHENTICATED
            return defer.succeed(keycard)

        return defer.succeed(None)

class FakeStreamer:
    caps = None
    mime = 'application/octet-stream'
    
    def __init__(self, mediumClass=FakeAuthMedium):
        self.medium = mediumClass()
        self.plugs = {'flumotion.component.plugs.loggers.Logger': {}}

    def get_content_type(self): return self.mime
    def add_client(self, fd): pass
    def connect(self, *args): pass
    def debug(self, *args): pass
    def getName(self): return "fakestreamer"

class TestHTTPStreamingResource(unittest.TestCase):
    # helpers
    def assertUnauthorized(self, resource, request):
        # make the resource authenticate the request, and verify
        # the request is not authorized
        d = resource.authenticate(request)
        d.addCallback(resource._authenticatedCallback, request)
        if weHaveAnOldTwisted():
            unittest.deferredResult(d)
        else:
            yield d

        error_code = http.UNAUTHORIZED
        self.assertEquals(request.headers.get('content-type', ''), 'text/html')
        self.assertEquals(request.headers.get('server', ''),
            resources.HTTP_VERSION)
        self.assertEquals(request.response, error_code)
        
        expected = resources.ERROR_TEMPLATE % {
            'code': error_code,
            'error': http.RESPONSES[error_code]}
        self.assertEquals(request.data, expected)
    assertUnauthorized = defer_generator_method(assertUnauthorized)
 
    def assertAuthorized(self, resource, request):
        # make the resource authenticate the request, and verify
        # the request is authorized
        d = resource.authenticate(request)
        d.addCallback(resource._authenticatedCallback, request)
        if weHaveAnOldTwisted():
            unittest.deferredResult(d)
        else:
            yield d

        self.failIfEquals(request.response, http.UNAUTHORIZED)
    assertAuthorized = defer_generator_method(assertAuthorized)

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
        resource._requests = ' ' * (resource.maxclients + 1)
        
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

    def testRenderHTTPAuthUnauthorized(self):
        streamer = FakeStreamer()
        resource = resources.HTTPStreamingResource(streamer)
        resource.setBouncerName('fakebouncer')
        resource.setDomain('FakeDomain')
        
        streamer.caps = True
        self.failUnless(resource.isReady())
        
        request = FakeRequest(ip='127.0.0.1', user='wronguser')
        self.assertUnauthorized(resource, request)

    def testRenderHTTPTokenUnauthorized(self):
        streamer = FakeStreamer(mediumClass=FakeTokenMedium)
        resource = resources.HTTPStreamingResource(streamer)
        # override issuer
        resource.setIssuerClass('HTTPTokenIssuer')
        resource.setBouncerName('fakebouncer')
        resource.setDomain('FakeDomain')
        
        streamer.caps = True
        self.failUnless(resource.isReady())
        
        # wrong token
        request = FakeRequest(ip='127.0.0.1', args={'token': 'WRONG'})
        self.assertUnauthorized(resource, request)

        # no token
        request = FakeRequest(ip='127.0.0.1', args={'notoken': 'LETMEIN'})
        self.assertUnauthorized(resource, request)

        # doublewrong token
        request = FakeRequest(ip='127.0.0.1',
            args={'token': ['WRONG', 'AGAIN']})
        self.assertUnauthorized(resource, request)

    def testRenderHTTPTokenAuthorized(self):
        streamer = FakeStreamer(mediumClass=FakeTokenMedium)
        resource = resources.HTTPStreamingResource(streamer)
        # override issuer
        resource.setIssuerClass('HTTPTokenIssuer')
        resource.setBouncerName('fakebouncer')
        resource.setDomain('FakeDomain')
        
        streamer.caps = True
        self.failUnless(resource.isReady())
        
        # right token
        request = FakeRequest(ip='127.0.0.1', args={'token': 'LETMEIN'})
        self.assertAuthorized(resource, request)

        # right token, twice
        request = FakeRequest(ip='127.0.0.1',
            args={'token': ['LETMEIN', 'LETMEIN']})
        self.assertAuthorized(resource, request)

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

class TestHTTPRoot(unittest.TestCase):
    def testRenderRootStreamer(self):
        # a streamer that is at /
        root = resources.HTTPRoot()
        site = server.Site(resource=root)

        streamer = FakeStreamer()
        resource = resources.HTTPStreamingResource(streamer)
        root.putChild('', resource)

        log.debug('unittest', 'requesting root, should work')
        request = FakeRequest(ip='')
        r = site.getResourceFor(request)
        self.assertEquals(r, resource)
        output = r.render(request)
        self.assertEquals(output,  server.NOT_DONE_YET)

        # a request for a/b should give 404
        log.debug('unittest', 'requesting a/b, should 404')
        request = FakeRequest(ip='', postpath=['a', 'b'])
        r = site.getResourceFor(request)
        output = r.render(request)
        self.assertEquals(request.response,  http.NOT_FOUND)

    def testRenderTopStreamer(self):
        # a streamer that is at /a
        root = resources.HTTPRoot()
        site = server.Site(resource=root)

        streamer = FakeStreamer()
        resource = resources.HTTPStreamingResource(streamer)
        root.putChild('a', resource)

        # a request for root should give 404
        log.debug('unittest', 'requesting root, should 404')
        request = FakeRequest(ip='')
        r = site.getResourceFor(request)
        output = r.render(request)
        self.assertEquals(request.response,  http.NOT_FOUND)

        # a request for a should work
        log.debug('unittest', 'requesting a, should work')
        request = FakeRequest(ip='', postpath=['a'])
        r = site.getResourceFor(request)
        self.assertEquals(r, resource)
        output = r.render(request)
        self.assertEquals(output,  server.NOT_DONE_YET)

        # a request for a/b should give 404
        log.debug('unittest', 'requesting a/b, should 404')
        request = FakeRequest(ip='', postpath=['a', 'b'])
        r = site.getResourceFor(request)
        output = r.render(request)
        self.assertEquals(request.response,  http.NOT_FOUND)

    def testRenderTreeStreamer(self):
        # a streamer that is at /a/b
        root = resources.HTTPRoot()
        site = server.Site(resource=root)

        streamer = FakeStreamer()
        resource = resources.HTTPStreamingResource(streamer)
        root.putChild('a/b', resource)

        # a request for root should give 404
        log.debug('unittest', 'requesting root, should 404')
        request = FakeRequest(ip='')
        r = site.getResourceFor(request)
        output = r.render(request)
        self.assertEquals(request.response,  http.NOT_FOUND)

        # a request for a/b should work
        log.debug('unittest', 'requesting a/b, should work')
        request = FakeRequest(ip='', postpath=['a', 'b'])
        r = site.getResourceFor(request)
        self.assertEquals(r, resource)
        output = r.render(request)
        self.assertEquals(output,  server.NOT_DONE_YET)
