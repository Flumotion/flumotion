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

import os
from xml.dom import minidom, Node
from xml.parsers import expat

from twisted.python import reflect 

from flumotion.common import log, errors, common, registry, fxml
from flumotion.configure import configure

from errors import ConfigError, ComponentWorkerConfigError

def _ignore(*args):
    pass

def buildEatersDict(eatersList, eaterDefs):
    eaters = {}
    for eater, feedId in eatersList:
        if eater is None:
            # cope with old <source> entries
            eater = eaterDefs[0].getName()
        feeders = eaters.get(eater, [])
        if feedId in feeders:
            raise ConfigError("Already have a feedId %s eating "
                              "from %s", feedId, eater)
        feeders.append(feedId)
        eaters[eater] = feeders
    for e in eaterDefs:
        eater = e.getName()
        if e.getRequired() and not eater in eaters:
            raise ConfigError("Component wants to eat on %s,"
                              " but no feeders specified."
                              % (e.getName(),))
        if not e.getMultiple() and len(eaters.get(eater, [])) > 1:
            raise ConfigError("Component does not support multiple "
                              "sources feeding %s (%r)"
                              % (eater, eaters[eater]))
    return eaters        

def parsePropertyValue(propName, type, value):
    def tryStr(s):
        try:
            return str(s)
        except UnicodeEncodeError:
            return s
    def strWithoutNewlines(s):
        return tryStr(' '.join([x.strip() for x in s.split('\n')]))
    def fraction(s):
        def frac(num, denom=1):
            return int(num), int(denom)
        return frac(*s.split('/'))

    try:
        # yay!
        return {'string': strWithoutNewlines,
                'rawstring': tryStr,
                'int': int,
                'long': long,
                'bool': common.strToBool,
                'float': float,
                'fraction': fraction}[type](value)
    except KeyError:
        raise ConfigError("unknown type '%s' for property %s"
                          % (type, propName))

def buildPropertyDict(propertyList, propertySpecList):
    ret = {}
    prop_specs = dict([(x.name, x) for x in propertySpecList])
    for name, value in propertyList:
        if not name in prop_specs:
            raise ConfigError('unknown property %s' % (name,))
        definition = prop_specs[name]

        parsed = parsePropertyValue(name, definition.type, value)
        if definition.multiple:
            vals = ret.get(name, [])
            vals.append(parsed)
            ret[name] = vals
        else:
            if name in ret:
                raise ConfigError("multiple value specified but not "
                                  "allowed for property %s" % (name,))
            ret[name] = parsed

    for name, definition in prop_specs.items():
        if definition.isRequired() and not name in ret:
            raise ConfigError("required but unspecified property %s"
                              % (name,))
    return ret

def buildPlugsSet(plugsList, sockets):
    ret = {}
    for socket in sockets:
        ret[socket] = []
    for type, propertyList in plugsList:
        plug = ConfigEntryPlug(type, propertyList)
        if plug.socket not in ret:
            raise ConfigError("Unsupported socket type: %s"
                              % (plug.socket,))
        ret[plug.socket].append({'type': plug.type, 'socket': plug.socket,
                                 'properties': plug.properties})
    return ret

class ConfigEntryPlug(log.Loggable):
    "I represent a <plug> entry in a planet config file"
    def __init__(self, type, propertyList):
        try:
            defs = registry.getRegistry().getPlug(type)
        except KeyError:
            raise ConfigError("unknown plug type: %s" % type)

        self.type = type
        self.socket = defs.getSocket()
        self.properties = buildPropertyDict(propertyList,
                                            defs.getProperties())

