# -*- Mode: Python; test-case-name: flumotion.test.test_registry -*-
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

import StringIO
import os
import shutil
import tempfile
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)

from twisted.internet import task

from flumotion.common import testsuite
from flumotion.common import registry, fxml, common


class TestRegistry(testsuite.TestCase):

    def setUp(self):
        self.reg = registry.ComponentRegistry(paths=[])
        self.reg.clean()

    def testDefault(self):
        self.failUnless(hasattr(registry, 'getRegistry'))
        reg = registry.getRegistry()
        self.failUnless(isinstance(reg, registry.ComponentRegistry))

    def testIsTrue(self):
        self.failUnless(common.strToBool('True'))
        self.failUnless(common.strToBool('true'))
        self.failUnless(common.strToBool('1'))
        self.failUnless(common.strToBool('yes'))
        self.failIf(common.strToBool('False'))
        self.failIf(common.strToBool('false'))
        self.failIf(common.strToBool('0'))
        self.failIf(common.strToBool('no'))
        self.failIf(common.strToBool('I am a monkey'))

    def testgetMTime(self):
        mtime = registry._getMTime(__file__)
        self.failUnless(mtime)
        self.failUnless(isinstance(mtime, int))

    def testParseBasic(self):
        self.failUnless(self.reg.isEmpty())
        self.reg.addFromString('<root></root>')
        self.failUnless(self.reg.isEmpty())
        self.reg.addFromString(
            '<registry><components></components></registry>')
        self.failUnless(self.reg.isEmpty())

    def testParseComponents(self):
        self.failUnless(self.reg.isEmpty())
        self.reg.addFromString("""
<registry>
  <components>
    <component type="bar" base="/">
    </component>
    <component type="baz" base="/">
    </component>
  </components>
</registry>""")

        self.failIf(self.reg.isEmpty())

        self.failUnless(self.reg.hasComponent('bar'))
        comp1 = self.reg.getComponent('bar')
        self.failUnless(isinstance(comp1, registry.RegistryEntryComponent))

        self.failUnless(self.reg.hasComponent('baz'))
        comp2 = self.reg.getComponent('baz')
        self.failUnless(isinstance(comp2, registry.RegistryEntryComponent))

        comps = self.reg.getComponents()
        comps.sort()
        self.assertEquals(len(comps), 2)
        self.failUnless(comp1 in comps)
        self.failUnless(comp2 in comps)

    def testParseComponentProperties(self):
        self.failUnless(self.reg.isEmpty())
        self.reg.addFromString("""
<registry>
  <components>
    <component type="component" base="/">
      <properties>
        <property name="source" type="string" required="yes"
                  multiple="yes" _description="a source property" />
      </properties>
    </component>
  </components>
</registry>""")

        comp = self.reg.getComponent('component')
        props = comp.getProperties()
        self.failUnless(props)
        self.assertEquals(len(props), 1)
        prop = props[0]
        self.assertEquals(prop.getName(), 'source')
        self.assertEquals(prop.getType(), 'string')
        self.assertEquals(prop.getDescription(), 'a source property')
        self.failUnless(prop.isRequired())
        self.failUnless(prop.isMultiple())

    def testParseComponentCompoundProperties(self):
        self.failUnless(self.reg.isEmpty())
        self.reg.addFromString("""
<registry>
  <components>
    <component type="component" base="/">
      <properties>
        <property name="source" type="string" required="yes" multiple="no"
                  _description="a source property" />
        <compound-property name="group" required="yes" multiple="yes"
                           _description="a group of properties">
          <property name="first" type="int" required="yes" multiple="no"
                    _description="a required int property" />
          <property name="last" type="bool" required="no" multiple="yes"
                    _description="an optional bool property" />
        </compound-property>
      </properties>
    </component>
  </components>
</registry>""")

        comp = self.reg.getComponent('component')
        props = dict([(p.getName(), p) for p in comp.getProperties()])
        self.failUnless(props)
        self.assertEquals(len(props), 2)
        self.failUnless(comp.hasProperty('source'))
        self.failUnless(comp.hasProperty('group'))

        prop = props['source']
        self.failUnless(isinstance(prop, registry.RegistryEntryProperty))
        self.failIf(isinstance(prop, registry.RegistryEntryCompoundProperty))
        self.assertEquals(prop.getName(), 'source')
        self.assertEquals(prop.getType(), 'string')
        self.assertEquals(prop.getDescription(), 'a source property')
        self.failUnless(prop.isRequired())
        self.failIf(prop.isMultiple())

        prop = props['group']
        self.failUnless(isinstance(prop, registry.RegistryEntryProperty))
        self.failUnless(isinstance(prop,
                                   registry.RegistryEntryCompoundProperty))
        self.assertEquals(prop.getName(), 'group')
        self.assertEquals(prop.getType(), 'compound')
        self.assertEquals(prop.getDescription(), 'a group of properties')
        self.failUnless(prop.isRequired())
        self.failUnless(prop.isMultiple())

        # get and test (sub)properties of the compound property 'group'
        props = dict([(p.getName(), p) for p in prop.getProperties()])
        self.failUnless(props)
        self.assertEquals(len(props), 2)
        self.failUnless(prop.hasProperty('first'))
        self.failUnless(prop.hasProperty('last'))

        prop = props['first']
        self.failUnless(isinstance(prop, registry.RegistryEntryProperty))
        self.failIf(isinstance(prop, registry.RegistryEntryCompoundProperty))
        self.assertEquals(prop.getName(), 'first')
        self.assertEquals(prop.getType(), 'int')
        self.assertEquals(prop.getDescription(), 'a required int property')
        self.failUnless(prop.isRequired())
        self.failIf(prop.isMultiple())

        prop = props['last']
        self.failUnless(isinstance(prop, registry.RegistryEntryProperty))
        self.failIf(isinstance(prop, registry.RegistryEntryCompoundProperty))
        self.assertEquals(prop.getName(), 'last')
        self.assertEquals(prop.getType(), 'bool')
        self.assertEquals(prop.getDescription(), 'an optional bool property')
        self.failIf(prop.isRequired())
        self.failUnless(prop.isMultiple())

    def testParseComponentPropertiesErrors(self):
        template = """
<registry>
  <components>
    <component type="component" base="/">
      <properties>
        %s
      </properties>
    </component>
  </components>
</registry>"""

        property = "<base-name/>"
        self.assertRaises(fxml.ParserError,
                          self.reg.addFromString, template % property)

        property = '<property without-name=""/>'
        self.assertRaises(fxml.ParserError,
                          self.reg.addFromString, template % property)

        property = '<property name="bar" without-type=""/>'
        self.assertRaises(fxml.ParserError,
                          self.reg.addFromString, template % property)

    def testClean(self):
        xml = """
<registry>
  <components>
    <component type="bar" base="/">
    </component>
  </components>
</registry>"""
        reg = registry.ComponentRegistry(paths=[])
        reg.addFromString(xml)
        reg.clean()
        self.failUnless(reg.isEmpty())

    def testComponentTypeError(self):
        reg = registry.ComponentRegistry(paths=[])
        xml = """
<registry>
  <components>
    <component type="bar" base="/"></component>
  </components>
</registry>"""
        reg.addFromString(xml)

    def testAddXmlParseError(self):
        reg = registry.ComponentRegistry(paths=[])
        xml = """
<registry>
  <components>
    <component></component>
  </components>
</registry>"""
        self.assertRaises(fxml.ParserError, reg.addFromString, xml)
        xml = """<registry><components><foo></foo></components></registry>"""
        self.assertRaises(fxml.ParserError, reg.addFromString, xml)

    def _compareRegistryAfterDump(self, orig, expected, name=''):
        reg = registry.ComponentRegistry(paths=[])
        reg.clean()
        reg.addFromString(orig)
        s = StringIO.StringIO()
        reg.dump(s)
        s.seek(0, 0)
        data = s.read()

        testsuite.diffStrings(data, expected, desc=name)

    # addFromString does not parse <directory> toplevel entries since they
    # should not be in partial registry files

    def testDump(self):
        xml = """
<registry>
  <components>
    <component type="bar" base="base/dir"
               _description="A bar component.">
      <entries>
        <entry type="test/test" location="loc" function="main"/>
      </entries>
    </component>
  </components>
  <plugs>
    <plug type="baz" socket="frogger" _description="a frog">
      <entries>
        <entry type="default" location="loc" function="main"/>
      </entries>
      <properties>
        <property name="qux" type="string" _description="a quxy property"/>
      </properties>
    </plug>
  </plugs>
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
</registry>"""

        target = """<registry>

  <components>

    <component type="bar" base="base/dir"
               _description="A bar component.">
      <source location="None"/>
      <synchronization required="no" clock-priority="100"/>
      <properties>
      </properties>
      <entries>
        <entry type="test/test" location="loc" function="main"/>
      </entries>
    </component>

  </components>

  <plugs>

    <plug type="baz" socket="frogger" _description="a frog">
      <entries>
        <entry type="default" location="loc" function="main"/>
      </entries>
      <properties>
        <property name="qux" type="string"
                  _description="a quxy property"
                  required="False" multiple="False"/>
      </properties>
    </plug>

  </plugs>

  <bundles>
    <bundle name="test-bundle" under="pythondir" project="flumotion">
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
</registry>
"""
        self._compareRegistryAfterDump(xml, target, 'testDump')

    def testDumpWithEscapedPropertyDescription(self):
        xml = """
<registry>
  <components>
    <component type="bar" base="base/dir"
               _description="A bar component.">
      <entries>
        <entry type="test/test" location="loc" function="main"/>
      </entries>
      <properties>
        <property name="c" type="int"
                  _description="c property %lt;needs escaping&gt;"/>
      </properties>
    </component>
  </components>
</registry>"""

        target = """<registry>

  <components>

    <component type="bar" base="base/dir"
               _description="A bar component.">
      <source location="None"/>
      <synchronization required="no" clock-priority="100"/>
      <properties>
        <property name="c" type="int"
                  _description="c property %lt;needs escaping&gt;"
                  required="False" multiple="False"/>
      </properties>
      <entries>
        <entry type="test/test" location="loc" function="main"/>
      </entries>
    </component>

  </components>

  <plugs>

  </plugs>

  <bundles>
  </bundles>
</registry>
"""
        self._compareRegistryAfterDump(
            xml, target,
            'testDumpWithEscapedPropertyDescription')

    def testDumpWithCompoundProperties(self):
        xml = """
<registry>
  <components>
    <component type="bar" base="base/dir"
               _description="A bar component.">
      <entries>
        <entry type="test/test" location="loc" function="main"/>
      </entries>
      <properties>
        <compound-property name="cgrr" _description="an cgrry property">
          <property name="c" type="int" _description="c property"/>
        </compound-property>
        <property name="cux" type="string" _description="a cuxy property"/>
      </properties>
    </component>
  </components>
  <plugs>
    <plug type="baz" socket="frogger" _description="a frog">
      <entry location="loc" function="main"/>
      <properties>
        <property name="qux" type="string" _description="a quxy property"/>
        <compound-property name="grr" _description="an agrry property">
          <property name="a" type="int" _description="a property"/>
        </compound-property>
      </properties>
    </plug>
  </plugs>
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
</registry>"""

        target = """<registry>

  <components>

    <component type="bar" base="base/dir"
               _description="A bar component.">
      <source location="None"/>
      <synchronization required="no" clock-priority="100"/>
      <properties>
        <compound-property name="cgrr"
                           _description="an cgrry property"
                           required="False" multiple="False">
          <property name="c" type="int"
                    _description="c property"
                    required="False" multiple="False"/>
        </compound-property>
        <property name="cux" type="string"
                  _description="a cuxy property"
                  required="False" multiple="False"/>
      </properties>
      <entries>
        <entry type="test/test" location="loc" function="main"/>
      </entries>
    </component>

  </components>

  <plugs>

    <plug type="baz" socket="frogger" _description="a frog">
      <entries>
        <entry type="default" location="loc" function="main"/>
      </entries>
      <properties>
        <property name="qux" type="string"
                  _description="a quxy property"
                  required="False" multiple="False"/>
        <compound-property name="grr"
                           _description="an agrry property"
                           required="False" multiple="False">
          <property name="a" type="int"
                    _description="a property"
                    required="False" multiple="False"/>
        </compound-property>
      </properties>
    </plug>

  </plugs>

  <bundles>
    <bundle name="test-bundle" under="pythondir" project="flumotion">
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
</registry>
"""
        self._compareRegistryAfterDump(xml, target,
                                       'testDumpWithCompoundProperties')


