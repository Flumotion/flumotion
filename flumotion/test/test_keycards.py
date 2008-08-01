# -*- Mode: Python; test-case-name: flumotion.test.test_keycards -*-
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

from flumotion.common import testsuite

from twisted.trial import unittest, util

from flumotion.twisted import credentials
from flumotion.twisted.defer import defer_generator_method
from flumotion.common import keycards


# test all the keycards


class TestKeycardUACPP(testsuite.TestCase):

    def testInit(self):
        keycard = keycards.KeycardUACPP('user', 'test', '127.0.0.1')
        self.assertEquals(keycard.state, keycards.REQUESTING)
        self.failUnless(credentials.IUsernameCryptPassword.providedBy(keycard))


class TestKeycardUACPCC(testsuite.TestCase):

    def testInit(self):
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')
        self.assertEquals(keycard.state, keycards.REQUESTING)
        self.failUnless(credentials.IUsernameCryptPassword.providedBy(keycard))


class TestKeycardToken(testsuite.TestCase):

    def testInit(self):
        keycard = keycards.KeycardToken('token', '127.0.0.1')
        self.assertEquals(keycard.state, keycards.REQUESTING)
        self.failUnless(credentials.IToken.providedBy(keycard))

        d = keycard.getData()
        self.assertEquals(d['token'], 'token')
        self.assertEquals(d['address'], '127.0.0.1')

        repr(keycard)


class TestKeycardHTTPDigest(testsuite.TestCase):

    def testInit(self):
        keycard = keycards.KeycardHTTPDigest('username')
        self.assertEquals(keycard.state, keycards.REQUESTING)

        d = keycard.getData()
        self.assertEquals(d['username'], 'username')

        repr(keycard)

# F0.8


class TestHTTPDigestKeycard(testsuite.TestCase):

    def testInit(self):
        keycard = keycards.HTTPDigestKeycard('username')
        self.assertEquals(keycard.state, keycards.REQUESTING)

    testInit.suppress = [util.suppress(
        message='Use KeycardHTTPDigest instead.', category=DeprecationWarning)]

# test the base class repr


class MyKeycard(keycards.Keycard):
    pass


class TestMyKeycard(testsuite.TestCase):

    def testInit(self):
        keycard = MyKeycard()
        self.assertEquals(keycard.state, keycards.REQUESTING)

        repr(keycard)


# test sending keycards back and forth


class Admin(testsuite.TestAdmin):
    pass


class Worker(testsuite.TestWorker):
    keycard = None

    def remote_getKeycard(self):
        if not self.keycard:
            keycard = keycards.KeycardUACPP('user', 'test', '127.0.0.1')
            #print "Worker keycard %r, id: %d" % (keycard, id(keycard))
            self.keycard = keycard

        return self.keycard

    def remote_giveKeycard(self, keycard):
        #print "Worker keycard %r, id: %d" % (keycard, id(keycard))
        pass


class Root(testsuite.TestManagerRoot):

    def remote_workerGetKeycard(self):
        d = self.workerReference.callRemote('getKeycard')
        d.addCallback(self._printKeycard)
        return d

    def remote_workerGiveKeycard(self, keycard):
        self._printKeycard(keycard)
        d = self.workerReference.callRemote('giveKeycard', keycard)
        return d

    def _printKeycard(self, keycard):
        #print "Manager keycard %r, id: %d" % (keycard, id(keycard))
        return keycard


class TestKeycardSending(testsuite.TestCase):

    def setUp(self):
        self.m = testsuite.TestManager()
        port = self.m.run(Root)
        self.a = Admin()
        d = self.a.run(port)
        yield d
        self.w = Worker()
        d = self.w.run(port)
        yield d
    setUp = defer_generator_method(setUp)

    def tearDown(self):
        d = self.m.stop()
        yield d
        d = self.a.stop()
        yield d
        d = self.w.stop()
        yield d
    tearDown = defer_generator_method(tearDown)

    def testSend(self):
        d = self.a.remoteRoot.callRemote('workerGetKeycard')

        def getKeycardCallback(keycard):
            # now send back the keycard to see what happens
            d2 = self.a.remoteRoot.callRemote('workerGiveKeycard', keycard)
            return d2
        d.addCallback(getKeycardCallback)
        return d

        # while writing this test, I came to the conclusion that since
        # this is a copyable, you really can't say much about the id's
        # of these objects as they get sent back and forth...

if __name__ == '__main__':
    unittest.main()
