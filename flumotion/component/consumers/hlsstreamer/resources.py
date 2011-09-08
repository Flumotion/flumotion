# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

import time
import base64
import hmac
import socket
import uuid
import resource
from datetime import datetime, timedelta

from twisted.internet import defer, reactor
from twisted.web import server, resource as web_resource

try:
    from twisted.web import http
except ImportError:
    from twisted.protocols import http

from flumotion.configure import configure
from flumotion.common import log
from flumotion.component.consumers.hlsstreamer.common import\
    FragmentNotFound, FragmentNotAvailable, PlaylistNotFound, KeyNotFound


__version__ = "$Rev: $"

HTTP_NAME = 'FlumotionAppleHTTPLiveServer'
HTTP_VERSION = configure.version
HTTP_SERVER = '%s/%s' % (HTTP_NAME, HTTP_VERSION)

M3U8_CONTENT_TYPE = 'application/vnd.apple.mpegurl'
PLAYLIST_EXTENSION = '.m3u8'
COOKIE_NAME = 'flumotion-session'
NOT_VALID = 0
VALID = 1
RENEW_AUTH = 2

ERROR_TEMPLATE = """<!doctype html public "-//IETF//DTD HTML 2.0//EN">
<html>
<head>
  <title>%(code)d %(error)s</title>
</head>
<body>
<h2>%(code)d %(error)s</h2>
</body>
</html>
"""

### the Twisted resource that handles the base URL


class Session(server.Session):

    sessionTimeout = 900
    _expireCall = None

    def _init_(self, site, uid):
        server.Session.__init__(self, site, uid)

    def startCheckingExpiration(self):
        """
        Start expiration tracking.

        @return: C{None}
        """
        self._expireCall = reactor.callLater(
            self.sessionTimeout, self.expire)

    def notifyOnExpire(self, callback):
        """
        Call this callback when the session expires or logs out.
        """
        self.expireCallbacks.append(callback)

    def expire(self):
        """
        Expire/logout of the session.
        """
        del self.site.sessions[self.uid]
        for c in self.expireCallbacks:
            c()
        self.expireCallbacks = []
        if self._expireCall and self._expireCall.active():
            self._expireCall.cancel()
            # Break reference cycle.
            self._expireCall = None

    def touch(self):
        """
        Notify session modification.
        """
        self.lastModified = time.time()
        if self._expireCall is not None:
            self._expireCall.reset(self.sessionTimeout)


