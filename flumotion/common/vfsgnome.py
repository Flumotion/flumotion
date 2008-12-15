# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2008 Fluendo, S.L. (www.fluendo.com).
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

"""GnomeVFS backend for Virtual File System.
"""

import os

from twisted.internet.defer import succeed
from twisted.spread.flavors import Copyable, RemoteCopy
from twisted.spread.jelly import setUnjellyableForClass
from zope.interface import implements

from flumotion.common import log
from flumotion.common.errors import AccessDeniedError
from flumotion.common.interfaces import IDirectory, IFile

# gnomevfs is only imported inside nested scopes so that
# pychecker can ignore them, If pychecker ever gets fixed,
# move it back where it belongs
__pychecker__ = 'keepgoing'


class GnomeVFSFile(Copyable, RemoteCopy):
    """I am object implementing L{IFile} on top of GnomeVFS,
    see L{IFile} for more information.
    """
    implements(IFile)

    def __init__(self, parent, fileInfo):
        self.parent = parent
        self.filename = fileInfo.name
        self.iconNames = ['gnome-fs-regular']

    # IFile

    def getPath(self):
        return os.path.join(self.parent, self.filename)


class GnomeVFSDirectory(Copyable, RemoteCopy):
    """I am object implementing L{IDirectory} on top of GnomeVFS,
    see L{IDirectory} for more information.
    """
    implements(IDirectory)

    def __init__(self, path, name=None):
        import gnomevfs
        self.path = path
        if name is None:
            fileInfo = gnomevfs.get_file_info(os.path.abspath(path))
            name = fileInfo.name
        self.filename = name
        self.iconNames = ['gnome-fs-directory']
        self._cachedFiles = None

    # IFile

    def getPath(self):
        return self.path

    # IDirectory

    def getFiles(self):
        return succeed(self._cachedFiles)

    def cacheFiles(self):
        """
        Fetches the files contained on the directory for posterior usage of
        them. This should be called on the worker side to work or the files
        wouldn't be the expected ones.
        """
        import gnomevfs
        log.debug('vfsgnome', 'getting files for %s' % (self.path, ))
        retval = []
        try:
            fileInfos = gnomevfs.open_directory(self.path)
        except gnomevfs.AccessDeniedError:
            raise AccessDeniedError
        if self.path != '/':
            retval.append(GnomeVFSDirectory(os.path.dirname(self.path),
                                            name='..'))
        for fileInfo in fileInfos:
            filename = fileInfo.name
            if filename.startswith('.'):
                continue
            if fileInfo.type == gnomevfs.FILE_TYPE_DIRECTORY:
                obj = GnomeVFSDirectory(os.path.join(self.path,
                                                     fileInfo.name))
            else:
                obj = GnomeVFSFile(self.path, fileInfo)
            retval.append(obj)
        log.log('vfsgnome', 'returning %r' % (retval, ))
        self._cachedFiles = retval


def registerGnomeVFSJelly():
    """Register the jelly used by the GnomeVFS VFS backend.
    """
    setUnjellyableForClass(GnomeVFSFile, GnomeVFSFile)
    setUnjellyableForClass(GnomeVFSDirectory, GnomeVFSDirectory)
    log.info('jelly', 'GnomeVFS registered')
