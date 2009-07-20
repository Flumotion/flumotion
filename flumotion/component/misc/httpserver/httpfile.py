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
import time

# mp4seek is a library to split MP4 files, see the MP4File class docstring
HAS_MP4SEEK = False
try:
    import mp4seek.async
    HAS_MP4SEEK = True
except ImportError:
    pass

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
                 requestModifiers=None,
                 metadataProvider=None):
        resource.Resource.__init__(self)

        self._path = path
        self._httpauth = httpauth
        # mapping of mime type -> File subclass
        self._mimeToResource = mimeToResource or {}
        self._rateController = rateController
        self._metadataProvider = metadataProvider
        self._requestModifiers = requestModifiers or []
        self._factory = MimedFileFactory(httpauth, self._mimeToResource,
                                         rateController=rateController,
                                         metadataProvider=metadataProvider,
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
        """
        The request gets rendered by asking the httpauth object for
        authentication, which returns a deferred.
        This deferred will callback when the request gets authenticated.
        """

        # PROBE: incoming request; see httpstreamer.resources
        self.debug('[fd %5d] (ts %f) incoming request %r',
                   request.transport.fileno(), time.time(), request)

        d = self._httpauth.startAuthentication(request)
        d.addCallbacks(self._requestAuthenticated, self._authenticationFailed,
                       callbackArgs=(request, ), errbackArgs=(request, ))
        # return NOT_DONE_YET, as required by the twisted.web interfaces
        return server.NOT_DONE_YET

    def _authenticationFailed(self, failure, request):
        # Authentication failed; nothing more to do, just swallow the
        # failure. The object responsible for authentication has already
        # written a proper response to the client and closed the request.
        pass

    def _requestAuthenticated(self, result, request):
        # Authentication suceeded. Start rendering the request.
        # We always want to call _terminateRequest after rendering,
        # regardless of whether there's a failure while rendering it or not.
        d = defer.succeed(result)
        d.addCallback(self._renderRequest, request)
        d.addBoth(self._terminateRequest, request)
        return d

    def _terminateRequest(self, body, request):
        if body == server.NOT_DONE_YET:
            # _renderRequest will return NOT_DONE_YET if it started serving the
            # file. This means the callback chain started by _renderRequest has
            # finished and we're currently serving the file.
            return
        if isinstance(body, Failure):
            # Something went wrong, log it
            self.warning("Failure during request rendering: %s",
                         log.getFailureMessage(body))
            body = self.internalServerError.render(request)
        if body:
            # the callback chain from _renderRequest chose to return a string
            # body, write it out to the client
            request.write(body)
        self.debug('[fd %5d] Terminate request %r',
                   request.transport.fileno(), request)
        request.finish()

    def _renderRequest(self, _, request):

        # PROBE: authenticated request; see httpstreamer.resources
        self.debug('[fd %5d] (ts %f) authenticated request %r',
                   request.transport.fileno(), time.time(), request)

        # Now that we're authenticated (or authentication wasn't requested),
        # write the file (or appropriate other response) to the client.
        # We override static.File to implement Range requests, and to get
        # access to the transfer object to abort it later; the bulk of this
        # is a direct copy of static.File.render, though.
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
        # UGLY HACK FIXME: if pdf, then do not accept range requests
        # because Adobe Reader plugin messes up
        if not self._path.path.endswith('.pdf'):
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
                    last = min(int(end), last)
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
        d = defer.maybeDeferred(self.do_prepareBody,
                                request, provider, first, last)

        def dispatchMethod(header, request):
            if request.method == 'HEAD':
                # the _terminateRequest callback will be fired, and the request
                # will be finished
                return ''
            return self._startRequest(request, header, provider, first, last)

        d.addCallback(dispatchMethod, request)

        return d

    def _startRequest(self, request, header, provider, first, last):
        # Call request modifiers
        for modifier in self._requestModifiers:
            modifier.modify(request)

        # PROBE: started request; see httpstreamer.resources
        self.debug('[fd %5d] (ts %f) started request %r',
                   request.transport.fileno(), time.time(), request)

        if self._metadataProvider:
            self.log("Retrieving metadata using %r", self._metadataProvider)
            d = self._metadataProvider.getMetadata(self._path.path)
        else:
            d = defer.succeed(None)

        def metadataError(failure):
            self.warning('Error retrieving metadata for file %s'
                        ' using plug %r. %r',
                        self._path.path,
                        self._metadataProvider,
                        failure.value)

        d.addErrback(metadataError)
        d.addCallback(self._configureTransfer, request, header,
                      provider, first, last)

        return d

    def _configureTransfer(self, metadata, request, header,
                           provider, first, last):
        if self._rateController:
            self.debug("Creating RateControl object using plug %r and "
                       "metadata %r", self._rateController, metadata)

            # We are passing a metadata dictionary as Proxy settings.
            # So the rate control can use it if needed.
            d = defer.maybeDeferred(
                self._rateController.createProducerConsumerProxy,
                request, metadata)
        else:
            d = defer.succeed(request)

        def attachProxy(consumer, provider, header, first, last):
            # If we have a header, give it to the consumer first
            if header:
                consumer.write(header)

            # Set the provider first, because for very small file
            # the transfer could terminate right away.
            request._provider = provider
            transfer = FileTransfer(provider, last + 1, consumer)
            request._transfer = transfer

            # The important NOT_DONE_YET was already returned by the render()
            # method and the value returned here is just part of a convention
            # between _renderRequest and _terminateRequest. The latter assumes
            # that if the deferred chain initiated by _renderRequest will fire
            # with NOT_DONE_YET if the transfer is in progress.
            return server.NOT_DONE_YET

        d.addCallback(attachProxy, provider, header, first, last)

        return d

    def do_prepareBody(self, request, provider, first, last):
        """
        I am called before the body of the response gets written,
        and after generic header setting has been done.

        I set Content-Length.

        Override me to send additional headers, or to prefix the body
        with data headers.

        I can return a Deferred, that should fire with a string header. That
        header will be written to the request.
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
                 requestModifiers=None,
                 metadataProvider=None):
        self._httpauth = httpauth
        self._mimeToResource = mimeToResource or {}
        self._rateController = rateController
        self._requestModifiers = requestModifiers
        self._metadataProvider = metadataProvider

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
                     requestModifiers=self._requestModifiers,
                     metadataProvider=self._metadataProvider)


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
        ret = ''

        # if there is a non-zero start get parameter, prefix the body with
        # our FLV header
        # each value is a list
        start = int(request.args.get('start', ['0'])[0])
        # range request takes precedence over our start parsing
        if request.getHeader('range') is None and start:
            self.debug('Start %d passed, seeking', start)
            provider.seek(start)
            length = last - start + 1 + len(self.header)
            ret = self.header

        request.setHeader("Content-Length", str(length))

        return ret


class MP4File(File):
    """
    I am a File resource for MP4 files.
    If I have a library for manipulating MP4 files available, I can handle
    requests with a 'start' GET parameter, Without the library, I ignore this
    parameter.
    The 'start' parameter represents the time offset from where to start, in
    seconds.  If it is non-zero, I will seek inside the file to the sample with
    that time, and prepend the content with rebuilt MP4 tables, to make the
    output playable.
    """

    def do_prepareBody(self, request, provider, first, last):
        self.log('do_prepareBody for MP4')
        length = last - first + 1
        ret = ''

        # if there is a non-zero start get parameter, split the file, prefix
        # the body with the regenerated header and seek inside the provider
        start = float(request.args.get('start', ['0'])[0])
        # range request takes precedence over our start parsing
        if request.getHeader('range') is None and start and HAS_MP4SEEK:
            self.debug('Start %f passed, seeking', start)
            provider.seek(0)
            d = self._split_file(provider, start)

            def seekAndSetContentLength(header_and_offset):
                header, offset = header_and_offset
                # the header is a file-like object with the file pointer at the
                # end, the offset is a number
                length = last - offset + 1 + header.tell()
                if offset:
                    provider.seek(offset)
                request.setHeader("Content-Length", str(length))
                header.seek(0)
                return header.read()

            d.addCallback(seekAndSetContentLength)
            return d
        else:
            request.setHeader('Content-Length', str(length))
            return defer.succeed(ret)

    def _split_file(self, provider, start):
        d = defer.Deferred()

        def read_some_data(how_much, from_where):
            if how_much:
                provider.seek(from_where)
                read_d = provider.read(how_much)
                read_d.addCallback(splitter.feed)
                read_d.addErrback(d.errback)
            else:
                d.callback(splitter.result())

        splitter = mp4seek.async.Splitter(start)
        splitter.start(read_some_data)

        return d


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
        self._finished = False # Set when we finish a transfer
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

        # We might have got a  stopProducing before the _cbGotData callback has
        # been fired, so we might be in the _finished state. If so, just
        # return.
        if self._finished:
            return

        if data:
            # WARNING! This call goes back to the reactor! Read the comment in
            # _writeToConsumer!
            self._writeToConsumer(data)

        # We again might be in _finished state, because we might just
        # got out of the reactor after writing some data to the consumer.
        #
        # The story goes thusly:
        # 1) you write the last data chunk
        # 2) before you get out of _writeToConsumer(), the _cbGotData gets
        #    fired again
        # 3) because it's the last write (we've written the entire file)
        #    _terminate() gets called
        # 4) consumer and provider are set to None
        # 5) you return from the _writeToConsumer call
        #
        # If this happened, just exit (again)
        if self._finished:
            return

        if self.provider.tell() == self.size:
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

    def _writeToConsumer(self, data):
        self.written += len(data)
        self.bytesWritten += len(data)
        # this .write will spin the reactor, calling .doWrite and then
        # .resumeProducing again, so be prepared for a re-entrant call
        self.consumer.write(data)

    def _terminate(self):
        self.provider.close()
        self.provider = None
        self.consumer.unregisterProducer()
        self.consumer.finish()
        self.consumer = None
        self._finished = True