class FragmentedResource(web_resource.Resource, log.Loggable):

    __reserve_fds__ = 50 # number of fd's to reserve for non-streaming
    logCategory = 'fragmented-resource'
    # IResource interface variable; True means it will not chain requests
    # further down the path to other resource providers through
    # getChildWithDefault
    isLeaf = True

    def __init__(self, streamer, httpauth, secretKey, sessionTimeout):
        """
        @param streamer: L{FragmentedStreamer}
        """
        self.streamer = streamer
        self.httpauth = httpauth
        self.secretKey = secretKey
        self.sessionTimeout = sessionTimeout
        self.maxclients = self.getMaxAllowedClients(-1)
        self.maxbandwidth = -1 # not limited by default

        # If set, a URL to redirect a user to when the limits above are reached
        self._redirectOnFull = None

        self.bytesSent = 0
        self.bytesReceived = 0
        self.logFilters = None

        socket = 'flumotion.component.plugs.request.RequestLoggerPlug'
        self.loggers = streamer.plugs.get(socket, [])

        socket = \
            'flumotion.component.plugs.requestmodifier.RequestModifierPlug'
        self.modifiers = streamer.plugs.get(socket, [])

        web_resource.Resource.__init__(self)

    def setMountPoint(self, mountPoint):
        if not mountPoint.startswith('/'):
            mountPoint = '/' + mountPoint
        if not mountPoint.endswith('/'):
            mountPoint = mountPoint + '/'
        self.mountPoint = mountPoint

    def setRoot(self, path):
        self.putChild(path, self)

    def setLogFilter(self, logfilter):
        self.logfilter = logfilter

    def rotateLogs(self):
        """
        Close the logfile, then reopen using the previous logfilename
        """
        for logger in self.loggers:
            self.debug('rotating logger %r', logger)
            logger.rotate()

    def logWrite(self, request):
        headers = request.getAllHeaders()
        if self.httpauth:
            username = self.httpauth.bouncerName
        else:
            username = '-'
        uid = request.session and request.session.uid or None
        args = {'ip': request.getClientIP(),
                'time': time.gmtime(),
                'method': request.method,
                'uri': request.uri,
                'username': username,
                'get-parameters': request.args,
                'clientproto': request.clientproto,
                'response': request.code,
                'bytes-sent': request.getBytesSent(),
                'referer': headers.get('referer', None),
                'user-agent': headers.get('user-agent', None),
                'time-connected': request.getDuration(),
                'session-id': uid}

        l = []
        for logger in self.loggers:
            l.append(defer.maybeDeferred(
                logger.event, 'http_session_completed', args))

        return defer.DeferredList(l)

    def setUserLimit(self, limit):
        self.info('setting maxclients to %d', limit)
        self.maxclients = self.getMaxAllowedClients(limit)
        # Log what we actually managed to set it to.
        self.info('set maxclients to %d', self.maxclients)

    def setBandwidthLimit(self, limit):
        self.maxbandwidth = limit
        self.info("set maxbandwidth to %d", self.maxbandwidth)

    def setRedirectionOnLimits(self, url):
        self._redirectOnFull = url

    def getMaxAllowedClients(self, maxclients):
        """
        maximum number of allowed clients based on soft limit for number of
        open file descriptors and fd reservation. Increases soft limit to
        hard limit if possible.
        """
        (softmax, hardmax) = resource.getrlimit(resource.RLIMIT_NOFILE)
        import sys
        version = sys.version_info

        if maxclients != -1:
            neededfds = maxclients + self.__reserve_fds__

            # Bug in python 2.4.3, see
            # http://sourceforge.net/tracker/index.php?func=detail&
            #   aid=1494314&group_id=5470&atid=105470
            if version[:3] == (2, 4, 3) and \
                not hasattr(socket, "has_2_4_3_patch"):
                self.warning(
                    'Setting hardmax to 1024 due to python 2.4.3 bug')
                hardmax = 1024

            if neededfds > softmax:
                lim = min(neededfds, hardmax)
                resource.setrlimit(resource.RLIMIT_NOFILE, (lim, hardmax))
                return lim - self.__reserve_fds__
            else:
                return maxclients
        else:
            return softmax - self.__reserve_fds__

    def reachedServerLimits(self):
        if self.maxclients >= 0 and \
                self.streamer.getClients() >= self.maxclients:
            return True
        elif self.maxbandwidth >= 0:
            # Reject if adding one more client would take us over the limit.
            if ((self.streamer.getClients() + 1) *
                    self.streamer.getCurrentBitrate() >= self.maxbandwidth):
                return True
        return False

    def isReady(self):
        return self.streamer.isReady()

    def _renewAuthentication(self, request, sessionID, authResponse):
        # Delete, if it's present, the 'flumotion-session' cookie
        for cookie in request.cookies:
            if cookie.startswith('%s=%s' % (COOKIE_NAME, cookie)):
                self.log("delete old cookie for session ID=%s", sessionID)
                request.cookies.remove(cookie)

        if authResponse and authResponse.duration != 0:
            authExpiracy = time.mktime((datetime.utcnow() +
            timedelta(seconds=authResponse.duration)).timetuple())
        else:
            authExpiracy = 0
        # Create a new token with the same Session ID and the renewed
        # authentication's expiration time
        token = self._generateToken(sessionID, request.getClientIP())
        request.addCookie(COOKIE_NAME, token, path=self.mountPoint)

    def _checkSession(self, request):
        """
        From t.w.s.Request.getSession()
        Associates the request to a session using the 'flumotion-session'
        cookie and updates the session's timeout.
        If the authentication has expired, re-authenticates the session and
        updates the cookie with the new authentication's expiracy time.
        If the cookie is not valid (bad IP or bad signature) or the session
        has expired, it creates a new session.
        """

        def processAuthentication(response):
            if response is None or response.duration == 0:
                authExpiracy = 0
            else:
                authExpiracy = time.mktime((datetime.utcnow() +
                    timedelta(seconds=res.duration)).timetuple())
            self._createSession(request, authExpiracy)

        if not request.session:
            cookie = request.getCookie(COOKIE_NAME)
            if cookie:
                # The request has a flumotion cookie
                cookieState, sessionID, authExpiracy = \
                        self._cookieIsValid(cookie, request.getClientIP(),
                                request.args.get('GKID', [None])[0])
                if cookieState != NOT_VALID:
                    # The cookie is valid: retrieve or create a session
                    try:
                        # The session exists in this streamer
                        request.session = request.site.getSession(sessionID)
                    except KeyError:
                        # The session doesn't exists in this streamer
                        self._createSession(request, authExpiracy, sessionID)
                        self.log("replicating session %s.", sessionID)
                    if cookieState == RENEW_AUTH:
                        # The authentication as expired, renew it
                        self.debug('renewing authentication')
                        d = self.httpauth.startAuthentication(request)
                        d.addCallback(lambda res:
                            self._renewAuthentication(request, sessionID, res))
                        d.addErrback(lambda x: self._delClient(sessionID))
                        return d

            # if it still hasn't been set, fix it up.
            if not request.session:
                self.debug('asked for authentication')
                d = self.httpauth.startAuthentication(request)
                d.addCallback(lambda res: processAuthentication(res))
                d.addErrback(lambda x: None)
                return d

        request.session.touch()

    def _createSession(self, request, authExpiracy=None, sessionID=None):
        """
        From t.w.s.Site.makeSession()
        Generates a new Session instance and store it for future reference
        """
        if authExpiracy is None:
            authExpiracy = 0
        if sessionID is None:
            sessionID = request.args.get('GKID', [uuid.uuid1().hex])[0]
        token = self._generateToken(
                sessionID, request.getClientIP(), authExpiracy)
        try:
            # Check if the session already exists
            request.session = request.site.getSession(sessionID)
            self.log("session already exists, the client is not using cookies"
                     "or the IP changed.")
        except:
            request.session = request.site.sessions[sessionID] =\
                    Session(request.site, sessionID)
            request.session.sessionTimeout = self.sessionTimeout
            request.session.startCheckingExpiration()
            request.session.notifyOnExpire(lambda:
                    self._delClient(sessionID))
            self._addClient()
        request.addCookie(COOKIE_NAME, token, path=self.mountPoint)

        self.debug('added new client with session id: "%s"' %
                request.session.uid)

    def _generateToken(self, sessionID, clientIP, authExpiracy):
        """
        Generate a cryptografic token:
        PAYLOAD = SESSION_ID||:||AUTH_EXPIRACY
        PRIVATE = CLIENT_IP||:||MOUNT_POINT
        SIG=HMAC(SECRET,PAYLOAD||:||PRIVATE)
        TOKEN=BASE64(PAYLOAD||:||SIG)
        """
        payload = ':'.join([sessionID, str(authExpiracy)])
        private = ':'.join([clientIP, self.mountPoint])
        sig = hmac.new(
                self.secretKey, ':'.join([payload, private])).hexdigest()
        return base64.b64encode(':'.join([payload, sig]))

    def _cookieIsValid(self, cookie, clientIP, urlSessionID):
        """
        Checks whether the cookie is valid against the authentication expiracy
        time and the signature (and implicitly the client IP and mount point).
        Returns the state of the cookie among 3 options:
        VALID: the cookie is valid (expiracy and signature are OK)
        RENEW_AUTH: the cookie is valid but the authentication has expired
        NOT_VALID: the cookie is not valid
        """
        private = ':'.join([clientIP, self.mountPoint])
        try:
            token = base64.b64decode(cookie)
            payload, sig = token.rsplit(':', 1)
            sessionID, authExpiracy = payload.split(':')
        except (TypeError, ValueError):
            self.debug("cookie is not valid. reason: malformed cookie")
            return (NOT_VALID, None, None)

        self.log("cheking cookie for client_ip=%s auth_expiracy:%s",
                clientIP, authExpiracy)

        # Check signature
        if hmac.new(self.secretKey, ':'.join([payload, private])).hexdigest()\
                != sig:
            self.debug("cookie is not valid. reason: invalid signature")
            return (NOT_VALID, None, None)
        # Check sessionID
        if urlSessionID is not None and urlSessionID != sessionID:
            self.debug("cookie is not valid. reason: different sessions")
            return (NOT_VALID, None, None)
        now = time.mktime(datetime.utcnow().timetuple())
        # Check authentication expiracy
        if float(authExpiracy) != 0 and float(authExpiracy) < now:
            self.debug("cookie is not valid. reason: authentication expired")
            return (RENEW_AUTH, sessionID, authExpiracy)
        self.log("cookie is valid")
        return (VALID, sessionID, None)

    def _addClient(self):
        self.streamer.clientAdded()

    def _delClient(self, uid):
        self.log("session %s expired", uid)
        self.streamer.clientRemoved()

    def _errorMessage(self, request, error_code):
        request.setHeader('content-type', 'html')
        request.setHeader('server', HTTP_VERSION)
        request.setResponseCode(error_code)

        return ERROR_TEMPLATE % {'code': error_code,
                                 'error': http.RESPONSES[error_code]}

    def _handleNotReady(self, request):
        self.debug("Not sending data, it's not ready")
        request.code = http.SERVICE_UNAVAILABLE
        return self._errorMessage(request, http.SERVICE_UNAVAILABLE)

    def _handleServerFull(self, request):
        if self._redirectOnFull:
            self.debug("Redirecting client, client limit %d reached",
                self.maxclients)
            error_code = http.FOUND
            request.setHeader('location', self._redirectOnFull)
        else:
            self.debug('Refusing clients, client limit %d reached',
                    self.maxclients)
            error_code = http.SERVICE_UNAVAILABLE
        return self._errorMessage(request, error_code)

    def _renderNotFoundResponse(self, failure, request):
        r = failure.trap(FragmentNotAvailable, FragmentNotFound,
                PlaylistNotFound, KeyNotFound)
        request.write(self._errorMessage(request, http.NOT_FOUND))
        request.finish()
        return ''

    def _renderForbidden(self, request):
        request.write(self._errorMessage(request, http.FORBIDDEN))
        request.finish()
        return ''

    def _writeHeaders(self, request, content, code=200):
        """
        Write out the HTTP headers for the incoming HTTP request.
        """

        request.setResponseCode(code)
        request.setHeader('Server', HTTP_SERVER)
        request.setHeader('Date', http.datetimeToString())
        request.setHeader('Cache-Control', 'no-cache')
        if content:
            request.setHeader('Content-type', content)

        # Call request modifiers
        for modifier in self.modifiers:
            modifier.modify(request)

        # Mimic Twisted as close as possible
        headers = []
        for name, value in request.headers.items():
            headers.append('%s: %s\r\n' % (name.capitalize(), value))
        for cookie in request.cookies:
            headers.append('%s: %s\r\n' % ("Set-Cookie", cookie))

    def getBytesSent(self):
        return self.bytesSent

    def getBytesReceived(self):
        return self.bytesReceived

    def logRequest(self, error, request):
        if error:
            self.info("%s %s error:%s", request.getClientIP(), request, error)
        else:
            uid = request.session and request.session.uid or None
            self.info("%s %s %s %s %s %s", request.getClientIP(), request,
                request.code, request.getBytesSent(),
                request.getDuration(), uid)

    def render(self, request):
        self.debug('Incoming client connection from %s: %s',
                request.getClientIP(), request)
        request.notifyFinish().addCallback(self.logRequest, request)
        return web_resource.Resource.render(self, request)


