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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os

from xml.dom import minidom, Node

class Component:
    def __init__(self, type, source, properties):
        self.type = type
        self.source = source
        self.properties = properties
        
    def getType(self):
        return self.type
    
class XmlParserError(Exception):
    pass

def check_node(node, tag):
    if node.nodeName == tag:
        return
    
    raise XmlParserError, \
          'expected <%s>, but <%s> found' % (tag, node.nodeName)

class RegistryXmlParser:
    def __init__(self, filename):
        self.components = []
    
        #debug('Parsing XML file: %s' % filename)
        self.doc = minidom.parse(filename)
        self.path = os.path.split(filename)[0]
        self.parse()
        
    def getPath(self):
        return self.path

    def getComponents(self):
        return self.components

    def parse(self):
        """<gst-media-test>
             <mediums>
             <test-case>
           </gst-media-test>"""

        root = self.doc.documentElement
        
        check_node(root, 'components')
        
        for node in root.childNodes:
            if node.nodeType != Node.ELEMENT_NODE:
                continue
            if node.nodeName == 'component':
                component = self.parse_components(node)
                self.components.append(component)
            else:
                raise XmlParserError, "unexpected node: %s" % child
            
    def parse_components(self, node):
        """<component type="...">
             <source>
             <properties>
           </component>"""    
        if not node.hasAttribute('type'):
            raise XmlParserError, "<component> must have a type attribute"

        source = None
        properties = None
        for child in node.childNodes:
            if child.nodeType != Node.ELEMENT_NODE:
                continue

            if child.nodeName == 'source':
                source = self.parse_source(child)
            elif child.nodeName == 'properties':
                properties = self.parse_properties(child)
            else:
                raise XmlParserError, "unexpected node: %s" % child

        
        return Component(node.getAttribute('type'), source, properties)

    def parse_source(self, node):
        """<source location="..."/>"""
        if not node.hasAttribute('location'):
            raise XmlParserError, "<source> must have a location attribute"

        return node.getAttribute('location')

    def parse_properties(self, node):
        """<properties>
             <property name="..." type="" required="..."/>
           </properties>"""
        
        properties = []
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
            
            if child.hasAttribute('required'):
                required = child.getAttribute('required')
            else:
                required = None

            property = (child.getAttribute('name'),
                        child.getAttribute('type'),
                        required)
            
            properties.append(property)

        return properties

class ComponentRegistry:
    def __init__(self):
        self.components = {}

    def addFromFile(self, filename):
        print filename
        parser = RegistryXmlParser(filename)
        for component in parser.getComponents():
            type = component.getType()
            if self.components.has_key(type):
                raise TypeError, \
                      "there is already a component of type %s" % type
            self.components[type] = component
            
    def getComponent(self, name):
        return self.components[name]

    def hasComponent(self, name):
        return self.component.has_key(name)

registry = ComponentRegistry()
