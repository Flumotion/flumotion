# -*- Mode: Python; test-case-name: flumotion.test.test_http -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

import struct
import socket

from twisted.web import http, server
from twisted.web import resource as web_resource
from twisted.internet import reactor, defer
from twisted.python import reflect, failure

from flumotion.configure import configure
from flumotion.common import errors
from flumotion.twisted.credentials import cryptChallenge

from flumotion.common import common, log, keycards

#__all__ = ['HTTPStreamingResource', 'MultifdSinkStreamer']
__version__ = "$Rev$"


HTTP_SERVER_NAME = 'FlumotionHTTPServer'
HTTP_SERVER_VERSION = configure.version

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

HTTP_SERVER = '%s/%s' % (HTTP_SERVER_NAME, HTTP_SERVER_VERSION)

### This is new Issuer code that eventually should move to e.g.
### flumotion.common.keycards or related


class Issuer(log.Loggable):
    """
    I am a base class for all Issuers.
    An issuer issues keycards of a given class based on an object
    (incoming HTTP request, ...)
    """

    def issue(self, *args, **kwargs):
        """
        Return a keycard, or None, based on the given arguments.
        """
        raise NotImplementedError


class HTTPGenericIssuer(Issuer):
    """
    I create L{flumotion.common.keycards.Keycard} based on just a
    standard HTTP request.  Useful for authenticating based on
    server-side checks such as time, rather than client credentials.
    """

    def issue(self, request):
        keycard = keycards.KeycardGeneric()
        self.debug("Asking for authentication, generic HTTP")
        return keycard


class HTTPAuthIssuer(Issuer):
    """
    I create L{flumotion.common.keycards.KeycardUACPP} keycards based on
    an incoming L{twisted.protocols.http.Request} request's standard
    HTTP authentication information.
    """

    def issue(self, request):
        # for now, we're happy with a UACPP keycard; the password arrives
        # plaintext anyway
        keycard = keycards.KeycardUACPP(
            request.getUser(),
            request.getPassword(), request.getClientIP())
        self.debug('Asking for authentication, user %s, password %s, ip %s' % (
            keycard.username, keycard.password, keycard.address))
        return keycard


class HTTPTokenIssuer(Issuer):
    """
    I create L{flumotion.common.keycards.KeycardToken} keycards based on
    an incoming L{twisted.protocols.http.Request} request's GET "token"
    parameter.
    """

    def issue(self, request):
        if not 'token' in request.args.keys():
            return None

        # args can have lists as values, if more than one specified
        token = request.args['token']
        if not isinstance(token, str):
            token = token[0]

        keycard = keycards.KeycardToken(token,
            request.getClientIP(), request.path)
        return keycard

BOUNCER_SOCKET = 'flumotion.component.bouncers.plug.BouncerPlug'


