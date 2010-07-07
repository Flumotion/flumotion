# -*- Mode: Python; test-case-name: flumotion.test.test_config -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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
parsing of manager configuration files
"""

import operator
import warnings

from flumotion.common import log, errors, common, registry
from flumotion.common import config as fluconfig
from flumotion.common.xmlwriter import cmpComponentType, XMLWriter
from flumotion.configure import configure

__version__ = "$Rev$"


def _ignore(*args):
    pass


def upgradeEaters(conf):

    def parseFeedId(feedId):
        if feedId.find(':') == -1:
            return "%s:default" % feedId
        else:
            return feedId

    eaterConfig = conf.get('eater', {})
    sourceConfig = conf.get('source', [])
    if eaterConfig == {} and sourceConfig != []:
        eaters = registry.getRegistry().getComponent(
            conf.get('type')).getEaters()
        eatersDict = {}
        eatersTuple = [(None, parseFeedId(s)) for s in sourceConfig]
        eatersDict = buildEatersDict(eatersTuple, eaters)
        conf['eater'] = eatersDict

    if sourceConfig:
        sources = []
        for s in sourceConfig:
            sources.append(parseFeedId(s))
        conf['source'] = sources


def upgradeAliases(conf):
    eaters = dict(conf.get('eater', {})) # a copy
    concat = lambda lists: reduce(list.__add__, lists, [])
    if not reduce(lambda x, y: y and isinstance(x, tuple),
                  concat(eaters.values()),
                  True):
        for eater in eaters:
            aliases = []
            feeders = eaters[eater]
            for i in range(len(feeders)):
                val = feeders[i]
                if isinstance(val, tuple):
                    feedId, alias = val
                    aliases.append(val[1])
                else:
                    feedId = val
                    alias = eater
                    while alias in aliases:
                        log.warning('config', "Duplicate alias %s for "
                                    "eater %s, uniquifying", alias, eater)
                        alias += '-bis'
                    aliases.append(alias)
                    feeders[i] = (feedId, val)
        conf['eater'] = eaters

UPGRADERS = [upgradeEaters, upgradeAliases]
CURRENT_VERSION = len(UPGRADERS)


def buildEatersDict(eatersList, eaterDefs):
    """Build a eaters dict suitable for forming part of a component
    config.

    @param eatersList: List of eaters. For example,
                       [('default', 'othercomp:feeder', 'foo')] says
                       that our eater 'default' will be fed by the feed
                       identified by the feedId 'othercomp:feeder', and
                       that it has the alias 'foo'. Alias is optional.
    @type  eatersList: List of (eaterName, feedId, eaterAlias?)
    @param  eaterDefs: The set of allowed and required eaters
    @type   eaterDefs: List of
                       L{flumotion.common.registry.RegistryEntryEater}
    @returns: Dict of eaterName => [(feedId, eaterAlias)]
    """

    def parseEaterTuple(tup):

        def parse(eaterName, feedId, eaterAlias=None):
            if eaterAlias is None:
                eaterAlias = eaterName
            return (eaterName, feedId, eaterAlias)
        return parse(*tup)

    eaters = {}
    for eater, feedId, alias in [parseEaterTuple(t) for t in eatersList]:
        if eater is None:
            if not eaterDefs:
                raise errors.ConfigError(
                    "Feed %r cannot be connected, component has no eaters" %
                    (feedId, ))
            # cope with old <source> entries
            eater = eaterDefs[0].getName()
        if alias is None:
            alias = eater
        feeders = eaters.get(eater, [])
        if feedId in feeders:
            raise errors.ConfigError(
                "Already have a feedId %s eating from %s" %
                (feedId, eater))
        while alias in [a for f, a in feeders]:
            log.debug('config', "Duplicate alias %s for eater %s, "
                      "uniquifying", alias, eater)
            alias += '-bis'

        feeders.append((feedId, alias))
        eaters[eater] = feeders
    for e in eaterDefs:
        eater = e.getName()
        if e.getRequired() and not eater in eaters:
            raise errors.ConfigError("Component wants to eat on %s,"
                              " but no feeders specified."
                              % (e.getName(), ))
        if not e.getMultiple() and len(eaters.get(eater, [])) > 1:
            raise errors.ConfigError("Component does not support multiple "
                              "sources feeding %s (%r)"
                              % (eater, eaters[eater]))
    aliases = reduce(list.__add__,
                     [[x[1] for x in tups] for tups in eaters.values()],
                     [])
    # FIXME: Python 2.3 has no sets
    # if len(aliases) != len(set(aliases):
    while aliases:
        alias = aliases.pop()
        if alias in aliases:
            raise errors.ConfigError("Duplicate alias: %s" % (alias, ))

    return eaters


def buildVirtualFeeds(feedPairs, feeders):
    """Build a virtual feeds dict suitable for forming part of a
    component config.

    @param feedPairs: List of virtual feeds, as name-feederName pairs. For
                      example, [('bar:baz', 'qux')] defines one
                      virtual feed 'bar:baz', which is provided by
                      the component's 'qux' feed.
    @type  feedPairs: List of (feedId, feedName) -- both strings.
    @param feeders: The feeders exported by this component, from the
                    registry.
    @type  feeders: List of str.
    """
    ret = {}
    for virtual, real in feedPairs:
        if real not in feeders:
            raise errors.ConfigError('virtual feed maps to unknown feeder: '
                              '%s -> %s' % (virtual, real))
        try:
            common.parseFeedId(virtual)
        except:
            raise errors.ConfigError('virtual feed name not a valid feedId: %s'
                              % (virtual, ))
        ret[virtual] = real
    return ret


def dictDiff(old, new, onlyOld=None, onlyNew=None, diff=None,
             keyBase=None):
    """Compute the difference between two config dicts.

    @returns: 3 tuple: (onlyOld, onlyNew, diff) where:
              onlyOld is a list of (key, value), representing key-value
              pairs that are only in old;
              onlyNew is a list of (key, value), representing key-value
              pairs that are only in new;
              diff is a list of (key, oldValue, newValue), representing
              keys with different values in old and new; and
              key is a tuple of strings representing the recursive key
              to get to a value. For example, ('foo', 'bar') represents
              the value d['foo']['bar'] on a dict d.
    """
    # key := tuple of strings

    if onlyOld is None:
        onlyOld = [] # key, value
        onlyNew = [] # key, value
        diff = [] # key, oldvalue, newvalue
        keyBase = ()

    for k in old:
        key = (keyBase + (k, ))
        if k not in new:
            onlyOld.append((key, old[k]))
        elif old[k] != new[k]:
            if isinstance(old[k], dict) and isinstance(new[k], dict):
                dictDiff(old[k], new[k], onlyOld, onlyNew, diff, key)
            else:
                diff.append((key, old[k], new[k]))

    for k in new:
        key = (keyBase + (k, ))
        if k not in old:
            onlyNew.append((key, new[k]))

    return onlyOld, onlyNew, diff


def dictDiffMessageString((old, new, diff), oldLabel='old',
                          newLabel='new'):

    def ref(label, k):
        return "%s%s: '%s'" % (label,
                               ''.join(["[%r]" % (subk, )
                                        for subk in k[:-1]]),
                               k[-1])

    out = []
    for k, v in old:
        out.append('Only in %s = %r' % (ref(oldLabel, k), v))
    for k, v in new:
        out.append('Only in %s = %r' % (ref(newLabel, k), v))
    for k, oldv, newv in diff:
        out.append('Value mismatch:')
        out.append('    %s = %r' % (ref(oldLabel, k), oldv))
        out.append('    %s = %r' % (ref(newLabel, k), newv))
    return '\n'.join(out)


class ConfigEntryComponent(log.Loggable):
    "I represent a <component> entry in a planet config file"
    nice = 0
    logCategory = 'config'

    __pychecker__ = 'maxargs=13'

    def __init__(self, name, parent, type, label, propertyList, plugList,
                 worker, eatersList, isClockMaster, project, version,
                 virtualFeeds=None):
        self.name = name
        self.parent = parent
        self.type = type
        self.label = label
        self.worker = worker
        self.defs = registry.getRegistry().getComponent(self.type)
        try:
            self.config = self._buildConfig(propertyList, plugList,
                                            eatersList, isClockMaster,
                                            project, version,
                                            virtualFeeds)
        except errors.ConfigError, e:
            # reuse the original exception?
            e.args = ("While parsing component %s: %s"
                      % (name, log.getExceptionMessage(e)), )
            raise

    def _buildVersionTuple(self, version):
        if version is None:
            return configure.versionTuple
        elif isinstance(version, tuple):
            assert len(version) == 4
            return version
        elif isinstance(version, str):
            try:
                return common.versionStringToTuple(version)
            except:
                raise errors.ConfigError(
                    "<component> version %r not parseable" % version)
        raise errors.ConfigError(
            "<component> version %r not parseable" % version)

    def _buildConfig(self, propertyList, plugsList, eatersList,
                     isClockMaster, project, version, virtualFeeds):
        """
        Build a component configuration dictionary.
        """
        # clock-master should be either an avatar id or None.
        # It can temporarily be set to True, and the flow parsing
        # code will change it to the avatar id or None.
        config = {'name': self.name,
                  'parent': self.parent,
                  'type': self.type,
                  'config-version': CURRENT_VERSION,
                  'avatarId': common.componentId(self.parent, self.name),
                  'project': project or configure.PACKAGE,
                  'version': self._buildVersionTuple(version),
                  'clock-master': isClockMaster or None,
                  'feed': self.defs.getFeeders(),
                  'properties': fluconfig.buildPropertyDict(propertyList,
                                                  self.defs.getProperties()),
                  'plugs': fluconfig.buildPlugsSet(plugsList,
                                         self.defs.getSockets()),
                  'eater': buildEatersDict(eatersList,
                                           self.defs.getEaters()),
                  'source': [tup[1] for tup in eatersList],
                  'virtual-feeds': buildVirtualFeeds(virtualFeeds or [],
                                                     self.defs.getFeeders())}

        if self.label:
            # only add a label attribute if it was specified
            config['label'] = self.label

        if not config['source']:
            # preserve old behavior
            del config['source']
        # FIXME: verify that config['project'] matches the defs

        return config

    def getType(self):
        return self.type

    def getLabel(self):
        return self.label

    def getName(self):
        return self.name

    def getParent(self):
        return self.parent

    def getConfigDict(self):
        return self.config

    def getWorker(self):
        return self.worker


class ConfigEntryFlow:
    """
    I represent a <flow> entry in a planet config file.

    @ivar name:       name of flow
    @type name:       str
    @ivar components: dict of name -> component config
    @type components: dict of str -> L{ConfigEntryComponent}
    """

    def __init__(self, name, components):
        self.name = name
        self.components = {}
        for c in components:
            if c.name in self.components:
                raise errors.ConfigError(
                    'flow %s already has component named %s' % (name, c.name))
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


class FlumotionConfigParser(fluconfig.BaseConfigParser):
    """
    This is a base class for parsing planet configuration files (both manager
    and flow files).
    """
    logCategory = 'config'

    def _parseFeedId(self, feedId):
        if feedId.find(':') == -1:
            return "%s:default" % feedId
        else:
            return feedId

    def _parseVirtualFeed(self, node):
        #  <virtual-feed name="foo" real="bar"/>
        name, real = self.parseAttributes(node, ('name', 'real'))
        # assert no content
        self.parseFromTable(node, {})
        return name, real

    def parseComponent(self, node, parent, isFeedComponent,
                       needsWorker):
        """
        Parse a <component></component> block.

        @rtype: L{ConfigEntryComponent}
        """
        # <component name="..." type="..." label="..."? worker="..."?
        #            project="..."? version="..."?>
        #   <source>...</source>*
        #   <eater name="...">...</eater>*
        #   <property name="name">value</property>*
        #   <clock-master>...</clock-master>?
        #   <plugs>...</plugs>*
        #   <virtual-feed name="foo" real="bar"/>*
        # </component>
        # F0.8
        # source tag is deprecated

        attrs = self.parseAttributes(node, ('name', 'type'),
                ('label', 'worker', 'project', 'version', ))
        name, componentType, label, worker, project, version = attrs
        if needsWorker and not worker:
            raise errors.ConfigError(
                'component %s does not specify the worker '
                'that it is to run on' % (name, ))
        elif worker and not needsWorker:
            raise errors.ConfigError('component %s specifies a worker to run '
                              'on, but does not need a worker' % (name, ))

        properties = []
        plugs = []
        eaters = []
        clockmasters = []
        sources = []
        virtual_feeds = []

        def parseBool(node):
            return self.parseTextNode(node, common.strToBool)
        parsers = {'property': (self._parseProperty, properties.append),
                   'compound-property': (self._parseCompoundProperty,
                                         properties.append),
                   'plugs': (self.parsePlugs, plugs.extend)}

        if isFeedComponent:
            parsers.update({'eater': (self._parseEater, eaters.extend),
                            'clock-master': (parseBool, clockmasters.append),
                            'source': (self._parseSource, sources.append),
                            'virtual-feed': (self._parseVirtualFeed,
                                             virtual_feeds.append)})

        self.parseFromTable(node, parsers)

        if len(clockmasters) == 0:
            isClockMaster = None
        elif len(clockmasters) == 1:
            isClockMaster = clockmasters[0]
        else:
            raise errors.ConfigError("Only one <clock-master> node allowed")

        if sources:
            msg = ('"source" tag has been deprecated in favor of "eater",'
                   ' please update your configuration file (found in'
                   ' component %r)' % name)
            warnings.warn(msg, DeprecationWarning)

        for feedId in sources:
            # map old <source> nodes to new <eater> nodes
            eaters.append((None, feedId))

        return ConfigEntryComponent(name, parent, componentType, label,
                                    properties, plugs, worker, eaters,
                                    isClockMaster, project, version,
                                    virtual_feeds)

    def _parseSource(self, node):
        return self._parseFeedId(self.parseTextNode(node))

    def _parseFeed(self, node):
        alias, = self.parseAttributes(node, (), ('alias', ))
        feedId = self._parseFeedId(self.parseTextNode(node))
        return feedId, alias

    def _parseEater(self, node):
        # <eater name="eater-name">
        #   <feed alias="foo"?>feeding-component:feed-name</feed>*
        # </eater>
        name, = self.parseAttributes(node, ('name', ))
        feeds = []
        parsers = {'feed': (self._parseFeed, feeds.append)}
        self.parseFromTable(node, parsers)
        if len(feeds) == 0:
            # we have an eater node with no feeds
            raise errors.ConfigError(
                "Eater node %s with no <feed> nodes, is not allowed" % (
                name, ))
        return [(name, feedId, alias) for feedId, alias in feeds]


class PlanetConfigParser(FlumotionConfigParser):
    """
    I represent a planet configuration file for Flumotion.

    @ivar atmosphere: A L{ConfigEntryAtmosphere}, filled in when parse() is
                      called.
    @ivar flows:      A list of L{ConfigEntryFlow}, filled in when parse() is
                      called.
    """
    logCategory = 'config'

    def __init__(self, file):
        FlumotionConfigParser.__init__(self, file)

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
            raise errors.ConfigError("unexpected root node': %s" %
                (root.nodeName, ))

        parsers = {'atmosphere': (self._parseAtmosphere,
                                  self.atmosphere.components.update),
                   'flow': (self._parseFlow,
                            self.flows.append),
                   'manager': (_ignore, _ignore)}
        self.parseFromTable(root, parsers)
        self.doc.unlink()
        self.doc = None

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
        name, = self.parseAttributes(node, ('name', ))
        if name == 'atmosphere':
            raise errors.ConfigError("<flow> cannot have 'atmosphere' as name")
        if name == 'manager':
            raise errors.ConfigError("<flow> cannot have 'manager' as name")

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
            raise errors.ConfigError("Multiple clock masters in flow %s: %s"
                              % (name, ', '.join([m.name for m in masters])))

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


class ManagerConfigParser(FlumotionConfigParser):
    """
    I parse manager configuration out of a planet configuration file.

    @ivar manager:    A L{ConfigEntryManager} containing options for
                      the manager section, filled in at construction time.
    """
    logCategory = 'config'

    MANAGER_SOCKETS = \
        ['flumotion.component.plugs.adminaction.AdminActionPlug',
         'flumotion.component.plugs.base.ManagerPlug',
         'flumotion.component.plugs.identity.IdentityProviderPlug']

    def __init__(self, file):
        FlumotionConfigParser.__init__(self, file)

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
            raise errors.ConfigError("unexpected root node': %s" %
                (root.nodeName, ))

        parsers = {'atmosphere': (_ignore, _ignore),
                   'flow': (_ignore, _ignore),
                   'manager': (lambda n: self._parseManagerWithoutRegistry(n),
                               lambda v: setattr(self, 'manager', v))}
        self.parseFromTable(root, parsers)

    def _parseManagerWithoutRegistry(self, node):
        # We parse without asking for a registry so the registry doesn't
        # verify before knowing the debug level
        name, = self.parseAttributes(node, (), ('name', ))
        ret = ConfigEntryManager(name, None, None, None, None, None,
                                 None, self.plugs)

        def simpleparse(proc):
            return lambda node: self.parseTextNode(node, proc)

        def recordval(k):

            def record(v):
                if getattr(ret, k):
                    raise errors.ConfigError('duplicate %s: %s'
                                      % (k, getattr(ret, k)))
                setattr(ret, k, v)
            return record

        def enum(*allowed):

            def eparse(v):
                v = str(v)
                if v not in allowed:
                    raise errors.ConfigError('unknown value %s (should be '
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
                raise errors.ConfigError('can only have one bouncer '
                                  '(%s is superfluous)' % (val.name, ))
            # FIXME: assert that it is a bouncer !
            self.bouncer = val

        def parseplugs(node):
            return fluconfig.buildPlugsSet(self.parsePlugs(node),
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

    def parseBouncerAndPlugs(self):
        # <planet>
        #     <manager>?
        #     <atmosphere>*
        #     <flow>*
        # </planet>
        root = self.doc.documentElement
        if not root.nodeName == 'planet':
            raise errors.ConfigError("unexpected root node': %s" %
                (root.nodeName, ))

        parsers = {'atmosphere': (_ignore, _ignore),
                   'flow': (_ignore, _ignore),
                   'manager': (self._parseManagerWithRegistry, _ignore)}
        self.parseFromTable(root, parsers)

    def unlink(self):
        self.doc.unlink()
        self.doc = None


class PlanetXMLWriter(XMLWriter):

    def __init__(self, planetState):
        super(PlanetXMLWriter, self).__init__()
        self._writePlanet(planetState)

    def _writePlanet(self, planet):
        attrs = [('name', planet.get('name'))]
        self.pushTag('planet', attrs)
        self.writeLine()
        self._writeAtmosphere(planet.get('atmosphere'))
        self.writeLine()
        for flow in planet.get('flows'):
            self._writeFlow(flow)
            self.writeLine()
        self.popTag()

    def _writeAtmosphere(self, atmosphere):
        self.pushTag('atmosphere')
        for component in atmosphere.get('components'):
            self._writeComponent(component, isFeedComponent=False)
        self.popTag()

    def _writeFlow(self, flow):
        attrs = [('name', flow.get('name'))]
        self.pushTag('flow', attrs)

        component = sorted(flow.get('components'),
                           cmp=cmpComponentType,
                           key=operator.attrgetter('type'))
        for component in components:
            self._writeComponent(component)
        self.popTag()

    def _writeComponent(self, component, isFeedComponent=True):
        config = component.get('config')
        attrs = [('name', component.get('name')),
                 ('type', component.get('type')),
                 ('label', config.get('label', component.get('name'))),
                 ('worker', component.get('workerRequested')),
                 ('project', config['project']),
                 ('version', common.versionTupleToString(config['version']))]
        self.pushTag('component', attrs)
        for name, feeders in config['eater'].items():
            self._writeEater(name, feeders)
        self._writeProperties(config['properties'].items())
        if isFeedComponent:
            if config['clock-master'] == config['avatarId']:
                value = 'true'
            else:
                value = 'false'
            self.writeTag('clock-master', data=value)
        self._writePlugs(config['plugs'].items())
        self._writeVirtualFeeds(config['virtual-feeds'].items())
        self.popTag()
        self.writeLine()

    def _writeEater(self, name, feeders):
        attrs = [('name', name)]
        self.pushTag('eater', attrs)
        for feedId, alias in feeders:
            attrs = [('alias', alias)]
            self.writeTag('feed', attrs, feedId)
        self.popTag()

    def _writeProperties(self, properties):

        def serialise(propVal):
            if isinstance(propVal, tuple): # fractions are our only tuple type
                return ["%d/%d" % propVal]
            elif isinstance(propVal, list):
                return propVal
            else:
                return [propVal]
        for name, value in properties:
            attrs = [('name', name)]
            for value in serialise(value):
                self.writeTag('property', attrs, value)

    def _writePlugs(self, plugs):
        if not plugs:
            return
        self.pushTag('plugs')
        for socket, plugs in plugs:
            for plug in plugs:
                self._writePlug(plug, socket)
        self.popTag()

    def _writePlug(self, plug, socket):
        attrs = [('socket', socket),
                 ('type', plug['type'])]
        self.pushTag('plug', attrs)
        self._writeProperties(plug['properties'].items())
        self.popTag()

    def _writeVirtualFeeds(self, virtualfeeds):
        for name, real in virtualfeeds:
            attrs = [('name', name),
                     ('real', real)]
            self.writeTag('virtual-feed', attrs)


def exportPlanetXml(p):
    pw = PlanetXMLWriter(p)
    return pw.getXML()
