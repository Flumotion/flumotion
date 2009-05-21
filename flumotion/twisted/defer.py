# -*- Mode: Python; test-case-name: flumotion.test.test_defer -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

import random

from twisted.internet import defer, reactor
from twisted.python import reflect

# FIXME: this is for HandledException - maybe it should move here instead ?
from flumotion.common import errors

__version__ = "$Rev$"


# See flumotion.test.test_defer for examples


def defer_generator(proc):

    def wrapper(*args, **kwargs):
        gen = proc(*args, **kwargs)
        result = defer.Deferred()

        # To support having the errback of last resort, we need to have
        # an errback which runs after all the other errbacks, *at the
        # point at which the deferred is fired*. So users of this code
        # have from between the time the deferred is created and the
        # time that the deferred is fired to attach their errbacks.
        #
        # Unfortunately we only control the time that the deferred is
        # created. So we attach a first errback that then adds an
        # errback to the end of the list. Unfortunately we can't add to
        # the list while the deferred is firing. In a decision between
        # having decent error reporting and being nice to a small part
        # of twisted I chose the former. This code takes a reference to
        # the callback list, so that we can add an errback to the list
        # while the deferred is being fired. It temporarily sets the
        # state of the deferred to not having been fired, so that adding
        # the errbacks doesn't automatically call the newly added
        # methods.
        result.__callbacks = result.callbacks

        def with_saved_callbacks(proc, *_args, **_kwargs):
            saved_callbacks, saved_called = result.callbacks, result.called
            result.callbacks, result.called = result.__callbacks, False
            proc(*_args, **_kwargs)
            result.callbacks, result.called = saved_callbacks, saved_called

        # Add errback-of-last-resort

        def default_errback(failure, d):
            # an already handled exception just gets propagated up without
            # doing a traceback
            if failure.check(errors.HandledException):
                return failure

            def print_traceback(f):
                import traceback
                print 'flumotion.twisted.defer: ' + \
                    'Unhandled error calling', proc.__name__, ':', f.type
                traceback.print_exc()
            with_saved_callbacks(lambda: d.addErrback(print_traceback))
            raise
        result.addErrback(default_errback, result)

        def generator_next():
            try:
                x = gen.next()
                if isinstance(x, defer.Deferred):
                    x.addCallback(callback, x).addErrback(errback, x)
                else:
                    result.callback(x)
            except StopIteration:
                result.callback(None)
            except Exception, e:
                result.errback(e)

        def errback(failure, d):

            def raise_error():
                # failure.parents[-1] will be the exception class for local
                # failures and the string name of the exception class
                # for remote failures (which might not exist in our
                # namespace)
                #
                # failure.value will be the tuple of arguments to the
                # exception in the local case, or a string
                # representation of that in the remote case (see
                # pb.CopyableFailure.getStateToCopy()).
                #
                # we can only reproduce a remote exception if the
                # exception class is in our namespace, and it only takes
                # one string argument. if either condition is not true,
                # we wrap the strings in a default Exception.
                k, v = failure.parents[-1], failure.value
                try:
                    if isinstance(k, str):
                        k = reflect.namedClass(k)
                    if isinstance(v, tuple):
                        e = k(*v)
                    else:
                        e = k(v)
                except Exception:
                    e = Exception('%s: %r' % (failure.type, v))
                raise e
            d.value = raise_error
            generator_next()

        def callback(result, d):
            d.value = lambda: result
            generator_next()

        generator_next()

        return result

    return wrapper


def defer_generator_method(proc):
    return lambda self, *args, **kwargs: \
        defer_generator(proc)(self, *args, **kwargs)


def defer_call_later(deferred):
    """
    Return a deferred which will fire from a callLater after d fires
    """

    def fire(result, d):
        reactor.callLater(0, d.callback, result)
    res = defer.Deferred()
    deferred.addCallback(fire, res)
    return res


class Resolution:
    """
    I am a helper class to make sure that the deferred is fired only once
    with either a result or exception.

    @ivar d: the deferred that gets fired as part of the resolution
    @type d: L{twisted.internet.defer.Deferred}
    """

    def __init__(self):
        self.d = defer.Deferred()
        self.fired = False

    def cleanup(self):
        """
        Clean up any resources related to the resolution.
        Subclasses can implement me.
        """
        pass

    def callback(self, result):
        """
        Make the result succeed, triggering the callbacks with
        the given result. If a result was already reached, do nothing.
        """
        if not self.fired:
            self.fired = True
            self.cleanup()
            self.d.callback(result)

    def errback(self, exception):
        """
        Make the result fail, triggering the errbacks with the given exception.
        If a result was already reached, do nothing.
        """
        if not self.fired:
            self.fired = True
            self.cleanup()
            self.d.errback(exception)


class RetryingDeferred(object):
    """
    Provides a mechanism to attempt to run some deferred operation until it
    succeeds. On failure, the operation is tried again later, exponentially
    backing off.
    """
    maxDelay = 1800 # Default to 30 minutes
    initialDelay = 5.0
    # Arbitrarily take these constants from twisted's ReconnectingClientFactory
    factor = 2.7182818284590451
    jitter = 0.11962656492
    delay = None

    def __init__(self, deferredCreate, *args, **kwargs):
        """
        Create a new RetryingDeferred. Will call
        deferredCreate(*args, **kwargs) each time a new deferred is needed.
        """
        self._create = deferredCreate
        self._args = args
        self._kwargs = kwargs

        self._masterD = None
        self._running = False
        self._callId = None

    def start(self):
        """
        Start trying. Returns a deferred that will fire when this operation
        eventually succeeds. That deferred will only errback if this
        RetryingDeferred is cancelled (it will then errback with the result of
        the next attempt if one is in progress, or a CancelledError.
        # TODO: yeah?
        """
        self._masterD = defer.Deferred()
        self._running = True
        self.delay = None

        self._retry()

        return self._masterD

    def cancel(self):
        if self._callId:
            self._callId.cancel()
            self._masterD.errback(errors.CancelledError())
            self._masterD = None

        self._callId = None
        self._running = False

    def _retry(self):
        self._callId = None
        d = self._create(*self._args, **self._kwargs)
        d.addCallbacks(self._success, self._failed)

    def _success(self, val):
        # TODO: what if we were cancelled and then get here?
        self._masterD.callback(val)
        self._masterD = None

    def _failed(self, failure):
        if self._running:
            next = self._nextDelay()
            self._callId = reactor.callLater(next, self._retry)
        else:
            self._masterD.errback(failure)
            self._masterD = None

    def _nextDelay(self):
        if self.delay is None:
            self.delay = self.initialDelay
        else:
            self.delay = self.delay * self.factor

        if self.jitter:
            self.delay = random.normalvariate(self.delay,
                self.delay * self.jitter)
        self.delay = min(self.delay, self.maxDelay)

        return self.delay
