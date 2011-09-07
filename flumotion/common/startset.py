# -*- Mode: Python -*-
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

"""a data structure to manage asynchronous avatar starts and shutdowns
"""

from twisted.internet import defer

from flumotion.common import log

__version__ = "$Rev$"


# This class was factored out of the worker's jobheaven, so sometimes
# the comments talk about jobs, but they refer to any asynchronous
# process. For example the multiadmin uses this to manage its
# connections to remote managers.


class StartSet(log.Loggable):

    def __init__(self, avatarLoggedIn, alreadyStartingError,
                 alreadyRunningError):
        """Create a StartSet, a data structure for managing starts and
        stops of remote processes, for example jobs in a jobheaven.

        @param avatarLoggedIn: a procedure of type avatarId->boolean;
        should return True if the avatarId is logged in and "ready", and
        False otherwise. An avatarId is ready if avatarStarted() could
        have been called on it. This interface is made this way because
        it is assumed that whatever code instantiates a StartSet keeps
        track of "ready" remote processes, and this way we prevent data
        duplication.
        @param alreadyStartingError: An exception class to raise if
        createStart() is called, but there is already a create deferred
        registered for that avatarId.
        @param alreadyRunningError: An exception class to raise if
        createStart() is called, but there is already a "ready" process
        with that avatarId.
        """
        self._avatarLoggedIn = avatarLoggedIn
        self._alreadyStartingError = alreadyStartingError
        self._alreadyRunningError = alreadyRunningError

        self._createDeferreds = {} # avatarId => deferred
        self._shutdownDeferreds = {} # avatarId => deferred

    def createStart(self, avatarId):
        """
        Create and register a deferred for starting a given process.
        The deferred will be fired when the process is ready, as
        triggered by a call to createSuccess().

        @param avatarId: the id of the remote process, for example the
        avatarId of the job

        @rtype: L{twisted.internet.defer.Deferred}
        """
        self.debug('making create deferred for %s', avatarId)

        d = defer.Deferred()

        # the question of "what jobs do we know about" is answered in
        # three places: the create deferreds hash, the set of logged in
        # avatars, and the shutdown deferreds hash. there are four
        # possible answers:
        if avatarId in self._createDeferreds:
            # (1) a job is already starting: it is in the
            # createdeferreds hash
            self.info('already have a create deferred for %s', avatarId)
            raise self._alreadyStartingError(avatarId)
        elif avatarId in self._shutdownDeferreds:
            # (2) a job is shutting down; note it is also in
            # heaven.avatars
            self.debug('waiting for previous %s to shut down like it '
                       'said it would', avatarId)
            # fixme: i don't understand this code

            def ensureShutdown(res,
                               shutdown=self._shutdownDeferreds[avatarId]):
                shutdown.addCallback(lambda _: res)
                return shutdown
            d.addCallback(ensureShutdown)
        elif self._avatarLoggedIn(avatarId):
            # (3) a job is running fine
            self.info('avatar named %s already running', avatarId)
            raise self._alreadyRunningError(avatarId)
        else:
            # (4) it's new; we know of nothing with this avatarId
            pass

        self.debug('registering deferredCreate for %s', avatarId)
        self._createDeferreds[avatarId] = d
        return d

    def createSuccess(self, avatarId):
        """
        Trigger a deferred start previously registerd via createStart().
        For example, a JobHeaven might call this method when a job has
        logged in and been told to start a component.

        @param avatarId: the id of the remote process, for example the
        avatarId of the job
        """
        self.debug('triggering create deferred for %s', avatarId)
        if not avatarId in self._createDeferreds:
            self.warning('No create deferred registered for %s', avatarId)
            return

        d = self._createDeferreds[avatarId]
        del self._createDeferreds[avatarId]
        # return the avatarId the component will use to the original caller
        d.callback(avatarId)

    def createFailed(self, avatarId, exception):
        """
        Notify the caller that a create has failed, and remove the create
        from the list of pending creates.

        @param avatarId: the id of the remote process, for example the
        avatarId of the job
        @param exception: either an exception or a failure describing
        why the create failed.
        """
        self.debug('create deferred failed for %s', avatarId)
        if not avatarId in self._createDeferreds:
            self.warning('No create deferred registered for %s', avatarId)
            return

        d = self._createDeferreds[avatarId]
        del self._createDeferreds[avatarId]
        d.errback(exception)

    def createRegistered(self, avatarId):
        """
        Check if a deferred create has been registered for the given avatarId.

        @param avatarId: the id of the remote process, for example the
        avatarId of the job

        @returns: The deferred create, if one has been registered.
        Otherwise None.
        """
        return self._createDeferreds.get(avatarId, None)

    def shutdownStart(self, avatarId):
        """
        Create and register a deferred that will be fired when a process
        has shut down cleanly.

        @param avatarId: the id of the remote process, for example the
        avatarId of the job

        @rtype: L{twisted.internet.defer.Deferred}
        """
        self.debug('making shutdown deferred for %s', avatarId)

        if avatarId in self._shutdownDeferreds:
            self.warning('already have a shutdown deferred for %s',
                         avatarId)
            return self._shutdownDeferreds[avatarId]
        else:
            self.debug('registering shutdown for %s', avatarId)
            d = defer.Deferred()
            self._shutdownDeferreds[avatarId] = d
            return d

    def shutdownSuccess(self, avatarId):
        """
        Trigger a callback on a deferred previously registered via
        shutdownStart(). For example, a JobHeaven would call this when a
        job for which shutdownStart() was called is reaped.

        @param avatarId: the id of the remote process, for example the
        avatarId of the job
        """
        self.debug('triggering shutdown deferred for %s', avatarId)
        if not avatarId in self._shutdownDeferreds:
            self.warning('No shutdown deferred registered for %s', avatarId)
            return

        d = self._shutdownDeferreds.pop(avatarId)
        d.callback(avatarId)

    def shutdownRegistered(self, avatarId):
        """
        Check if a deferred shutdown has been registered for the given
        avatarId.

        @param avatarId: the id of the remote process, for example the
        avatarId of the job

        @returns: True if a deferred shutdown has been registered for
        this object, False otherwise
        """
        return avatarId in self._shutdownDeferreds

    def avatarStarted(self, avatarId):
        """
        Notify the startset that an avatar has started. If there was a
        create deferred registered for this avatar, this will cause
        createSuccess() to be called.

        @param avatarId: the id of the remote process, for example the
        avatarId of the job
        """
        if avatarId in self._createDeferreds:
            self.createSuccess(avatarId)
        else:
            self.log('avatar %s started, but we were not waiting for'
                     ' it', avatarId)

    def avatarStopped(self, avatarId, getFailure):
        """
        Notify the startset that an avatar has stopped. If there was a
        shutdown deferred registered for this avatar, this will cause
        shutdownSuccess() to be called.

        On the other hand, if there was a create deferred still pending,
        we will call createFailed with the result of calling getFailure.

        If no start or create was registered, we do nothing.

        @param avatarId: the id of the remote process, for example the
        avatarId of the job
        @param getFailure: procedure of type avatarId -> Failure. The
        returned failure should describe the reason that the job failed.
        """
        if avatarId in self._createDeferreds:
            self.createFailed(avatarId, getFailure(avatarId))
        elif avatarId in self._shutdownDeferreds:
            self.shutdownSuccess(avatarId)
        else:
            self.debug('unknown avatar %s logged out', avatarId)
