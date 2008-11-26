# -*- Mode: Python; test-case-name: flumotion.test.test_misc_httpserver -*-
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

import string
import os

from twisted.web import resource, server, http
from twisted.web import error as weberror, static
from twisted.internet import defer, reactor, error, abstract
from twisted.cred import credentials
from twisted.python.failure import Failure

from flumotion.configure import configure
from flumotion.component import component
from flumotion.common import log, messages, errors, netutils
from flumotion.component.component import moods
from flumotion.component.misc.porter import porterclient
from flumotion.component.misc.httpserver import fileprovider
from flumotion.component.base import http as httpbase
from flumotion.twisted import fdserver

__version__ = "$Rev$"

LOG_CATEGORY = "httpserver"


class BadRequest(weberror.ErrorPage):
    """
    Web error for invalid requests
    """

    def __init__(self, message="Invalid request format"):
        weberror.ErrorPage.__init__(self, http.BAD_REQUEST,
                                    "Bad Request", message)


class InternalServerError(weberror.ErrorPage):
    """
    Web error for internal failures
    """

    def __init__(self, message="The server failed to complete the request"):
        weberror.ErrorPage.__init__(self, http.INTERNAL_SERVER_ERROR,
                                    "Internal Server Error", message)


class File(resource.Resource, log.Loggable):
    """
    this file is inspired by/adapted from twisted.web.static
    """

    logCategory = LOG_CATEGORY

    defaultType = "application/octet-stream"

    childNotFound = weberror.NoResource("File not found.")
    forbiddenResource = weberror.ForbiddenResource("Access forbidden")
    badRequest = BadRequest()
    internalServerError = InternalServerError()

    def __init__(self, path, httpauth,
                 mimeToResource=None,
                 rateController=None,
                 requestModifiers=None):
        resource.Resource.__init__(self)

        self._path = path
        self._httpauth = httpauth
        # mapping of mime type -> File subclass
        self._mimeToResource = mimeToResource or {}
        self._rateController = rateController
        self._requestModifiers = requestModifiers or []
        self._factory = MimedFileFactory(httpauth, self._mimeToResource,
                                         rateController=rateController,
                                         requestModifiers=requestModifiers)

    def getChild(self, path, request):
        self.log('getChild: self %r, path %r', self, path)
        # we handle a request ending in '/' as well; this is how those come in
        if path == '':
            return self

        try:
            child = self._path.child(path)
        except fileprovider.NotFoundError:
            return self.childNotFound
        except fileprovider.AccessError:
            return self.forbiddenResource
        except fileprovider.InsecureError:
            return self.badRequest

        return self._factory.create(child)

    def render(self, request):
        self.debug('[fd %5d] render incoming request %r',
                   request.transport.fileno(), request)
        d = self._httpauth.startAuthentication(request)
        d.addCallbacks(self._requestAuthenticated, self._authenticationFailed,
                       callbackArgs=(request, ), errbackArgs=(request, ))
        return server.NOT_DONE_YET

    def _authenticationFailed(self, failure, request):
        # Authentication failed; nothing more to do, just swallow the failure.
        pass

    def _requestAuthenticated(self, result, request):
        d = defer.succeed(result)
        d.addCallback(self._renderRequest, request)
        d.addBoth(self._terminateRequest, request)
        return d

    def _terminateRequest(self, body, request):
        if body == server.NOT_DONE_YET:
            # Currently serving the file
            return
        if isinstance(body, Failure):
            # Something goes wrong, log it
            self.warning("Failure during request rendering: %s",
                         log.getFailureMessage(body))
            body = self.internalServerError.render(request)
        if body:
            # render result/error page
            request.write(body)
        self.debug('Finish request %r' % request)
        request.finish()

    def _renderRequest(self, _, request):
        # Now that we're authenticated (or authentication wasn't requested),
        # write the file (or appropriate other response) to the client.
        # We override static.File to implement Range requests, and to get
        # access to the transfer object to abort it later; the bulk of this
        # is a direct copy of static.File.render, though.
        self.debug('Render authenticated request %r' % request)
        try:
            self.debug("Opening file %s", self._path)
            provider = self._path.open()
        except fileprovider.NotFoundError:
            self.debug("Could not find resource %s", self._path)
            return self.childNotFound.render(request)
        except fileprovider.CannotOpenError:
            self.debug("%s is a directory, can't be GET", self._path)
            return self.childNotFound.render(request)
        except fileprovider.AccessError:
            return self.forbiddenResource.render(request)

        # Different headers not normally set in static.File...
        # Specify that we will close the connection after this request, and
        # that the client must not issue further requests.
        # We do this because future requests on this server might actually need
        # to go to a different process (because of the porter)
        request.setHeader('Server', 'Flumotion/%s' % configure.version)
        request.setHeader('Connection', 'close')
        # We can do range requests, in bytes.
        request.setHeader('Accept-Ranges', 'bytes')

        if request.setLastModified(provider.getmtime()) is http.CACHED:
            return ''

        contentType = provider.mimeType or self.defaultType

        if contentType:
            self.debug('File content type: %r' % contentType)
            request.setHeader('content-type', contentType)

        fileSize = provider.getsize()
        # first and last byte offset we will write
        first = 0
        last = fileSize - 1

        requestRange = request.getHeader('range')
        if requestRange is not None:
            # We have a partial data request.
            # for interpretation of range, see RFC 2068 14.36
            # examples: bytes=500-999; bytes=-500 (suffix mode; last 500)
            self.log('range request, %r', requestRange)
            rangeKeyValue = string.split(requestRange, '=')
            if len(rangeKeyValue) != 2:
                request.setResponseCode(http.REQUESTED_RANGE_NOT_SATISFIABLE)
                return ''

            if rangeKeyValue[0] != 'bytes':
                request.setResponseCode(http.REQUESTED_RANGE_NOT_SATISFIABLE)
                return ''

            # ignore a set of range requests for now, only take the first
            ranges = rangeKeyValue[1].split(',')[0]
            l = ranges.split('-')
            if len(l) != 2:
                request.setResponseCode(http.REQUESTED_RANGE_NOT_SATISFIABLE)
                return ''

            start, end = l

            if start:
                # byte-range-spec
                first = int(start)
                if end:
                    last = int(end)
            elif end:
                # suffix-byte-range-spec
                count = int(end)
                # we can't serve more than there are in the file
                if count > fileSize:
                    count = fileSize
                first = fileSize - count
            else:
                # need at least start or end
                request.setResponseCode(http.REQUESTED_RANGE_NOT_SATISFIABLE)
                return ''

            # Start sending from the requested position in the file
            if first:
                # TODO: logs suggest this is called with negative values,
                # figure out how
                self.debug("Request for range \"%s\" of file, seeking to "
                           "%d of total file size %d", ranges, first, fileSize)
                provider.seek(first)

            # FIXME: is it still partial if the request was for the complete
            # file ? Couldn't find a conclusive answer in the spec.
            request.setResponseCode(http.PARTIAL_CONTENT)
            request.setHeader('Content-Range', "bytes %d-%d/%d" %
                              (first, last, fileSize))

        request.setResponseRange(first, last, fileSize)
        self.do_prepareBody(request, provider, first, last)

        if request.method == 'HEAD':
            return ''

        # Call request modifiers
        for modifier in self._requestModifiers:
            modifier.modify(request)

        if self._rateController:
            self.log("Creating RateControl object using plug %r",
                self._rateController)
            # What do we want to pass to this? The consumer we proxy to,
            # perhaps the request object too? This object? The file itself?

            # We probably want the filename part of the request URL - the bit
            # after the mount-point. e.g. in /customer1/videos/video1.ogg, we
            # probably want to provide /videos/video1.ogg to this..
            d = defer.maybeDeferred(
                self._rateController.createProducerConsumerProxy,
                request, request)
        else:
            d = defer.succeed(request)

        def attachProxy(consumer):
            # Set the provider first, because for very small file
            # the transfer could terminate right away.
            request._provider = provider
            transfer = FileTransfer(provider, last + 1, consumer)
            request._transfer = transfer

        d.addCallback(attachProxy)

        return server.NOT_DONE_YET

    def do_prepareBody(self, request, provider, first, last):
        """
        I am called before the body of the response gets written,
        and after generic header setting has been done.

        I set Content-Length.

        Override me to send additional headers, or to prefix the body
        with data headers.
        """
        request.setHeader("Content-Length", str(last - first + 1))


