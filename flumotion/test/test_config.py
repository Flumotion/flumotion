# -*- Mode: Python; test-case-name:flumotion.test.test_config -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_config.py: regression test for flumotion.config.config
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from flumotion.common import config, registry, errors

registry.registry.addFromString("""
<registry>
  <components>
    <component name="foobie" type="test-component">
      <properties>
        <property name="one" type="string"/>
        <property name="two" type="int"/>
        <property name="three" type="float"/>
        <property name="four" type="xml"/>
        <property name="five" type="bool"/>
        <property name="six" type="long"/>
      </properties>
    </component>
  </components>
</registry>""")

class TestConfig(unittest.TestCase):
    def testParseEmpty(self):
        conf = config.FlumotionConfigXML(None, '<planet/>')

    def testParseAtmosphere(self):
        conf = config.FlumotionConfigXML(None,
             """
             <planet>
               <atmosphere>
                 <component name="component-name" type="test-component"/>
               </atmosphere>
             </planet>""")
        assert conf.atmosphere
        assert conf.atmosphere.components
        assert len(conf.atmosphere.components) == 1
        assert conf.atmosphere.components['component-name']
        assert conf.atmosphere.components['component-name'].name == "component-name"

    def testParseComponent(self):
        conf = config.FlumotionConfigXML(None,
             """
             <planet>
               <flow>
                 <component name="component-name" type="test-component"/>
               </flow>
             </planet>
             """)

        flow = conf.flows[0]
        assert flow.components.has_key('component-name')
        component = flow.components['component-name']
        assert component.name == 'component-name'
        assert component.type == 'test-component'
        dict = component.getConfigDict()
        assert dict.get('name') == 'component-name', dict['name']
        assert dict.get('type') == 'test-component', dict['type']
        
    def testParseManager(self):
        conf = config.FlumotionConfigXML(None,
             """
             <planet>
               <manager>
                 <component name="component-name" type="test-component"/>
               </manager>
             </planet>""")
        assert conf.manager
        assert conf.manager.bouncer
        assert conf.manager.bouncer.name
        assert conf.manager.bouncer.name == "component-name"

    def obsolete_testParseWorkers(self):
        conf = config.FlumotionConfigXML(None,
             """<planet>
             <workers policy="password">
               <worker username="root" password="god"/>
             </workers>
             </planet>""")

        workers = conf.getWorkers()
        assert workers.getPolicy() == 'password'
        assert len(workers) == 1
        worker = iter(workers).next()
        assert worker.getUsername() == 'root'
        assert worker.getPassword() == 'god'
        assert conf.hasWorker('root')
        
    def testParseError(self):
        xml = '<planet><bad-node/></planet>'
        self.assertRaises(config.ConfigError,
                          config.FlumotionConfigXML, None, xml)

    def testParseComponentError(self):
        xml = """<planet>
            <flow><component name="unused" type="not-existing"/></flow>
            </planet>"""
        self.assertRaises(errors.UnknownComponentError,
            config.FlumotionConfigXML, None, xml)

        xml = '<planet><component/></planet>'
        self.assertRaises(config.ConfigError,
                          config.FlumotionConfigXML, None, xml)

        xml = '<planet><component name="without-type"/></planet>'
        self.assertRaises(config.ConfigError,
                          config.FlumotionConfigXML, None, xml)

    def testParseManagerError(self):
        xml = """<planet><manager>
            <component name="first" type="test-component"></component>
            <component name="second" type="test-component"></component>
            </manager></planet>"""
        self.assertRaises(config.ConfigError,
                          config.FlumotionConfigXML, None, xml)
 
    def obsolete_testParseWorkersError(self):
        xml = '<planet><workers/></planet>'
        self.assertRaises(config.ConfigError,
                          config.FlumotionConfigXML, None, xml)

        xml = '<planet><workers policy="unknown-policy"/></planet>'
        self.assertRaises(config.ConfigError,
                          config.FlumotionConfigXML, None, xml)

        xml = '<planet><workers><worker/></workers></planet>'
        self.assertRaises(config.ConfigError,
                          config.FlumotionConfigXML, None, xml)

        xml = '<planet><workers><worker username="without-password"/></workers></planet>'
        self.assertRaises(config.ConfigError,
                          config.FlumotionConfigXML, None, xml)

    def testParseProperties(self):
        planet = config.FlumotionConfigXML(None,
             """<planet><flow>
             <component name="component-name" type="test-component">
               <one>string</one>
               <two>1</two>
               <three>2.5</three>
               <four attr="attr-value">value</four>
               <five>True</five>
               <six>3981391981389138998131389L</six>
             </component></flow>
             </planet>""")
        flow = planet.flows[0]
        component = flow.components['component-name']
        conf = component.getConfigDict()
        assert conf.get('one') == 'string'
        assert conf.get('two') == 1
        assert conf.get('three') == 2.5
        custom = conf.get('four')
        assert custom
        assert getattr(custom, 'data', None) == 'value'
        assert getattr(custom, 'attr', None) == 'attr-value'
        assert conf.get('five') == True
        assert conf.get('six') == 3981391981389138998131389L
