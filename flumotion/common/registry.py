# -*- Mode: Python; test-case-name: flumotion.test.test_registry -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

import os
import stat
import sys
from xml.dom import minidom, Node

from twisted.python import reflect

from flumotion import config
from flumotion.utils import log

__all__ = ['ComponentRegistry', 'registry']

def istrue(value):
    if value in ('True', 'true', '1', 'yes'):
        return True

    return False

def getMTime(file):
    return os.stat(file)[stat.ST_MTIME]

class RegistryEntryComponent:
    "This class represents a <component> entry in the registry"
    def __init__(self, filename, type, factory, source, properties, files):
        self.filename = filename
        self.type = type
        self.factory = factory
        self.source = source
        self.properties = properties
        self.files = files
        
    def getProperties(self):
        return self.properties

    def getFiles(self):
        return self.files

    def getGUIEntry(self):
        if not self.files:
            return
        
        # FIXME: Handle multiple files
        if len(self.files) > 1:
            return
        
        return self.files[0].getFilename()
    
    def getType(self):
        return self.type

    def getSource(self):
        return self.source
    
    def isFactory(self):
        return self.factory

class RegistryEntryProperty:
    "This class represents a <property> entry in the registry"
    def __init__(self, name, type, required=False, multiple=False):
        self.name = name
        self.type = type
        self.required = required
        self.multiple = multiple

    def __repr__(self):
        return '<Property name=%s>' % self.name
    
    def getName(self):
        return self.name

    def getType(self):
        return self.type
    
    def isRequired(self):
        return self.required

    def isMultiple(self):
        return self.multiple

class RegistryEntryFile:
    "This class represents a <file> entry in the registry"
    def __init__(self, filename, type):
        self.filename = filename
        self.type = type

    def getName(self):
        return os.path.basename(self.filename)

    def getType(self):
        return self.type
    
    def getFilename(self):
        return self.filename

    def isType(self, type):
        return self.type == type
    
class XmlParserError(Exception):
    pass

def check_node(node, tag):
    if node.nodeName == tag:
        return
    
    raise XmlParserError, \
          'expected <%s>, but <%s> found' % (tag, node.nodeName)

# TODO
# Proper description
# Links to other files (glade, python, png)

class RegistryXmlParser(log.Loggable):
    def __init__(self, filename, string=None):
        self.components = {}
        self.filename = filename
        self.path = os.path.split(filename)[0]

        if string:
            self.debug('Parsing XML string')
            self.doc = minidom.parseString(string)
        else:
            self.debug('Parsing XML file: %s' % filename)
            self.doc = minidom.parse(filename)
        self.parse()
        
    def getPath(self):
        return self.path

    def getComponents(self):
        return self.components.values()

    def getComponent(self, name):
        return self.components[name]
    
    def parse(self):
        # <components>
        #   <component>
        # </components>

        root = self.doc.documentElement
        
        check_node(root, 'components')
        
        for node in root.childNodes:
            if node.nodeType != Node.ELEMENT_NODE:
                continue
            if node.nodeName == 'component':
                component = self.parse_component(node)
                self.components[component.getType()] = component
            else:
                raise XmlParserError, "unexpected node: %s" % node
            
    def parse_component(self, node):
        # <component type="...">
        #   <source>
        #   <properties>
        # </component>
        if not node.hasAttribute('type'):
            raise XmlParserError, "<component> must have a type attribute"
        type = str(node.getAttribute('type'))

        properties = {}
        # Merge in options for inherit
        if node.hasAttribute('inherit'):
            base_type = str(node.getAttribute('inherit'))
            base = self.getComponent(base_type)
            for prop in base.getProperties():
                properties[prop.getName()] = prop
                
        files = []
        source = None
        for child in node.childNodes:
            if child.nodeType != Node.ELEMENT_NODE:
                continue

            if child.nodeName == 'source':
                source = self.parse_source(child)
            elif child.nodeName == 'properties':
                child_properties = self.parse_properties(properties, child)
            elif child.nodeName == 'files':
                files = self.parse_files(child)
            else:
                raise XmlParserError, "unexpected node: %s" % child

        factory = True
        if node.hasAttribute('factory'):
            factory = node.getAttribute('factory')
            if not istrue(factory):
                factory = False

        return RegistryEntryComponent(self.filename,
                                      type, factory, source, 
                                      properties.values(), files)

    def parse_source(self, node):
        # <source location="..."/>
        if not node.hasAttribute('location'):
            raise XmlParserError, "<source> must have a location attribute"

        return str(node.getAttribute('location'))

    def parse_properties(self, properties, node):
        # <properties>
        #   <property name="..." type="" required="yes/no" multiple="yes/no"/>
        #  </properties>
        
        for child in node.childNodes:
            if (child.nodeType == Node.TEXT_NODE or
                child.nodeType == Node.COMMENT_NODE):
                continue
            
            if child.nodeName != "property":
                raise XmlParserError, "unexpected node: %s" % child
        
            if not child.hasAttribute('name'):
                raise XmlParserError, "<property> must have a name attribute"
            elif not child.hasAttribute('type'):
                raise XmlParserError, "<property> must have a type attribute"

            name = str(child.getAttribute('name'))
            type = str(child.getAttribute('type'))

            optional = {}
            if child.hasAttribute('required'):
                optional['required'] = istrue(child.getAttribute('required'))

            if child.hasAttribute('multiple'):
                optional['multiple'] = istrue(child.getAttribute('multiple'))

            property = RegistryEntryProperty(name, type, **optional)

            properties[name] = property

    def parse_files(self, node):
        # <files>
        #   <file name="..." type=""/>
        #  </files>

        files = []
        for child in node.childNodes:
            if (child.nodeType == Node.TEXT_NODE or
                child.nodeType == Node.COMMENT_NODE):
                continue
            
            if child.nodeName != "file":
                raise XmlParserError, "unexpected node: %s" % child
        
            if not child.hasAttribute('name'):
                raise XmlParserError, "<file> must have a name attribute"

            if not child.hasAttribute('type'):
                raise XmlParserError, "<file> must have a type attribute"

            name = str(child.getAttribute('name'))
            type = str(child.getAttribute('type'))

            dir = os.path.split(self.filename)[0]
            filename = os.path.join(dir, name)
            file = RegistryEntryFile(filename, type)
            files.append(file)
            
        return files

