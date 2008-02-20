# -*- Mode: Python; test-case-name: flumotion.test.test_manager_config -*-
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

from cStringIO import StringIO

from flumotion.common import testsuite
from flumotion.common.errors import ConfigError
from flumotion.manager.config import ManagerConfigParser, ConfigEntryManager, \
     ConfigEntryComponent

__version__ = "$Rev$"

def flatten(seq):
    rv = []
    for item in seq:
        rv.extend(item)
    return rv

def build(child, extra=''):
    return StringIO('<planet><manager%s>%s</manager></planet>' % (
        extra, child))


class TestConfigParser(testsuite.TestCase):
    def testParseEmpty(self):
        f = StringIO("")
        self.assertRaises(ConfigError, ManagerConfigParser, f)

    def testParseSimple(self):
        f = StringIO("<planet/>")
        parser = ManagerConfigParser(f)
        self.failIf(parser.manager)

    def testParseManager(self):
        f = build("""<host>mhost</host>
                     <port>999</port>
                     <transport>tcp</transport>
                     <certificate>manager.cert</certificate>
                     <debug>true</debug>""",
                  extra=' name="mname"')
        parser = ManagerConfigParser(f)
        self.failUnless(parser.manager)
        manager = parser.manager
        self.failUnless(isinstance(manager, ConfigEntryManager))
        self.assertEquals(manager.name, 'mname')
        self.assertEquals(manager.host, 'mhost')
        self.assertEquals(manager.port, 999)
        self.assertEquals(manager.transport, 'tcp')
        self.assertEquals(manager.certificate, 'manager.cert')
        self.assertEquals(manager.fludebug, 'true')

    def testParseManagerInvalid(self):
        f = build('<transport>foo</transport>')
        self.assertRaises(ConfigError, ManagerConfigParser, f)
        f = build('<xxx/>')
        self.assertRaises(ConfigError, ManagerConfigParser, f)
        f = build('<host>xxx</host><host>xxx</host>')
        self.assertRaises(ConfigError, ManagerConfigParser, f)
        f = build('<host><xxx/></host>')
        self.assertRaises(ConfigError, ManagerConfigParser, f)

    def testParseBouncerComponent(self):
        f = build("""<component name="foobar" type="bouncer"/>""")
        parser = ManagerConfigParser(f)
        self.failIf(parser.bouncer)
        parser.parseBouncerAndPlugs()
        self.failUnless(parser.bouncer)
        self.failUnless(isinstance(parser.bouncer, ConfigEntryComponent))
        self.assertEquals(parser.bouncer.type, 'bouncer')
        self.assertEquals(parser.bouncer.name, 'foobar')

    def testParsePlugs(self):
        f = build("""<plugs>
                       <plug socket="flumotion.component.plugs.adminaction.AdminAction"
                             type="adminactionfilelogger">
                         <property name="logfile">/dev/stdout</property>
                       </plug>
                     </plugs>""")
        parser = ManagerConfigParser(f)
        self.failIf(flatten(parser.plugs.values()))
        parser.parseBouncerAndPlugs()
        values = flatten(parser.plugs.values())
        self.failUnless(values)
        first = values[0]
        self.failUnless(isinstance(first, dict))
        self.failUnless('type' in first)
        self.assertEquals(first['type'], 'adminactionfilelogger')
        self.failUnless('properties' in first)
        properties = first['properties']
        self.failUnless('logfile' in properties)
        self.assertEquals(properties['logfile'], '/dev/stdout')
