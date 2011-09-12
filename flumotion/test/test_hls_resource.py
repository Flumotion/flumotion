# -*- Mode: Python; test-case-name: flumotion.test.test_resource -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2009,2010 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.
# flumotion-fragmented-streaming - Flumotion Advanced  fragmented streaming

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

import base64

from twisted.trial import unittest
from twisted.web import server
from twisted.web.http import Request, HTTPChannel
from twisted.internet import defer, reactor
try:
    from twisted.web import http
except ImportError:
    from twisted.protocols import http

from flumotion.common import keycards, errors
from flumotion.component.consumers.hlsstreamer import resources, hlsring
from flumotion.component.base.http import HTTPAuthentication

MAIN_PLAYLIST=\
"""#EXTM3U
#EXT-X-ALLOW-CACHE:YES
#EXT-X-TARGETDURATION:10
#EXT-X-MEDIA-SEQUENCE:0
#EXTINF:10,
http://localhost/fragment-0.webm
"""

FRAGMENT = 'fragment1'


class FakeStreamer:

    def __init__(self):
        self.clients = 0
        self.currentBitRate = 1000
        self.ready = True
        self.mountPoint = "localhost"
        self.ring = hlsring.HLSRing("main.m3u8",
                "stream.m3u8", "")
        self.ring.setHostname("localhost")
        self.ring.addFragment(FRAGMENT, 0, 10)

        self.medium = FakeAuthMedium()
        self.plugs = {
                'flumotion.component.plugs.request.RequestLoggerPlug': {}}
        self.httpauth = HTTPAuthentication(self)

    def clientAdded(self):
        self.clients += 1

    def clientRemoved(self):
        self.clients -=1

    isReady = lambda s: s.ready
    getClients = lambda s: s.clients
    getCurrentBitrate = lambda s: s.currentBitRate
    getRing = lambda s: s.ring
    getName = lambda s: s.getName


class FakeTransport:

    def __init__(self):
        pass

    def writeSequence(self, seq):
        pass

    def fileno(self):
        return None

    def write(self, data):
        pass

    def read(self, data):
        pass

    def __getatt__(self, attr):
        return ''


class FakeRequest:
    transport = FakeTransport()

    def __init__(self, site, method, path, args={}, onFinish=None):
        self.site = site
        self.method = method
        self.path = path
        self.uri = 'http://'+path
        self.args = args
        self.cookies = {}
        self.session = None
        self.headers = {}
        self.response = http.OK
        self.data = ""
        self.clientproto=''
        self.code=''


        self.onFinish=onFinish

        self.user = "fakeuser"
        self.passwd = "fakepasswd"
        self.ip = "255.255.255.255"

        # fake out request.transport.fileno
        self.fdIncoming = 3

        # copied from test_web.DummyRequest
        self.sitepath = []
        self.prepath = []
        self.postpath = ['']

    def setResponseCode(self, code):
        self.response = code

    def setHeader(self, field, value):
        self.headers[field] = value

    def addCookie(self, cookieName, cookie, path="/"):
        self.cookies[cookieName] = cookie

    def getCookie(self, cookieName):
        return self.cookies.get(cookieName, None)

    def write(self, text):
        self.data = self.data + text

    def finish(self):
        if isinstance(self.onFinish, defer.Deferred):
            self.onFinish.callback(self)

    getUser = lambda s: s.user
    getPassword = lambda s: s.passwd
    getClientIP = lambda s: s.ip
    getAllHeaders = lambda s: s.headers
    getBytesSent = lambda s: ''
    getDuration = lambda s: 0


class FakeAuthMedium:
    # this medium allows HTTP auth with fakeuser/fakepasswd

    def __init__(self):
        self.count = 0

    def authenticate(self, bouncerName, keycard):
        if keycard.username == 'fakeuser' and keycard.password == 'fakepasswd':
            # the medium should also generate a unique keycard ID
            keycard.id = self.count
            self.count += 1
            keycard.state = keycards.AUTHENTICATED
            return defer.succeed(keycard)

        return defer.succeed(None)


