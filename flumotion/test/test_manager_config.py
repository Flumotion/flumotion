# -*- Mode: Python; test-case-name: flumotion.test.test_manager_config -*-
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

from cStringIO import StringIO

from flumotion.common import testsuite
from flumotion.common.errors import ConfigError
from flumotion.manager.config import ConfigEntryComponent, \
     ConfigEntryManager, ManagerConfigParser, PlanetConfigParser


def flatten(seq):
    rv = []
    for item in seq:
        rv.extend(item)
    return rv


class TestManagerConfigParser(testsuite.TestCase):

    def _buildManager(self, child, extra=''):
        xml = '<planet><manager%s>%s</manager></planet>' % (extra, child)
        return StringIO(xml)

    def testParseEmpty(self):
        f = StringIO("")
        self.assertRaises(ConfigError, ManagerConfigParser, f)

    def testParseSimple(self):
        f = StringIO("<planet/>")
        parser = ManagerConfigParser(f)
        self.failIf(parser.manager)

    def testParseManager(self):
        f = self._buildManager("""<host>mhost</host>
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
        f = self._buildManager('<transport>foo</transport>')
        self.assertRaises(ConfigError, ManagerConfigParser, f)
        f = self._buildManager('<xxx/>')
        self.assertRaises(ConfigError, ManagerConfigParser, f)
        f = self._buildManager('<host>xxx</host><host>xxx</host>')
        self.assertRaises(ConfigError, ManagerConfigParser, f)
        f = self._buildManager('<host><xxx/></host>')
        self.assertRaises(ConfigError, ManagerConfigParser, f)

    def testParseBouncerComponent(self):
        f = self._buildManager("""<component name="foobar" type="bouncer"/>""")
        config = ManagerConfigParser(f)
        self.failIf(config.bouncer)
        config.parseBouncerAndPlugs()
        self.failUnless(config.bouncer)
        self.failUnless(isinstance(config.bouncer, ConfigEntryComponent))
        self.assertEquals(config.bouncer.type, 'bouncer')
        self.assertEquals(config.bouncer.name, 'foobar')

    def testParsePlugs(self):
        f = self._buildManager(
            """<plugs>
  <plug socket="flumotion.component.plugs.adminaction.AdminAction"
          type="adminactionfilelogger">
    <property name="logfile">/dev/stdout</property>
  </plug>
</plugs>""")
        config = ManagerConfigParser(f)
        self.failIf(flatten(config.plugs.values()))
        config.parseBouncerAndPlugs()
        values = flatten(config.plugs.values())
        self.failUnless(values)
        first = values[0]
        self.failUnless(isinstance(first, dict))
        self.failUnless('type' in first)
        self.assertEquals(first['type'], 'adminactionfilelogger')
        self.failUnless('properties' in first)
        properties = first['properties']
        self.failUnless('logfile' in properties)
        self.assertEquals(properties['logfile'], '/dev/stdout')


class TestPlanetConfigParser(testsuite.TestCase):

    def _buildPlanet(self, child, extra=''):
        xml = '<planet%s>%s</planet>' % (extra, child)
        return StringIO(xml)

    def _buildAtmosphere(self, child, extra=''):
        return self._buildPlanet('<atmosphere%s>%s</atmosphere>' % (
            extra, child))

    def _buildFlow(self, child, name='flow'):
        return self._buildPlanet('<flow name="%s">%s</flow>' % (
            name, child))

    def testParseInvalid(self):
        f = StringIO("<xxx/>")
        config = PlanetConfigParser(f)
        self.assertRaises(ConfigError, config.parse)

    def testParseSimple(self):
        f = self._buildPlanet('')
        config = PlanetConfigParser(f)
        config.parse()
        self.failIf(config.flows)
        self.failIf(config.path)
        self.failIf(config.atmosphere.components)

    def testParseAtmosphereEmpty(self):
        f = self._buildAtmosphere('')
        config = PlanetConfigParser(f)
        config.parse()
        self.failIf(config.atmosphere.components)

    def testParseAtmosphereWithComponent(self):
        f = self._buildAtmosphere(
            '<component name="cname" type="http-server" worker="worker"/>')
        config = PlanetConfigParser(f)
        config.parse()
        components = config.atmosphere.components
        self.failUnless(components)
        self.failUnless('cname' in components)
        component = components.pop('cname')
        self.failUnless(component)
        self.failUnless(isinstance(component, ConfigEntryComponent))
        self.assertEquals(component.worker, 'worker')
        self.assertEquals(component.type, 'http-server')
        self.assertEquals(component.config['avatarId'], '/atmosphere/cname')
        self.failIf(flatten(component.config['plugs'].values()))

    def testParseAtmosphereInvalid(self):
        f = self._buildAtmosphere(
            '<component name="cname" type="http-server" worker="worker">'
            '  <clock-master>true</clock-master>'
            '</component>')
        config = PlanetConfigParser(f)
        self.assertRaises(ConfigError, config.parse)

    def testParseFlow(self):
        f = self._buildFlow(
            '<component name="audio" type="audiotest-producer" '
            'worker="worker">'
            '  <clock-master>true</clock-master>'
            '</component>'
            '<component name="video" type="videotest-producer" '
            'worker="worker">'
            '</component>')
        config = PlanetConfigParser(f)
        config.parse()
        self.failUnless(config.flows)
        self.assertEquals(len(config.flows), 1)
        components = config.flows[0].components
        self.failUnless(components)
        self.failUnless('video' in components)
        component = components.pop('audio')
        self.assertEquals(component.type, 'audiotest-producer')
        self.assertEquals(component.config['clock-master'], '/flow/audio')
        component = components.pop('video')
        self.assertEquals(component.type, 'videotest-producer')
        self.assertEquals(component.config['clock-master'], '/flow/audio')
        self.failIf(components)

    def testParseFlowInvalid(self):
        # missing name
        f = self._buildPlanet('<flow/>')
        config = PlanetConfigParser(f)
        self.assertRaises(ConfigError, config.parse)

        # invalid name
        for name in ['atmosphere', 'manager']:
            f = self._buildFlow('', name=name)
            config = PlanetConfigParser(f)
            self.assertRaises(ConfigError, config.parse)

        # multiple clock master
        f = self._buildFlow(
            '<component name="one" type="http-server" worker="worker">'
            '  <clock-master>true</clock-master>'
            '</component>'
            '<component name="two" type="http-server" worker="worker">'
            '  <clock-master>true</clock-master>'
            '</component>')
        config = PlanetConfigParser(f)
        self.assertRaises(ConfigError, config.parse)
