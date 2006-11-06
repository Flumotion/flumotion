# -*- Mode: Python; test-case-name:flumotion.test.test_config -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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

from StringIO import StringIO

from twisted.trial import unittest

from flumotion.common import config, registry, errors

import common

regchunk = """
<registry>
  <components>
    <component type="test-component">
      <properties>
        <property name="one" type="string"/>
        <property name="two" type="int"/>
        <property name="three" type="float"/>
        <!-- four elided -->
        <property name="five" type="bool"/>
        <property name="six" type="long"/>
        <property name="seven" type="fraction"/>
        <property name="eight" type="int" multiple="yes" />
      </properties>
      <sockets>
        <socket type="foo.bar"/>
      </sockets>
    </component>
    <component type="test-component-sync">
      <synchronization required="true" />
    </component>
    <component type="test-component-sync-provider">
      <synchronization required="true" clock-priority="130"/>
    </component>
  </components>
  <plugs>
    <plug socket="foo.bar" type="frobulator">
      <entry location="bar/baz.py" function="Frobulator"/>
      <properties>
        <property name="rate" type="fraction" required="true"/>
      </properties>
    </plug>
    <plug socket="flumotion.component.plugs.adminaction.AdminAction"
          type="test-adminaction">
      <entry location="qux/baz.py" function="Quxulator"/>
      <properties>
        <property name="foo" type="string" required="true"/>
      </properties>
    </plug>
  </plugs>
</registry>"""

reg = registry.getRegistry()
reg.addFromString(regchunk)

def ConfigXML(string):
    f = StringIO(string)
    conf = config.FlumotionConfigXML(f)
    f.close()
    return conf

