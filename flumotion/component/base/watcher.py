# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2006,2007 Fluendo, S.L. (www.fluendo.com).
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
import time

from twisted.internet import reactor

from flumotion.common import log

__version__ = "$Rev$"


class BaseWatcher(log.Loggable):
    """I watch for file changes.

    I am a base class for a file watcher. I can be specialized to watch
    any set of files.
    """

    def __init__(self, timeout):
        """Make a file watcher object.

        @param timeout: timeout between checks, in seconds
        @type timeout: int
        """
        self.timeout = timeout
        self._reset()
        self._subscribeId = 0
        self.subscribers = {}

    def _reset(self):
        self._stableData = {}
        self._changingData = {}
        self._delayedCall = None

    def _subscribe(self, **events):
        """Subscribe to events.

        @param events: The events to subscribe to. Subclasses are
        expected to formalize this dict, specifying which events they
        support via declaring their kwargs explicitly.

        @returns: A subscription ID that can later be passed to
        unsubscribe().
        """
        sid = self._subscribeId
        self._subscribeId += 1
        self.subscribers[sid] = events
        return sid

    def subscribe(self, fileChanged=None, fileDeleted=None):
        """Subscribe to events.

        @param fileChanged: A function to call when a file changes. This
        function will only be called if the file's details (size, mtime)
        do not change during the timeout period.
        @type fileChanged: filename -> None
        @param fileDeleted: A function to call when a file is deleted.
        @type fileDeleted: filename -> None

        @returns: A subscription ID that can later be passed to
        unsubscribe().
        """
        return self._subscribe(fileChanged=fileChanged,
                               fileDeleted=fileDeleted)

    def unsubscribe(self, id):
        """Unsubscribe from file change notifications.

        @param id: Subscription ID received from subscribe()
        """
        del self.subscribers[id]

    def event(self, event, *args, **kwargs):
        """Fire an event.

        This method is intended for use by object implementations.
        """
        for s in self.subscribers.values():
            if s[event]:
                # Exceptions raised by subscribers need to be catched to
                # continue polling for changes
                try:
                    s[event](*args, **kwargs)
                except Exception, e:
                    self.warning("A callback for event %s raised an error: %s"
                            % (event, log.getExceptionMessage(e)))

    # FIXME: this API has tripped up two people thus far, including its
    # author. make subscribe() call start() if necessary?

    def start(self):
        """Start checking for file changes.

        Subscribers will be notified asynchronously of changes to the
        watched files.
        """

        def checkFiles():
            self.log("checking for file changes")
            new = self.getFileData()
            changing = self._changingData
            stable = self._stableData
            for f in new:
                if f not in changing:
                    if not f in stable and self.isNewFileStable(f, new[f]):
                        self.debug('file %s stable when noted', f)
                        stable[f] = new[f]
                        self.event('fileChanged', f)
                    elif f in stable and new[f] == stable[f]:
                        # no change
                        pass
                    else:
                        self.debug('change start noted for %s', f)
                        changing[f] = new[f]
                else:
                    if new[f] == changing[f]:
                        self.debug('change finished for %s', f)
                        del changing[f]
                        stable[f] = new[f]
                        self.event('fileChanged', f)
                    else:
                        self.log('change continues for %s', f)
                        changing[f] = new[f]
            for f in stable.keys():
                if f not in new:
                    # deletion
                    del stable[f]
                    self.debug('file %s has been deleted', f)
                    self.event('fileDeleted', f)
            for f in changing.keys():
                if f not in new:
                    self.debug('file %s has been deleted', f)
                    del changing[f]
            self._delayedCall = reactor.callLater(self.timeout,
                                                  checkFiles)

        assert self._delayedCall is None
        checkFiles()

    def stop(self):
        """Stop checking for file changes.
        """
        self._delayedCall.cancel()
        self._reset()

    def getFileData(self):
        """
        @returns: a dict, {filename => DATA}
        DATA can be anything. In the default implementation it is a pair
        of (mtime, size).
        """
        ret = {}
        for f in self.getFilesToStat():
            try:
                stat = os.stat(f)
                ret[f] = (stat.st_mtime, stat.st_size)
            except OSError, e:
                self.debug('could not read file %s: %s', f,
                           log.getExceptionMessage(e))
        return ret

    def isNewFileStable(self, fName, fData):
        """
        Check if the file is already stable when being added to the
        set of watched files.

        @param fName: filename
        @type  fName: str
        @param fData: DATA, as returned by L{getFileData} method. In
                      the default implementation it is a pair of
                      (mtime, size).

        @rtype: bool
        """
        __pychecker__ = 'unusednames=fName'

        ret = fData[0] + self.timeout < time.time()
        return ret

    def getFilesToStat(self):
        """
        @returns: sequence of filename
        """
        raise NotImplementedError


class DirectoryWatcher(BaseWatcher):
    """
    Directory Watcher
    Watches a directory for new files.
    """

    def __init__(self, path, ignorefiles=(), timeout=30):
        BaseWatcher.__init__(self, timeout)
        self.path = path
        self._ignorefiles = ignorefiles

    def getFilesToStat(self):
        return [os.path.join(self.path, f)
                for f in os.listdir(self.path)
                if f not in self._ignorefiles]


class FilesWatcher(BaseWatcher):
    """
    Watches a collection of files for modifications.
    """

    def __init__(self, files, timeout=30):
        BaseWatcher.__init__(self, timeout)
        self._files = files

    def getFilesToStat(self):
        return self._files
