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
        assert not reg.hasComponent('foobie')
        assert reg.hasComponent('baz')

    def testClean(self):
        reg = registry.ComponentRegistry()
        reg.addFromString("""<components>
          <component name="foo" type="bar"></component></components>""")
        reg.clean()
        assert reg.isEmpty()

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
        
