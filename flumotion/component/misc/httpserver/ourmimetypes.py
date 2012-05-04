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

import os

from twisted.web import static


class MimeTypes(object):

    @staticmethod
    def loadMimeTypes():
        # Add our own mime types to the ones parsed from /etc/mime.types
        d = static.loadMimeTypes()
        d['.flv'] = 'video/x-flv'
        d['.mp4'] = 'video/mp4'
        d['.webm'] = 'video/webm'
        d['.ts'] = 'video/MP2T'
        d['.m3u8'] = 'application/vnd.apple.mpegurl'
        return d

    def __init__(self):
        self._mimetypes = self.loadMimeTypes()

    def fromPath(self, path, default=None):
        ext = os.path.splitext(path)[1]
        return self._mimetypes.get(ext.lower(), default)
