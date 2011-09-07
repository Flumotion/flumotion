# -*- Mode: Python; test-case-name: flumotion.test.test_rtsp -*-
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

"""
RTSP - Real Time Streaming Protocol.

See RFC 2326, and its Robin, RFC 2068.
"""

import sys
import re
import types

from twisted.web import http
from twisted.web import server, resource
from twisted.internet import defer

from twisted.python import log, failure, reflect

try:
    from twisted.protocols._c_urlarg import unquote
except ImportError:
    from urllib import unquote

from flumotion.common import log as flog

__version__ = "$Rev$"

SERVER_PROTOCOL = "RTSP/1.0"
# I can be overridden to add the version

SERVER_STRING = "Flumotion RTP"

# response codes
CONTINUE = 100

OK = 200
CREATED = 201
LOW_STORAGE = 250

MULTIPLE_CHOICE = 300
MOVED_PERMANENTLY = 301
MOVED_TEMPORARILY = 302
SEE_OTHER = 303
NOT_MODIFIED = 304
USE_PROXY = 305

BAD_REQUEST = 400
UNAUTHORIZED = 401
PAYMENT_REQUIRED = 402
FORBIDDEN = 403
NOT_FOUND = 404
NOT_ALLOWED = 405
NOT_ACCEPTABLE = 406
PROXY_AUTH_REQUIRED = 407
REQUEST_TIMEOUT = 408
GONE = 410
LENGTH_REQUIRED = 411
PRECONDITION_FAILED = 412
REQUEST_ENTITY_TOO_LARGE = 413
REQUEST_URI_TOO_LONG = 414
UNSUPPORTED_MEDIA_TYPE = 415

PARAMETER_NOT_UNDERSTOOD = 451
CONFERENCE_NOT_FOUND = 452
NOT_ENOUGH_BANDWIDTH = 453
SESSION_NOT_FOUND = 454
METHOD_INVALID_STATE = 455
HEADER_FIELD_INVALID = 456
INVALID_RANGE = 457
PARAMETER_READ_ONLY = 458
AGGREGATE_NOT_ALLOWED = 459
AGGREGATE_ONLY_ALLOWED = 460
UNSUPPORTED_TRANSPORT = 461
DESTINATION_UNREACHABLE = 462

INTERNAL_SERVER_ERROR = 500
NOT_IMPLEMENTED = 501
BAD_GATEWAY = 502
SERVICE_UNAVAILABLE = 503
GATEWAY_TIMEOUT = 504
RTSP_VERSION_NOT_SUPPORTED = 505
OPTION_NOT_SUPPORTED = 551

RESPONSES = {
    # 100
    CONTINUE: "Continue",

    # 200
    OK: "OK",
    CREATED: "Created",
    LOW_STORAGE: "Low on Storage Space",

    # 300
    MULTIPLE_CHOICE: "Multiple Choices",
    MOVED_PERMANENTLY: "Moved Permanently",
    MOVED_TEMPORARILY: "Moved Temporarily",
    SEE_OTHER: "See Other",
    NOT_MODIFIED: "Not Modified",
    USE_PROXY: "Use Proxy",

    # 400
    BAD_REQUEST: "Bad Request",
    UNAUTHORIZED: "Unauthorized",
    PAYMENT_REQUIRED: "Payment Required",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    NOT_ALLOWED: "Method Not Allowed",
    NOT_ACCEPTABLE: "Not Acceptable",
    PROXY_AUTH_REQUIRED: "Proxy Authentication Required",
    REQUEST_TIMEOUT: "Request Time-out",
    GONE: "Gone",
    LENGTH_REQUIRED: "Length Required",
    PRECONDITION_FAILED: "Precondition Failed",
    REQUEST_ENTITY_TOO_LARGE: "Request Entity Too Large",
    REQUEST_URI_TOO_LONG: "Request-URI Too Large",
    UNSUPPORTED_MEDIA_TYPE: "Unsupported Media Type",

    PARAMETER_NOT_UNDERSTOOD: "Parameter Not Understood",
    CONFERENCE_NOT_FOUND: "Conference Not Found",
    NOT_ENOUGH_BANDWIDTH: "Not Enough Bandwidth",
    SESSION_NOT_FOUND: "Session Not Found",
    METHOD_INVALID_STATE: "Method Not Valid In This State",
    HEADER_FIELD_INVALID: "Header Field Not Valid for Resource",
    INVALID_RANGE: "Invalid Range",
    PARAMETER_READ_ONLY: "Parameter is Read-Only",
    AGGREGATE_NOT_ALLOWED: "Aggregate operation not allowed",
    AGGREGATE_ONLY_ALLOWED: "Only aggregate operation allowed",
    UNSUPPORTED_TRANSPORT: "Unsupported transport",
    DESTINATION_UNREACHABLE: "Destination unreachable",

    # 500
    INTERNAL_SERVER_ERROR: "Internal Server Error",
    NOT_IMPLEMENTED: "Not Implemented",
    BAD_GATEWAY: "Bad Gateway",
    SERVICE_UNAVAILABLE: "Service Unavailable",
    GATEWAY_TIMEOUT: "Gateway Time-out",
    RTSP_VERSION_NOT_SUPPORTED: "RTSP Version not supported",
    OPTION_NOT_SUPPORTED: "Option not supported",
}


