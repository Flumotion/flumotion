# -*- Mode: Python; test-case-name:flumotion.test.test_config -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

from StringIO import StringIO

from flumotion.common import errors
from flumotion.common import testsuite
from flumotion.admin import config


def AdminConfig(sockets, string):
    f = StringIO(string)
    conf = config.AdminConfigParser(sockets, f)
    f.close()
    return conf


class AdminConfigTest(testsuite.TestCase):

    def testMinimal(self):
        doc = ('<admin>'
               '<plugs>'
               '</plugs>'
               '</admin>')
        parser = AdminConfig((), doc)
        self.failUnless(parser.plugs == {}, 'expected empty plugset')

    def testMinimal2(self):
        doc = ('<admin>'
               '<plugs>'
               '</plugs>'
               '</admin>')
        parser = AdminConfig((), doc)
        self.failUnless(parser.plugs == {}, 'expected empty plugset')

    def testMinimal3(self):
        doc = ('<admin>'
               '<plugs>'
               '</plugs>'
               '</admin>')
        parser = AdminConfig(('foo.bar', ), doc)
        self.failUnless(parser.plugs == {
            'foo.bar': []},
                        parser.plugs)

    def testUnknownPlug(self):
        doc = ('<admin>'
               '<plugs>'
               '<plug type="plugdoesnotexist">'
               '</plug>'
               '</plugs>'
               '</admin>')
        self.assertRaises(errors.UnknownPlugError,
                          lambda: AdminConfig(('foo.bar', ), doc))

    def testUnknownSocket(self):
        doc = ('<admin>'
               '<plugs>'
               '<plug type="frobulator">'
               '</plug>'
               '</plugs>'
               '</admin>')
        self.assertRaises(errors.ConfigError,
                          lambda: AdminConfig(('foo.bar', ), doc))