class ConfigEntryComponent(log.Loggable):
    "I represent a <component> entry in a planet config file"
    nice = 0
    logCategory = 'config'

    def __init__(self, name, parent, type, propertyList, plugList,
                 worker, eatersList, isClockMaster, version):
        self.name = name
        self.parent = parent
        self.type = type
        self.worker = worker
        self.defs = registry.getRegistry().getComponent(self.type)
        self.config = self._buildConfig(propertyList, plugList,
                                        eatersList, isClockMaster,
                                        version)

    def _buildVersionTuple(self, version):
        if version is None:
            return configure.versionTuple
        elif isinstance(version, tuple):
            assert len(version) == 4
            return version
        elif isinstance(version, str):
            try:
                def parse(maj, min, mic, nan=0):
                    return maj, min, mic, nan
                return parse(*map(int, version.split('.')))
            except:
                raise ComponentWorkerConfigError("<component> version not"
                                                 " parseable")
        raise ComponentWorkerConfigError("<component> version not"
                                         " parseable")
        
    def _buildConfig(self, propertyList, plugsList, eatersList,
                     isClockMaster, version):
        """
        Build a component configuration dictionary.
        """
        # clock-master should be either an avatar id or None.
        # It can temporarily be set to True, and the flow parsing
        # code will change it to the avatar id or None.
        config = {'name': self.name,
                  'parent': self.parent,
                  'type': self.type,
                  'avatarId': common.componentId(self.parent, self.name),
                  'version': self._buildVersionTuple(version),
                  'clock-master': isClockMaster or None,
                  'feed': self.defs.getFeeders(),
                  'properties': buildPropertyDict(propertyList,
                                                  self.defs.getProperties()),
                  'plugs': buildPlugsSet(plugsList,
                                         self.defs.getSockets()),
                  'eater': buildEatersDict(eatersList,
                                           self.defs.getEaters()),
                  'source': [feedId for eater, feedId in eatersList]}

        if not config['source']:
            # preserve old behavior
            del config['source']

        return config

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
    def __init__(self, name, components):
        self.name = name
        self.components = {}
        for c in components:
            if c.name in self.components:
                raise ConfigError('flow %s already has component named %s'
                                  % (name, c.name))
            self.components[c.name] = c

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
    parserError = ConfigError

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

    def parseTextNode(self, node, type=str):
        ret = []
        for child in node.childNodes:
            if child.nodeType == Node.TEXT_NODE:
                ret.append(child.data)
            elif child.nodeType == Node.COMMENT_NODE:
                continue
            else:
                raise ConfigError('unexpected non-text content of %r: %r'
                                  % (node, child))
        try:
            return type(''.join(ret))
        except Exception, e:
            raise ConfigError('failed to parse %s as %s: %s', node,
                              type, log.getExceptionMessage(e))

    def parsePlugs(self, node):
        # <plugs>
        #  <plug>
        # returns: list of (socket, type, properties)
        self.checkAttributes(node)

        plugs = []
        def parsePlug(node):
            # <plug socket=... type=...>
            #   <property>
            # FIXME: is it even necessary to have socket specified?
            # seems not
            socket, type = self.parseAttributes(node, ('socket', 'type'))
            properties = []
            parsers = {'property': (self._parseProperty,
                                    properties.append)}
            self.parseFromTable(node, parsers)
            return type, properties

        parsers = {'plug': (parsePlug, plugs.append)}
        self.parseFromTable(node, parsers)
        return plugs

    def parseComponent(self, node, parent, isFeedComponent,
                       needsWorker):
        """
        Parse a <component></component> block.

        @rtype: L{ConfigEntryComponent}
        """
        # <component name="..." type="..." worker="...">
        #   <source>...</source>* (deprecated)
        #   <eater name="...">...</eater>*
        #   <property name="name">value</property>*
        #   <clock-master>...</clock-master>?
        #   <plugs>...</plugs>*
        # </component>
        
        attrs = (('name', 'type'), ('worker', 'version',))
        name, type, worker, version = self.parseAttributes(node, *attrs)
        if needsWorker and not worker:
            raise ConfigError('component %s does not specify the worker '
                              'that it is to run on' % (name,))
        elif worker and not needsWorker:
            raise ConfigError('component %s specifies a worker to run '
                              'on, but does not need a worker' % (name,))

        properties = []
        plugs = []
        eaters = []
        clockmasters = []
        sources = []
        
        def parseBool(node):
            return self.parseTextNode(node, common.strToBool)
        parsers = {'property': (self._parseProperty, properties.append),
                   'plugs': (self.parsePlugs, plugs.extend)}

        if isFeedComponent:
            parsers.update({'eater': (self._parseEater, eaters.extend),
                            'clock-master': (parseBool, clockmasters.append),
                            'source': (self.parseTextNode, sources.append)})

        self.parseFromTable(node, parsers)

        if len(clockmasters) == 0:
            isClockMaster = None
        elif len(clockmasters) == 1:
            isClockMaster = clockmasters[0]
        else:
            raise ConfigError("Only one <clock-master> node allowed")

        for feedId in sources:
            # map old <source> nodes to new <eater> nodes
            eaters.append((None, feedId))

        return ConfigEntryComponent(name, parent, type, properties,
                                    plugs, worker, eaters,
                                    isClockMaster, version)

    def _parseEater(self, node):
        # <eater name="eater-name">
        #   <feed>feeding-component:feed-name</feed>*
        # </eater>
        name, = self.parseAttributes(node, ('name',))
        feedIds = []
        parsers = {'feed': (self.parseTextNode, feedIds.append)}
        self.parseFromTable(node, parsers)
        return [(name, feedId) for feedId in feedIds]

    def _parseProperty(self, node):
        name, = self.parseAttributes(node, ('name',))
        return name, self.parseTextNode(node, lambda x: x)

