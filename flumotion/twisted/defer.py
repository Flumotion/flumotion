# -*- Mode: Python; test-case-name: flumotion.test.test_defer -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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


# appease pychecker's desire for instance methods
class _Foo:
    def bar(self):
        pass

_instancemethod = type(_Foo.bar)
def _makemethod(proc, obj):
    return _instancemethod(proc, obj, defer.Deferred)

# See flumotion.test.test_defer for examples
def defer_generator(proc):
    def wrapper(*args, **kwargs):
        gen = proc(*args, **kwargs)
        result = defer.Deferred()

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
                raise failure.type(failure.value)
            d.value = _makemethod(lambda self: raise_error(), d)
            generator_next()

        def callback(result, d):
            d.value = _makemethod(lambda self: result, d)
            generator_next()

        generator_next()

        return result

    return wrapper

def defer_generator_method(proc):
    return lambda self, *args, **kwargs: \
        defer_generator(proc)(self, *args, **kwargs)
