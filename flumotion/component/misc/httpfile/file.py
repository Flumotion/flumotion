# -*- Mode: Python -*-
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

class File(resource.Resource, filepath.FilePath, log.Loggable):
    __pychecker__ = 'no-objattrs'

    contentTypes = loadMimeTypes()

    defaultType = "application/octet-stream"

    childNotFound = weberror.NoResource("File not found.")

    def __init__(self, path, component):
        resource.Resource.__init__(self)
        filepath.FilePath.__init__(self, path)

        self.component = component

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
        def terminateSimpleRequest(res, request):
            if res != server.NOT_DONE_YET:
                request.finish()

        d = self.component.startAuthentication(request)
        d.addCallback(self.renderAuthenticated, request)
        d.addCallback(terminateSimpleRequest, request)

        return server.NOT_DONE_YET

    def renderAuthenticated(self, res, request):
        """ 
        Now that we're authenticated (or authentication wasn't requested), 
        write the file (or appropriate other response) to the client.
        We override static.File to implement Range requests, and to get access
        to the transfer object to abort it later; the bulk of this is a direct
        copy, though.
        """
        self.restat()

        ext = os.path.splitext(self.basename())[1].lower()
        type = self.contentTypes.get(ext, self.defaultType)

        if not self.exists():
            self.debug("Couldn't find resource %s", self.basename())
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

        tsize = fsize = size = self.getFileSize()
        range = request.getHeader('range')
        start = 0
        if range is not None:
            # TODO: Add a unit test - or several - for this stuff.
            # We have a partial-data request...
            # Some variables... we start at byte offset 'start', end at byte 
            # offset 'end'. fsize is the number of bytes we're sending. tsize 
            # is the total size of the file. 'size' is the byte offset we will
            # stop at, plus 1.
            bytesrange = string.split(range, '=')
            if len(bytesrange) != 2:
                request.setResponseCode(http.REQUESTED_RANGE_NOT_SATISFIABLE)
                return ''

            start, end = string.split(bytesrange[1], '-', 1)
            if start:
                start = int(start)
                f.seek(start)
                if end:
                    end = int(end)
                else:
                    end = size - 1
                fsize = end - start + 1
            elif end:
                lastbytes = int(end)
                if size < lastbytes:
                    lastbytes = size
                start = size - lastbytes
                f.seek(start)
                fsize = lastbytes
                end = size - 1
            else:
                request.setResponseCode(http.REQUESTED_RANGE_NOT_SATISFIABLE)
                return ''
            size = end + 1

            request.setResponseCode(http.PARTIAL_CONTENT)
            request.setHeader('Content-Range', "bytes %d-%d/%d" % 
                (start, end, tsize))

        request.setHeader("Content-Length", str(fsize))

        if request.method == 'HEAD':
             return ''
           
        request._transfer = FileTransfer(f, size, request)

        return server.NOT_DONE_YET

    def createSimilarFile(self, path):
        self.debug("createSimilarFile at %r", path)
        f = self.__class__(path, self.component)
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

