# -*- Mode: Python; test-case-name: flumotion.test.test_config -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/common/config.py: parse configuration files
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

"""
Parsing of configuration files.
"""

import os
from xml.dom import minidom, Node
from xml.parsers import expat

from twisted.python import reflect 

from flumotion.common.registry import registry
from flumotion.common import log

class ConfigError(Exception):
    pass

class ConfigEntryAtmosphere:
    "I represent a <atmosphere> entry in a planet config file"
    def __init__(self):
        self.components = {}

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

    # XXX: kill this code
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

class ConfigEntryFlow:
    "I represent a <flow> entry in a planet config file"
    def __init__(self):
        self.components = {}

class ConfigEntryManager:
    "I represent a <manager> entry in a planet config file"
    def __init__(self):
        self.bouncer = None

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

    def __iter__(self):
        return iter(self.workers)
    
    def __len__(self):
        return len(self.workers)
    
    def getPolicy(self):
        return self.policy

class FlumotionConfigXML(log.Loggable):
    logCategory = 'config'

    def __init__(self, filename, string=None):
        self.flows = []
        self.manager = None
        self.atmosphere = None

        try:
            if filename is not None:
                self.debug('Loading configuration file `%s\'' % filename)
                self.doc = minidom.parse(filename)
            else:
                self.doc = minidom.parseString(string)
        except expat.ExpatError, e:
            raise ConfigError("XML parser error: %s" % e)
        
        if filename is not None:
            self.path = os.path.split(filename)[0]
        else:
            self.path = None
            
        self.parse()
        
    def getPath(self):
        return self.path

   
    def parse(self):
        # <planet>
        #     <manager>
        #     <atmosphere>
        #     <flow>
        #     ...
        # </planet>

        root = self.doc.documentElement
        
        if not root.nodeName == 'planet':
            raise ConfigError("unexpected root node': %s" % root.nodeName)
        
        for node in root.childNodes:
            if node.nodeType != Node.ELEMENT_NODE:
                continue
            if node.nodeName == 'atmosphere':
                entry = self.parseAtmosphere(node)
                self.atmosphere = entry
            elif node.nodeName == 'flow':
                entry = self.parseFlow(node)
                self.flows.append(entry)
            elif node.nodeName == 'manager':
                entry = self.parseManager(node)
                self.manager = entry
            else:
                raise ConfigError("unexpected node under 'planet': %s" % node.nodeName)

    def parseAtmosphere(self, node):
        # <atmosphere>
        #   <component>
        #   ...
        # </atmosphere>

        atmosphere = ConfigEntryAtmosphere()
        for child in node.childNodes:
            if (child.nodeType == Node.TEXT_NODE or
                child.nodeType == Node.COMMENT_NODE):
                continue
            
            if child.nodeName == "component":
                component = self.parseComponent(child)
            else:
                raise ConfigError("unexpected 'atmosphere' node: %s" % child.nodeName)

            atmosphere.components[component.name] = component
        return atmosphere
     
    def parseComponent(self, node):
        # <component name="..." type="..." worker="">
        
        if not node.hasAttribute('name'):
            raise ConfigError("<component> must have a name attribute")
        if not node.hasAttribute('type'):
            raise ConfigError("<component> must have a type attribute")

        type = str(node.getAttribute('type'))
        name = str(node.getAttribute('name'))

        worker = None
        if node.hasAttribute('worker'):
            worker = str(node.getAttribute('worker'))

        try:
            defs = registry.getComponent(type)
        except KeyError:
            raise KeyError("unknown component type: %s" % type)
        
        properties = defs.getProperties()

        self.debug('Parsing component: %s' % name)
        options = self.parseProperties(node, type, properties)

        config = { 'name': name,
                   'type': type }
        config.update(options)

        return ConfigEntryComponent(name, type, config, defs, worker)

    def parseFlow(self, node):
        # <flow>
        #   <component>
        #   ...
        # </flow>

        flow = ConfigEntryFlow()
        for child in node.childNodes:
            if (child.nodeType == Node.TEXT_NODE or
                child.nodeType == Node.COMMENT_NODE):
                continue
            
            if child.nodeName == "component":
                component = self.parseComponent(child)
            else:
                raise ConfigError("unexpected 'flow' node: %s" % child.nodeName)

            flow.components[component.name] = component
        return flow

    def parseManager(self, node):
        # <manager>
        #   <component>
        #   ...
        # </manager>

        manager = ConfigEntryManager()
        for child in node.childNodes:
            if (child.nodeType == Node.TEXT_NODE or
                child.nodeType == Node.COMMENT_NODE):
                continue
            
            if child.nodeName != "component":
                raise ConfigError("unexpected 'manager' node: %s" % child.nodeName)
            if manager.bouncer:
                raise ConfigError("<manager> section can only have one <component>")
            manager.bouncer = self.parseComponent(child)
            # FIXME: assert that it is a bouncer !
        return manager
     
    def DEPRECATED_parse_workers(self, node):
        # <workers policy="password/anonymous">
        #     <worker name="..." password=""/>
        # </workers>

        if not node.hasAttribute('policy'):
            raise ConfigError("<workers> must have a policy attribute")

        policy = str(node.getAttribute('policy'))

        if policy not in ('password', 'anonymous'):
            raise ConfigError("policy for <workers> must be password or anonymous")
            
        
        workers = []
        for child in node.childNodes:
            if (child.nodeType == Node.TEXT_NODE or
                child.nodeType == Node.COMMENT_NODE):
                continue
            
            if child.nodeName != "worker":
                raise ConfigError, "unexpected node: %r" % child
        
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

    def get_long_value(self, nodes):
        return [long(subnode.childNodes[0].data) for subnode in nodes]

    def get_bool_value(self, nodes):
        valid = ['True', 'true', '1', 'Yes', 'yes']
        return [subnode.childNodes[0].data in valid for subnode in nodes]

    def get_string_value(self, nodes):
        values = []
        for subnode in nodes:
            data = str(subnode.childNodes[0].data)
            if '\n' in data:
                parts = [x.strip() for x in data.split('\n')]
                data = ' '.join(parts)
            values.append(data)

        return values

    def get_raw_string_value(self, nodes):
        values = []
        for subnode in nodes:
            data = str(subnode.childNodes[0].data)
            values.append(data)

        string = "".join(values)
        return [string, ]
     
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
        # XXX: We might end up calling float(), which breaks
        #      when using LC_NUMERIC when it is not C
        import locale
        locale.setlocale(locale.LC_NUMERIC, "C")

        config = {}
        for definition in properties:
            name = definition.name

            nodes = []
            for subnode in node.childNodes:
                if subnode.nodeName == name:
                    nodes.append(subnode)
                
            if definition.isRequired() and not nodes:
                raise ConfigError("'%s' is required but not specified" % name)

            if not definition.multiple and len(nodes) > 1:
                raise ConfigError("multiple value specified but not allowed")

            type = definition.type
            if type == 'string':
                value = self.get_string_value(nodes)
            elif type == 'rawstring':
                value = self.get_raw_string_value(nodes)
            elif type == 'int':
                value = self.get_int_value(nodes)
            elif type == 'long':
                value = self.get_long_value(nodes)
            elif type == 'bool':
                value = self.get_bool_value(nodes)
            elif type == 'float':
                value = self.get_float_value(nodes)
            elif type == 'xml':
                value = self.get_xml_value(nodes)
            else:
                raise ConfigError("invalid property type: %s" % type)

            if value == []:
                continue
            
            if not definition.multiple:
                value = value[0]
            
            config[name] = value
            
        return config