class RTSPError(Exception):
    """An exception with the RTSP status code and a str as arguments"""


class RTSPRequest(http.Request, flog.Loggable):
    logCategory = 'request'
    code = OK
    code_message = RESPONSES[OK]
    host = None
    port = None

    def delHeader(self, key):
        if key.lower() in self.headers.keys():
            del self.headers[key.lower()]

    # base method override

    # copied from HTTP since we have our own set of RESPONSES

    def setResponseCode(self, code, message=None):
        """
        Set the RTSP response code.
        """
        self.code = code
        if message:
            self.code_message = message
        else:
            self.code_message = RESPONSES.get(code, "Unknown Status")

    def process(self):
        # First check that we have a valid request.
        if self.clientproto != SERVER_PROTOCOL:
            e = ErrorResource(BAD_REQUEST)
            self.render(e)
            return

        # process the request and render the resource or give a failure
        first = "%s %s %s" % (self.method, self.path, SERVER_PROTOCOL)
        self.debug('incoming request: %s' % first)

        lines = []
        for key, value in self.received_headers.items():
            lines.append("%s: %s" % (key, value))

        self.debug('incoming headers:\n%s\n' % "\n".join(lines))

        #self.debug('user-agent: %s' % self.received_headers.get('user-agent',
        #    '[Unknown]'))
        #self.debug('clientid: %s' % self.received_headers.get('clientid',
        #    '[Unknown]'))

        # don't store site locally; we can't be sure every request has gone
        # through our customized handlers
        site = self.channel.site
        ip = self.getClientIP()
        site.logRequest(ip, first, lines)

        if not self._processPath():
            return

        try:
            if self.path == "*":
                resrc = site.resource
            else:
                resrc = site.getResourceFor(self)
            self.debug("RTSPRequest.process(): got resource %r" % resrc)
            try:
                self.render(resrc)
            except server.UnsupportedMethod:
                e = ErrorResource(OPTION_NOT_SUPPORTED)
                self.setHeader('Allow', ",".join(resrc.allowedMethods))
                self.render(e)
            except RTSPError, e:
                er = ErrorResource(e.args[0])
                self.render(er)
        except Exception, e:
            self.warning('failed to process %s: %s' %
                (lines and lines[0] or "[No headers]",
                    flog.getExceptionMessage(e)))
            self.processingFailed(failure.Failure())

    def _processPath(self):
        # process self.path into components; return whether or not it worked
        self.log("path %s" % self.path)

        self.prepath = [] # used in getResourceFor

        # check Request-URI; RFC 2326 6.1 says it's "*" or absolute URI
        if self.path == '*':
            self.log('Request-URI is *')
            return True

        # match the host:port
        matcher = re.compile('rtspu?://([^/]*)')
        m = matcher.match(self.path)
        hostport = None
        if m:
            hostport = m.expand('\\1')

        if not hostport:
            # malformed Request-URI; 400 seems like a likely reply ?
            self.log('Absolute rtsp URL required: %s' % self.path)
            self.render(ErrorResource(BAD_REQUEST,
                "Malformed Request-URI %s" % self.path))
            return False

        # get the rest after hostport starting with '/'
        rest = self.path.split(hostport)[1]
        self.host = hostport
        if ':' in hostport:
            chunks = hostport.split(':')
            self.host = chunks[0]
            self.port = int(chunks[1])
            # if we got fed crap, they're in other chunks, and we ignore them

        self.postpath = map(unquote, rest.split('/'))
        self.log(
            'split up self.path in host %s, port %r, pre %r and post %r' % (
            self.host, self.port, self.prepath, self.postpath))
        return True

    def processingFailed(self, reason):
        self.warningFailure(reason)
        # FIXME: disable tracebacks until we can reliably disable them
        if not True: # self.site or self.site.displayTracebacks:
            self.debug('sending traceback to client')
            import traceback
            tb = sys.exc_info()[2]
            text = "".join(traceback.format_exception(
                reason.type, reason.value, tb))
        else:
            text = "RTSP server failed to process your request.\n"

        self.setResponseCode(INTERNAL_SERVER_ERROR)
        self.setHeader('Content-Type', "text/plain")
        self.setHeader('Content-Length', str(len(text)))
        self.write(text)
        self.finish()
        return reason

    def _error(self, code, *lines):
        self.setResponseCode(code)
        self.setHeader('content-type', "text/plain")
        body = "\n".join(lines)
        return body

    def render(self, resrc):
        self.log('%r.render(%r)' % (resrc, self))
        result = resrc.render(self)
        self.log('%r.render(%r) returned result %r' % (resrc, self, result))
        if isinstance(result, defer.Deferred):
            result.addCallback(self._renderCallback, resrc)
            result.addErrback(self._renderErrback, resrc)
        else:
            self._renderCallback(result, resrc)

    # TODO: Refactor this and renderCallback to be cleaner and share code.

    def _renderErrback(self, failure, resrc):
        body = self._error(INTERNAL_SERVER_ERROR,
            "Request failed: %r" % failure)
        self.setHeader('Content-Length', str(len(body)))
        lines = []
        for key, value in self.headers.items():
            lines.append("%s: %s" % (key, value))

        self.channel.site.logReply(self.code, self.code_message, lines, body)

        self.write(body)
        self.finish()

    def _renderCallback(self, result, resrc):
        body = result
        if type(body) is not types.StringType:
            self.warning('request did not return a string but %r' %
                type(body))
            body = self._error(INTERNAL_SERVER_ERROR,
                "Request did not return a string",
                "Request: " + reflect.safe_repr(self),
                "Resource: " + reflect.safe_repr(resrc),
                "Value: " + reflect.safe_repr(body))
        self.setHeader('Content-Length', str(len(body)))

        lines = []
        for key, value in self.headers.items():
            lines.append("%s: %s" % (key, value))
        # FIXME: debug response code
        self.debug('responding to %s %s with %s (%d)' % (
            self.method, self.path, self.code_message, self.code))
        self.debug('outgoing headers:\n%s\n' % "\n".join(lines))
        if body:
            self.debug('body:\n%s\n' % body)
        self.log('RTSPRequest._renderCallback(): outgoing response:\n%s\n' %
            "\n".join(lines))
        self.log("\n".join(lines))
        self.log("\n")
        self.log(body)

        self.channel.site.logReply(self.code, self.code_message, lines, body)

        self.write(body)
        self.finish()

