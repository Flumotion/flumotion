# -*- Mode: Python; test-case-name: flumotion.test.test_common -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_common.py: regression test for flumotion.common.common
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

from twisted.trial import unittest

from flumotion.common import common

class TestFormatStorage(unittest.TestCase):
    def testBytes(self):
        value = 4
        assert common.formatStorage(value) == "4.00 "

    def testKibibyte(self):
        value = 1024
        assert common.formatStorage(value) == "1.02 k"
        assert common.formatStorage(value, 3) == "1.024 k"

    def testMegabyte(self):
        value = 1000 * 1000
        assert common.formatStorage(value) == "1.00 M"

    def testMebibyte(self):
        value = 1024 * 1024
        assert common.formatStorage(value) == "1.05 M"
        assert common.formatStorage(value, 3) == "1.049 M"
        assert common.formatStorage(value, 4) == "1.0486 M"

    def testGibibyte(self):
        value = 1024 * 1024 * 1024
        assert common.formatStorage(value, 4) == "1.0737 G"
    
    def testTebibyte(self):
        value = 1024 * 1024 * 1024 * 1024
        assert common.formatStorage(value, 4) == "1.0995 T"
    
    def testPebibyte(self):
        value = 1024 * 1024 * 1024 * 1024 * 1024
        assert common.formatStorage(value, 4) == "1.1259 P"
    
    def testExbibyte(self):
        value = 1024 * 1024 * 1024 * 1024 * 1024 * 1024
        assert common.formatStorage(value, 4) == "1.1529 E"

class TestFormatTime(unittest.TestCase):
    def testSecond(self):
        value = 1
        assert common.formatTime(value) == "00:00"

    def testMinuteSecond(self):
        value = 60 + 1
        assert common.formatTime(value) == "00:01"

    def testHourMinuteSecond(self):
        value = 60 * 60 + 60 + 2
        assert common.formatTime(value) == "01:01"

    def testDay(self):
        value = 60 * 60 * 24
        assert common.formatTime(value) == "1 day 00:00"

    def testDays(self):
        value = 60 * 60 * 24 * 2
        assert common.formatTime(value) == "2 days 00:00"
    
    def testWeek(self):
        value = 60 * 60 * 24 * 7
        assert common.formatTime(value) == "1 week 00:00"
    
    def testWeeks(self):
        value = 60 * 60 * 24 * 7 * 2
        assert common.formatTime(value) == "2 weeks 00:00"
    
    def testYear(self):
        value = 60 * 60 * 24 * 365
        assert common.formatTime(value) == "52 weeks 1 day 00:00"
    
    def testReallyLong(self):
        minute = 60
        hour = minute * 60
        day = hour * 24
        week = day * 7
        
        value = week * 291 + day * 5 + hour * 13 + minute * 5
        assert common.formatTime(value) == "291 weeks 5 days 13:05"

class I1: pass
class I2: pass

class A:
    __implements__ = (I1, )

class B:
    __implements__ = (I2, )
    
class C: pass
class TestMergeImplements(unittest.TestCase):
    def testTwoImplements(self):
        self.assertEquals(common.mergeImplements(A, B), (I1, I2))
        
    def testFirstWithout(self):
        self.assertEquals(common.mergeImplements(B, C), (I2, ))

    def testSecondWithout(self):
        self.assertEquals(common.mergeImplements(A, C), (I1, ))

    def testBothWithout(self):
        self.assertEquals(common.mergeImplements(C, C), ( ))
     
class TestVersion(unittest.TestCase):
    def testVersion(self):
        self.assert_(common.version('abinary'))
if __name__ == '__main__':
    unittest.main()
