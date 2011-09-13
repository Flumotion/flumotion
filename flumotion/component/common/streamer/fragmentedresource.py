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
import uuid
from datetime import datetime, timedelta

from twisted.internet import reactor
from twisted.web import server

try:
    from twisted.web import http
except ImportError:
    from twisted.protocols import http

from flumotion.common import log
from flumotion.component.common.streamer.resources import\
    HTTPStreamingResource, ERROR_TEMPLATE, HTTP_VERSION

__version__ = "$Rev: $"

COOKIE_NAME = 'flumotion-session'
NOT_VALID = 0
VALID = 1
RENEW_AUTH = 2


class FragmentNotFound(Exception):
    "The requested fragment is not found."


class FragmentNotAvailable(Exception):
    "The requested fragment is not available."


class PlaylistNotFound(Exception):
    "The requested playlist is not found."


class KeyNotFound(Exception):
    "The requested key is not found."


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


class FragmentedResource(HTTPStreamingResource, log.Loggable):

    HTTP_NAME = 'FlumotionAppleHTTPLiveServer'
    HTTP_SERVER = '%s/%s' % (HTTP_NAME, HTTP_VERSION)

    logCategory = 'fragmented-resource'

    def __init__(self, streamer, httpauth, secretKey, sessionTimeout):
        """
        @param streamer: L{FragmentedStreamer}
        """
        HTTPStreamingResource.__init__(self, streamer, httpauth)
        self.secretKey = secretKey
        self.sessionTimeout = sessionTimeout
        self.bytesSent = 0
        self.bytesReceived = 0

    def setMountPoint(self, mountPoint):
        if not mountPoint.startswith('/'):
            mountPoint = '/' + mountPoint
        if not mountPoint.endswith('/'):
            mountPoint = mountPoint + '/'
        self.mountPoint = mountPoint

    def isReady(self):
        return self.streamer.isReady()

    def _addClient(self, request):
        HTTPStreamingResource._addClient(self, request)
        self.streamer.clientAdded()

    def _removeClient(self, uid, request):
        HTTPStreamingResource._removeClient(self, request)
        self.log("session %s expired", uid)
        self.streamer.clientRemoved()

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
        token = self._generateToken(sessionID, request.getClientIP(),
                                    authExpiracy)
        request.addCookie(COOKIE_NAME, token, path=self.mountPoint)

    def _handleNotReady(self, request):
        self.debug("Not sending data, it's not ready")
        request.code = http.SERVICE_UNAVAILABLE
        return self._errorMessage(request, http.SERVICE_UNAVAILABLE)

    def _getExtraLogArgs(self, request):
        uid = request.session and request.session.uid or None
        return {'uid': uid}

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
                    timedelta(seconds=response.duration)).timetuple())
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
                    self._removeClient(sessionID, request))
            self._addClient(request)
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

    def _errorMessage(self, request, error_code):
        request.setHeader('content-type', 'html')
        request.setHeader('server', HTTP_VERSION)
        request.setResponseCode(error_code)

        return ERROR_TEMPLATE % {'code': error_code,
                                 'error': http.RESPONSES[error_code]}

    def _renderNotFoundResponse(self, failure, request):
        failure.trap(FragmentNotAvailable, FragmentNotFound,
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
        request.setHeader('Server', self.HTTP_SERVER)
        request.setHeader('Date', http.datetimeToString())
        request.setHeader('Cache-Control', 'no-cache')
        if content:
            request.setHeader('Content-type', content)

        # Call request modifiers
        for modifier in self.modifiers:
            modifier.modify(request)

    def getBytesSent(self):
        return self.bytesSent

    def getBytesReceived(self):
        return self.bytesReceived

    def render(self, request):
        self.debug('Incoming client connection from %s: %s',
                request.getClientIP(), request)
        request.notifyFinish().addCallback(self._logRequest, request)
        return HTTPStreamingResource.render(self, request)

    def _logWrite(self, request):
        return self.logWrite(request, request.getBytesSent(),
                             request.getDuration())

    def _logRequest(self, error, request):
        if error:
            self.info("%s %s error:%s", request.getClientIP(), request, error)
        else:
            uid = request.session and request.session.uid or None
            self.info("%s %s %s %s %s %s", request.getClientIP(), request,
                request.code, request.getBytesSent(),
                request.getDuration(), uid)