class TestComponentEntry(testsuite.TestCase):

    def setUp(self):
        self.file = registry.RegistryEntryFile('gui-filename', 'type')
        rec = registry.RegistryEntryComponent
        self.entry = rec(
            'filename', 'type', 'source', 'description', 'base',
            ['prop'], [self.file], {}, [], [], False, 100, [], [])
        self.empty_entry = rec(
            'filename', 'type', 'source', 'description', 'base',
            ['prop'], [], {}, [], [], True, 130, [], [])
        self.multiple_entry = rec(
            'filename', 'type', 'source', 'description',
            'base', ['prop'],
            [self.file, self.file], {}, [], [],
            False, 100, [], [])

    def testThings(self):
        self.assertEquals(self.entry.getType(), 'type')
        self.assertEquals(self.entry.getSource(), 'source')
        self.assertEquals(self.entry.getFiles(), [self.file])
        self.assertEquals(self.entry.getGUIEntry(), 'gui-filename')
        self.assertEquals(self.empty_entry.getGUIEntry(), None)
        self.assertEquals(self.multiple_entry.getGUIEntry(), None)
        self.assertEquals(self.empty_entry.getNeedsSynchronization(), True)
        self.assertEquals(self.empty_entry.getClockPriority(), 130)
        self.assertEquals(self.multiple_entry.getNeedsSynchronization(), False)
        self.assertEquals(self.multiple_entry.getClockPriority(), 100)
        self.assertEquals(self.multiple_entry.getSockets(), [])


