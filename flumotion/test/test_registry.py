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
        self.entry = registry.RegistryEntryComponent('filename', 'type', False,
                                                     'source', ['prop'],
                                                     ['files'])
    def testThings(self):
        assert self.entry.getType() == 'type'
        assert not self.entry.isFactory()
        assert self.entry.getSource() == 'source'
        assert self.entry.getFiles() == ['files']
        