# RTSP keeps the initial request alive, pinging it regularly.
# for now we just keep it persistent for ever


class RTSPChannel(http.HTTPChannel):

    requestFactory = RTSPRequest

    def checkPersistence(self, request, version):
        if version == SERVER_PROTOCOL:
            return 1
        log.err('version %s not handled' % version)
        return 0

#class RTSPFactory(http.HTTPFactory):
#    protocol = RTSPChannel
#    timeout = 60


class RTSPSite(server.Site):
    """
    I am a ServerFactory that can be used in
    L{twisted.internet.interfaces.IReactorTCP}'s .listenTCP
    Create me with an L{RTSPResource} object.
    """
    protocol = RTSPChannel
    requestFactory = RTSPRequest

    def logRequest(self, ip, requestLine, headerLines):
        pass

    def logReply(self, code, message, headerLines, body):
        pass


class RTSPResource(resource.Resource, flog.Loggable):
    """
    I am a base class for all RTSP Resource classes.

    @type allowedMethods: tuple
    @ivar allowedMethods: a tuple of allowed methods that can be invoked
                          on this resource.
    """

    logCategory = 'resource'
    allowedMethods = ['OPTIONS']

    def getChild(self, path, request):
        return NoResource()
        # use WithDefault so static children have a chance too
        self.log(
            'RTSPResource.getChild(%r, %s, <request>), pre %r, post %r' % (
            self, path, request.prepath, request.postpath))
        res = resource.Resource.getChild(self, path, request)
        self.log('RTSPResource.getChild(%r, %s, <request>) returns %r' % (
            self, path, res))
        return res

    def getChildWithDefault(self, path, request):
        self.log(
            'RTSPResource.getChildWithDefault(%r, %s, <request>), pre %r, '
            'post %r' % (
            self, path, request.prepath, request.postpath))
        self.log('children: %r' % self.children.keys())
        res = resource.Resource.getChildWithDefault(self, path, request)
        self.log(
            'RTSPResource.getChildWithDefault(%r, %s, <request>) '
            'returns %r' % (
            self, path, res))
        return res

    # FIXME: remove

    def noputChild(self, path, r):
        self.log('RTSPResource.putChild(%r, %s, %r)' % (self, path, r))
        return resource.Resource.putChild(self, path, r)

    # needs to be done for ALL responses
    # see 12.17 CSeq and H14.19 Date

    def render_startCSeqDate(self, request, method):
        """
        Set CSeq and Date on response to given request.
        This should be done even for errors.
        """
        self.log('render_startCSeqDate, method %r' % method)
        cseq = request.getHeader('CSeq')
        # RFC says clients MUST have CSeq field, but we're lenient
        # in what we accept and assume 0 if not specified
        if cseq == None:
            cseq = 0
        request.setHeader('CSeq', cseq)
        request.setHeader('Date', http.datetimeToString())

    def render_start(self, request, method):
        ip = request.getClientIP()
        self.log('RTSPResource.render_start(): client from %s requests %s' % (
            ip, method))
        self.log('RTSPResource.render_start(): uri %r' % request.path)

        self.render_startCSeqDate(request, method)
        request.setHeader('Server', SERVER_STRING)
        request.delHeader('Content-Type')

        # tests for 3gpp
        request.setHeader('Last-Modified', http.datetimeToString())
        request.setHeader('Cache-Control', 'must-revalidate')
        #request.setHeader('x-Accept-Retransmit', 'our-revalidate')
        #request.setHeader('x-Accept-Dynamic-Rate', '1')
        #request.setHeader('Content-Base', 'rtsp://core.fluendo.com/test.3gpp')
        #request.setHeader('Via', 'RTSP/1.0 288f9c2a')

        # hacks for Real
        if 'Real' in request.received_headers.get('user-agent', ''):
            self.debug('Detected Real client, sending specific headers')
            # request.setHeader('Public', 'OPTIONS, DESCRIBE, ANNOUNCE, PLAY,
            #                   SETUP, GET_PARAMETER, SET_PARAMETER, TEARDOWN')
            # Public seems to be the same as allowed-methods, and real clients
            # seem to respect SET_PARAMETER not listed here
            request.setHeader(
                'Public',
                'OPTIONS, DESCRIBE, ANNOUNCE, PLAY, SETUP, TEARDOWN')
            # without a RealChallenge1, clients don't even go past OPTIONS
            request.setHeader('RealChallenge1',
                              '28d49444034696e1d523f2819b8dcf4c')
            #request.setHeader('StatsMask', '3')

    def render_GET(self, request):
        # the Resource.get_HEAD refers to this -- pacify pychecker
        raise NotImplementedError


class ErrorResource(RTSPResource):

    def __init__(self, code, *lines):
        resource.Resource.__init__(self)
        self.code = code
        self.body = ""
        if lines != (None, ):
            self.body = "\n".join(lines) + "\n\n"

        # HACK!
        if not hasattr(self, 'method'):
            self.method = 'GET'

    def render(self, request):
        request.clientproto = SERVER_PROTOCOL
        self.render_startCSeqDate(request, request.method)
        request.setResponseCode(self.code)
        if self.body:
            request.setHeader('content-type', "text/plain")
        return self.body

    def render_GET(self, request):
        # the Resource.get_HEAD refers to this -- pacify pychecker
        raise NotImplementedError

    def getChild(self, chname, request):
        return self


class NoResource(ErrorResource):

    def __init__(self, message=None):
        ErrorResource.__init__(self, NOT_FOUND, message)
