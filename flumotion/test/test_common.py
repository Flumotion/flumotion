# -*- Mode: Python; test-case-name: flumotion.test.test_common -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

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
    
if __name__ == '__main__':
    unittest.main()