class MimedFileFactory(log.Loggable):
    """
    I create File subclasses based on the mime type of the given path.
    """

    logCategory = LOG_CATEGORY

    defaultType = "application/octet-stream"

    def __init__(self, httpauth,
                 mimeToResource=None,
                 rateController=None,
                 requestModifiers=None):
        self._httpauth = httpauth
        self._mimeToResource = mimeToResource or {}
        self._rateController = rateController
        self._requestModifiers = requestModifiers

    def create(self, path):
        """
        Creates and returns an instance of a File subclass based
        on the mime type of the given path.
        """
        mimeType = path.mimeType or self.defaultType
        self.debug("Create %s file for %s", mimeType, path)
        klazz = self._mimeToResource.get(mimeType, File)
        return klazz(path, self._httpauth,
                     mimeToResource=self._mimeToResource,
                     rateController=self._rateController,
                     requestModifiers=self._requestModifiers)


class FLVFile(File):
    """
    I am a File resource for FLV files.
    I can handle requests with a 'start' GET parameter.
    This parameter represents the byte offset from where to start.
    If it is non-zero, I will output an FLV header so the result is
    playable.
    """
    header = 'FLV\x01\x01\000\000\000\x09\000\000\000\x09'

    def do_prepareBody(self, request, provider, first, last):
        self.log('do_prepareBody for FLV')
        length = last - first + 1

        # if there is a non-zero start get parameter, prefix the body with
        # our FLV header
        # each value is a list
        start = int(request.args.get('start', ['0'])[0])
        # range request takes precedence over our start parsing
        if first == 0 and start:
            self.debug('Start %d passed, seeking', start)
            provider.seek(start)
            length = last - start + 1 + len(self.header)

        request.setHeader("Content-Length", str(length))

        if request.method == 'HEAD':
            return ''

        if first == 0 and start:
            request.write(self.header)


