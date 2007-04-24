# -*- Mode: Python; test-case-name: flumotion.test.test_misc_httpfile -*-
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

from flumotion.component import component
from flumotion.common import log, messages, errors, netutils
from flumotion.component.component import moods
from flumotion.component.misc.porter import porterclient
from flumotion.component.base import http as httpbase
from twisted.web import resource, server, http
from twisted.web import error as weberror
from twisted.internet import defer, reactor, error, abstract
from twisted.python import filepath
from flumotion.twisted import fdserver
from twisted.cred import credentials

from twisted.web.static import loadMimeTypes, getTypeAndEncoding

# this file is inspired by/adapted from twisted.web.static

class File(resource.Resource, filepath.FilePath, log.Loggable):
    contentTypes = loadMimeTypes()

    defaultType = "application/octet-stream"

    childNotFound = weberror.NoResource("File not found.")

    def __init__(self, path, component):
        """
        @param component: L{flumotion.component.component.BaseComponent}
        """
        resource.Resource.__init__(self)
        filepath.FilePath.__init__(self, path)

        self._component = component

    def getChild(self, path, request):
        self.restat()

        if not self.isdir():
            return self.childNotFound

        if path:
            fpath = self.child(path)
        else:
            return self.childNotFound

        if not fpath.exists():
            return self.childNotFound

        return self.createSimilarFile(fpath.path)

    def openForReading(self):
        """Open a file and return it."""
        f = self.open()
        self.debug("Reading file from FD: %d", f.fileno())
        return f

    def getFileSize(self):
        """Return file size."""
        return self.getsize()

    def render(self, request):
        self.debug('render request %r' % request)
        def terminateSimpleRequest(res, request):
            if res != server.NOT_DONE_YET:
                request.finish()

        d = self._component.startAuthentication(request)
        d.addCallback(self.renderAuthenticated, request)
        d.addCallback(terminateSimpleRequest, request)

        return server.NOT_DONE_YET

    def renderAuthenticated(self, _, request):
        # Now that we're authenticated (or authentication wasn't requested), 
        # write the file (or appropriate other response) to the client.
        # We override static.File to implement Range requests, and to get access
        # to the transfer object to abort it later; the bulk of this is a direct
        # copy of static.File.render, though.
        # self.restat()
        self.debug('renderAuthenticated request %r' % request)

        ext = os.path.splitext(self.basename())[1].lower()
        type = self.contentTypes.get(ext, self.defaultType)

        if not self.exists():
            self.debug("Couldn't find resource %s", self.path)
            return self.childNotFound.render(request)

        if self.isdir():
            return self.childNotFound.render(request)

        # Different headers not normally set in static.File...        
        # Specify that we will close the connection after this request, and
        # that the client must not issue further requests. 
        # We do this because future requests on this server might actually need
        # to go to a different process (because of the porter)
        request.setHeader('Connection', 'close')
        # We can do range requests, in bytes.
        request.setHeader('Accept-Ranges', 'bytes')

        if type:
            request.setHeader('content-type', type)

        try:
            f = self.openForReading()
        except IOError, e:
            import errno
            if e[0] == errno.EACCES:
                return weberror.ForbiddenResource().render(request)
            else:
                raise

        if request.setLastModified(self.getmtime()) is http.CACHED:
            return ''

        fileSize = self.getFileSize()
        # first and last byte offset we will write
        first = 0
        last = fileSize - 1

        range = request.getHeader('range')
        if range is not None:
            # We have a partial data request.
            # for interpretation of range, see RFC 2068 14.36
            # examples: bytes=500-999; bytes=-500 (suffix mode; last 500)
            rangeKeyValue = string.split(range, '=')
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
            f.seek(first)

            # FIXME: is it still partial if the request was for the complete
            # file ? Couldn't find a conclusive answer in the spec.
            request.setResponseCode(http.PARTIAL_CONTENT)
            request.setHeader('Content-Range', "bytes %d-%d/%d" % 
                (first, last, fileSize))

        request.setHeader("Content-Length", str(last - first + 1))

        if request.method == 'HEAD':
             return ''
           
        request._transfer = FileTransfer(f, last + 1, request)

        return server.NOT_DONE_YET

    def createSimilarFile(self, path):
        self.debug("createSimilarFile at %r", path)
        f = self.__class__(path, self._component)
        return f

class FileTransfer:
    """
    A class to represent the transfer of a file over the network.
    """
    request = None

    def __init__(self, file, size, request):
        self.file = file
        self.size = size
        self.request = request
        self.written = self.file.tell()
        self.bytesWritten = 0
        request.registerProducer(self, 0)

    def resumeProducing(self):
        if not self.request:
            return
        data = self.file.read(min(abstract.FileDescriptor.bufferSize, 
            self.size - self.written))
        if data:
            self.written += len(data)
            self.bytesWritten += len(data)
            # this .write will spin the reactor, calling .doWrite and then
            # .resumeProducing again, so be prepared for a re-entrant call
            self.request.write(data)
        if self.request and self.file.tell() == self.size:
            self.request.unregisterProducer()
            self.request.finish()
            self.request = None

    def pauseProducing(self):
        pass

    def stopProducing(self):
        self.file.close()
        self.request = None

