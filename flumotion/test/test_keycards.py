# -*- Mode: Python; test-case-name: flumotion.test.test_keycards -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_keycards.py:
# regression test for flumotion.common.keycards
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

import common
from twisted.trial import unittest

from twisted.python import components

from flumotion.twisted import credentials
from flumotion.common import keycards

class TestKeycardUACPP(unittest.TestCase):
    def testInit(self):
        keycard = keycards.KeycardUACPP('user', 'test', '127.0.0.1')
        self.assertEquals(keycard.state, keycards.REQUESTING)
        self.assert_(components.implements(keycard, credentials.IUsernameCryptPassword))

class TestKeycardUACPCC(unittest.TestCase):
    def testInit(self):
        keycard = keycards.KeycardUACPCC('user', '127.0.0.1')
        self.assertEquals(keycard.state, keycards.REQUESTING)
        self.assert_(components.implements(keycard, credentials.IUsernameCryptPassword))
        
if __name__ == '__main__':
     unittest.main()