class FileTransfer(log.Loggable):
    """
    A class to represent the transfer of a file over the network.
    """

    logCategory = LOG_CATEGORY

    consumer = None

    def __init__(self, provider, size, consumer):
        """
        @param provider: an asynchronous file provider
        @type  provider: L{fileprovider.File}
        @param size: file position to which file should be read
        @type  size: int
        @param consumer: consumer to receive the data
        @type  consumer: L{twisted.internet.interfaces.IFinishableConsumer}
        """
        self.provider = provider
        self.size = size
        self.consumer = consumer
        self.written = self.provider.tell()
        self.bytesWritten = 0
        self._pending = None
        self._again = False # True if resume was called while waiting for data
        self.debug("Calling registerProducer on %r", consumer)
        consumer.registerProducer(self, 0)

    def resumeProducing(self):
        if not self.consumer:
            return
        self._produce()

    def pauseProducing(self):
        pass

    def stopProducing(self):
        self.debug('Stop producing from %s at %d/%d bytes',
                   self.provider, self.provider.tell(), self.size)
        # even though it's the consumer stopping us, from looking at
        # twisted code it looks like we still are required to
        # unregister and notify the request that we're done...
        self._terminate()

    def _produce(self):
        if self._pending:
            # We already are waiting for data, just remember more is needed
            self._again = True
            return
        self._again = False
        d = self.provider.read(min(abstract.FileDescriptor.bufferSize,
                                   self.size - self.written))
        self._pending = d
        d.addCallbacks(self._cbGotData, self._ebReadFailed)

    def _cbGotData(self, data):
        self._pending = None
        if self.consumer and data:
            self.written += len(data)
            self.bytesWritten += len(data)
            # this .write will spin the reactor, calling .doWrite and then
            # .resumeProducing again, so be prepared for a re-entrant call
            self.consumer.write(data)
        if self.consumer and (self.provider.tell() == self.size):
            self.debug('Written entire file of %d bytes from %s',
                       self.size, self.provider)
            self._terminate()
        elif self._again:
            # Continue producing
            self._produce()

    def _ebReadFailed(self, failure):
        self._pending = None
        self.warning('Failure during file %s reading: %s',
                     self.provider, log.getFailureMessage(failure))
        self._terminate()

    def _terminate(self):
        self.provider.close()
        self.provider = None
        self.consumer.unregisterProducer()
        self.consumer.finish()
        self.consumer = None
