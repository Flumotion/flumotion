# -*- Mode: Python; test-case-name: flumotion.test.test_common -*-
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

"""cancellable, periodic call to a procedure
"""

from twisted.internet import reactor
from twisted.internet.defer import maybeDeferred

from flumotion.common import log

__version__ = "$Rev$"


class Poller(object, log.Loggable):
    """A class representing a cancellable, periodic call to a procedure,
    which is robust in the face of exceptions raised by the procedure.

    The poller will wait for a specified number of seconds between
    calls. The time taken for the procedure to complete is not counted
    in the timeout. If the procedure returns a deferred, rescheduling
    will be performed after the deferred fires.

    For example, if the timeout is 10 seconds and the procedure returns
    a deferred which fires 5 seconds later, the next invocation of the
    procedure will be performed 15 seconds after the previous
    invocation.
    """

    def __init__(self, proc, timeout, immediately=False, start=True):
        """
        @param proc: a procedure of no arguments
        @param timeout: float number of seconds to wait between calls
        @param immediately: whether to immediately call proc, or to wait
            until one period has passed
        @param start: whether to start the poller (defaults to True)
        """

        self.proc = proc
        self.logName = 'poller-%s' % proc.__name__
        self.timeout = timeout

        self._dc = None
        self.running = False

        if start:
            self.start(immediately)

    def start(self, immediately=False):
        """Start the poller.

        This procedure is called during __init__, so it is normally not
        necessary to call it. It will ensure that the poller is running,
        even after a previous call to stop().

        @param immediately: whether to immediately invoke the poller, or
        to wait until one period has passed
        """
        if self.running:
            self.debug('already running')
        else:
            self.running = True
            self._reschedule(immediately)

    def _reschedule(self, immediately=False):
        assert self._dc is None
        if self.running:
            if immediately:
                self.run()
            else:
                self._dc = reactor.callLater(self.timeout, self.run)
        else:
            self.debug('shutting down, not rescheduling')

    def run(self):
        """Run the poller immediately, regardless of when it was last
        run.
        """

        def reschedule(v):
            self._reschedule()
            return v

        if self._dc and self._dc.active():
            # we don't get here in the normal periodic case, only for
            # explicit run() invocations
            self._dc.cancel()
        self._dc = None
        d = maybeDeferred(self.proc)
        d.addBoth(reschedule)

    def stop(self):
        """Stop the poller.

        This procedure ensures that the poller is stopped. It may be
        called multiple times.
        """
        if self._dc:
            self._dc.cancel()
            self._dc = None
        self.running = False
