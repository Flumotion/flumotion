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

from flumotion.common.registry import registry
from flumotion.utils import log

class ConfigError(Exception):
    pass

class ConfigEntryComponent(log.Loggable):
    "I represent a <component> entry in a registry file"
    nice = 0
    logCategory = 'config'
    def __init__(self, name, type, config, defs, worker):
        self.name = name
        self.type = type
        self.config = config
        self.defs = defs
        self.worker = worker
        
    def getType(self):
        return self.type
    
    def getName(self):
        return self.name

    def getConfigDict(self):
        return self.config

    def getWorker(self):
        return self.worker

    # XXX: kill this codex
    def getComponent(self):
        defs = self.defs
        dict = self.config
        
        # Setup files to be transmitted over the wire. Must be a
        # better way of doing this.
        source = defs.getSource()
        self.info('Loading %s' % source)
        try:
            module = reflect.namedAny(source)
        except ValueError:
            raise ConfigError("%s source file could not be found" % source)
        
        if not hasattr(module, 'createComponent'):
            self.warning('no createComponent() for %s' % source)
            return
        
        dir = os.path.split(module.__file__)[0]
        files = {}
        for file in defs.getFiles():
            filename = os.path.basename(file.getFilename())
            real = os.path.join(dir, filename)
            files[real] = file
        
        # Create the component which the specified configuration
        # directives. Note that this can't really be moved from here
        # since it gets called by the launcher from another process
        # and we don't want to create it in the main process, since
        # we're going to listen to ports and other stuff which should
        # be separated from the main process.

        component = module.createComponent(dict)
        component.setFiles(files)
        return component

    def startFactory(self):
        return self.config.get('start-factory', True)

class ConfigEntryWorker:
    "I represent a <worker> entry in a registry file"
    def __init__(self, username, password):
        self.username = username
        self.password = password

    def getUsername(self):
        return self.username
    
    def getPassword(self):
        return self.password

class ConfigEntryWorkers:
    "I represent a <workers> entry in a registry file"
    def __init__(self, workers, policy):
        self.workers = workers
        self.policy = policy

    def getWorkers(self):
        return self.workers
    
    def getPolicy(self):
        return self.policy

class FlumotionConfigXML(log.Loggable):
    logCategory = 'config'

    def __init__(self, filename):
        self.entries = {}
        self.workers = None
        
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

    def getWorkers(self):
        return self.workers

    def hasWorker(self, name):
        return True
    
        #print self.workers.getWorkers()
        for worker in self.workers.getWorkers():
            if worker.getUsername() == name:
                return True

        return False
    
    def parse(self):
        # <root>
        #     <component>
        #     <workers>
        # </root>

        root = self.doc.documentElement
        
        #check_node(root, 'root')
        
        for node in root.childNodes:
            if node.nodeType != Node.ELEMENT_NODE:
                continue
            if node.nodeName == 'component':
                entry = self.parse_component(node)
                if entry is not None:
                    self.entries[entry.getName()] = entry
            elif node.nodeName == 'workers':
                entry = self.parse_workers(node)
                self.workers = entry
            else:
                raise ConfigError, "unexpected node: %s" % child
            
    def parse_component(self, node):
        # <component name="..." type="..." worker="">
        #     ...
        # </component>
        
        if not node.hasAttribute('name'):
            raise ConfigError, "<component> must have a name attribute"
        if not node.hasAttribute('type'):
            raise ConfigError, "<component> must have a type attribute"

        type = str(node.getAttribute('type'))
        name = str(node.getAttribute('name'))

        worker = None
        if not node.hasAttribute('worker'):
            worker = str(node.getAttribute('worker'))

        try:
            defs = registry.getComponent(type)
        except KeyError:
            raise KeyError, "unknown component type: %s" % type
        
        properties = defs.getProperties()

        self.debug('Parsing component: %s' % name)
        options = self.parseProperties(node, type, properties)

        config = { 'name': name,
                   'type': type,
                   'config' : self,
                   'start-factory': defs.isFactory() }
        config.update(options)

        return ConfigEntryComponent(name, type, config, defs, worker)

    def parse_workers(self, node):
        # <workers policy="password/anonymous">
        #     <worker name="..." password=""/>
        # </workers>

        if not node.hasAttribute('policy'):
            raise ConfigError, "<workers> must have a policy attribute"

        policy = str(node.getAttribute('policy'))
        
        workers = []
        for child in node.childNodes:
            if (child.nodeType == Node.TEXT_NODE or
                child.nodeType == Node.COMMENT_NODE):
                continue
            
            if child.nodeName != "worker":
                raise ConfigError, "unexpected node: %s" % child
        
            if not child.hasAttribute('username'):
                raise ConfigError, "<worker> must have a username attribute"

            if not child.hasAttribute('password'):
                raise ConfigError, "<worker> must have a password attribute"

            username = str(child.getAttribute('username'))
            password = str(child.getAttribute('password'))

            worker = ConfigEntryWorker(username, password)
            workers.append(worker)

        return ConfigEntryWorkers(workers, policy)

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
