# -*- Mode: Python; test-case-name: flumotion.test.test_component_providers -*-
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

from twisted.internet import defer

from flumotion.common import log
from flumotion.component.misc.httpserver import fileprovider
from flumotion.component.misc.httpserver import localpath
from flumotion.component.misc.httpserver.httpcached import file_reader


BASE_PATH = "/"

LOG_CATEGORY = "fileprovider-httpcached"


class FileProviderHTTPCachedPlug(fileprovider.FileProviderPlug, log.Loggable):
    """
    Implements the FileProviderPlug interface over a FileReader instance.

    Needed because FileReader do not support file browsing.
    """

    logCategory = LOG_CATEGORY

    def __init__(self, args):
        self._reader = file_reader.FileReaderHTTPCachedPlug(args)

    def start(self, component):
        d = defer.Deferred()
        d.addCallback(lambda _: self._reader.start())
        d.addCallback(lambda _: self) # Don't return internal references
        d.callback(None)
        return d

    def stop(self, component):
        d = defer.Deferred()
        d.addCallback(lambda _: self._reader.stop())
        d.addCallback(lambda _: self) # Don't return internal references
        d.callback(None)
        return d

    def startStatsUpdates(self, updater):
        #FIXME: This is temporary. Should be done with plug UI.
        # Used for the UI to know which plug is used
        updater.update("provider-name", "fileprovider-httpcached")
        self._reader.stats.startUpdates(updater)

    def stopStatsUpdates(self):
        self._reader.stats.stopUpdates()

    def getRootPath(self):
        return VirtualPath(self, BASE_PATH)


class VirtualPath(localpath.LocalPath, log.Loggable):

    logCategory = LOG_CATEGORY

    def __init__(self, plug, path):
        localpath.LocalPath.__init__(self, path)
        self.plug = plug

    def child(self, name):
        childpath = self._getChildPath(name)
        return VirtualPath(self.plug, childpath)

    def open(self):
        return self.plug._reader.open(self._path)
