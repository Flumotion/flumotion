# -*- Mode: Python; test-case-name: flumotion.test.test_config -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

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
    def __init__(self, name, host, port, transport, certificate, bouncer,
            fludebug):
        self.name = name
        self.host = host
        self.port = port
        self.transport = transport
        self.certificate = certificate
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
        self._repr = None

        try:
            if filename != None:
                self.debug('Loading configuration file `%s\'' % filename)
                self.doc = minidom.parse(filename)
                self._repr = filename
            else:
                self.debug('Loading string file `%s\'' % string)
                self.doc = minidom.parseString(string)
                self._repr = "<string>"
        except expat.ExpatError, e:
            filestr = "<no filename>"
            if filename:
                filestr = filename
                
            raise ConfigError("XML parser error in file %s: %s" % (
                filestr,e))
        
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
        #   <source>*
        #   <property name="name">value</property>*
        # </component>
        
        if not node.hasAttribute('name'):
            raise ConfigError("<component> must have a name attribute")
        if not node.hasAttribute('type'):
            raise ConfigError("<component> must have a type attribute")

        type = str(node.getAttribute('type'))
        name = str(node.getAttribute('name'))

        worker = None
        if node.hasAttribute('worker'):
            worker = str(node.getAttribute('worker'))

        # FIXME: flumotion-launch does not define parent, type, or
        # avatarId. Thus they don't appear to be necessary, like they're
        # just extra info for the manager or so. Figure out what's going
        # on with that. Also, -launch treats clock-master differently.
        config = { 'name': name,
                   'parent': parent,
                   'type': type,
                   'avatarId': common.componentPath(name, parent)
                 }

        try:
            defs = registry.getRegistry().getComponent(type)
        except KeyError:
            raise errors.UnknownComponentError(
                "unknown component type: %s" % type)
        
        possible_node_names = ['source', 'clock-master', 'property']
        for subnode in node.childNodes:
            if subnode.nodeType == Node.COMMENT_NODE:
                continue
            elif subnode.nodeType == Node.TEXT_NODE:
                # fixme: should check here that the string is empty
                # should just make a dtd, gah
                continue
            elif subnode.nodeName not in possible_node_names:
                raise ConfigError("Invalid subnode of <component>: %s"
                                  % subnode.nodeName)

        # let the component know what its feeds should be called
        config['feed'] = defs.getFeeders()

        sources = self._parseSources(node, defs)
        if sources:
            config['source'] = sources

        config['clock-master'] = self._parseClockMaster(node)

        properties = defs.getProperties()

        self.debug('Parsing component: %s' % name)
        config['properties'] = self._parseProperties(node, name, type,
            properties)

        # fixme: all of the information except the worker is in the
        # config dict: why?
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

        # handle master clock selection
        masters = [x for x in flow.components.values()
                     if x.config['clock-master']]
        if len(masters) > 1:
            raise ConfigError("Multiple clock masters in flow %s: %r"
                              % (name, masters))

        need_sync = [(x.defs.getClockPriority(), x)
                     for x in flow.components.values()
                     if x.defs.getNeedsSynchronization()]
        need_sync.sort()
        need_sync = [x[1] for x in need_sync]

        if need_sync:
            if masters:
                master = masters[0]
            else:
                master = need_sync[-1]

            masterAvatarId = master.config['avatarId']
            self.info("Setting %s as clock master" % masterAvatarId)

            for c in need_sync:
                c.config['clock-master'] = masterAvatarId
        elif masters:
            self.info('master clock specified, but no synchronization '
                      'necessary -- ignoring')
            masters[0].config['clock-master'] = None

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
        certificate = None
        bouncer = None
        fludebug = None

        if node.hasAttribute('name'):
            name = str(node.getAttribute('name'))

        for child in node.childNodes:
            if (child.nodeType == Node.TEXT_NODE or
                child.nodeType == Node.COMMENT_NODE):
                continue
            
            if child.nodeName == "host":
                host = self._nodeGetString("host", child)
            elif child.nodeName == "port":
                port = self._nodeGetInt("port", child)
            elif child.nodeName == "transport":
                transport = self._nodeGetString("transport", child)
                if not transport in ('tcp', 'ssl'):
                    raise ConfigError("<transport> must be ssl or tcp")
            elif child.nodeName == "certificate":
                certificate = self._nodeGetString("certificate", child)
            elif child.nodeName == "component":
                if noRegistry:
                    continue

                if bouncer:
                    raise ConfigError(
                        "<manager> section can only have one <component>")
                bouncer = self._parseComponent(child, 'manager')
            elif child.nodeName == "debug":
                fludebug = self._nodeGetString("debug", child)
            else:
                raise ConfigError("unexpected '%s' node: %s" % (
                    node.nodeName, child.nodeName))

            # FIXME: assert that it is a bouncer !

        return ConfigEntryManager(name, host, port, transport, certificate,
            bouncer, fludebug)

    def _nodeGetInt(self, name, node):
        try:
            value = int(node.firstChild.nodeValue)
        except ValueError:
            raise ConfigError("<%s> value must be an integer" % name)
        except AttributeError:
            raise ConfigError("<%s> value not specified" % name)
        return value

    def _nodeGetString(self, name, node):
        try:
            value = str(node.firstChild.nodeValue)
        except AttributeError:
            raise ConfigError("<%s> value not specified" % name)
        return value

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

    def _parseSources(self, node, defs):
        # <source>feeding-component:feed-name</source>
        eaters = dict([(x.getName(), x) for x in defs.getEaters()])

        nodes = []
        for subnode in node.childNodes:
            if subnode.nodeName == 'source':
                nodes.append(subnode)
        strings = self._get_string_value(nodes)

        # at this point we don't support assigning certain sources to
        # certain eaters -- a problem to fix later. for now take the
        # union of the properties.
        required = True in [x.getRequired() for x in eaters.values()]
        multiple = True in [x.getMultiple() for x in eaters.values()]

        if len(strings) == 0 and required:
            raise ConfigError("Component %s wants to eat on %s, but no "
                              "source specified"
                              % (node.nodeName, eaters.keys()[0]))
        elif len(strings) > 1 and not multiple:
            raise ConfigError("Component %s does not support multiple "
                              "sources feeding %s (%r)"
                              % (node.nodeName, eaters.keys()[0], strings))

        return strings
            
    def _parseClockMaster(self, node):
        nodes = []
        for subnode in node.childNodes:
            if subnode.nodeName == 'clock-master':
                nodes.append(subnode)
        bools = self._get_bool_value(nodes)

        if len(bools) > 1:
            raise ConfigError("Only one <clock-master> node allowed")

        if bools and bools[0]:
            return True # will get changed to avatarId in parseFlow
        else:
            return None
            
    def _parseProperties(self, node, componentName, type, properties):
        # XXX: We might end up calling float(), which breaks
        #      when using LC_NUMERIC when it is not C -- only in python
        #      2.3 though, no prob in 2.4
        import locale
        locale.setlocale(locale.LC_NUMERIC, "C")

        properties_given = {}
        for subnode in node.childNodes:
            if subnode.nodeName == 'property':
                if not subnode.hasAttribute('name'):
                    raise ConfigError(
                        "%s: <property> must have a name attribute" %
                        componentName)
                name = subnode.getAttribute('name')
                if not name in properties_given:
                    properties_given[name] = []
                properties_given[name].append(subnode)
                
        property_specs = dict([(x.name, x) for x in properties])

        config = {}
        for name, nodes in properties_given.items():
            if not name in property_specs:
                    raise ConfigError(
                        "%s: %s: unknown property" % (
                            componentName, name))
                
            definition = property_specs[name]

            if not definition.multiple and len(nodes) > 1:
                raise ConfigError(
                    "%s: %s: multiple value specified but not allowed" % (
                        componentName, name))

            parsers = {'string': self._get_string_value,
                       'rawstring': self._get_raw_string_value,
                       'int': self._get_int_value,
                       'long': self._get_long_value,
                       'bool': self._get_bool_value,
                       'float': self._get_float_value,
                       'xml': self._get_xml_value,
                       'fraction': self._get_fraction_value}
                       
            if not definition.type in parsers:
                raise ConfigError(
                    "%s: %s: invalid property type %s" % (
                        componentName, name, definition.type))
                
            value = parsers[definition.type](nodes)

            if value == []:
                continue
            
            if not definition.multiple:
                value = value[0]
            
            config[name] = value
            
        for name, definition in property_specs.items():
            if definition.isRequired() and not name in config:
                raise ConfigError(
                    "%s: %s: required but unspecified property" % (
                        componentName, name))

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
