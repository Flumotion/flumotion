# -*- Mode: Python; test-case-name: flumotion.test.test_common -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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
from flumotion.common import format as formatting


class TestFormatStorage(TestCase):

    def testBytes(self):
        value = 4
        self.assertEquals(formatting.formatStorage(value), "4.00 ")

    def testKibibyte(self):
        value = 1024
        self.assertEquals(formatting.formatStorage(value), "1.02 k")
        self.assertEquals(formatting.formatStorage(value, 3), "1.024 k")

    def testMegabyte(self):
        value = 1000 * 1000
        self.assertEquals(formatting.formatStorage(value), "1.00 M")

    def testMebibyte(self):
        value = 1024 * 1024
        self.assertEquals(formatting.formatStorage(value), "1.05 M")
        self.assertEquals(formatting.formatStorage(value, 3), "1.049 M")
        self.assertEquals(formatting.formatStorage(value, 4), "1.0486 M")

    def testGibibyte(self):
        value = 1024 * 1024 * 1024
        self.assertEquals(formatting.formatStorage(value, 4), "1.0737 G")

    def testTebibyte(self):
        value = 1024 * 1024 * 1024 * 1024
        self.assertEquals(formatting.formatStorage(value, 4), "1.0995 T")

    def testPebibyte(self):
        value = 1024 * 1024 * 1024 * 1024 * 1024
        self.assertEquals(formatting.formatStorage(value, 4), "1.1259 P")

    def testExbibyte(self):
        value = 1024 * 1024 * 1024 * 1024 * 1024 * 1024
        self.assertEquals(formatting.formatStorage(value, 4), "1.1529 E")


class TestFormatTime(TestCase):

    def testFractionalSecond(self):
        value = 1.1
        self.assertEquals(formatting.formatTime(value, fractional=2),
            "00:00:01.10")

    def testSecond(self):
        value = 1
        self.assertEquals(formatting.formatTime(value), "00:00")

    def testMinuteSecond(self):
        value = 60 + 1
        self.assertEquals(formatting.formatTime(value), "00:01")

    def testHourMinuteSecond(self):
        value = 60 * 60 + 60 + 2
        self.assertEquals(formatting.formatTime(value), "01:01")

    def testDay(self):
        value = 60 * 60 * 24
        self.assertEquals(formatting.formatTime(value), "1 day 00:00")

    def testDays(self):
        value = 60 * 60 * 24 * 2
        self.assertEquals(formatting.formatTime(value), "2 days 00:00")

    def testWeek(self):
        value = 60 * 60 * 24 * 7
        self.assertEquals(formatting.formatTime(value), "1 week 00:00")

    def testWeeks(self):
        value = 60 * 60 * 24 * 7 * 2
        self.assertEquals(formatting.formatTime(value), "2 weeks 00:00")

    def testYear(self):
        value = 60 * 60 * 24 * 365
        self.assertEquals(formatting.formatTime(value), "52 weeks 1 day 00:00")

    def testReallyLong(self):
        minute = 60
        hour = minute * 60
        day = hour * 24
        week = day * 7

        value = week * 291 + day * 5 + hour * 13 + minute * 5
        self.assertEquals(formatting.formatTime(value),
            "291 weeks 5 days 13:05")

    def testNegative(self):
        self.assertEquals(formatting.formatTime(-1.0, fractional=1),
            "- 00:00:01.0")
