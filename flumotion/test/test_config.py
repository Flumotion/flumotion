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
    <component type="test-component-with-feeder">
      <feeder name="default" />
    </component>
    <component type="test-component-with-one-eater">
      <eater name="default" required="true" />
    </component>
    <component type="test-component-with-two-eaters">
      <eater name="video" required="true" />
      <eater name="audio" required="true" />
    </component>
    <component type="test-component-with-multiple-eater">
      <eater name="default" multiple="true" />
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

def ConfigXML(string, parser=config.FlumotionConfigXML):
    f = StringIO(string)
    conf = parser(f)
    f.close()
    return conf

def ManagerConfigXML(string):
    return ConfigXML(string, config.ManagerConfigParser)

class TestFunctions(unittest.TestCase):
    def testBuildEatersDict(self):
        def assertEaters(comptype, l, expected):
            defs = reg.getComponent(comptype)
            self.assertEquals(config.buildEatersDict(l, defs.getEaters()),
                              expected)
        def assertRaises(comptype, l, err):
            defs = reg.getComponent(comptype)
            self.assertRaises(err, config.buildEatersDict, l,
                              defs.getEaters())
        assertEaters('test-component-with-multiple-eater',
                     [('default', 'foo:bar'),
                      ('default', 'baz')],
                     {'default': ['foo:bar', 'baz']})
        assertRaises('test-component-with-multiple-eater',
                     [], config.ConfigError)
        assertEaters('test-component-with-multiple-eater',
                     [(None, 'foo:bar')],
                     {'default': ['foo:bar']})
                       
