# -*- Mode: Python; test-case-name: flumotion.test.test_component_providers -*-
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

import errno

from twisted.internet import defer

from flumotion.common import log

from flumotion.component.misc.httpserver import fileprovider
from flumotion.component.misc.httpserver import cachestats

LOG_CATEGORY = "resource-manager"


errnoLookup = {errno.ENOENT: fileprovider.NotFoundError,
               errno.EISDIR: fileprovider.CannotOpenError,
               errno.EACCES: fileprovider.AccessError}


class DataSource(object):
    """
    Base class for all resources data source.
    """

    url = None
    identifier = None
    mimeType = None
    mtime = None
    size = None

    def read(self, offset, size):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()


class ResourceManager(log.Loggable):
    """
    Provide file-like resources for URLs.
    """

    logCategory = LOG_CATEGORY

    def __init__(self, strategy, stats):
        self.strategy = strategy
        self.stats = stats

    def getResourceFor(self, url):
        self.debug("Resource requested with %s", url)

        stats = cachestats.RequestStatistics(self.stats)

        d = defer.Deferred()
        d.addCallback(self.strategy.getSourceFor, stats)
        d.addCallback(Resource, stats)

        d.callback(url)

        return d


class Resource(object):
    """
    Offers a file-like interface of a data source.
    Handle errors and asynchronous readings and file offset.
    """

    def __init__(self, source, stats):
        self._open(source)
        self._offset = 0
        self._reading = False
        self.stats = stats

    def getMimeType(self):
        return self.mimeType

    def getmtime(self):
        return self._source.mtime

    def getsize(self):
        return self._source.size

    def tell(self):
        return self._offset

    def seek(self, offset):
        self._check()
        self._offset = offset

    def read(self, size):
        self._check()
        assert not self._reading, "Simultaneous read not supported"
        try:
            d = self._source.read(self._offset, size)
            if isinstance(d, defer.Deferred):
                self._reading = True
                return d.addCallback(self._cbUpdateOffset)
            self._offset += len(d)
            return defer.succeed(d)
        except IOError, e:
            cls = errnoLookup.get(e.errno, fileprovider.FileError)
            return defer.fail(cls("Failed to read data: %s", str(e)))
        except:
            return defer.fail()

    def produce(self, consumer, fromOffset=None):
        """
        Returns a producer that produce data from the specified position
        or from the current position if None is specified.
        Can return None if a producer cannot be provided or is not convenient.
        """
        self._check()
        return self._source.produce(consumer, fromOffset or self._offset)

    def close(self):
        self._check()
        self._source.close()
        self._source = None

    def getLogFields(self):
        return self.stats.getLogFields()

    ### Protected Methods ###

    def _check(self):
        if self._source is None:
            raise fileprovider.FileClosedError("File Closed")

    def _open(self, source):
        self._source = source
        self.mimeType = source.mimeType

    ### Private Methods ###

    def _cbUpdateOffset(self, data):
        self._reading = False
        self._offset += len(data)
        return data
