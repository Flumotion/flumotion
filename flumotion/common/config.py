# -*- Mode: Python; test-case-name: flumotion.test.test_config -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

# Config XML FIXME: Make all <property> nodes be children of
# <properties>; it's the only thing standing between now and a
# table-driven, verifying config XML parser

import os
from xml.dom import minidom, Node
from xml.parsers import expat

from twisted.python import reflect 

from flumotion.common import log, errors, common, registry, fxml
from flumotion.configure import configure

from errors import ConfigError, ComponentWorkerConfigError

# all these string values should result in True
BOOL_TRUE_VALUES = ['True', 'true', '1', 'Yes', 'yes']

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
            fludebug, plugs):
        self.name = name
        self.host = host
        self.port = port
        self.transport = transport
        self.certificate = certificate
        self.bouncer = bouncer
        self.fludebug = fludebug
        self.plugs = plugs

class ConfigEntryAtmosphere:
    "I represent a <atmosphere> entry in a planet config file"
    def __init__(self):
        self.components = {}

    def __len__(self):
        return len(self.components)

class BaseConfigParser(fxml.Parser):
    def __init__(self, file):
        """
        @param file: The file to parse, either as an open file object,
        or as the name of a file to open.
        @type  file: str or file.
        """
        self.add(file)

    def add(self, file):
        """
        @param file: The file to parse, either as an open file object,
        or as the name of a file to open.
        @type  file: str or file.
        """
        try:
            self.path = os.path.split(file.name)[0]
        except AttributeError:
            # for file objects without the name attribute, e.g. StringIO
            self.path = None

        try:
            self.doc = self.getRoot(file)
        except fxml.ParserError, e:
            raise ConfigError(e.args[0])

    def getPath(self):
        return self.path

    def export(self):
        return self.doc.toxml()

    def get_float_values(self, nodes):
        return [float(subnode.childNodes[0].data) for subnode in nodes]

    def get_int_values(self, nodes):
        return [int(subnode.childNodes[0].data) for subnode in nodes]

    def get_long_values(self, nodes):
        return [long(subnode.childNodes[0].data) for subnode in nodes]

    def get_bool_values(self, nodes):
        return [subnode.childNodes[0].data in BOOL_TRUE_VALUES \
            for subnode in nodes]

    def get_string_values(self, nodes):
        values = []
        for subnode in nodes:
            try:
                data = subnode.childNodes[0].data
            except IndexError:
                continue
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

    def get_raw_string_values(self, nodes):
        values = []
        for subnode in nodes:
            try:
                data = str(subnode.childNodes[0].data)
                values.append(data)
            except IndexError: # happens on a subnode without childNOdes
                pass

        string = "".join(values)
        return [string, ]
     
    def get_fraction_values(self, nodes):
        def fraction_from_string(string):
            parts = string.split('/')
            if len(parts) == 2:
                return (int(parts[0]), int(parts[1]))
            elif len(parts) == 1:
                return (int(parts[0]), 1)
            else:
                raise ConfigError("Invalid fraction: %s", string)
        return [fraction_from_string(subnode.childNodes[0].data)
                for subnode in nodes]

    def parseProperties(self, node, properties, error):
        """
        Parse a <property>-containing node in a configuration XML file.
        Ignores any subnode not named <property>.

        @param node: The <properties> XML node to parse.
        @type  node: L{xml.dom.Node}
        @param properties: The set of valid properties.
        @type  properties: list of
        L{flumotion.common.registry.RegistryEntryProperty}
        @param error: An exception factory for parsing errors.
        @type  error: Callable that maps str => Exception.

        @returns: The parsed properties, as a dict of name => value.
        Absent optional properties will not appear in the dict.
        """
        # FIXME: non-validating, see first FIXME
        # XXX: We might end up calling float(), which breaks
        #      when using LC_NUMERIC when it is not C -- only in python
        #      2.3 though, no prob in 2.4
        import locale
        locale.setlocale(locale.LC_NUMERIC, "C")

        properties_given = {}
        for subnode in node.childNodes:
            if subnode.nodeName == 'property':
                if not subnode.hasAttribute('name'):
                    raise error("<property> must have a name attribute")
                name = subnode.getAttribute('name')
                if not name in properties_given:
                    properties_given[name] = []
                properties_given[name].append(subnode)
                
        property_specs = dict([(x.name, x) for x in properties])

        config = {}
        for name, nodes in properties_given.items():
            if not name in property_specs:
                raise error("%s: unknown property" % name)
                
            definition = property_specs[name]

            if not definition.multiple and len(nodes) > 1:
                raise error("%s: multiple value specified but not "
                            "allowed" % name)

            parsers = {'string': self.get_string_values,
                       'rawstring': self.get_raw_string_values,
                       'int': self.get_int_values,
                       'long': self.get_long_values,
                       'bool': self.get_bool_values,
                       'float': self.get_float_values,
                       'fraction': self.get_fraction_values}
                       
            if not definition.type in parsers:
                raise error("%s: invalid property type %s"
                            % (name, definition.type))
                
            values = parsers[definition.type](nodes)

            if values == []:
                continue
            
            if not definition.multiple:
                values = values[0]
            
            config[name] = values
            
        for name, definition in property_specs.items():
            if definition.isRequired() and not name in config:
                raise error("%s: required but unspecified property"
                            % name)

        return config

    def parsePlug(self, node):
        # <plug socket=... type=...>
        #   <property>
        socket, type = self.parseAttributes(node, ('socket', 'type'))

        try:
            defs = registry.getRegistry().getPlug(type)
        except KeyError:
            raise ConfigError("unknown plug type: %s" % type)
        
        possible_node_names = ['property']
        for subnode in node.childNodes:
            if (subnode.nodeType == Node.COMMENT_NODE
                or subnode.nodeType == Node.TEXT_NODE):
                continue
            elif subnode.nodeName not in possible_node_names:
                raise ConfigError("Invalid subnode of <plug>: %s"
                                  % subnode.nodeName)

        property_specs = defs.getProperties()
        def err(str):
            return ConfigError('%s: %s' % (type, str))
        properties = self.parseProperties(node, property_specs, err)

        return {'type':type, 'socket':socket, 'properties':properties}

    def parsePlugs(self, node, sockets):
        # <plugs>
        #  <plug>
        # returns: dict of socket -> list of plugs
        # where a plug is 'type'->str, 'socket'->str,
        #  'properties'->dict of properties
        plugs = {}
        for socket in sockets:
            plugs[socket] = []
        def addplug(plug):
            if plug['socket'] not in sockets:
                raise ConfigError("Component does not support "
                                  "sockets of type %s" % plug['socket'])
            plugs[plug['socket']].append(plug)

        parsers = {'plug': (self.parsePlug, addplug)}
        self.parseFromTable(node, parsers)

        return plugs