class TestConfig(unittest.TestCase):
    def testParseEmpty(self):
        conf = ConfigXML('<planet/>')
        self.failIf(conf.getPath())
        self.failUnless(conf.export())

    def testParseWrongConfig(self):
        conf = ConfigXML('<somethingorother/>')
        self.assertRaises(config.ConfigError, conf.parse)

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
        self.assertRaises(config.ConfigError, conf.parse)
        conf = ConfigXML(
             """
             <planet>
               <atmosphere>
                 <component name="component-name" type="test-component"
                            worker=""/>
               </atmosphere>
             </planet>""")
        self.assertRaises(config.ConfigError, conf.parse)

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
        self.assertEquals(component.label, None)
        self.assertEquals(component.getLabel(), None)
        self.assertEquals(component.type, 'test-component')
        self.assertEquals(component.getType(), 'test-component')
        self.assertEquals(component.getParent(), 'default')
        self.assertEquals(component.getWorker(), 'foo')
        dict = component.getConfigDict()
        self.assertEquals(dict.get('name'), 'component-name', dict['name'])
        self.assertEquals(dict.get('type'), 'test-component', dict['type'])

    def testParseComponentWithLabel(self):
        conf = ConfigXML(
             """
             <planet>
               <flow name="default">
                 <component name="component-name" type="test-component"
                            label="component-label" worker="foo"/>
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
        self.assertEquals(component.label, 'component-label')
        self.assertEquals(component.getLabel(), 'component-label')
        self.assertEquals(component.type, 'test-component')
        self.assertEquals(component.getType(), 'test-component')
        self.assertEquals(component.getParent(), 'default')
        self.assertEquals(component.getWorker(), 'foo')
        dict = component.getConfigDict()
        self.assertEquals(dict.get('name'), 'component-name', dict['name'])
        self.assertEquals(dict.get('type'), 'test-component', dict['type'])
        
    def testParseComponentWithProject(self):
        conf = ConfigXML(
             """
             <planet>
               <flow name="default">
                 <component name="component-name" type="test-component"
                            worker="foo" project="flumotion" version="0.4.2"/>
               </flow>
             </planet>
             """)

        self.failIf(conf.flows)
        conf.parse()

        flow = conf.flows[0]
        self.failUnless(flow.components.has_key('component-name'))
        conf = flow.components['component-name'].getConfigDict()
        self.assertEquals(conf['project'], 'flumotion', conf['type'])
        self.assertEquals(conf['version'], (0,4,2,0), conf['type'])
        
        # now the same, but without specifying project
        conf = ConfigXML(
             """
             <planet>
               <flow name="default">
                 <component name="component-name" type="test-component"
                            worker="foo" version="0.4.2"/>
               </flow>
             </planet>
             """)

        self.failIf(conf.flows)
        conf.parse()

        flow = conf.flows[0]
        self.failUnless(flow.components.has_key('component-name'))
        conf = flow.components['component-name'].getConfigDict()
        self.assertEquals(conf['project'], 'flumotion', conf['type'])
        self.assertEquals(conf['version'], (0,4,2,0), conf['type'])
        
    def testParseManager(self):
        conf = ManagerConfigXML(
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

        conf.parseBouncerAndPlugs()
        self.failUnless(conf.bouncer)
        self.failUnless(conf.bouncer.name)
        self.assertEquals(conf.bouncer.name, "component-name")

    def testParseManagerWithPlugs(self):
        conf = ManagerConfigXML(
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
        conf.parseBouncerAndPlugs()
        self.failUnless(conf.manager)
        self.failIf(conf.manager.host)
        self.failIf(conf.bouncer)
        self.assertEquals(conf.plugs,
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
        conf = ManagerConfigXML(
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
        self.assertRaises(errors.UnknownPlugError, conf.parseBouncerAndPlugs)

    def testParseError(self):
        xml = '<planet><bad-node/></planet>'
        conf = ConfigXML(xml)
        self.failUnless(conf)
        self.assertRaises(config.ConfigError, conf.parse)

        self.assertRaises(config.ConfigError, ManagerConfigXML, xml)

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
        conf = ManagerConfigXML(xml)
        self.failUnless(conf)
        self.assertRaises(config.ConfigError, conf.parseBouncerAndPlugs)

        xml = """<planet>
               <manager name="aname">
                 <port>notanint</port>
               </manager>
             </planet>"""
        self.assertRaises(config.ConfigError,
            ManagerConfigXML, xml)

        xml = """<planet>
               <manager name="aname">
                 <transport>notatransport</transport>
               </manager>
             </planet>"""
        self.assertRaises(config.ConfigError,
            ManagerConfigXML, xml)
  
        xml = """<planet>
               <manager name="aname">
                 <notanode/>
               </manager>
             </planet>"""
        self.assertRaises(config.ConfigError,
            ManagerConfigXML, xml)
   
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

    def testParseComponentsWithEaters(self):
        conf = ConfigXML(
            """
            <planet>
              <flow name="default">
                <component name="prod" type="test-component-with-feeder"
                           worker="foo"/>
                <component name="cons" type="test-component-with-one-eater"
                           worker="foo">
                  <eater name="default">
                    <feed>prod:default</feed>
                  </eater>
                </component>
              </flow>
            </planet>
            """)
        conf.parse()
        entries = conf.getComponentEntries()
        self.failUnless(entries.has_key('/default/prod'))
        self.failUnless(entries.has_key('/default/cons'))
        cons = entries['/default/cons'].getConfigDict()
        self.failUnless(cons.has_key('eater'))
        self.failUnless(cons['eater'].has_key('default'))
        self.failUnless(cons['eater']['default'] == ["prod:default"])
        self.failUnless(cons['source'] == ["prod:default"])

    def testParseComponentsWithEatersNotSpecified(self):
        conf = ConfigXML(
            """
            <planet>
              <flow name="default">
                <component name="cons" type="test-component-with-one-eater"
                           worker="foo">
                </component>
              </flow>
            </planet>
            """)
        self.assertRaises(config.ConfigError, conf.parse)

    def testParseComponentsWithEatersDeprecatedWay(self):
        conf = ConfigXML(
            """
            <planet>
              <flow name="default">
                <component name="prod" type="test-component-with-feeder"
                           worker="foo"/>
                <component name="cons" type="test-component-with-one-eater"
                           worker="foo">
                  <source>prod:default</source>
                </component>
              </flow>
            </planet>
            """)
        conf.parse()
        entries = conf.getComponentEntries()
        self.failUnless(entries.has_key('/default/prod'))
        self.failUnless(entries.has_key('/default/cons'))
        cons = entries['/default/cons'].getConfigDict()
        self.failUnless(cons.has_key('source'))
        self.failUnless(cons['source'] == ["prod:default"])
        self.failUnless(cons['eater']['default'] == ["prod:default"])

    def testParseComponentsWithTwoEaters(self):
        conf = ConfigXML(
            """
            <planet>
              <flow name="default">
                <component name="prod" type="test-component-with-feeder"
                           worker="foo"/>
                <component name="prod2" type="test-component-with-feeder"
                           worker="foo"/>
                <component name="cons" type="test-component-with-two-eaters"
                           worker="foo">
                  <eater name="video">
                    <feed>prod:default</feed>
                  </eater>
                  <eater name="audio">
                    <feed>prod2:default</feed>
                  </eater>
                </component>
              </flow>
            </planet>
            """)
        conf.parse()
        entries = conf.getComponentEntries()
        self.failUnless(entries.has_key('/default/prod'))
        self.failUnless(entries.has_key('/default/cons'))
        cons = entries['/default/cons'].getConfigDict()
        self.failUnless(cons.has_key('eater'))
        self.failUnless(cons['eater'].has_key('video'))
        self.failUnless(cons['eater']['video'] == ["prod:default"])
        self.failUnless(cons['eater'].has_key('audio'))
        self.failUnless(cons['eater']['audio'] == ['prod2:default'])

    def testParseComponentsWithTwoEatersDeprecatedWay(self):
        conf = ConfigXML(
            """
            <planet>
              <flow name="default">
                <component name="prod" type="test-component-with-feeder"
                           worker="foo"/>
                <component name="prod2" type="test-component-with-feeder"
                           worker="foo"/>
                <component name="cons" type="test-component-with-two-eaters"
                           worker="foo">
                  <source>prod:default</source>
                  <source>prod2:default</source>
                </component>
              </flow>
            </planet>
            """)
        self.assertRaises(config.ConfigError, conf.parse)

    def testParseComponentsWithMultipleEater(self):
        conf = ConfigXML(
            """
            <planet>
              <flow name="default">
                <component name="prod" type="test-component-with-feeder"
                           worker="foo"/>
                <component name="prod2" type="test-component-with-feeder"
                           worker="foo"/>
                <component name="cons" type="test-component-with-multiple-eater"
                           worker="foo">
                  <eater name="default">
                    <feed>prod:default</feed>
                    <feed>prod2:default</feed>
                  </eater>
                </component>
              </flow>
            </planet>
            """)
        conf.parse()
        entries = conf.getComponentEntries()
        self.failUnless(entries.has_key('/default/prod'))
        self.failUnless(entries.has_key('/default/cons'))
        cons = entries['/default/cons'].getConfigDict()
        self.failUnless(cons.has_key('eater'))
        self.failUnless(cons['eater'].has_key('default'))
        self.failUnless(cons['eater']['default'] == [
            "prod:default", "prod2:default"])
        self.failUnless(cons.has_key('source'))
        self.failUnless(cons['source'] == [
            "prod:default", "prod2:default"])

    def testParseComponentsWithMultipleEaterDeprecatedWay(self):
        conf = ConfigXML(
            """
            <planet>
              <flow name="default">
                <component name="prod" type="test-component-with-feeder"
                           worker="foo"/>
                <component name="prod2" type="test-component-with-feeder"
                           worker="foo"/>
                <component name="cons" type="test-component-with-multiple-eater"
                           worker="foo">
                  <source>prod:default</source>
                  <source>prod2:default</source>
                </component>
              </flow>
            </planet>
            """)
        conf.parse()
        entries = conf.getComponentEntries()
        self.failUnless(entries.has_key('/default/prod'))
        self.failUnless(entries.has_key('/default/cons'))
        cons = entries['/default/cons'].getConfigDict()
        self.failUnless(cons.has_key('eater'))
        self.failUnless(cons['eater'].has_key('default'))
        self.failUnless(cons['eater']['default'] == [
            "prod:default", "prod2:default"])
        self.failUnless(cons.has_key('source'))
        self.failUnless(cons['source'] == [
            "prod:default", "prod2:default"])

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
        self.assertRaises(errors.UnknownPlugError,
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

class TestDictDiff(unittest.TestCase):
    def assertOND(self, d1, d2, old, new, diff):
        o, n, d = config.dictDiff(d1, d2)
        self.assertEquals(old, o)
        self.assertEquals(new, n)
        self.assertEquals(diff, d)

    def testSimple(self):
        ass = self.assertOND
        ass({}, {}, [], [], [])

        ass({'foo': 'bar'}, {}, [(('foo',), 'bar')], [], [])

        ass({}, {'foo': 'bar'}, [], [(('foo',), 'bar')], [])

        ass({'foo': 'bar'}, {'foo': 'baz'}, [], [], [(('foo',), 'bar', 'baz')])

    def testRecursive(self):
        ass = self.assertOND
        ass({}, {}, [], [], [])

        ass({'foo': {'bar': 'baz'}},
            {},
            [(('foo',), {'bar':'baz'})],
            [],
            [])

        ass({'foo': {'bar': 'baz'}},
            {'foo': {}},
            [(('foo','bar'), 'baz')],
            [],
            [])

        ass({'foo': {}},
            {'foo': {'bar': 'baz'}},
            [],
            [(('foo','bar'), 'baz')],
            [])

        ass({},
            {'foo': {'bar': 'baz'}},
            [],
            [(('foo',), {'bar':'baz'})],
            [])

        ass({'foo': {'bar': 'baz'}},
            {'foo': {'bar': 'qux'}},
            [],
            [],
            [(('foo','bar'), 'baz', 'qux')])

    def testHumanReadable(self):
        def test(d1, d2, s):
            msg = config.dictDiffMessageString(config.dictDiff(d1, d2))
            self.assertEquals(msg, s)

        test({}, {}, '')
        test({'foo': 42}, {}, "Only in old: 'foo' = 42")
        test({}, {'foo': 42}, "Only in new: 'foo' = 42")
        test({'foo': 17}, {'foo': 42},
             "Value mismatch:\n"
             "    old: 'foo' = 17\n"
             "    new: 'foo' = 42")

        test({'foo': {'bar': 'baz'}},
             {},
             "Only in old: 'foo' = {'bar': 'baz'}")

        test({'foo': {'bar': 'baz'}},
             {'foo': {}},
             "Only in old['foo']: 'bar' = 'baz'")

        test({'foo': {}},
             {'foo': {'bar': 'baz'}},
             "Only in new['foo']: 'bar' = 'baz'")

        test({},
             {'foo': {'bar': 'baz'}},
             "Only in new: 'foo' = {'bar': 'baz'}")

        test({'foo': {'bar': 'baz'}},
             {'foo': {'bar': 'qux'}},
             "Value mismatch:\n"
             "    old['foo']: 'bar' = 'baz'\n"
             "    new['foo']: 'bar' = 'qux'")