class ComponentRegistry(log.Loggable):
    """Registry, this is normally not instantiated."""
    logCategory = 'registry'
    filename = os.path.join(config.registrydir, 'components.xml')
    def __init__(self):
        self.components = {}

    def addFromFile(self, filename, string=None):
        self.info('Merging registry from %s' % filename)
        parser = RegistryXmlParser(filename, string)
        for component in parser.getComponents():
            type = component.getType()
            if self.components.has_key(type):
                raise TypeError, \
                      "there is already a component of type %s" % type
            self.components[type] = component

    def addFromString(self, string):
        self.addFromFile('<string>', string)
        
    def isEmpty(self):
        return len(self.components) == 0

    def getComponent(self, name):
        return self.components[name]

    def hasComponent(self, name):
        return self.components.has_key(name)

    def getComponents(self):
        return self.components.values()
    
    def dump(self, fd):
        print >> fd, '<components>'
        for component in self.components.values():
            data = ''
            if not component.isFactory():
                data += ' factory="false"'
                
            print >> fd, '  <component type="%s"%s>' % (component.getType(), data)
            print >> fd, '    <source location="%s"/>' % component.getSource()

            print >> fd, '    <properties>'
            for prop in component.getProperties():
                print >> fd, '      <property name="%s" type="%s" required="%s" multiple="%s"/>' % (
                    prop.getName(),
                    prop.getType(),
                    prop.isRequired(),
                    prop.isMultiple())
            print >> fd, '    </properties>'

            files = component.getFiles()
            if files:
                print >> fd, '    <files>'
                for file in files:
                    print >> fd, '      <file name="%s" type="%s"/>' % (
                        file.getName(),
                        file.getType())
                print >> fd, '    </files>'

            print >> fd, '  </component>'
        print >> fd, '</components>'

    def clean(self):
        self.components = {}

    def getFileList(self, root):
        files = []
        for dir in os.listdir(root):
            dir = os.path.join(root, dir)
            if not os.path.isdir(dir):
                continue
            for filename in os.listdir(dir):
                filename = os.path.join(dir, filename)
                if not os.path.exists(filename):
                    continue
                if filename.endswith('.xml'):
                    files.append(filename)
        return files
    
    def update(self, root):
        for filename in self.getFileList(root):
            registry.addFromFile(filename)

        self.info('Saving registry to %s' % self.filename)
        # create parent directory
        dir = os.path.split(self.filename)[0]
        if not os.path.exists(dir):
            os.makedirs(dir)
        if not os.path.isdir(dir):
            self.error('Registry directory %s is not a directory !')
        fd = open(self.filename, 'w')
        registry.dump(fd)

    def isDirty(self, root):
        if registry.isEmpty():
            return True

        files = self.getFileList(root)
        if not files:
            self.warning('Empty registry')
            return True
        
        max_mtime = max(map(getMTime, files))
        if max_mtime > getMTime(self.filename):
            return True

        return False
    
    def verify(self, root, force=False):
        dir = os.path.join(root, 'flumotion', 'component')
        
        if not os.path.exists(self.filename):
            force = True
        else:
            registry.addFromFile(self.filename)

        if force or self.isDirty(dir):
            self.info('Rebuilding registry')
            registry.clean()
            registry.update(dir)
            
registry = ComponentRegistry()