# FIXME: rename to PlanetConfigParser or something (should include the
# word 'planet' in the name)
class FlumotionConfigXML(BaseConfigParser):
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

    def __init__(self, file):
        BaseConfigParser.__init__(self, file)

        self.flows = []
        self.manager = None
        self.atmosphere = ConfigEntryAtmosphere()

        # We parse without asking for a registry so the registry doesn't
        # verify before knowing the debug level
        self.parse(noRegistry=True)
        
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
                self.atmosphere.components.update(entry)
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

        ret = {}
        for child in node.childNodes:
            if (child.nodeType == Node.TEXT_NODE or
                child.nodeType == Node.COMMENT_NODE):
                continue
            
            if child.nodeName == "component":
                component = self._parseComponent(child, 'atmosphere')
            else:
                raise ConfigError("unexpected 'atmosphere' node: %s" % child.nodeName)

            ret[component.name] = component
        return ret
     
    def _parseComponent(self, node, parent, forManager=False):
        """
        Parse a <component></component> block.

        @rtype: L{ConfigEntryComponent}
        """
        # <component name="..." type="..." worker="...">
        #   <source>*
        #   <property name="name">value</property>*
        # </component>
        
        if not node.hasAttribute('name'):
            raise ConfigError("<component> must have a name attribute")
        if not node.hasAttribute('type'):
            raise ConfigError("<component> must have a type attribute")
        if forManager:
            if node.hasAttribute('worker'):
                raise ComponentWorkerConfigError("components in manager"
                                                 "cannot have workers")
        else:
            if (not node.hasAttribute('worker')
                or not node.getAttribute('worker')):
                # new since 0.3, give it a different error
                raise ComponentWorkerConfigError("<component> must have a"
                                                 " worker attribute")
        version = None
        if node.hasAttribute('version'):
            versionString = node.getAttribute("version")
            try:
                versionList = map(int, versionString.split('.'))
                if len(versionList) == 3:
                    version = tuple(versionList) + (0,)
                elif len(versionList) == 4:
                    version = tuple(versionList)
            except:
                raise ComponentWorkerConfigError("<component> version not"
                                                 " parseable")

        # If we don't have a version at all, use the current version
        if not version:
            version = configure.versionTuple

        type = str(node.getAttribute('type'))
        name = str(node.getAttribute('name'))
        if forManager:
            worker = None
        else:
            worker = str(node.getAttribute('worker'))

        # FIXME: flumotion-launch does not define parent, type, or
        # avatarId. Thus they don't appear to be necessary, like they're
        # just extra info for the manager or so. Figure out what's going
        # on with that. Also, -launch treats clock-master differently.
        config = { 'name': name,
                   'parent': parent,
                   'type': type,
                   'avatarId': common.componentId(parent, name),
                   'version': version
                 }

        try:
            defs = registry.getRegistry().getComponent(type)
        except KeyError:
            raise errors.UnknownComponentError(
                "unknown component type: %s" % type)
        
        possible_node_names = ['source', 'clock-master', 'property',
                               'plugs']
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
        config['plugs'] = self._parsePlugs(node, defs.getSockets())

        properties = defs.getProperties()

        self.debug('Parsing component: %s' % name)
        def err(str):
            return ConfigError('%s: %s' % (name, str))
        config['properties'] = self.parseProperties(node, properties, err)

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
        plugs = {}

        manager_sockets = \
            ['flumotion.component.plugs.adminaction.AdminAction',
             'flumotion.component.plugs.lifecycle.ManagerLifecycle',
             'flumotion.component.plugs.identity.IdentityProvider']
        for k in manager_sockets:
            plugs[k] = []

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
                bouncer = self._parseComponent(child, 'manager',
                                               forManager=True)
            elif child.nodeName == "plugs":
                if noRegistry:
                    continue

                for k, v in self._parsePlugs(node, manager_sockets).items():
                    plugs[k].extend(v)
            elif child.nodeName == "debug":
                fludebug = self._nodeGetString("debug", child)
            else:
                raise ConfigError("unexpected '%s' node: %s" % (
                    node.nodeName, child.nodeName))

            # FIXME: assert that it is a bouncer !

        return ConfigEntryManager(name, host, port, transport, certificate,
            bouncer, fludebug, plugs)

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

    def _parseSources(self, node, defs):
        # <source>feeding-component:feed-name</source>
        eaters = dict([(x.getName(), x) for x in defs.getEaters()])

        nodes = []
        for subnode in node.childNodes:
            if subnode.nodeName == 'source':
                nodes.append(subnode)
        strings = self.get_string_values(nodes)

        # at this point we don't support assigning certain sources to
        # certain eaters -- a problem to fix later. for now take the
        # union of the properties.
        required = [x for x in eaters.values() if x.getRequired()]
        multiple = [x for x in eaters.values() if x.getMultiple()]

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
        bools = self.get_bool_values(nodes)

        if len(bools) > 1:
            raise ConfigError("Only one <clock-master> node allowed")

        if bools and bools[0]:
            return True # will get changed to avatarId in parseFlow
        else:
            return None
            
    def _parsePlugs(self, node, sockets):
        plugs = {}
        for socket in sockets:
            plugs[socket] = []
        for subnode in node.childNodes:
            if subnode.nodeName == 'plugs':
                newplugs = self.parsePlugs(subnode, sockets)
                for socket in sockets:
                    plugs[socket].extend(newplugs[socket])
        return plugs

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
                path = common.componentId('atmosphere', c.name)
                entries[path] = c
            
        for flowEntry in self.flows:
            for c in flowEntry.components.values():
                path = common.componentId(c.parent, c.name)
                entries[path] = c

        return entries

class AdminConfigParser(BaseConfigParser):
    """
    Admin configuration file parser.
    """
    logCategory = 'config'

    def __init__(self, sockets, file):
        """
        @param file: The file to parse, either as an open file object,
        or as the name of a file to open.
        @type  file: str or file.
        """
        self.plugs = {}
        for socket in sockets:
            self.plugs[socket] = []

        # will start the parse via self.add()
        BaseConfigParser.__init__(self, file)
        
    def _parse(self):
        # <admin>
        #   <plugs>
        root = self.doc.documentElement
        if not root.nodeName == 'admin':
            raise ConfigError("unexpected root node': %s" % root.nodeName)
        
        def parseplugs(node):
            return self.parsePlugs(node, self.plugs.keys())
        def addplugs(plugs):
            for socket in plugs:
                try:
                    self.plugs[socket].extend(plugs[socket])
                except KeyError:
                    raise ConfigError("Admin does not support "
                                      "sockets of type %s" % socket)
        parsers = {'plugs': (parseplugs, addplugs)}

        self.parseFromTable(root, parsers)

    def add(self, file):
        """
        @param file: The file to parse, either as an open file object,
        or as the name of a file to open.
        @type  file: str or file.
        """
        BaseConfigParser.add(self, file)
        self._parse()
