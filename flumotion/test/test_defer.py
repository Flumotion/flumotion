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

from twisted.internet import defer, reactor

from flumotion.common import errors
from flumotion.common import testsuite
from flumotion.twisted.defer import defer_generator, RetryingDeferred


class TestDefer(testsuite.TestCase):
    result = None
    error = None

    def testYieldResultAtFirst(self):
        self.result = None

        def gen():
            yield 42
        gen = defer_generator(gen)

        d = gen()
        d.addCallback(lambda x: setattr(self, 'result', x))
        assert self.result == 42

    def testYieldResultAfter(self):
        self.result = None

        def square_later(x):
            d = defer.Deferred()
            reactor.callLater(0.1, lambda: d.callback(x*x))
            return d

        def gen():
            yield square_later(0)
            yield 42
        gen = defer_generator(gen)

        d = gen()
        d.addCallback(lambda x: setattr(self, 'result', x))

        def checkResult(res):
            assert self.result == 42
        d.addCallback(checkResult)
        return d

    def testYieldNothing(self):
        self.result = 42

        def square_later(x):
            d = defer.Deferred()
            reactor.callLater(0.1, lambda: d.callback(x*x))
            return d

        def gen():
            yield square_later(0)
        gen = defer_generator(gen)

        d = gen()
        d.addCallback(lambda x: setattr(self, 'result', x))

        def checkResult(res):
            assert self.result == None
        d.addCallback(checkResult)
        return d

    def testValues(self):
        self.result = None

        def square_later(x):
            d = defer.Deferred()
            reactor.callLater(0.1, lambda: d.callback(x*x))
            return d

        def gen():
            for i in range(10):
                d = square_later(i)
                yield d

                # .value() gets the result of the deferred
                assert d.value() == i*i

            yield d.value()
        gen = defer_generator(gen)

        d = gen()
        d.addCallback(lambda x: setattr(self, 'result', x))

        def checkResult(res):
            assert self.result == 81
        d.addCallback(checkResult)
        return d

    def testBarfOnNongenerator(self):

        def nongen():
            pass
        try:
            nongen = defer_generator(nongen)
            assert 'not reached'
        except Exception:
            pass

    def testException(self):
        self.result = None

        def divide_later(x, y):
            d = defer.Deferred()

            def divide():
                try:
                    d.callback(x/y)
                except ZeroDivisionError, e:
                    d.errback(e)
            reactor.callLater(0.1, divide)
            return d

        def gen():
            d = divide_later(42, 0)
            yield d

            # .value() gets the result of the deferred and raises
            # if there was an errback
            try:
                assert d.value() == 42
            except ZeroDivisionError:
                d = divide_later(42, 1)
                yield d

                assert d.value() == 42
                yield True
        gen = defer_generator(gen)

        d = gen()
        d.addCallback(lambda x: setattr(self, 'result', x))

        def checkResult(res):
            assert self.result == True
        d.addCallback(checkResult)
        return d

    def testExceptionChain(self):

        def divide_later(x, y):
            d = defer.Deferred()

            def divide():
                try:
                    d.callback(x/y)
                except ZeroDivisionError, e:
                    d.errback(e)
            reactor.callLater(0.1, divide)
            return d

        def gen():
            d = divide_later(42, 0)
            yield d
            yield d.value()
        gen = defer_generator(gen)

        exception_chain = []

        def oserrorback(failure):
            exception_chain.append('oserror')
            failure.trap(OSError)

        def zerodivisionerrorback(failure):
            exception_chain.append('zerodivisionerror')
            failure.trap(ZeroDivisionError)

        def runtimeerrorback(failure):
            exception_chain.append('runtimeerror')
            failure.trap(RuntimeError)

        def checkexceptionchain(value):
            self.result = exception_chain

        self.result = False
        d = gen()
        d.addErrback(oserrorback)
        d.addErrback(zerodivisionerrorback)
        d.addErrback(runtimeerrorback)
        d.addCallback(checkexceptionchain)

        def checkResult(res):
            assert self.result == ['oserror', 'zerodivisionerror'],\
                   "Unexpected exception chain: %r" % (self.result, )
        d.addCallback(checkResult)
        return d


class TestRetryingDeferred(testsuite.TestCase):

    def testSimple(self):

        def genDef():
            return defer.succeed(True)

        rd = RetryingDeferred(genDef)
        d = rd.start()

        return d

    def testRetryOnce(self):
        self.__first = True

        def genDef():
            if self.__first:
                self.__first = False
                return defer.fail(errors.FlumotionError())
            else:
                return defer.succeed(None)

        rd = RetryingDeferred(genDef)
        rd.initialDelay = 0.1 # Set it short so the test isn't long-running.
        d = rd.start()

        return d
