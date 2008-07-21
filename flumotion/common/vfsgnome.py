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

import gnomevfs
from twisted.internet.defer import succeed
from twisted.spread.flavors import Copyable, RemoteCopy
from twisted.spread.jelly import setUnjellyableForClass
from zope.interface import implements

from flumotion.common import log
from flumotion.common.errors import AccessDeniedError
from flumotion.common.interfaces import IDirectory, IFile



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

    def __init__(self, path):
        fileInfo = gnomevfs.get_file_info(os.path.abspath(path))
        self.path = path
        self.filename = fileInfo.name
        self.iconNames = ['gnome-fs-directory']

    # IFile

    def getPath(self):
        return self.path

    # IDirectory

    def getFiles(self):
        log.info('vfsgnome', 'getting files for %s' % (self.path,))
        retval = []
        try:
            fileInfos = gnomevfs.open_directory(self.path)
        except gnomevfs.AccessDeniedError:
            raise AccessDeniedError
        for fileInfo in fileInfos:
            filename = fileInfo.name
            if filename.startswith('.') and filename != '..':
                continue
            if fileInfo.type == gnomevfs.FILE_TYPE_DIRECTORY:
                obj = GnomeVFSDirectory(os.path.join(self.path,
                                                     fileInfo.name))
            else:
                obj = GnomeVFSFile(self.path, fileInfo)
            retval.append(obj)
        log.info('vfsgnome', 'returning %r' % (retval,))
        return succeed(retval)


def registerGnomeVFSJelly():
    """Register the jelly used by the GnomeVFS VFS backend.
    """
    setUnjellyableForClass(GnomeVFSFile, GnomeVFSFile)
    setUnjellyableForClass(GnomeVFSDirectory, GnomeVFSDirectory)
    log.info('jelly', 'GnomeVFS registered')