def rmdir(root):
    for file in os.listdir(root):
        filename = os.path.join(root, file)
        if os.path.isdir(filename):
            rmdir(filename)
        else:
            os.remove(filename)
    os.rmdir(root)


def writeComponent(filename, name):
    open(filename, 'w').write("""
<registry>
  <components>
    <component type="%s" base="/">
      <properties>
      </properties>
    </component>
  </components>
</registry>""" % name)
    return filename


class TestFindComponents(testsuite.TestCase):

    def setUp(self):
        self.reg = registry.ComponentRegistry(paths=[])
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
        writeComponent('subdir/first.xml', 'first')
        writeComponent('subdir/foo/second.xml', 'second')
        writeComponent('subdir/bar/third.xml', 'third')

    def tearDown(self):
        rmdir('subdir')
        os.chdir(self.cwd)
        self.reg.clean()
        rmdir(self.tempdir)

        if os.path.exists(self.reg.filename):
            os.unlink(self.reg.filename)

    def testSimple(self):
        self.reg.addRegistryPath('.', prefix='subdir')
        components = self.reg.getComponents()
        self.assertEquals(len(components), 3)
        types = [c.getType() for c in components]
        types.sort()
        self.assertEquals(types, ['first', 'second', 'third']) # alpha order


class TestRegistryUpdate(testsuite.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.regcache = os.path.join(self.tempdir, 'registry.xml')
        self.regpath = self.tempdir

        # monkeypatch registry._getMTime() so we can simulate filesystem
        # updates
        self.mtime = {}
        self._getMTime = registry._getMTime
        registry._getMTime = self.mtime.__getitem__
        self.mtime[registry.__file__] = self._getMTime(registry.__file__)

    def tearDown(self):
        registry._getMTime = self._getMTime
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def testConcurrentCacheUpdate(self):
        clock = task.Clock()

        # create tree containing registry snippets
        d = os.path.join(self.regpath, 'flumotion')
        os.mkdir(d)
        f1 = writeComponent(os.path.join(d, 'first.xml'), 'first')
        f2 = writeComponent(os.path.join(d, 'second.xml'), 'second')
        self.mtime[d] = self.mtime[f1] = self.mtime[f2] = clock.seconds()

        # initialize registry
        reg = registry.ComponentRegistry(
            [self.regpath], 'flumotion', self.regcache, clock.seconds)

        # modify registry snippet
        clock.advance(1)
        f2 = writeComponent(os.path.join(d, 'second.xml'), 'second-new')
        self.mtime[f2] += clock.seconds()

        # another process updates the registry cache
        self.mtime[self.regcache] = clock.seconds()

        # the registry should be rebuilt anyway
        self.assert_(reg.rebuildNeeded())
        reg.verify()
        types = sorted(c.getType() for c in reg.getComponents())
        self.assertEquals(types, ['first', 'second-new'])
