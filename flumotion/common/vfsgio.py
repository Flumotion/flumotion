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

"""GIO backend for Virtual File System.
"""

import os

import gobject
from twisted.internet.defer import succeed
from twisted.spread.flavors import Copyable, RemoteCopy
from twisted.spread.jelly import setUnjellyableForClass
from zope.interface import implements

from flumotion.common import log
from flumotion.common.errors import AccessDeniedError
from flumotion.common.interfaces import IDirectory, IFile

# gio is only imported inside nested scopes so that
# pychecker can ignore them, If pychecker ever gets fixed,
# move it back where it belongs
__pychecker__ = 'keepgoing'


class GIOFile(Copyable, RemoteCopy):
    """I am object implementing L{IFile} on top of GIO,
    see L{IFile} for more information.
    """
    implements(IFile)

    def __init__(self, parent, gfile):
        self.parent = parent
        self.filename = gfile.name
        self.iconNames = self._getIconNames()

    def _getIconNames(self):
        import gio
        gFile = gio.File(self._filename)
        gFileInfo = gFile.query_info('standard::icon')
        gIcon = gFileInfo.get_icon()
        return gIcon.get_names()

    # IFile

    def getPath(self):
        return os.path.join(self.parent.get_path(), self.name)


class GIODirectory(Copyable, RemoteCopy):
    """I am object implementing L{IDirectory} on top of GIO,
    see L{IDirectory} for more information.
    """
    implements(IDirectory)

    def __init__(self, path):
        import gio
        gfile = gio.File(os.path.abspath(path))
        self.path = path
        self.filename = gfile.get_basename()
        self.iconNames = self._getIconNames(gfile)

    def _getIconNames(self, gFile):
        gFileInfo = gFile.query_info('standard::icon')
        gIcon = gFileInfo.get_icon()
        return gIcon.get_names()


    # IFile

    def getPath(self):
        return self.path

    # IDirectory

    def getFiles(self):
        import gio
        log.info('vfsgio', 'getting files for %s' % (self.path, ))
        retval = []
        gfile = gio.File(os.path.abspath(self.path))
        try:
            gfiles = gfile.enumerate_children('standard::*')
        except gobject.GError, e:
            if (e.domain == gio.ERROR and
                e.code == gio.ERROR_PERMISSION_DENIED):
                raise AccessDeniedError
            raise
        for gfile in gfiles:
            filename = gfile.get_basename()
            if filename.startswith('.') and filename != '..':
                continue
            if gfile.get_file_type() == gio.FILE_TYPE_DIRECTORY:
                obj = GIODirectory(os.path.join(self.path, gfile.name))
            else:
                obj = GIOFile(self.path, gfile)
            retval.append(obj)
        log.info('vfsgio', 'returning %r' % (retval, ))
        return succeed(retval)


def registerGIOJelly():
    """Register the jelly used by the GIO VFS backend.
    """
    setUnjellyableForClass(GIOFile, GIOFile)
    setUnjellyableForClass(GIODirectory, GIODirectory)
    log.info('jelly', 'GIO registered')
