# -*- Mode: Python; test-case-name:flumotion.test.test_config -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_config.py: regression test for flumotion.config.config
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

from flumotion.common import config, registry

registry.registry.addFromString("""<components>
<component name="foobie" type="test-component">
  <properties>
    <property name="one" type="string"/>
    <property name="two" type="int"/>
    <property name="three" type="float"/>
    <property name="four" type="xml"/>
    <property name="five" type="bool"/>
  </properties>
</component>
</components>""")

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
               <grid>
                 <component name="component-name" type="test-component"/>
               </grid>
             </planet>
             """)

        grid = conf.grids[0]
        assert grid.components.has_key('component-name')
        component = grid.components['component-name']
        assert component.name == 'component-name'
        assert component.type == 'test-component'
        dict = component.getConfigDict()
        assert dict.get('name') == 'component-name', dict['name']
        assert dict.get('type') == 'test-component', dict['type']
        assert component.startFactory()
        
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
            <grid><component name="unused" type="not-existing"/></grid>
            </planet>"""
        self.assertRaises(KeyError, config.FlumotionConfigXML, None, xml)

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
             """<planet><grid>
             <component name="component-name" type="test-component">
               <one>string</one>
               <two>1</two>
               <three>2.5</three>
               <four attr="attr-value">value</four>
               <five>True</five>
             </component></grid>
             </planet>""")
        grid = planet.grids[0]
        component = grid.components['component-name']
        conf = component.getConfigDict()
        assert conf.get('one') == 'string'
        assert conf.get('two') == 1
        assert conf.get('three') == 2.5
        custom = conf.get('four')
        assert custom
        assert getattr(custom, 'data', None) == 'value'
        assert getattr(custom, 'attr', None) == 'attr-value'
        assert conf.get('five') == True
        
