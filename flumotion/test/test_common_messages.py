# -*- Mode: Python; test-case-name: flumotion.test.test_common_messages -*-
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

from twisted.trial import unittest
from twisted.spread import jelly
from twisted.internet import reactor

import common

from flumotion.common import messages

class SerializeTest(unittest.TestCase):
    def testSerialize(self):
        text = "Something is really wrong."
        self.cmsg = messages.Error(text)
        self.mmsg = jelly.unjelly(jelly.jelly(self.cmsg))
        self.assertEquals(self.mmsg.text, text)
        self.assertEquals(self.mmsg.level, messages.ERROR)
        self.amsg = jelly.unjelly(jelly.jelly(self.mmsg))
        self.assertEquals(self.amsg.text, text)
        self.assertEquals(self.amsg.level, messages.ERROR)

    def testCreate(self):
        self.failUnless(messages.Info("info"))
        self.failUnless(messages.Warning("warning"))

if __name__ == '__main__':
    unittest.main()