class TestAppleStreamerSessions(unittest.TestCase):

    def checkResponse(self, request, expected):
        self.assertEquals(request.data, expected)
        for d in reactor.getDelayedCalls():
            d.cancel()

    def assertUnauthorized(self, request):
        # make the resource authenticate the request, and verify
        # the request is not authorized

        def checkResult(res):
            errorCode = http.UNAUTHORIZED
            self.assertEquals(request.headers.get('content-type', ''),
                'text/html')
            self.assertEquals(request.headers.get('server', ''),
                resources.HTTP_VERSION)
            self.assertEquals(request.response, errorCode)

            expected = resources.ERROR_TEMPLATE % {
                'code': errorCode,
                'error': http.RESPONSES[errorCode]}
            self.checkResponse(request, expected)

            return res

        d = self.streamer.httpauth.startAuthentication(request)
        d.addCallbacks(checkResult, checkResult)
        d1 = self.assertFailure(d, errors.NotAuthenticatedError)
        return d1

    def assertAuthorized(self, request):
        # make the resource authenticate the request, and verify
        # the request is authorized

        def checkResult(res):
            self.assertEquals(request.response, http.OK)

        d = self.streamer.httpauth.startAuthentication(request)
        d.addCallbacks(checkResult, checkResult)
        return d

    def processRequest(self, method, path):
        d = defer.Deferred()
        request = FakeRequest(self.site, method, path, onFinish=d)
        self.resource.render_GET(request)
        return d

    def setUp(self):
        self.streamer = FakeStreamer()
        self.resource = resources.HTTPLiveStreamingResource(
                self.streamer, self.streamer.httpauth, 'secret', 0.001)
        self.site = server.Site(self.resource)

    def testNotReady(self):
        self.streamer.ready = False
        request = FakeRequest(self.site, "GET", "/test")
        self.resource.render_GET(request)
        self.assertEquals(request.response, http.SERVICE_UNAVAILABLE)

    def testServerFull(self):
        self.resource.reachedServerLimits = lambda: True
        request = FakeRequest(self.site, "GET", "/test")
        self.resource.render_GET(request)
        self.assertEquals(request.response, http.SERVICE_UNAVAILABLE)

    def testForbiddenRequest(self):
        request = FakeRequest(self.site, "GET", "test.m3u8")
        self.resource.render_GET(request)
        expected = resources.ERROR_TEMPLATE % {
                'code': http.FORBIDDEN,
                'error': http.RESPONSES[http.FORBIDDEN]}
        self.assertEquals(expected, request.data)

    def testPlaylistNotFound(self):
        d = self.processRequest("GET", "/localhost/test.m3u8")
        expected = resources.ERROR_TEMPLATE % {
                'code': http.NOT_FOUND,
                'error': http.RESPONSES[http.NOT_FOUND]}
        d.addCallback(self.checkResponse, expected)
        return d

    def testFragmentNotFound(self):
        d = self.processRequest("GET", "/localhost/test.ts")
        expected = resources.ERROR_TEMPLATE % {
                'code': http.NOT_FOUND,
                'error': http.RESPONSES[http.NOT_FOUND]}
        d.addCallback(self.checkResponse, expected)
        return d

    def testGetMainPlaylist(self):
        d = self.processRequest("GET", "/localhost/stream.m3u8")
        d.addCallback(self.checkResponse, MAIN_PLAYLIST)
        return d

    def testGetFragment(self):
        d = self.processRequest("GET", "/localhost/fragment-0.webm")
        d.addCallback(self.checkResponse, FRAGMENT)
        return d

    def testNewSession(self):

        def checkSessionCreated(request):
            cookie = request.getCookie(resources.COOKIE_NAME)
            self.failIf(cookie is None)
            sessionID = base64.b64decode(cookie).split(':')[0]
            session = self.site.sessions.get(sessionID, None)
            self.failIf(session is None)
            for d in reactor.getDelayedCalls():
                d.cancel()

        d = self.processRequest("GET", "/localhost/stream.m3u8")
        d.addCallback(checkSessionCreated)
        return d

    def testSessionExpired(self):

        def sessionExpired():
            self.assertEquals(self.streamer.getClients(), 0)
            for d in reactor.getDelayedCalls():
                d.cancel()

        def checkSessionExpired(request):
            cookie = request.getCookie(resources.COOKIE_NAME)
            self.failIf(cookie is None)
            sessionID = base64.b64decode(cookie).split(':')[0]
            session = self.site.sessions.get(sessionID, None)
            self.failIf(session is None)
            d1 = defer.Deferred()
            session.notifyOnExpire(lambda: d1.callback(''))
            return d1

        resources.SESSION_TIMEOUT = 1
        d = self.processRequest("GET", "/localhost/stream.m3u8")
        d.addCallback(checkSessionExpired)
        return d

    def testTokens(self):
        IP1='192.168.1.1'
        IP2='192.168.1.2'
        SESSIONID='1111'

        cookie = self.resource._generateToken(SESSIONID, IP1, 0)
        # Test wrong IP
        self.assertEquals(self.resource._cookieIsValid(
            cookie, IP2, SESSIONID)[0], resources.NOT_VALID)
        # Test Bad Signature
        cookie = self.resource._generateToken(SESSIONID, IP1, 0)
        self.resource.secretKey= 'bad-secret'
        self.assertEquals(self.resource._cookieIsValid(
            cookie, IP1, SESSIONID)[0], resources.NOT_VALID)
        # Test authentication expired
        cookie = self.resource._generateToken(SESSIONID, IP1, 1)
        self.assertEquals(self.resource._cookieIsValid(
            cookie, IP1, SESSIONID)[0], resources.RENEW_AUTH)
        # Test different sessions ID
        cookie = self.resource._generateToken(SESSIONID, IP1, 1)
        self.assertEquals(self.resource._cookieIsValid(
            cookie, IP1, SESSIONID+'1')[0], resources.NOT_VALID)

    def testRenderHTTPAuthUnauthorized(self):
        self.streamer.httpauth.setBouncerName('fakebouncer')
        self.streamer.httpauth.setDomain('FakeDomain')
        request = FakeRequest(self.site, "GET", "/localhost/stream.m3u8")
        request.passwd = 'badpassword'
        return self.assertUnauthorized(request)

    def testRenderHTTPAuthAuthorized(self):
        self.streamer.httpauth.setBouncerName('fakebouncer')
        self.streamer.httpauth.setDomain('FakeDomain')
        request = FakeRequest(self.site, "GET", "/localhost/stream.m3u8")
        return self.assertAuthorized(request)

    def testRenewAuthentication(self):

        def checkSessionID(request):
            # The auth is not valid anymore and has been renewed,
            # but the session should stay the same
            cookie = request.getCookie(resources.COOKIE_NAME)
            self.failIf(cookie is None)
            sessionID, authExpiracy, none = \
                   base64.b64decode(cookie).split(':')
            self.assertEquals(authExpiracy, '10')
            self.assertEquals(sessionID, self.sessionID)
            for d in reactor.getDelayedCalls():
                d.cancel()

        def resendRequest(request):
            cookie = request.getCookie(resources.COOKIE_NAME)
            self.failIf(cookie is None)
            self.sessionID = base64.b64decode(cookie).split(':')[0]
            cookie = self.resource._generateToken(
                   self.sessionID, "255.255.255.255", 10)
            d = defer.Deferred()
            request = FakeRequest(self.site, "GET",
                    "/localhost/stream.m3u8", onFinish=d)
            request.addCookie("flumotion-session", cookie, "/localhost")
            d.addCallback(checkSessionID)
            # Send the same request after 2 seconds, when the auth has
            # expired. The session id should be the same
            reactor.callLater(2, self.resource.render_GET, request)
            return d

        self.streamer.httpauth.setBouncerName('fakebouncer')
        self.streamer.httpauth.setDomain('FakeDomain')
        d = self.processRequest("GET", "/localhost/stream.m3u8")
        d.addCallback(resendRequest)
        return d

if __name__ == '__main__':
    unittest.main()
