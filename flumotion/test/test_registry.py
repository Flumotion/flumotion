# -*- Mode: Python; test-case-name: flumotion.test.test_registry -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_registry.py: regression test for flumotion.common.registry
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.c om). All rights reserved.

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

import common
from twisted.trial import unittest

import os
import warnings
import tempfile
warnings.filterwarnings('ignore', category=FutureWarning)

from flumotion.common import registry
from flumotion.common.registry import istrue

class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = registry.ComponentRegistry()
        self.reg.clean()
        
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
        assert self.reg.isEmpty()
        self.reg.addFromString('<root></root>')
        assert self.reg.isEmpty()
        self.reg.addFromString('<registry><components></components></registry>')
        assert self.reg.isEmpty()
        
    def testParseComponents(self):
        assert self.reg.isEmpty()
        self.reg.addFromString("""
<registry>
  <components>
    <component name="foo" type="bar">
    </component>
    <component name="foobie" type="baz">
    </component>
  </components>
</registry>""")

        assert not self.reg.isEmpty()
        
        assert not self.reg.hasComponent('foo')
        assert self.reg.hasComponent('bar')
        comp1 = self.reg.getComponent('bar')
        assert isinstance(comp1, registry.RegistryEntryComponent)

        assert not self.reg.hasComponent('foobie')

        assert self.reg.hasComponent('baz')
        comp2 = self.reg.getComponent('baz')
        assert isinstance(comp2, registry.RegistryEntryComponent)

        comps = self.reg.getComponents()
        comps.sort()
        assert len(comps) == 2
        assert comp1 in comps
        assert comp2 in comps
        
    def testParseComponentProperties(self):
        assert self.reg.isEmpty()
        self.reg.addFromString("""
<registry>
  <components>
    <component name="foobie" type="component">
      <properties>
        <property name="source" type="string" required="yes" multiple="yes"/>
      </properties>
    </component>
  </components>
</registry>""")

        comp = self.reg.getComponent('component')
        props = comp.getProperties()
        assert props
        assert len(props) == 1
        prop = props[0]
        assert prop.getName() == 'source'
        assert prop.getType() == 'string'
        assert prop.isRequired()
        assert prop.isMultiple()

    def testParseComponentPropertiesErrors(self):
        template = """
<registry>
  <components>
    <component name="foobie" type="component">
      <properties>
        %s
      </properties>
    </component>
  </components>
</registry>"""

        property = "<base-name/>"
        self.assertRaises(registry.XmlParserError,
                          self.reg.addFromString, template % property)

        property = '<property without-name=""/>'
        self.assertRaises(registry.XmlParserError,
                          self.reg.addFromString, template % property)

        property = '<property name="bar" without-type=""/>'
        self.assertRaises(registry.XmlParserError,
                          self.reg.addFromString, template % property)

    def testClean(self):
        xml = """
<registry>
  <components>
    <component name="foo" type="bar">
    </component>
  </components>
</registry>"""
        reg = registry.ComponentRegistry()
        reg.addFromString(xml)
        reg.clean()
        assert reg.isEmpty()

    def testComponentTypeError(self):
        reg = registry.ComponentRegistry()
        xml = """
<registry>
  <components>
    <component name="foo" type="bar"></component>
  </components>
</registry>"""
        reg.addFromString(xml) 
       
    def testAddXmlParseError(self):
        reg = registry.ComponentRegistry()
        xml = """
<registry>
  <components>
    <component name="unique"></component>
  </components>
</registry>"""
        self.assertRaises(registry.XmlParserError, reg.addFromString, xml)
        xml = """<registry><components><foo></foo></components></registry>"""
        self.assertRaises(registry.XmlParserError, reg.addFromString, xml)
        
    def testDump(self):
        xml = """
<registry>
  <components>
    <component type="bar" base="base/dir">
      <entries>
        <entry type="test/test" location="loc" function="main"/>
      </entries>
    </component>
  </components>
  <bundles>
    <bundle name="test-bundle">
      <dependencies>
        <dependency name="test-dependency"/>
      </dependencies>
      <directories>
        <directory name="/tmp">
          <filename location="loc" relative="lob"/>
        </directory>
        <directory name="foobie">
          <filename location="barie"/>
        </directory>
      </directories>
    </bundle>
  </bundles>
  <directories>
    <directory filename="test"/>
  </directories>
</registry>"""
        reg = registry.ComponentRegistry()
        reg.clean()
        reg.addFromString(xml)
        import sys, StringIO
        s = StringIO.StringIO()
        reg.dump(s)
        s.seek(0, 0)
        data = s.read()
        self.assertEquals("""<registry>
  <components>
    <component type="bar" base="base/dir">
      <source location="None"/>
      <properties>
      </properties>
      <entries>
        <entry type="test/test" location="loc" function="main"/>
      </entries>
    </component>
  </components>
  <bundles>
    <bundle name="test-bundle">
      <dependencies>
        <dependency name="test-dependency"/>
      </dependencies>
      <directories>
        <directory name="/tmp">
          <filename location="loc" relative="lob"/>
        </directory>
        <directory name="foobie">
          <filename location="barie" relative="foobie/barie"/>
        </directory>
      </directories>
    </bundle>
  </bundles>
  <directories>
    <directory filename="test"/>
  </directories>
</registry>
""", data)
        
class TestComponentEntry(unittest.TestCase):
    def setUp(self):
        self.file = registry.RegistryEntryFile('gui-filename', 'type')
        self.entry = registry.RegistryEntryComponent('filename', 'type',
                                                     'source', 'base', 
                                                     ['prop'],
                                                     [self.file])
        self.empty_entry = registry.RegistryEntryComponent('filename', 'type',
                                                           'source', 'base', ['prop'],
                                                           [])
        self.multiple_entry = registry.RegistryEntryComponent('filename', 'type', 
                                                              'source', 'base', ['prop'],
                                                              [self.file, self.file])
    def testThings(self):
        self.assertEquals(self.entry.getType(), 'type')
        self.assertEquals(self.entry.getSource(), 'source')
        self.assertEquals(self.entry.getFiles(), [self.file])
        self.assertEquals(self.entry.getGUIEntry(), 'gui-filename')
        self.assertEquals(self.empty_entry.getGUIEntry(), None)
        self.assertEquals(self.multiple_entry.getGUIEntry(), None)

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
        self.reg = registry.ComponentRegistry()
        self.reg.clean()

        # override the registry's filename so make distcheck works
        fd, self.reg.filename = tempfile.mkstemp()
        os.close(fd)
        os.unlink(self.reg.filename)

        self.tempdir = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.tempdir) 
        os.makedirs('subdir')
        os.makedirs('subdir/foo')
        os.makedirs('subdir/bar')
        self.writeComponent('subdir/first.xml', 'first')
        self.writeComponent('subdir/foo/second.xml', 'second')
        self.writeComponent('subdir/bar/third.xml', 'third')

    def tearDown(self):
        rmdir('subdir')
        os.chdir(self.cwd)
        self.reg.clean()
        rmdir(self.tempdir)

        if os.path.exists(self.reg.filename):
            os.unlink(self.reg.filename)

    def writeComponent(self, filename, name):
        open(filename, 'w').write("""
<registry>
  <components>
    <component type="%s">
      <properties>
      </properties>
    </component>
  </components>
</registry>""" % name)
    
    def testSimple(self):
        self.reg.addDirectory('.')
        components = self.reg.getComponents()
        assert len(components) == 3, len(components)
        types = [c.getType() for c in components]
        types.sort()
        assert types == ['first', 'second', 'third'] # alpha order
