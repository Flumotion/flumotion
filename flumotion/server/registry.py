# -*- Mode: Python -*-
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
import sys
from xml.dom import minidom, Node

from twisted.python import reflect

from flumotion import config

__all__ = ['ComponentRegistry', 'registry']

def istrue(value):
    if value in ('True', 'true', '1', 'yes'):
        return True

    return False

class Property:
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
    
class Component:
    def __init__(self, filename, type, factory, source,
                 source_gui=None, properties={}):
        self.filename = filename
        self.type = type
        self.factory = factory
        self.source = source
        self.source_gui = source_gui
        self.properties = properties

    def getProperties(self):
        return self.properties

    def getType(self):
        return self.type

    def getSource(self):
        return self.source
    
    def isFactory(self):
        return self.factory

    def getSourceLocation(self):
        dir = os.path.split(self.filename)[0]
        filename = os.path.join(dir, self.source)
        return reflect.filenameToModuleName(filename) 
    
class XmlParserError(Exception):
    pass

def check_node(node, tag):
    if node.nodeName == tag:
        return
    
    raise XmlParserError, \
          'expected <%s>, but <%s> found' % (tag, node.nodeName)

# TODO
# ====
#
# Properties (required, type)
# Inherit or interfaces?
# Proper description
# Read and merge other files
# Links to other files (glade, python, png)

class RegistryXmlParser:
    def __init__(self, filename):
        self.components = {}
        self.filename = filename
        
        #debug('Parsing XML file: %s' % filename)
        self.doc = minidom.parse(filename)
        self.path = os.path.split(filename)[0]
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
                raise XmlParserError, "unexpected node: %s" % child
            
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

        source = None
        source_gui = None
        for child in node.childNodes:
            if child.nodeType != Node.ELEMENT_NODE:
                continue

            if child.nodeName == 'source':
                source = self.parse_source(child)
            elif child.nodeName == 'source-gui':
                source = self.parse_source(child)
            elif child.nodeName == 'properties':
                child_properties = self.parse_properties(properties, child)
            else:
                raise XmlParserError, "unexpected node: %s" % child

        factory = True
        if node.hasAttribute('factory'):
            factory = node.getAttribute('factory')
            if not istrue(factory):
                factory = False

        return Component(self.filename,
                         type, factory, source, source_gui,
                         properties.values())

    def parse_source(self, node):
        # <source location="..."/>
        if not node.hasAttribute('location'):
            raise XmlParserError, "<source> must have a location attribute"

        return str(node.getAttribute('location'))

    def parse_properties(self, properties, node):
        # <properties>
        #   <property name="..." type="" required="yes/no" multiple="yes/bno"/>
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

            property = Property(name, type, **optional)

            properties[name] = property

class ComponentRegistry:
    """Registry, this is normally not instantiated."""
    filename = os.path.join(config.datadir, 'registry', 'basecomponents.xml')
    def __init__(self):
        self.components = {}

    def addFromFile(self, filename):
        parser = RegistryXmlParser(filename)
        for component in parser.getComponents():
            type = component.getType()
            if self.components.has_key(type):
                raise TypeError, \
                      "there is already a component of type %s" % type
            self.components[type] = component
            
    def isEmpty(self):
        return len(self.components) == 0

    def getComponent(self, name):
        return self.components[name]

    def hasComponent(self, name):
        return self.component.has_key(name)

    def dump(self, fd):
        print >> fd, '<components>'
        for component in self.components.values():
            data = ''
            if not component.isFactory():
                data += ' factory="false"'
                
            print >> fd, '  <component type="%s"%s>' % (component.getType(), data)
            print >> fd, '    <source location="%s"/>' % component.getSourceLocation()
            print >> fd, '    <properties>'
            
            for prop in component.getProperties():
                print >> fd, '      <property name="%s" type="%s" required="%s" multiple="%s"/>' % (
                    prop.getName(),
                    prop.getType(),
                    prop.isRequired(),
                    prop.isMultiple())
                
            print >> fd, '    </properties>'
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
                if filename.endswith('.xml'):
                    files.append(filename)
        return file
    
    def update(self, root):
        for file in self.getFileList(root):
            registry.addFromFile(filename)
                    
        fd = open(self.filename, 'w')
        registry.dump(fd)

    def verify(self):
        registry.addFromFile(self.filename)

        if registry.isEmpty():
            dir = os.path.join(root, 'flumotion', 'components')
            registry.clean()
            registry.update(dir)
    
registry = ComponentRegistry()

