# -*- Mode: Python; test-case-name: flumotion.test.test_http -*-
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

import socket
import resource
import time

try:
    from twisted.web import http
except ImportError:
    from twisted.protocols import http

from twisted.web import server, resource as web_resource
from twisted.internet import defer

from flumotion.configure import configure
from flumotion.common import log

# register serializable
from flumotion.common import keycards


__all__ = ['HTTPStreamingResource']
__version__ = "$Rev$"


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

HTTP_VERSION = configure.version


class HTTPStreamingResource(web_resource.Resource, log.Loggable):
    HTTP_NAME = 'FlumotionHTTPServer'
    HTTP_SERVER = '%s/%s' % (HTTP_NAME, HTTP_VERSION)

    __reserve_fds__ = 50 # number of fd's to reserve for non-streaming

    logCategory = 'httpstreamer'

    # IResource interface variable; True means it will not chain requests
    # further down the path to other resource providers through
    # getChildWithDefault
    isLeaf = True

    def __init__(self, streamer, httpauth):
        """
        @param streamer: L{Streamer}
        """
        self.streamer = streamer
        self.httpauth = httpauth

        self._requests = {}            # request fd -> Request
        self._removing = {} # Optional deferred notification of client removals

        self.maxclients = self.getMaxAllowedClients(-1)
        self.maxbandwidth = -1 # not limited by default

        # If set, a URL to redirect a user to when the limits above are reached
        self._redirectOnFull = None

        socket = 'flumotion.component.plugs.request.RequestLoggerPlug'
        self.loggers = streamer.plugs.get(socket, [])

        socket = \
            'flumotion.component.plugs.requestmodifier.RequestModifierPlug'
        self.modifiers = streamer.plugs.get(socket, [])

        self.logfilter = None

        web_resource.Resource.__init__(self)

    def removeAllClients(self):
        l = []
        for fd in self._requests.keys():
            self._removing[fd] = defer.Deferred()
            l.append(self._removing[fd])
            self.streamer.remove_client(fd)

        return defer.DeferredList(l)

    def setRoot(self, path):
        self.putChild(path, self)

    def setLogFilter(self, logfilter):
        self.logfilter = logfilter

    def rotateLogs(self):
        """
        Close the logfile, then reopen using the previous logfilename
        """
        for logger in self.loggers:
            self.debug('rotating logger %r' % logger)
            logger.rotate()

    def getLogFields(self, request):
        """ """
        headers = request.getAllHeaders()

        args = {'ip': request.getClientIP(),
                'time': time.mktime(time.gmtime()),
                'method': request.method,
                'uri': request.uri,
                'username': '-',  # FIXME: put the httpauth name
                'get-parameters': request.args,
                'clientproto': request.clientproto,
                'response': request.code,
                'referer': headers.get('referer', None),
                'user-agent': headers.get('user-agent', None)}

        args.update(self._getExtraLogArgs(request))
        return args

    def logWrite(self, request, bytes_sent, time_connected):
        headers = request.getAllHeaders()

        args = {'ip': request.getClientIP(),
                'time': time.gmtime(),
                'method': request.method,
                'uri': request.uri,
                'username': '-', # FIXME: put the httpauth name
                'get-parameters': request.args,
                'clientproto': request.clientproto,
                'response': request.code,
                'bytes-sent': bytes_sent,
                'referer': headers.get('referer', None),
                'user-agent': headers.get('user-agent', None),
                'time-connected': time_connected}

        args.update(self._getExtraLogArgs(request))

        l = []
        for logger in self.loggers:
            l.append(defer.maybeDeferred(
                logger.event, 'http_session_completed', args))

        return defer.DeferredList(l)

    def setUserLimit(self, limit):
        self.info('setting maxclients to %d' % limit)
        self.maxclients = self.getMaxAllowedClients(limit)
        # Log what we actually managed to set it to.
        self.info('set maxclients to %d' % self.maxclients)

    def setBandwidthLimit(self, limit):
        self.maxbandwidth = limit
        self.info("set maxbandwidth to %d", self.maxbandwidth)

    def setRedirectionOnLimits(self, url):
        self._redirectOnFull = url

    def isReady(self):
        raise NotImplementedError("isReady must be implemented by "
                                  "subclasses")

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
        """
        Check whether or not the server reached the limit of concurrent client
        """
        if self.maxclients >= 0 and len(self._requests) >= self.maxclients:
            return True
        elif self.maxbandwidth >= 0:
            # Reject if adding one more client would take us over the limit.
            if ((len(self._requests) + 1) *
                    self.streamer.getCurrentBitrate() >= self.maxbandwidth):
                return True
        return False

    def _getExtraLogArgs(self, request):
        """
        Extra arguments for logging. Should be overriden by subclasses
        that provide extra arguments for logging

        @rtype: dict
        @returns: A dictionary with the extra arguments
        """
        return {}

    def _setRequestHeaders(self, request, content=None, allow_cache=False):
        content = content or self.streamer.get_content_type()
        request.setHeader('Server', self.HTTP_SERVER)
        request.setHeader('Date', http.datetimeToString())
        if not allow_cache:
            request.setHeader('Cache-Control', 'no-cache')
            request.setHeader('Cache-Control', 'private')
        request.setHeader('Content-type', content)

    def _addClient(self, id, request=None):
        """
        Add a request, so it can be used for statistics.

        @param id: the of the client (fd or session id)
        @type request: int
        """
        self._requests[id] = request and request or id

    def _removeClient(self, id):
        """
        Delete a request from the list

        @param request: the id of the client
        @type request: int
        """
        try:
            del self._requests[id]
        except Exception:
            self.warning("Error removing request: %s", id)

    def _logRequestFromIP(self, ip):
        """
        Returns whether we want to log a request from this IP; allows us to
        filter requests from automated monitoring systems.
        """
        if self.logfilter:
            return not self.logfilter.isInRange(ip)
        else:
            return True

    ### resource.Resource methods

    def _handleNotReady(self, request):
        self.debug('Not sending data, it\'s not ready')
        return server.NOT_DONE_YET

    def _handleServerFull(self, request):
        if self._redirectOnFull:
            self.debug("Redirecting client, client limit %d reached",
                self.maxclients)
            error_code = http.FOUND
            request.setHeader('location', self._redirectOnFull)
        else:
            self.debug('Refusing clients, client limit %d reached' %
                self.maxclients)
            error_code = http.SERVICE_UNAVAILABLE

        request.setHeader('content-type', 'text/html')

        request.setHeader('server', HTTP_VERSION)
        request.setResponseCode(error_code)

        return ERROR_TEMPLATE % {'code': error_code,
                                 'error': http.RESPONSES[error_code]}
