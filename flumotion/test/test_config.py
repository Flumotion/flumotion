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
  </properties>
</component>
</components>""")

class TestConfig(unittest.TestCase):
    def testParseEmpty(self):
        conf = config.FlumotionConfigXML(None, '<root/>')

    def testParseComponent(self):
        conf = config.FlumotionConfigXML(None,
             """<root>
             <component name="component-name" type="test-component"/>
             </root>""")

        entries = conf.getEntries()
        assert entries.has_key('component-name')
        entry = conf.getEntry('component-name')
        assert entry.getName() == 'component-name', entry.getName()
        assert entry.getType() == 'test-component', entry.getType()
        assert conf.getEntryType('component-name') == entry.getType()
        dict = entry.getConfigDict()
        assert dict.get('name') == 'component-name', dict['name']
        assert dict.get('type') == 'test-component', dict['type']
        assert entry.startFactory()
        assert not entry.getWorker()
        
    def testParseWorkers(self):
        conf = config.FlumotionConfigXML(None,
             """<root>
             <workers policy="password">
               <worker username="root" password="god"/>
             </workers>
             </root>""")

        workers = conf.getWorkers()
        assert workers.getPolicy() == 'password'
        assert len(workers) == 1
        worker = iter(workers).next()
        assert worker.getUsername() == 'root'
        assert worker.getPassword() == 'god'
        assert conf.hasWorker('root')
        
    def testParseError(self):
        xml = '<root><bad-node/></root>'
        self.assertRaises(config.ConfigError,
                          config.FlumotionConfigXML, None, xml)

    def testParseComponentError(self):
        xml = '<root><component name="unused" type="not-existing"/></root>'
        self.assertRaises(KeyError, config.FlumotionConfigXML, None, xml)

        xml = '<root><component/></root>'
        self.assertRaises(config.ConfigError,
                          config.FlumotionConfigXML, None, xml)

        xml = '<root><component name="without-type"/></root>'
        self.assertRaises(config.ConfigError,
                          config.FlumotionConfigXML, None, xml)

    def testParseWorkersError(self):
        xml = '<root><workers/></root>'
        self.assertRaises(config.ConfigError,
                          config.FlumotionConfigXML, None, xml)

        xml = '<root><workers policy="unknown-policy"/></root>'
        self.assertRaises(config.ConfigError,
                          config.FlumotionConfigXML, None, xml)

        xml = '<root><workers><worker/></workers></root>'
        self.assertRaises(config.ConfigError,
                          config.FlumotionConfigXML, None, xml)

        xml = '<root><workers><worker username="without-password"/></workers></root>'
        self.assertRaises(config.ConfigError,
                          config.FlumotionConfigXML, None, xml)

    def testParseProperties(self):
        conf = config.FlumotionConfigXML(None,
             """<root>
             <component name="component-name" type="test-component">
               <one>string</one>
               <two>1</two>
               <three>2.5</three>
               <four attr="attr-value">value</four>
             </component>
             </root>""")
        entry = conf.getEntry('component-name')
        conf = entry.getConfigDict()
        assert conf.get('one') == 'string'
        assert conf.get('two') == 1
        assert conf.get('three') == 2.5
        custom = conf.get('four')
        assert custom
        assert getattr(custom, 'data', None) == 'value'
        assert getattr(custom, 'attr', None) == 'attr-value'
        