class HTTPLiveStreamingResource(FragmentedResource):

    logCategory = 'apple-streamer'

    def __init__(self, streamer, httpauth, secretKey, sessionTimeout):
        """
        @param streamer: L{AppleHTTPLiveStreamer}
        """
        self.ring = streamer.getRing()
        self.setMountPoint(streamer.mountPoint)
        FragmentedResource.__init__(self, streamer, httpauth, secretKey,
            sessionTimeout)

    def _renderKey(self, res, request):
        self._writeHeaders(request, 'binary/octect-stream')
        if request.method == 'GET':
            key = self.ring.getEncryptionKey(request.args['key'][0])
            request.write(key)
            self.bytesSent += len(key)
            self.logWrite(request)
        elif request.method == 'HEAD':
            self.debug('handling HEAD request')
        request.finish()
        return res

    def _renderPlaylist(self, res, request, resource):
        self.debug('_render(): asked for playlist %s', resource)
        request.setHeader("Connection", "Keep-Alive")
        self._writeHeaders(request, M3U8_CONTENT_TYPE)
        if request.method == 'GET':
            playlist = self.ring.renderPlaylist(resource, request.args)
            request.write(playlist)
            self.bytesSent += len(playlist)
            self.logWrite(request)
        elif request.method == 'HEAD':
            self.debug('handling HEAD request')
        request.finish()
        return res

    def _renderFragment(self, res, request, resource):
        self.debug('_render(): asked for fragment %s', resource)
        request.setHeader('Connection', 'close')
        self._writeHeaders(request, 'video/mpeg')
        if request.method == 'GET':
            data = self.ring.getFragment(resource)
            request.setHeader('content-length', len(data))
            request.write(data)
            self.bytesSent += len(data)
            self.logWrite(request)
        if request.method == 'HEAD':
            self.debug('handling HEAD request')
        request.finish()
        return res

    def _render(self, request):
        if not self.isReady():
            return self._handleNotReady(request)
        if self.reachedServerLimits():
            return self._handleServerFull(request)

        # A GET request will be like 'mountpoint+resource':
        # 'GET /iphone/fragment-0.ts' or 'GET /fragment-0.ts'
        # The mountpoint is surrounded by '/' in setMountPoint()
        # so we can safely look for the mountpoint and extract the
        # resource name
        if not request.path.startswith(self.mountPoint):
            return self._renderForbidden(request)
        resource = request.path.replace(self.mountPoint, '', 1)

        d = defer.maybeDeferred(self._checkSession, request)

        # Playlists
        if resource.endswith(PLAYLIST_EXTENSION):
            d.addCallback(self._renderPlaylist, request, resource)
        # Keys
        elif resource == 'key' and 'key' in request.args:
            d.addCallback(self._renderKey, request)
        # Fragments
        else:
            d.addCallback(self._renderFragment, request, resource)

        d.addErrback(self._renderNotFoundResponse, request)
        return server.NOT_DONE_YET

    render_GET = _render
    render_HEAD = _render