class TestConfig(unittest.TestCase):
    def testParseEmpty(self):
        conf = ConfigXML('<planet/>')
        self.failIf(conf.getPath())
        self.failUnless(conf.export())

    def testParseWrongConfig(self):
        self.assertRaises(config.ConfigError,
            ConfigXML, '<somethingorother/>')

    def testParseWrongSyntax(self):
        self.assertRaises(config.ConfigError,
            ConfigXML, 'planet/>')

    def testParseComponentNoWorker(self):
        conf = ConfigXML(
             """
             <planet>
               <atmosphere>
                 <component name="component-name" type="test-component"/>
               </atmosphere>
             </planet>""")
        self.assertRaises(config.ComponentWorkerConfigError, conf.parse)
        conf = ConfigXML(
             """
             <planet>
               <atmosphere>
                 <component name="component-name" type="test-component"
                            worker=""/>
               </atmosphere>
             </planet>""")
        self.assertRaises(config.ComponentWorkerConfigError, conf.parse)

    def testParseAtmosphere(self):
        conf = ConfigXML(
             """
             <planet>
               <atmosphere>
                 <component name="component-name" type="test-component"
                            worker="foo"/>
               </atmosphere>
             </planet>""")
        self.failIf(conf.atmosphere)
        conf.parse()
        self.failUnless(conf.atmosphere)
        self.failUnless(conf.atmosphere.components)
        self.assertEquals(len(conf.atmosphere.components), 1)
        self.failUnless(conf.atmosphere.components['component-name'])
        self.assertEquals(conf.atmosphere.components['component-name'].name,
            "component-name")

    def testParseWrongAtmosphere(self):
        xml = """
             <planet>
               <atmosphere>
                 <somethingwrong name="component-name" type="test-component"
                                 worker="foo"/>
               </atmosphere>
             </planet>"""
        conf = ConfigXML(xml)
        self.failUnless(conf)
        self.assertRaises(config.ConfigError, conf.parse)
 
    def testParseComponent(self):
        conf = ConfigXML(
             """
             <planet>
               <flow name="default">
                 <component name="component-name" type="test-component"
                            worker="foo"/>
               </flow>
             </planet>
             """)

        self.failIf(conf.flows)
        conf.parse()

        flow = conf.flows[0]
        self.failUnless(flow.components.has_key('component-name'))
        component = flow.components['component-name']
        self.assertEquals(component.name, 'component-name')
        self.assertEquals(component.getName(), 'component-name')
        self.assertEquals(component.type, 'test-component')
        self.assertEquals(component.getType(), 'test-component')
        self.assertEquals(component.getParent(), 'default')
        self.assertEquals(component.getWorker(), 'foo')
        dict = component.getConfigDict()
        self.assertEquals(dict.get('name'), 'component-name', dict['name'])
        self.assertEquals(dict.get('type'), 'test-component', dict['type'])
        
    def testParseManager(self):
        conf = ConfigXML(
             """
             <planet>
               <manager name="aname">
                 <host>mymachine</host>
                 <port>7000</port>
                 <transport>tcp</transport>
                 <debug>5</debug>
                 <component name="component-name" type="test-component"/>
               </manager>
             </planet>""")
        self.failUnless(conf.manager)
        self.failIf(conf.manager.bouncer)

        conf.parse()
        self.failUnless(conf.manager.bouncer)
        self.failUnless(conf.manager.bouncer.name)
        self.assertEquals(conf.manager.bouncer.name, "component-name")

    def testParseManagerWithPlugs(self):
        conf = ConfigXML(
             """
             <planet>
               <manager name="aname">
                 <plugs>
                   <plug socket="flumotion.component.plugs.adminaction.AdminAction"
                         type="test-adminaction">
                     <property name="foo">bar</property>
                   </plug>
                 </plugs>
               </manager>
             </planet>""")
        conf.parse()
        self.failUnless(conf.manager)
        self.failIf(conf.manager.bouncer)
        self.failIf(conf.manager.host)
        self.assertEquals(conf.manager.plugs,
                          {'flumotion.component.plugs.adminaction.AdminAction':
                           [{'type':'test-adminaction',
                             'socket':
                             'flumotion.component.plugs.adminaction.AdminAction',
                             'properties': {'foo': 'bar'}}],
                           'flumotion.component.plugs.lifecycle.ManagerLifecycle':
                           [],
                           'flumotion.component.plugs.identity.IdentityProvider':
                           []})

    def testParseManagerWithBogusPlug(self):
        conf = ConfigXML(
             """
             <planet>
               <manager name="aname">
                 <plugs>
                   <plug socket="doesnotexist"
                         type="frob">
                   </plug>
                 </plugs>
               </manager>
             </planet>""")
        self.assertRaises(config.ConfigError, conf.parse)

    def testParseError(self):
        xml = '<planet><bad-node/></planet>'
        conf = ConfigXML(xml)
        self.failUnless(conf)
        self.assertRaises(config.ConfigError, conf.parse)

    def testParseComponentError(self):
        xml = """<planet>
            <flow name="default">
            <component name="unused" type="not-existing" worker="foo"/>
            </flow>
            </planet>"""
        conf = ConfigXML(xml)
        self.failUnless(conf)
        self.assertRaises(errors.UnknownComponentError, conf.parse)

        xml = """<planet>
              <flow name="default">
                <component type="not-named" worker="foo"/>
              </flow>
            </planet>"""
        conf = ConfigXML(xml)
        self.failUnless(conf)
        self.assertRaises(config.ConfigError, conf.parse)

        xml = """<planet>
              <flow name="default">
                <component name="not-typed" worker="foo"/>
              </flow>
            </planet>"""
        conf = ConfigXML(xml)
        self.failUnless(conf)
        self.assertRaises(config.ConfigError, conf.parse)
        
    def testParseFlowError(self):
        xml = """<planet>
            <flow>
            <component name="unused" type="not-existing" worker="foo"/>
            </flow>
            </planet>"""
        conf = ConfigXML(xml)
        self.failUnless(conf)
        self.assertRaises(config.ConfigError, conf.parse)

        xml = """<planet>
              <flow name="manager">
                <component name="unused" type="not-existing" worker="foo"/>
              </flow>
            </planet>"""
        conf = ConfigXML(xml)
        self.failUnless(conf)
        self.assertRaises(config.ConfigError, conf.parse)

        xml = """<planet>
              <flow name="atmosphere">
                <component name="unused" type="not-existing" worker="foo"/>
              </flow>
            </planet>"""
        conf = ConfigXML(xml)
        self.failUnless(conf)
        self.assertRaises(config.ConfigError, conf.parse)

        xml = """<planet>
              <flow name="wrongcomponentnode">
                <wrongnode name="unused" type="not-existing" worker="foo"/>
              </flow>
            </planet>"""
        conf = ConfigXML(xml)
        self.failUnless(conf)
        self.assertRaises(config.ConfigError, conf.parse)


    def testParseManagerError(self):
        xml = """<planet><manager>
            <component name="first" type="test-component" worker="foo"/>
            <component name="second" type="test-component" worker="foo"/>
            </manager></planet>"""
        conf = ConfigXML(xml)
        self.failUnless(conf)
        self.assertRaises(config.ConfigError, conf.parse)

        xml = """<planet>
               <manager name="aname">
                 <port>notanint</port>
               </manager>
             </planet>"""
        self.assertRaises(config.ConfigError,
            ConfigXML, xml)

        xml = """<planet>
               <manager name="aname">
                 <transport>notatransport</transport>
               </manager>
             </planet>"""
        self.assertRaises(config.ConfigError,
            ConfigXML, xml)
  
        xml = """<planet>
               <manager name="aname">
                 <notanode/>
               </manager>
             </planet>"""
        self.assertRaises(config.ConfigError,
            ConfigXML, xml)
   
    def testParseProperties(self):
        planet = ConfigXML(
             """<planet><flow name="default">
             <component name="component-name" type="test-component" worker="foo">
               <property name="one">string</property>
               <property name="two">1</property>
               <property name="three">2.5</property>
               <!-- no four -->
               <property name="five">True</property>
               <property name="six">3981391981389138998131389L</property>
               <property name="seven">30000/1001</property>
               <property name="eight">1</property>
               <property name="eight">2</property>
             </component></flow>
             </planet>""")
        self.failIf(planet.flows)

        planet.parse()
        flow = planet.flows[0]
        component = flow.components['component-name']
        conf = component.getConfigDict()
        props = conf.get('properties')
        self.failUnless(isinstance(props, dict))
        self.assertEquals(props.get('one'), 'string')
        self.assertEquals(props.get('two'), 1)
        self.assertEquals(props.get('three'), 2.5)
        self.failUnless(props.get('five'))
        self.assertEquals(props.get('six'), 3981391981389138998131389L)
        self.assertEquals(props.get('seven'), (30000, 1001))
        self.assertEquals(props.get('eight'), [1,2])

        # should be none -- no master in a pipeline that doesn't need
        # synchronization
        self.assertEquals(conf['clock-master'], None)

    def testParsePlugs(self):
        planet = ConfigXML(
             """<planet><flow name="default">
             <component name="component-name" type="test-component"
                        worker="foo">
               <plugs>
                 <plug socket="foo.bar" type="frobulator">
                   <property name="rate">3/4</property>
                 </plug>
               </plugs>
             </component></flow>
             </planet>""")
        self.failIf(planet.flows)

        planet.parse()
        flow = planet.flows[0]
        component = flow.components['component-name']
        conf = component.getConfigDict()
        plugs = conf['plugs']
        self.assertEquals(plugs.keys(), ['foo.bar'])
        foobars = plugs['foo.bar']
        self.assertEquals(len(foobars), 1)
        self.assertEquals(foobars[0],
                          {'socket': 'foo.bar',
                           'type': 'frobulator',
                           'properties': {'rate': (3, 4)}})

    def testParseNoPlugs(self):
        planet = ConfigXML(
             """<planet><flow name="default">
             <component name="component-name" type="test-component"
                        worker="foo">
             </component></flow>
             </planet>""")
        self.failIf(planet.flows)

        planet.parse()
        flow = planet.flows[0]
        component = flow.components['component-name']
        conf = component.getConfigDict()
        self.assertEquals(conf['plugs'], {'foo.bar': []})

    def testClockMasterAutoSelection(self):
        planet = ConfigXML(
             """<planet>
             <flow name="default">
             <component name="one" type="test-component-sync" worker="foo">
             </component>
             <component name="two" type="test-component-sync-provider"
                        worker="foo">
             </component>
             </flow>
             </planet>""")
        self.failIf(planet.flows)

        planet.parse()
        flow = planet.flows[0]
        one = flow.components['one']
        two = flow.components['two']
        confone = one.getConfigDict()
        conftwo = two.getConfigDict()
        self.assertEquals(confone['clock-master'], '/default/two')
        self.assertEquals(conftwo['clock-master'], '/default/two')

    def testClockMasterUserSelection(self):
        planet = ConfigXML(
             """<planet>
             <flow name="default">
             <component name="one" type="test-component-sync" worker="foo">
               <clock-master>yes</clock-master>
             </component>
             <component name="two" type="test-component-sync-provider"
                        worker="foo">
             </component>
             </flow>
             </planet>""")
        self.failIf(planet.flows)

        planet.parse()
        flow = planet.flows[0]
        one = flow.components['one']
        two = flow.components['two']
        confone = one.getConfigDict()
        conftwo = two.getConfigDict()
        self.assertEquals(confone['clock-master'], '/default/one')
        self.assertEquals(conftwo['clock-master'], '/default/one')

    def testClockMasterError(self):
        planet = ConfigXML(
             """<planet>
             <flow name="default">
             <component name="one" type="test-component-sync" worker="foo">
               <clock-master>yes</clock-master>
             </component>
             <component name="two" type="test-component-sync-provider"
                        worker="foo">
               <clock-master>yes</clock-master>
             </component>
             </flow>
             </planet>""")
        self.failIf(planet.flows)

        self.assertRaises(config.ConfigError, planet.parse)

    def testGetComponentEntries(self):
        conf = ConfigXML(
             """
             <planet>
               <atmosphere>
                 <component name="atmocomp" type="test-component"
                            worker="foo"/>
               </atmosphere>
               <flow name="default">
                 <component name="flowcomp" type="test-component"
                            worker="foo"/>
               </flow>
             </planet>
             """)
        conf.parse()
        entries = conf.getComponentEntries()
        self.failUnless(entries.has_key('/atmosphere/atmocomp'))
        self.failUnless(entries.has_key('/default/flowcomp'))

    def testGetComponentEntriesWrong(self):
        xml = """
             <planet>
               <flow name="atmosphere">
                 <component name="flowcomp" type="test-component"
                            worker="foo"/>
               </flow>
             </planet>
             """
        conf = ConfigXML(xml)
        self.assertRaises(config.ConfigError, conf.parse)

def AdminConfig(sockets, string):
    f = StringIO(string)
    conf = config.AdminConfigParser(sockets, f)
    f.close()
    return conf

class AdminConfigTest(unittest.TestCase):
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
        parser = AdminConfig(('foo.bar',), doc)
        self.failUnless(parser.plugs == {'foo.bar':[]}, parser.plugs)

    def testUnknownPlug(self):
        doc = ('<admin>'
               '<plugs>'
               '<plug type="plugdoesnotexist" socket="foo.bar">'
               '</plug>'
               '</plugs>'
               '</admin>')
        self.assertRaises(config.ConfigError,
                          lambda: AdminConfig(('foo.bar',), doc))

    def testUnknownSocket(self):
        doc = ('<admin>'
               '<plugs>'
               '<plug type="frobulator" socket="baz">'
               '</plug>'
               '</plugs>'
               '</admin>')
        self.assertRaises(config.ConfigError,
                          lambda: AdminConfig(('foo.bar',), doc))
