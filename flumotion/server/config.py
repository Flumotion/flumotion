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

class ConfigComponent:
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

class FlumotionConfigXML:
    def __init__(self, filename):
        self.components = {}
    
        self.msg('Loading configuration file `%s\'' % filename)
        self.doc = minidom.parse(filename)
        self.path = os.path.split(filename)[0]
        self.parse()
        
    msg = lambda s, *a: log.msg('config', *a)
    warn = lambda s, *a: log.warn('config', *a)

    def getPath(self):
        return self.path

    def getComponents(self):
        return self.components

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
                component = self.parse_component(node)
                self.components[component.getName()] = component
            else:
                raise XmlParserError, "unexpected node: %s" % child
            
    def parse_component(self, node):
        # <component name="..." type="...">
        #     ...
        # </component>
        if not node.hasAttribute('name'):
            raise XmlParserError, "<component> must have a name attribute"
        if not node.hasAttribute('type'):
            raise XmlParserError, "<component> must have a type attribute"

        type = node.getAttribute('type')
        name = node.getAttribute('name')
        defs = registry.getComponent(type)
        module = reflect.namedAny(defs.source)
        if not hasattr(module, 'createComponent'):
            # XXX: Throw an error
            self.warn('no createComponent() for %s' % defs.source)
            return

        config = {}
        config['name'] = name
        config['type'] = type

        self.parse_property_def(type, defs.getProperties(), node, config)
        
        function = module.createComponent
        component = ConfigComponent(name, type, function, config)
        return component

    def get_int_value(self, nodes):
        values = []
        for subnode in nodes:
            data = subnode.childNodes[0].data
            values.append(int(data))

        return values

    def get_string_value(self, nodes):
        values = []
        for subnode in nodes:
            data = str(subnode.childNodes[0].data)
            if '\n' in data:
                parts = [x.strip() for x in data.split('\n')]
                data = ' '.join(parts)
            values.append(data)

        return values
    
    def parse_property_def(self, type, defs, node, config):
        self.msg('Parsing component: %s' % config['name'])
        for definition in defs:
            name = definition.name

            nodes = []
            for subnode in node.childNodes:
                if subnode.nodeName == name:
                    nodes.append(subnode)
                
            if definition.required and not nodes:
                raise ConfigError("%s is required but not specified" % name)

            if not definition.multiple and len(nodes) > 1:
                raise ConfigError("multiple value specified but not allowed")

            type = definition.type
            if type == 'string':
                value = self.get_string_value(nodes)
            elif type == 'int':
                value = self.get_int_value(nodes)
            else:
                raise ConfigError, "invalid property type: %s" % type

            if value == []:
                continue
            
            if not definition.multiple:
                value = value[0]
            
            #print '%s=%r' % (name, value)
            config[name] = value
            
        #raise SystemExit
