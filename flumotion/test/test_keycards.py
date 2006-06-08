# -*- Mode: Python; test-case-name: flumotion.test.test_keycards -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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

import common
import testclasses

from twisted.trial import unittest

from flumotion.twisted import credentials
from flumotion.twisted import compat
from flumotion.twisted.defer import defer_generator_method
from flumotion.common import keycards
import twisted.copyright #T1.3
#T1.3
def weHaveAnOldTwisted():
    return twisted.copyright.version[0] < '2'

class TestKeycardUACPP(unittest.TestCase):
    def testInit(self):
        keycard = keycards.KeycardUACPP('user', 'test', '127.0.0.1')
        self.assertEquals(keycard.state, keycards.REQUESTING)
        self.failUnless(compat.implementsInterface(
            keycard, credentials.IUsernameCryptPassword))

class TestKeycardUACPCC(unittest.TestCase):
    def testInit(self):
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')
        self.assertEquals(keycard.state, keycards.REQUESTING)
        self.failUnless(compat.implementsInterface(
            keycard, credentials.IUsernameCryptPassword))
        
# test sending keycards back and forth
class Admin(testclasses.TestAdmin):
    pass
class Worker(testclasses.TestWorker):
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
     
class Root(testclasses.TestManagerRoot):
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

class TestKeycardSending(unittest.TestCase):
    def setUp(self):
        self.m = testclasses.TestManager()
        port = self.m.run(Root)
        self.a = Admin()
        d = self.a.run(port)
        if weHaveAnOldTwisted():
            unittest.deferredResult(d)
        else:
            yield d
        self.w = Worker()
        d = self.w.run(port)
        if weHaveAnOldTwisted():
            unittest.deferredResult(d)
        else:
            yield d
    setUp = defer_generator_method(setUp)

    def tearDown(self):
        d = self.m.stop()
        if weHaveAnOldTwisted():
            unittest.deferredResult(d)
        else:
            yield d
        d = self.a.stop()
        if weHaveAnOldTwisted():
            unittest.deferredResult(d)
        else:
            yield d
        d = self.w.stop()
        if weHaveAnOldTwisted():
            unittest.deferredResult(d)
        else:
            yield d
    tearDown = defer_generator_method(tearDown)

    def testSend(self):
        d = self.a.perspective.callRemote('workerGetKeycard')
        def getKeycardCallback(keycard):
            # now send back the keycard to see what happens
            d2 = self.a.perspective.callRemote('workerGiveKeycard', keycard)
            return d2
        d.addCallback(getKeycardCallback)
        if weHaveAnOldTwisted():
            result = unittest.deferredResult(d)
        else:
            return d
        
        # while writing this test, I came to the conclusion that since
        # this is a copyable, you really can't say much about the id's
        # of these objects as they get sent back and forth...

if __name__ == '__main__':
     unittest.main()
