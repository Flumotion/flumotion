# -*- Mode: Python; test-case-name: flumotion.test.test_registry -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_registry.py: regression test for flumotion.common.registry
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

import os
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)

from twisted.trial import unittest

from flumotion.common import registry
from flumotion.common.registry import istrue

class TestRegistry(unittest.TestCase):
    def testDefault(self):
        assert hasattr(registry, 'registry')
        reg = registry.registry
        assert isinstance(reg, registry.ComponentRegistry)
        
    def testIsTrue(self):
        assert istrue('True')
        assert istrue('true')
        assert istrue('1')
        assert istrue('yes')
        assert not istrue('False') 
        assert not istrue('false') 
        assert not istrue('0') 
        assert not istrue('no') 
        assert not istrue('I am a monkey') 

    def testgetMTime(self):
        mtime = registry.getMTime(__file__)
        assert mtime
        assert isinstance(mtime, int)
        
    def testParseBasic(self):
        reg = registry.ComponentRegistry()
        assert reg.isEmpty()
        reg.addFromString('<components></components>')
        assert reg.isEmpty()
        self.assertRaises(registry.XmlParserError,
                          reg.addFromString, '<root></root>')
        
    def testParseComponents(self):
        reg = registry.ComponentRegistry()
        assert reg.isEmpty()
        reg.addFromString("""<components>
          <component name="foo" type="bar">
          </component>
          <component name="foobie" type="baz">
          </component>
        </components>""")

        assert not reg.isEmpty()
        
        assert not reg.hasComponent('foo')
        assert reg.hasComponent('bar')
        comp1 = reg.getComponent('bar')
        assert isinstance(comp1, registry.RegistryEntryComponent)

        assert not reg.hasComponent('foobie')

        assert reg.hasComponent('baz')
        comp2 = reg.getComponent('baz')
        assert isinstance(comp2, registry.RegistryEntryComponent)

        comps = reg.getComponents()
        comps.sort()
        assert len(comps) == 2
        assert comp1 in comps
        assert comp2 in comps
        
    def testParseProperties(self):
        reg = registry.ComponentRegistry()
        assert reg.isEmpty()
        reg.addFromString("""<components>
          <component name="foobie" type="component">
            <properties>
              <property name="source" type="string" required="yes" multiple="yes"/>
            </properties>
          </component>
        </components>""")

        comp = reg.getComponent('component')
        props = comp.getProperties()
        assert props
        assert len(props) == 1
        prop = props[0]
        assert prop.getName() == 'source'
        assert prop.getType() == 'string'
        assert prop.isRequired()
        assert prop.isMultiple()

    def testParsePropertiesErrors(self):
        reg = registry.ComponentRegistry()
        assert reg.isEmpty()
        template = """<components>
          <component name="foobie" type="component">
            <properties>
              %s
            </properties>
          </component>
        </components>"""

        property = "<base-name/>"
        self.assertRaises(registry.XmlParserError,
                          reg.addFromString, template % property)

        property = '<property without-name=""/>'
        self.assertRaises(registry.XmlParserError,
                          reg.addFromString, template % property)

        property = '<property name="bar" without-type=""/>'
        self.assertRaises(registry.XmlParserError,
                          reg.addFromString, template % property)

    def testClean(self):
        xml = """<components>
          <component name="foo" type="bar"></component></components>"""
        reg = registry.ComponentRegistry()
        reg.addFromString(xml)
        reg.clean()
        assert reg.isEmpty()

    def testAddTypeError(self):
        reg = registry.ComponentRegistry()
        xml = """<components>
          <component name="foo" type="bar"></component></components>"""
        reg.addFromString(xml)
        self.assertRaises(TypeError, reg.addFromString, xml)
        
    def testAddXmlParseError(self):
        reg = registry.ComponentRegistry()
        xml = """<components>
          <component name="unique"></component></components>"""
        self.assertRaises(registry.XmlParserError, reg.addFromString, xml)
        xml = """<components>
          <foo></foo></components>"""
        self.assertRaises(registry.XmlParserError, reg.addFromString, xml)
        
    def testDump(self):
        xml = """<components>
          <component name="foo" type="bar"></component></components>"""
        reg = registry.ComponentRegistry()
        reg.addFromString(xml)
        import sys, StringIO
        s = StringIO.StringIO()
        reg.dump(s)
        s.seek(0, 0)
        data = s.read()
        assert data == """<components>
  <component type="bar">
    <source location="None"/>
    <properties>
    </properties>
  </component>
</components>
""", data
        
class TestComponentEntry(unittest.TestCase):
    def setUp(self):
        self.file = registry.RegistryEntryFile('gui-filename', 'type')
        self.entry = registry.RegistryEntryComponent('filename', 'type', False,
                                                     'source', ['prop'],
                                                     [self.file])
        self.empty_entry = registry.RegistryEntryComponent('filename', 'type', False,
                                                           'source', ['prop'],
                                                           [])
        self.multiple_entry = registry.RegistryEntryComponent('filename', 'type', False,
                                                              'source', ['prop'],
                                                              [self.file, self.file])
    def testThings(self):
        assert self.entry.getType() == 'type'
        assert not self.entry.isFactory()
        assert self.entry.getSource() == 'source'
        assert self.entry.getFiles() == [self.file]
        assert self.entry.getGUIEntry() == 'gui-filename'
        assert self.empty_entry.getGUIEntry() == None
        assert self.multiple_entry.getGUIEntry() == None
        

def rmdir(root):
    for file in os.listdir(root):
        filename = os.path.join(root, file)
        if os.path.isdir(filename):
            rmdir(filename)
        else:
            os.remove(filename)
    os.rmdir(root)
            
class TestFindComponents(unittest.TestCase):
    def setUp(self):
        os.makedirs('subdir')
        os.makedirs('subdir/foo')
        os.makedirs('subdir/bar')
        self.writeComponent('subdir/first.xml', 'first')
        self.writeComponent('subdir/foo/second.xml', 'second')
        self.writeComponent('subdir/bar/third.xml', 'third')
        registry.registry.clean()

    def writeComponent(self, filename, name):
        open(filename, 'w').write("""<components>
  <component type="%s">
    <properties>
    </properties>
  </component>
</components>
""" % name)
    
    def testSimple(self):
        registry.registry.update('.')
        components = registry.registry.getComponents()
        assert len(components) == 3, len(components)
        types = [c.getType() for c in components]
        types.sort()
        assert types == ['first', 'second', 'third'] # alpha order

    def testVerify(self):
        os.makedirs('flumotion/component')
        registry.registry.verify('.')
        rmdir('flumotion/component')
        
    def testVerifyForce(self):
        os.makedirs('flumotion/component')
        registry.registry.verify('.', force=True)
        rmdir('flumotion/component')

    def tearDown(self):
        registry.registry.clean()
        rmdir('subdir')
        