class HTTPAuthentication(log.Loggable):
    """
    Helper object for handling HTTP authentication for twisted.web
    Resources, using issuers and bouncers.
    """

    logCategory = 'httpauth'

    KEYCARD_TTL = 60 * 60
    KEYCARD_KEEPALIVE_INTERVAL = 20 * 60
    KEYCARD_TRYAGAIN_INTERVAL = 1 * 60

    def __init__(self, component):
        self.component = component
        self._fdToKeycard = {}         # request fd -> Keycard
        self._idToKeycard = {}         # keycard id -> Keycard
        self._fdToDurationCall = {}    # request fd -> IDelayedCall
                                       # for duration
        self._domain = None            # used for auth challenge and on keycard
        self._issuer = HTTPAuthIssuer() # issues keycards; default for compat
        self.bouncerName = None
        self.setRequesterId(component.getName())
        self._defaultDuration = None   # default duration to use if the keycard
                                       # doesn't specify one.
        self._pendingCleanups = []
        self._keepAlive = None

        if (BOUNCER_SOCKET in self.component.plugs
            and self.component.plugs[BOUNCER_SOCKET]):
            assert len(self.component.plugs[BOUNCER_SOCKET]) == 1
            self.plug = self.component.plugs[BOUNCER_SOCKET][0]
        else:
            self.plug = None

    def scheduleKeepAlive(self, tryingAgain=False):

        def timeout():

            def reschedule(res):
                if isinstance(res, failure.Failure):
                    self.info('keepAlive failed, rescheduling in %d '
                              'seconds', self.KEYCARD_TRYAGAIN_INTERVAL)
                    self._keepAlive = None
                    self.scheduleKeepAlive(tryingAgain=True)
                else:
                    self.info('keepAlive successful')
                    self._keepAlive = None
                    self.scheduleKeepAlive(tryingAgain=False)

            if self.bouncerName is not None:
                self.debug('calling keepAlive on bouncer %s',
                           self.bouncerName)
                d = self.keepAlive(self.bouncerName, self.issuerName,
                                   self.KEYCARD_TTL)
                d.addCallbacks(reschedule, reschedule)
            else:
                self.scheduleKeepAlive()

        if tryingAgain:
            self._keepAlive = reactor.callLater(
                self.KEYCARD_TRYAGAIN_INTERVAL, timeout)
        else:
            self._keepAlive = reactor.callLater(
                self.KEYCARD_KEEPALIVE_INTERVAL, timeout)

    def stopKeepAlive(self):
        if self._keepAlive is not None:
            self._keepAlive.cancel()
            self._keepAlive = None

    def setDomain(self, domain):
        """
        Set a domain name on the resource, used in HTTP auth challenges and
        on the keycard.

        @type domain: string
        """
        self._domain = domain

    def setBouncerName(self, bouncerName):
        self.bouncerName = bouncerName

    def setRequesterId(self, requesterId):
        self.requesterId = requesterId
        # make something uniquey
        self.issuerName = str(self.requesterId) + '-' + cryptChallenge()

    def setDefaultDuration(self, defaultDuration):
        self._defaultDuration = defaultDuration

    def setIssuerClass(self, issuerClass):
        # FIXME: in the future, we want to make this pluggable and have it
        # look up somewhere ?
        if issuerClass == 'HTTPTokenIssuer':
            self._issuer = HTTPTokenIssuer()
        elif issuerClass == 'HTTPAuthIssuer':
            self._issuer = HTTPAuthIssuer()
        elif issuerClass == 'HTTPGenericIssuer':
            self._issuer = HTTPGenericIssuer()
        else:
            raise ValueError("issuerClass %s not accepted" % issuerClass)

    def authenticate(self, request):
        """
        Returns: a deferred returning a keycard or None
        """
        keycard = self._issuer.issue(request)
        if not keycard:
            self.debug('no keycard from issuer, firing None')
            return defer.succeed(None)

        keycard.requesterId = self.requesterId
        keycard.issuerName = self.issuerName
        keycard._fd = request.transport.fileno()
        keycard.setDomain(self._domain)

        if self.plug:
            self.debug('authenticating against plug')
            return self.plug.authenticate(keycard)
        elif self.bouncerName == None:
            self.debug('no bouncer, accepting')
            return defer.succeed(keycard)
        else:
            keycard.ttl = self.KEYCARD_TTL
            self.debug('sending keycard to remote bouncer %r',
                       self.bouncerName)
            return self.authenticateKeycard(self.bouncerName, keycard)

    def authenticateKeycard(self, bouncerName, keycard):
        return self.component.medium.authenticate(bouncerName, keycard)

    def keepAlive(self, bouncerName, issuerName, ttl):
        return self.component.medium.keepAlive(bouncerName, issuerName, ttl)

    def cleanupKeycard(self, bouncerName, keycard):
        return self.component.medium.removeKeycardId(bouncerName, keycard.id)

    # FIXME: check this

    def clientDone(self, fd):
        return self.component.remove_client(fd)

    def doCleanupKeycard(self, bouncerName, keycard):
        # cleanup this one keycard, and take the opportunity to retry
        # previous failed cleanups

        def cleanup(bouncerName, keycard):

            def cleanupLater(res, pair):
                self.log('failed to clean up keycard %r, will do '
                         'so later', keycard)
                self._pendingCleanups.append(pair)
            d = self.cleanupKeycard(bouncerName, keycard)
            d.addErrback(cleanupLater, (bouncerName, keycard))
        pending = self._pendingCleanups
        self._pendingCleanups = []
        cleanup(bouncerName, keycard)
        for bouncerName, keycard in pending:
            cleanup(bouncerName, keycard)

    # public

    def cleanupAuth(self, fd):
        if self.bouncerName and fd in self._fdToKeycard:
            keycard = self._fdToKeycard[fd]
            del self._fdToKeycard[fd]
            del self._idToKeycard[keycard.id]
            self.debug('[fd %5d] asking bouncer %s to remove keycard id %s',
                       fd, self.bouncerName, keycard.id)
            self.doCleanupKeycard(self.bouncerName, keycard)
        if fd in self._fdToDurationCall:
            self.debug('[fd %5d] canceling later expiration call' % fd)
            self._fdToDurationCall[fd].cancel()
            del self._fdToDurationCall[fd]

    def _durationCallLater(self, fd):
        """
        Expire a client due to a duration expiration.
        """
        self.debug('[fd %5d] duration exceeded, expiring client' % fd)

        # we're called from a callLater, so we've already run; just delete
        if fd in self._fdToDurationCall:
            del self._fdToDurationCall[fd]

        self.debug('[fd %5d] asking streamer to remove client' % fd)
        self.clientDone(fd)

    def expireKeycard(self, keycardId):
        """
        Expire a client's connection associated with the keycard Id.
        """
        keycard = self._idToKeycard[keycardId]
        fd = keycard._fd

        self.debug('[fd %5d] expiring client' % fd)

        if fd in self._fdToDurationCall:
            self.debug('[fd %5d] canceling later expiration call' % fd)
            self._fdToDurationCall[fd].cancel()
            del self._fdToDurationCall[fd]

        self.debug('[fd %5d] asking streamer to remove client' % fd)
        self.clientDone(fd)

    ### resource.Resource methods

    def startAuthentication(self, request):
        d = self.authenticate(request)
        d.addCallback(self._authenticatedCallback, request)
        d.addErrback(self._authenticatedErrback, request)
        d.addErrback(self._defaultErrback, request)

        return d

    def _authenticatedCallback(self, keycard, request):
        # !: since we are a callback, the incoming fd might have gone away
        # and closed
        self.debug('_authenticatedCallback: keycard %r' % keycard)
        if not keycard:
            raise errors.NotAuthenticatedError()

        # properly authenticated
        if request.method == 'GET':
            fd = request.transport.fileno()

            if self.bouncerName:
                if keycard.id in self._idToKeycard:
                    self.warning("Duplicate keycard id: refusing")
                    raise errors.NotAuthenticatedError()

                self._fdToKeycard[fd] = keycard
                self._idToKeycard[keycard.id] = keycard

            duration = keycard.duration or self._defaultDuration

            if duration:
                self.debug('new connection on %d will expire in %f seconds' % (
                    fd, duration))
                self._fdToDurationCall[fd] = reactor.callLater(
                    duration, self._durationCallLater, fd)

        return None

    def _authenticatedErrback(self, failure, request):
        failure.trap(errors.UnknownComponentError,
                     errors.NotAuthenticatedError)
        self._handleUnauthorized(request, http.UNAUTHORIZED)
        return failure

    def _defaultErrback(self, failure, request):
        if failure.check(errors.UnknownComponentError,
                errors.NotAuthenticatedError) is None:
            # If something else went wrong, we want to disconnect the client
            # and give them a 500 Internal Server Error.
            self._handleUnauthorized(request, http.INTERNAL_SERVER_ERROR)
        return failure

    def _handleUnauthorized(self, request, code):
        self.debug('client from %s is unauthorized' % (request.getClientIP()))
        request.setHeader('content-type', 'text/html')
        request.setHeader('server', HTTP_SERVER_VERSION)
        if self._domain and code == http.UNAUTHORIZED:
            request.setHeader('WWW-Authenticate',
                              'Basic realm="%s"' % self._domain)

        request.setResponseCode(code)

        # we have to write data ourselves,
        # since we already returned NOT_DONE_YET
        html = ERROR_TEMPLATE % {'code': code,
                                 'error': http.RESPONSES[code]}
        request.write(html)
        request.finish()


