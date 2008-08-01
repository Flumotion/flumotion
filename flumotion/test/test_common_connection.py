# -*- Mode: Python; test-case-name:flumotion.test.test_config -*-
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

from flumotion.common import connection
from flumotion.common import testsuite


class TestConnection(testsuite.TestCase):

    def assertParseEquals(self, _in, out, **kwargs):
        self.assertEquals(str(connection.parsePBConnectionInfo(
            _in, **kwargs)), out)

    def assertParseInvariant(self, string):
        self.assertParseEquals(string, string)

    def testParse(self):
        self.assertParseInvariant('foo@baz:1234')
        self.assertParseEquals('baz', 'user@baz:7531')
        self.assertParseEquals('baz', 'foo@baz:1234',
                               username='foo', port=1234)
        self.assertParseEquals('baz:1234', 'foo@baz:1234',
                               username='foo', password='bar')
        self.assertParseEquals('foo@baz:1234', 'foo@baz:1234',
                               password='bar')