# FIXME: rename to PlanetConfigParser or something (should include the
# word 'planet' in the name)
class FlumotionConfigXML(BaseConfigParser):
    """
    I represent a planet configuration file for Flumotion.

    @ivar atmosphere: A L{ConfigEntryAtmosphere}, filled in when parse() is
                      called.
    @ivar flows:      A list of L{ConfigEntryFlow}, filled in when parse() is
                      called.
    """
    logCategory = 'config'

    def __init__(self, file):
        BaseConfigParser.__init__(self, file)

        self.flows = []
        self.atmosphere = ConfigEntryAtmosphere()
        
    def parse(self):
        # <planet>
        #     <manager>?
        #     <atmosphere>*
        #     <flow>*
        # </planet>
        root = self.doc.documentElement
        if root.nodeName != 'planet':
            raise ConfigError("unexpected root node': %s" % root.nodeName)
        
        parsers = {'atmosphere': (self._parseAtmosphere,
                                  self.atmosphere.components.update),
                   'flow': (self._parseFlow,
                            self.flows.append),
                   'manager': (_ignore, _ignore)}
        self.parseFromTable(root, parsers)

    def _parseAtmosphere(self, node):
        # <atmosphere>
        #   <component>
        #   ...
        # </atmosphere>
        ret = {}
        def parseComponent(node):
            return self.parseComponent(node, 'atmosphere', False, True)
        def gotComponent(comp):
            ret[comp.name] = comp
        parsers = {'component': (parseComponent, gotComponent)}
        self.parseFromTable(node, parsers)
        return ret
     
    def _parseFlow(self, node):
        # <flow name="...">
        #   <component>
        #   ...
        # </flow>
        # "name" cannot be atmosphere or manager
        name, = self.parseAttributes(node, ('name',))
        if name == 'atmosphere':
            raise ConfigError("<flow> cannot have 'atmosphere' as name")
        if name == 'manager':
            raise ConfigError("<flow> cannot have 'manager' as name")

        components = []
        def parseComponent(node):
            return self.parseComponent(node, name, True, True)
        parsers = {'component': (parseComponent, components.append)}
        self.parseFromTable(node, parsers)

        # handle master clock selection; probably should be done in the
        # manager in persistent "flow" objects rather than here in the
        # config
        masters = [x for x in components if x.config['clock-master']]
        if len(masters) > 1:
            raise ConfigError("Multiple clock masters in flow %s: %r"
                              % (name, masters))

        need_sync = [(x.defs.getClockPriority(), x) for x in components
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

        return ConfigEntryFlow(name, components)

    # FIXME: remove, this is only used by the tests
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

# FIXME: manager config and flow configs are currently conflated in the
# planet config files; need to separate.
class ManagerConfigParser(BaseConfigParser):
    """
    I parse manager configuration out of a planet configuration file.

    @ivar manager:    A L{ConfigEntryManager} containing options for the manager
                      section, filled in at construction time.
    """
    logCategory = 'config'

    MANAGER_SOCKETS = \
        ['flumotion.component.plugs.adminaction.AdminAction',
         'flumotion.component.plugs.lifecycle.ManagerLifecycle',
         'flumotion.component.plugs.identity.IdentityProvider']

    def __init__(self, file):
        BaseConfigParser.__init__(self, file)

        # the base config: host, port, etc
        self.manager = None

        # the bouncer ConfigEntryComponent
        self.bouncer = None

        self.plugs = {}
        for socket in self.MANAGER_SOCKETS:
            self.plugs[socket] = []

        self._parseParameters()
        
    def _parseParameters(self):
        root = self.doc.documentElement
        if not root.nodeName == 'planet':
            raise ConfigError("unexpected root node': %s" % root.nodeName)
        
        parsers = {'atmosphere': (_ignore, _ignore),
                   'flow': (_ignore, _ignore),
                   'manager': (lambda n: self._parseManagerWithoutRegistry(n),
                               lambda v: setattr(self, 'manager', v))}
        self.parseFromTable(root, parsers)

    def _parseManagerWithoutRegistry(self, node):
        # We parse without asking for a registry so the registry doesn't
        # verify before knowing the debug level
        name = self.parseAttributes(node, (), ('name',))
        ret = ConfigEntryManager(name, None, None, None, None, None,
                                 None, self.plugs)

        def simpleparse(proc):
            return lambda node: self.parseTextNode(node, proc)
        def recordval(k):
            def record(v):
                if getattr(ret, k):
                    raise ConfigError('duplicate %s: %s'
                                      % (k, getattr(ret, k)))
                setattr(ret, k, v)
            return record
        def enum(*allowed):
            def eparse(v):
                v = str(v)
                if v not in allowed:
                    raise ConfigError('unknown value %s (should be '
                                      'one of %r)' % (v, allowed))
                return v
            return eparse

        parsers = {'host': (simpleparse(str), recordval('host')),
                   'port': (simpleparse(int), recordval('port')),
                   'transport': (simpleparse(enum('tcp', 'ssl')),
                                 recordval('transport')), 
                   'certificate': (simpleparse(str), recordval('certificate')),
                   'component': (_ignore, _ignore),
                   'plugs': (_ignore, _ignore),
                   'debug': (simpleparse(str), recordval('fludebug'))}
        self.parseFromTable(node, parsers)
        return ret

    def _parseManagerWithRegistry(self, node):
        def parsecomponent(node):
            return self.parseComponent(node, 'manager', False, False)
        def gotcomponent(val):
            if self.bouncer is not None:
                raise ConfigError('can only have one bouncer '
                                  '(%s is superfluous)' % val.name)
            # FIXME: assert that it is a bouncer !
            self.bouncer = val
        def parseplugs(node):
            return buildPlugsSet(self.parsePlugs(node),
                                 self.MANAGER_SOCKETS)
        def gotplugs(newplugs):
            for socket in self.plugs:
                self.plugs[socket].extend(newplugs[socket])

        parsers = {'host': (_ignore, _ignore),
                   'port': (_ignore, _ignore),
                   'transport': (_ignore, _ignore),
                   'certificate': (_ignore, _ignore),
                   'component': (parsecomponent, gotcomponent),
                   'plugs': (parseplugs, gotplugs),
                   'debug': (_ignore, _ignore)}
        self.parseFromTable(node, parsers)
        return None

    def parseBouncerAndPlugs(self):
        # <planet>
        #     <manager>?
        #     <atmosphere>*
        #     <flow>*
        # </planet>
        root = self.doc.documentElement
        if not root.nodeName == 'planet':
            raise ConfigError("unexpected root node': %s" % root.nodeName)
        
        parsers = {'atmosphere': (_ignore, _ignore),
                   'flow': (_ignore, _ignore),
                   'manager': (self._parseManagerWithRegistry, _ignore)}
        self.parseFromTable(root, parsers)

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
            return buildPlugsSet(self.parsePlugs(node),
                                 self.plugs.keys())
        def addplugs(plugs):
            for socket in plugs:
                self.plugs[socket].extend(plugs[socket])
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
