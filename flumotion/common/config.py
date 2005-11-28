# -*- Mode: Python; test-case-name: flumotion.test.test_config -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
parsing of configuration files
"""

import os
from xml.dom import minidom, Node
from xml.parsers import expat

from twisted.python import reflect 

from flumotion.common import log, errors, common, registry

# FIXME: move this to errors and adapt everywhere
from errors import ConfigError

class ConfigEntryComponent(log.Loggable):
    "I represent a <component> entry in a planet config file"
    nice = 0
    logCategory = 'config'
    def __init__(self, name, parent, type, config, defs, worker):
        self.name = name
        self.parent = parent
        self.type = type
        self.config = config
        self.defs = defs
        self.worker = worker
        
    def getType(self):
        return self.type
    
    def getName(self):
        return self.name

    def getParent(self):
        return self.parent

    def getConfigDict(self):
        return self.config

    def getWorker(self):
        return self.worker

class ConfigEntryFlow:
    "I represent a <flow> entry in a planet config file"
    def __init__(self, name):
        self.name = name
        self.components = {}

class ConfigEntryManager:
    "I represent a <manager> entry in a planet config file"
    def __init__(self, name, host, port, transport, bouncer, fludebug):
        self.name = name
        self.host = host
        self.port = port
        self.transport = transport
        self.bouncer = bouncer
        self.fludebug = fludebug

class ConfigEntryAtmosphere:
    "I represent a <atmosphere> entry in a planet config file"
    def __init__(self):
        self.components = {}

# FIXME: rename
class FlumotionConfigXML(log.Loggable):
    """
    I represent a planet configuration file for Flumotion.

    @ivar manager:    A L{ConfigEntryManager} containing options for the manager
                      section, filled in at construction time.
    @ivar atmosphere: A L{ConfigEntryAtmosphere}, filled in when parse() is
                      called.
    @ivar flows:      A list of L{ConfigEntryFlow}, filled in when parse() is
                      called.
    """
    logCategory = 'config'

    def __init__(self, filename, string=None):
        self.flows = []
        self.manager = None
        self.atmosphere = None

        try:
            if filename != None:
                self.debug('Loading configuration file `%s\'' % filename)
                self.doc = minidom.parse(filename)
            else:
                self.debug('Loading string file `%s\'' % string)
                self.doc = minidom.parseString(string)
        except expat.ExpatError, e:
            raise ConfigError("XML parser error: %s" % e)
        
        if filename != None:
            self.path = os.path.split(filename)[0]
        else:
            self.path = None
            
        # We parse without asking for a registry so the registry doesn't
        # verify before knowing the debug level
        self.parse(noRegistry=True)
        
    def getPath(self):
        return self.path

    def export(self):
        return self.doc.toxml()

    def parse(self, noRegistry=False):
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

            if noRegistry and node.nodeName != 'manager':
                continue
                
            if node.nodeName == 'atmosphere':
                entry = self._parseAtmosphere(node)
                self.atmosphere = entry
            elif node.nodeName == 'flow':
                entry = self._parseFlow(node)
                self.flows.append(entry)
            elif node.nodeName == 'manager':
                entry = self._parseManager(node, noRegistry)
                self.manager = entry
            else:
                raise ConfigError("unexpected node under 'planet': %s" % node.nodeName)

    def _parseAtmosphere(self, node):
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
                component = self._parseComponent(child, 'atmosphere')
            else:
                raise ConfigError("unexpected 'atmosphere' node: %s" % child.nodeName)

            atmosphere.components[component.name] = component
        return atmosphere
     
    def _parseComponent(self, node, parent):
        """
        Parse a <component></component> block.

        @rtype: L{ConfigEntryComponent}
        """
        # <component name="..." type="..." worker="">
        #   <feed>*
        #   <source>*
        #   <prop1>*
        #   ...
        # FIXME <propN>... should be in <properties> (#286)
        
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
            defs = registry.getRegistry().getComponent(type)
        except KeyError:
            raise errors.UnknownComponentError(
                "unknown component type: %s" % type)
        
        properties = defs.getProperties()

        self.debug('Parsing component: %s' % name)
        options = self._parseProperties(node, type, properties)

        feeds = self._parseFeeds(node, defs)
        sources = self._parseSources(node, defs)

        # FIXME: this shouldn't be necessary in the future
        if feeds:
            options['feed'] = feeds
        if sources:
            options['source'] = sources

        feeders = defs.getFeeders()
        if feeders:
            if not 'feed' in options:
                # assert that the old code works the way it should; when
                # we stop writing <feed> entries this can go
                raise ConfigError("no <feed> entries for component %s", name)
        for feeder in feeders:
            if not feeder in options['feed']:
                # assert that the old code works the way it should; when
                # we stop writing <feed> entries this can go
                raise ConfigError("component %s missing <feed> entry for %s",
                    name, feeder)

        # FIXME: 'name', 'parent', 'type', 'feed', and 'source' should
        # be in a different namespace from the other properties
        config = { 'name': name,
                   'parent': parent,
                   'type': type }
        config.update(options)

        return ConfigEntryComponent(name, parent, type, config, defs, worker)

    def _parseFlow(self, node):
        # <flow name="...">
        #   <component>
        #   ...
        # </flow>
        # "name" cannot be atmosphere or manager

        if not node.hasAttribute('name'):
            raise ConfigError("<flow> must have a name attribute")

        name = str(node.getAttribute('name'))
        if name == 'atmosphere':
            raise ConfigError("<flow> cannot have 'atmosphere' as name")
        if name == 'manager':
            raise ConfigError("<flow> cannot have 'manager' as name")

        flow = ConfigEntryFlow(name)

        for child in node.childNodes:
            if (child.nodeType == Node.TEXT_NODE or
                child.nodeType == Node.COMMENT_NODE):
                continue
            
            if child.nodeName == "component":
                component = self._parseComponent(child, name)
            else:
                raise ConfigError("unexpected 'flow' node: %s" % child.nodeName)

            flow.components[component.name] = component
        return flow

    def _parseManager(self, node, noRegistry=False):
        # <manager>
        #   <component>
        #   ...
        # </manager>

        name = None
        host = None
        port = None
        transport = None
        bouncer = None
        fludebug = None

        if node.hasAttribute('name'):
            name = str(node.getAttribute('name'))

        for child in node.childNodes:
            if (child.nodeType == Node.TEXT_NODE or
                child.nodeType == Node.COMMENT_NODE):
                continue
            
            if child.nodeName == "host":
                host = str(child.firstChild.nodeValue)
            elif child.nodeName == "port":
                try:
                    port = int(child.firstChild.nodeValue)
                except ValueError:
                    raise ConfigError("<port> value must be an integer")
            elif child.nodeName == "transport":
                transport = str(child.firstChild.nodeValue)
                if not transport in ('tcp', 'ssl'):
                    raise ConfigError("<transport> must be ssl or tcp")
            elif child.nodeName == "component":
                if noRegistry:
                    continue

                if bouncer:
                    raise ConfigError("<manager> section can only have one <component>")
                bouncer = self._parseComponent(child, 'manager')
            elif child.nodeName == "debug":
                fludebug = str(child.firstChild.nodeValue)
            else:
                raise ConfigError("unexpected '%s' node: %s" % (node.nodeName, child.nodeName))

            # FIXME: assert that it is a bouncer !

        return ConfigEntryManager(name, host, port, transport, bouncer, fludebug)

    def _get_float_value(self, nodes):
        return [float(subnode.childNodes[0].data) for subnode in nodes]

    def _get_int_value(self, nodes):
        return [int(subnode.childNodes[0].data) for subnode in nodes]

    def _get_long_value(self, nodes):
        return [long(subnode.childNodes[0].data) for subnode in nodes]

    def _get_bool_value(self, nodes):
        valid = ['True', 'true', '1', 'Yes', 'yes']
        return [subnode.childNodes[0].data in valid for subnode in nodes]

    def _get_string_value(self, nodes):
        values = []
        for subnode in nodes:
            data = subnode.childNodes[0].data
            # libxml always gives us unicode, even when we encode values
            # as strings. try to make normal strings again, unless that
            # isn't possible.
            try:
                data = str(data)
            except UnicodeEncodeError:
                pass
            if '\n' in data:
                parts = [x.strip() for x in data.split('\n')]
                data = ' '.join(parts)
            values.append(data)

        return values

    def _get_raw_string_value(self, nodes):
        values = []
        for subnode in nodes:
            data = str(subnode.childNodes[0].data)
            values.append(data)

        string = "".join(values)
        return [string, ]
     
    def _get_xml_value(self, nodes):
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

    def _get_fraction_value(self, nodes):
        def fraction_from_string(string):
            parts = string.split('/')
            if not len(parts) == 2:
                raise ConfigError("Invalid fraction: %s", string)
            return (int(parts[0]), int(parts[1]))
        return [fraction_from_string(subnode.childNodes[0].data)
                for subnode in nodes]

    def _parseFeeds(self, node, defs):
        nodes = []
        for subnode in node.childNodes:
            if subnode.nodeName == 'feed':
                nodes.append(subnode)
        feeds = self._get_string_value(nodes)
        for feed in feeds:
            if not feed in defs.getFeeders():
                # should be an error, but flumotion.wizard.save is too
                # dumb right now
                self.warning('Invalid feed for component type %s: %s'
                    % (defs.getType(), feed))
        return feeds

    def _parseSources(self, node, defs):
        nodes = []
        for subnode in node.childNodes:
            if subnode.nodeName == 'source':
                nodes.append(subnode)
        return self._get_string_value(nodes)

    def _parseProperties(self, node, type, properties):
        # XXX: We might end up calling float(), which breaks
        #      when using LC_NUMERIC when it is not C
        import locale
        locale.setlocale(locale.LC_NUMERIC, "C")

        # FIXME: validate nodes, make sure they are all valid properties
        # as well as the other way around

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
                value = self._get_string_value(nodes)
            elif type == 'rawstring':
                value = self._get_raw_string_value(nodes)
            elif type == 'int':
                value = self._get_int_value(nodes)
            elif type == 'long':
                value = self._get_long_value(nodes)
            elif type == 'bool':
                value = self._get_bool_value(nodes)
            elif type == 'float':
                value = self._get_float_value(nodes)
            elif type == 'xml':
                value = self._get_xml_value(nodes)
            elif type == 'fraction':
                value = self._get_fraction_value(nodes)
            else:
                raise ConfigError("invalid property type: %s" % type)

            if value == []:
                continue
            
            if not definition.multiple:
                value = value[0]
            
            config[name] = value
            
        return config

    # FIXME: move to a config base class ?
    def getComponentEntries(self):
        """
        Get all component entries from both atmosphere and all flows
        from the configuration.

        @rtype: dictionary of /parent/name -> L{ConfigEntryComponent}
        """
        entries = {}
        if self.atmosphere and self.atmosphere.components:
            for c in self.atmosphere.components.values():
                path = common.componentPath(c.name, 'atmosphere')
                entries[path] = c
            
        for flowEntry in self.flows:
            for c in flowEntry.components.values():
                path = common.componentPath(c.name, c.parent)
                entries[path] = c

        return entries
