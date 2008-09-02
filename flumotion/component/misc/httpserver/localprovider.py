# -*- Mode: Python; test-case-name: -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

import os
import stat
import errno

from twisted.internet import defer

from flumotion.common import log
from flumotion.component.misc.httpserver import fileprovider, localpath
from flumotion.component.misc.httpserver.fileprovider import FileError
from flumotion.component.misc.httpserver.fileprovider import FileClosedError

# os.SEEK_SET is not definied in python 2.4
SEEK_SET = 0

LOG_CATEGORY = "fileprovider-local"


class LocalPlug(fileprovider.FileProvider, log.Loggable):
    """
    I am a plug that provide local files directly,
    faking the file access is asynchronous.
    """

    logcategory = LOG_CATEGORY

    def __init__(self, args):
        props = args['properties']
        self._path = props.get('path', None)

    def startStatsUpdates(self, updater):
        # No statistics for local file provider
        pass

    def stopStatsUpdates(self):
        pass

    def getRootPath(self):
        if self._path is None:
            return None
        return LocalPath(self._path)


class LocalPath(localpath.LocalPath):

    def open(self):
        return LocalFile(self.path, self.mimeType)


class LocalFile(fileprovider.File, log.Loggable):
    """
    I offer a fake asynchronous wrapper around a synchronous file.
    I'm not thread-safe, I should only be used to read small blocks
    from a local file system and I don't support cloning.
    """

    logCategory = LOG_CATEGORY

    _errorLookup = {errno.ENOENT: fileprovider.NotFoundError,
                    errno.EISDIR: fileprovider.CannotOpenError,
                    errno.EACCES: fileprovider.AccessError}

    # Overriding parent class properties to become attribute
    mimeType = None

    # Default values
    _file = None
    _info = None

    def __init__(self, path, mimeType):
        self._path = path
        self.mimeType = mimeType
        try:
            self._file = open(path, 'rb')
            self.debug("%s opened [fd %5d]", self, self._file.fileno())
        except IOError, e:
            cls = self._errorLookup.get(e[0], FileError)
            raise cls("Failed to open file '%s': %s" % (path, str(e)))
        try:
            self._info = os.fstat(self._file.fileno())
        except OSError, e:
            cls = self._errorLookup.get(e[0], FileError)
            raise cls("Failed to stat file '%s': %s" % (path, str(e)))

    def __str__(self):
        return "<LocalFile '%s'>" % self._path

    def getsize(self):
        if self._file is None:
            raise FileClosedError("File closed")
        # The size is not supposed to change over time
        return self._info[stat.ST_SIZE]

    def getmtime(self):
        if self._file is None:
            raise FileClosedError("File closed")
        # The modification time is not supposed to change over time
        return self._info[stat.ST_MTIME]

    def tell(self):
        if self._file is None:
            raise FileClosedError("File closed")
        try:
            return self._file.tell()
        except IOError, e:
            cls = self._errorLookup.get(e[0], FileError)
            raise cls("Failed to tell position in file '%s': %s"
                      % (self._path, str(e)))

    def seek(self, offset):
        if self._file is None:
            raise FileClosedError("File closed")
        try:
            self._file.seek(offset, SEEK_SET)
        except IOError, e:
            cls = self._errorLookup.get(e[0], FileError)
            raise cls("Failed to seek in file '%s': %s"
                      % (self._path, str(e)))

    def read(self, size):
        if self._file is None:
            raise FileClosedError("File closed")
        try:
            data = self._file.read(size)
            return defer.succeed(data)
        except IOError, e:
            cls = self._errorLookup.get(e[0], FileError)
            return defer.fail(cls("Failed to read data from %s: %s"
                                  % (self._path, str(e))))
        except:
            return defer.fail()

    def close(self):
        if self._file is not None:
            try:
                try:
                    self._file.close()
                finally:
                    self._file = None
                    self._info = None
            except IOError, e:
                cls = self._errorLookup.get(e[0], FileError)
                raise cls("Failed to close file '%s': %s"
                          % (self._path, str(e)))

    def __del__(self):
        self.close()

    def getLogFields(self):
        return {}