class LogFilter:

    def __init__(self):
        self.filters = [] # list of (network, mask)

    def addIPFilter(self, filter):
        """
        Add an IP filter of the form IP/prefix-length (CIDR syntax), or just
        a single IP address
        """
        definition = filter.split('/')
        if len(definition) == 2:
            (net, prefixlen) = definition
            prefixlen = int(prefixlen)
        elif len(definition) == 1:
            net = definition[0]
            prefixlen = 32
        else:
            raise errors.ConfigError(
                "Cannot parse filter definition %s" % filter)

        if prefixlen < 0 or prefixlen > 32:
            raise errors.ConfigError("Invalid prefix length")

        mask = ~((1 << (32 - prefixlen)) - 1)
        try:
            net = struct.unpack(">I", socket.inet_pton(socket.AF_INET, net))[0]
        except socket.error:
            raise errors.ConfigError(
                "Failed to parse network address %s" % net)
        net = net & mask # just in case

        self.filters.append((net, mask))

    def isInRange(self, ip):
        """
        Return true if ip is in any of the defined network(s) for this filter
        """
        # Handles IPv4 only.
        realip = struct.unpack(">I", socket.inet_pton(socket.AF_INET, ip))[0]
        for f in self.filters:
            if (realip & f[1]) == f[0]:
                return True
        return False
