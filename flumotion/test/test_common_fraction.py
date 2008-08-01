# -*- Mode: Python; test-case-name: flumotion.test.test_common_componentui -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2008 Fluendo, S.L. (www.fluendo.com).
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

from flumotion.common.testsuite import TestCase
from flumotion.common.fraction import fractionFromValue, fractionAsFloat, \
     fractionAsString


class TestFraction(TestCase):

    def testFractionFromValue(self):
        self.assertEquals(fractionFromValue('1'), (1, 1))
        self.assertEquals(fractionFromValue('1/1'), (1, 1))
        self.assertEquals(fractionFromValue('2/1'), (2, 1))
        self.assertEquals(fractionFromValue('3/4'), (3, 4))
        #self.assertEquals(fractionFromValue('0.5'), (1, 2))

        self.assertEquals(fractionFromValue('10'), (10, 1))
        self.assertEquals(fractionFromValue(u'10'), (10, 1))
        self.assertEquals(fractionFromValue(10), (10, 1))
        self.assertEquals(fractionFromValue(10L), (10, 1))
        self.assertEquals(fractionFromValue(10.0), (10, 1))
        self.assertRaises(ValueError, fractionFromValue, '1/2/3')
        self.assertRaises(ValueError, fractionFromValue, '/')
        self.assertRaises(ValueError, fractionFromValue, '1/')
        self.assertRaises(ValueError, fractionFromValue, '/')
        self.assertRaises(ValueError, fractionFromValue, 'a/1')
        self.assertRaises(ValueError, fractionFromValue, None)

    def testFractionAsString(self):
        self.assertEquals(fractionAsString((10, 10)), '10/10')
        self.assertEquals(fractionAsString((4, 3)), '4/3')

    def testFractionAsFloat(self):
        self.assertEquals(fractionAsFloat((10, 10)), 1)
        self.assertEquals(fractionAsFloat((4, 5)), 0.8)
