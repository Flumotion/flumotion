# -*- Mode: Python; test-case-name: flumotion.test.test_reflect -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_reflect.py: unittest for reflect enhancements
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

from flumotion.twisted import reflect

class TestSimple(unittest.TestCase):
    def testSimple(self):
        s = reflect.namedAny('flumotion.test.test_reflect.TestSimple')
        self.failUnlessIdentical(s, TestSimple)

    # XXX: Write a test for the exception, but how?
