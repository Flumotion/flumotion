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
from xml.dom import minidom, Node

from twisted.python import reflect 

from flumotion.server.registry import registry
from flumotion.utils import log

class ConfigError(Exception):
    pass

class ConfigEntry:
    nice = 0
    def __init__(self, name, type, func, config):
        self.name = name
        self.type = type
        self.func = func
        self.config = config

    def getType(self):
        return self.type
    
    def getName(self):
        return self.name
    
    def getComponent(self, *args):
        return self.func(self.config, *args)

    def startFactory(self):
        return self.config.get('start-factory', True)
    
class FlumotionConfigXML(log.Loggable):
    logCategory = 'config'

    def __init__(self, filename):
        self.entries = {}
    
        self.debug('Loading configuration file `%s\'' % filename)
        self.doc = minidom.parse(filename)
        self.path = os.path.split(filename)[0]
        self.parse()
        
    def getPath(self):
        return self.path

    def getEntries(self):
        return self.entries

    def getEntry(self, name):
        return self.entries[name]

    def getEntryType(self, name):
        entry = self.entries[name]
        return entry.getType()
    
    def getFunction(self, defs):
        source = defs.getSource()
        try:
            module = reflect.namedAny(source)
        except ValueError:
            raise ConfigError("%s source file could not be found" % source)
        
        if not hasattr(module, 'createComponent'):
            self.warn('no createComponent() for %s' % source)
            return
        
        return module.createComponent
    
    def parse(self):
        # <root>
        #     <component>
        # </root>

        root = self.doc.documentElement
        
        #check_node(root, 'root')
        
        for node in root.childNodes:
            if node.nodeType != Node.ELEMENT_NODE:
                continue
            if node.nodeName == 'component':
                entry = self.parse_entry(node)
                if entry is not None:
                    self.entries[entry.getName()] = entry
            else:
                raise XmlParserError, "unexpected node: %s" % child
            
    def parse_entry(self, node):
        # <component name="..." type="...">
        #     ...
        # </component>
        if not node.hasAttribute('name'):
            raise XmlParserError, "<component> must have a name attribute"
        if not node.hasAttribute('type'):
            raise XmlParserError, "<component> must have a type attribute"

        type = str(node.getAttribute('type'))
        name = str(node.getAttribute('name'))

        defs = registry.getComponent(type)
        properties = defs.getProperties()

        self.debug('Parsing component: %s' % name)
        options = self.parseProperties(node, type, properties)

        function = self.getFunction(defs)
        if not function:
            return
        
        config = { 'name': name,
                   'type': type,
                   'config' : self,
                   'start-factory': defs.isFactory() }
        config.update(options)
        
        return ConfigEntry(name, type, function, config)

    def get_float_value(self, nodes):
        return [float(subnode.childNodes[0].data) for subnode in nodes]

    def get_int_value(self, nodes):
        return [int(subnode.childNodes[0].data) for subnode in nodes]

    def get_string_value(self, nodes):
        values = []
        for subnode in nodes:
            data = str(subnode.childNodes[0].data)
            if '\n' in data:
                parts = [x.strip() for x in data.split('\n')]
                data = ' '.join(parts)
            values.append(data)

        return values
    
    def get_xml_value(self, nodes):
        class XMLProperty:
            pass
        
        values = []
        for subnode in nodes:
            # XXX: Child nodes recursively
            
            data = subnode.childNodes[0].data
            if '\n' in data:
                parts = [x.strip() for x in data.split('\n')]
                data = ' '.join(parts)
                
            property = XMLProperty()
            property.data = data
            for key in subnode.attributes.keys():
                value = subnode.attributes[key].value
                setattr(property, str(key), value)

            values.append(property)

        return values

    def parseProperties(self, node, type, properties):
        config = {}
        for definition in properties:
            name = definition.name

            nodes = []
            for subnode in node.childNodes:
                if subnode.nodeName == name:
                    nodes.append(subnode)
                
            if definition.isRequired() and not nodes:
                raise ConfigError("%s is required but not specified" % name)

            if not definition.multiple and len(nodes) > 1:
                raise ConfigError("multiple value specified but not allowed")

            type = definition.type
            if type == 'string':
                value = self.get_string_value(nodes)
            elif type == 'int':
                value = self.get_int_value(nodes)
            elif type == 'float':
                value = self.get_float_value(nodes)
            elif type == 'xml':
                value = self.get_xml_value(nodes)
            else:
                raise ConfigError, "invalid property type: %s" % type

            if value == []:
                continue
            
            if not definition.multiple:
                value = value[0]
            
            config[name] = value
            
        return config
