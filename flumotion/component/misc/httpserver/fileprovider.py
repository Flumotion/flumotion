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

from flumotion.component.plugs import base as plugbase


class FileError(Exception):
    """
    I am raised when a File or a FilePath operation failed.
    Like trying to get the size or open a file that does not exists.
    """


class InsecureError(FileError):
    """
    I am raised when trying to build an insecure path using FilePath.
    For example, when trying to retrieve a child with a name that
    contains insecure characters like os.sep .
    """


class NotFoundError(FileError):
    """
    I am raised when trying to retrieve a child that does nor exists,
    or do an operation on a file that does not exists.
    """


class CannotOpenError(FileError):
    """
    I am raised when trying to open a path that is not a file.
    """


class AccessError(FileError):
    """
    I am raised when a file operation failed because of right restriction.
    """


class FileClosedError(FileError):
    """
    I am raised when trying to do some operation on a closed file.
    """


class FilePath(object):
    """
    I am pointing at a path in the file repository.
    I can point at a file or at a directory.
    I can open the pointed file object.
    I'm used to browse file repository to lookup for file.
    """

    def getMimeType(self):
        """
        @return: the mime type of the pointed file or None if unknown
        @rtype:  str
        """
    mimeType = property(getMimeType)

    def child(self, name):
        """
        @param name: the name of a child of the pointed directory
        @type  name: str

        @return: a FilePath that point at the specified child
        @rtype:  L{MediaPath}
        @raises NotFoundError: if the child does not exists
        @raises InsecureError: if the specified name compromise security
        """

    def open(self):
        """
        @return: the pointed file opened as an asynchronous file
        @rtype:  L{AsyncFile}
        @raises NotFoundError: if the file does not exists anymore
        @raises AccessError: if the file cannot be opened
                             because of right restriction
        """


class File(object):
    """
    I am an asynchronous interface to a file.
    I can be read and written asynchronously.
    """

    def getMimeType(self):
        """
        @return: the mime type of the file or None if unknown
        @rtype:  str
        """
    mimeType = property(getMimeType)

    def getmtime(self):
        """
        @return: the modification time of the file
        @rtype:  int
        """

    def getsize(self):
        """
        @return: the size of the file
        @rtype:  long
        """

    def tell(self):
        """
        @returns: the current read/write position in the file
        @rtype:   long
        """

    def seek(self, offset):
        """
        Moves the reading/writing position inside the file.
        Only support absolute offset from file start.

        @param offset: the byte offset from the start of the file to go to
        @type  offset: long
        """

    def read(self, size):
        """
        Reads the specified amount of data asynchronously.

        @param size: the amount of byte to read from the file
        @type  size: int

        @return:     a deferred fired with the read data or a failure.
                     The data can be empty or smaller than the wanted size
                     if the end of file is reached.
        @type:       L{defer.Deferred}
        """

    def close(self):
        """
        Close and cleanup the file.
        """

    def getLogFields(self):
        """
        @returns: a dictionary of log fields related to the file usage
        @rtype:   dict
        """


class FileProviderPlug(plugbase.ComponentPlug):
    """
    I am a plug that provide a root FilePath instance
    that can be used to lookup and open file objects.
    """

    def startStatsUpdates(self, updater):
        """
        Start updating statistics.
        """

    def stopStatsUpdates(self):
        """
        Stop updating statistics.
        """

    def getRootPath(self):
        """
        @return: the root of the file repository
        @rtype:  L{FilePath}
        """
