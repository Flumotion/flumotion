# -*- Mode: Python -*-
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
flumotion.launch.parse: A parsing library for flumotion-launch syntax.
"""

import copy
import sys

from flumotion.common import log, common, dag, registry
from flumotion.manager import config

__all__ = ['parse_args']
__version__ = "$Rev$"


def err(x):
    sys.stderr.write(x + '\n')
    raise SystemExit(1)


class Component(object):
    __slots__ = ('type', 'name', 'properties', 'plugs', 'source',
                 'clock_priority', 'config_entry', '_reg')

    def __init__(self, type, name):
        self.type = type
        self.name = name
        self.properties = []
        self.plugs = []
        self.source = []

        self.config_entry = None

        r = registry.getRegistry()
        if not r.hasComponent(self.type):
            err('Unknown component type: %s' % self.type)

        self._reg = r.getComponent(self.type)
        if self._reg.getNeedsSynchronization():
            self.clock_priority = self._reg.getClockPriority()
        else:
            self.clock_priority = None

    def complete_and_verify(self):
        self.config_entry = config.ConfigEntryComponent(
            self.name,
            None,
            self.type,
            None,
            self.properties,
            self.plugs,
            None,
            [(None, feedId) for feedId in self.source],
            None,
            None,
            None)

    def as_config_dict(self):
        return copy.deepcopy(self.config_entry.config)


class ComponentStore:

    def __init__(self):
        self._names = {}
        self._last_component = None
        self.components = {}
        assert not self # make sure that i am false if empty

    def _make_name(self, type):
        i = self._names.get(type, 0)
        self._names[type] = i + 1
        return '%s%d' % (type, i)

    def add(self, type):
        self._last_component = name = self._make_name(type)
        self.components[name] = Component(type, name)

    def add_plug_to_current(self, type, props):
        self[self.last()].plugs.append((type, props))

    def add_prop_to_current(self, key, val):
        self[self.last()].properties.append((key, val))

    def last(self):
        assert self._last_component
        return self._last_component

    def names(self):
        return self.components.keys()

    def complete_and_verify_configs(self):
        for name in self.components:
            self.components[name].complete_and_verify()

        # hackily stolen from config.ConfigXML.parseFlow, definitely
        # hackariffic

        need_sync = [(x.clock_priority, x) for x in self.components.values()
                     if x.clock_priority]
        need_sync.sort()
        need_sync = [x[1] for x in need_sync]

        if need_sync:
            master = need_sync[-1]
            for x in need_sync:
                x.config_entry.config['clock-master'] = (
                    master.config_entry.config['avatarId'])

    def sorted_configs(self, partial_orders):
        sort = dag.topological_sort
        return [self[name].as_config_dict()
                for name in sort(self.names(), partial_orders)]

    def __getitem__(self, key):
        return self.components[key]

    def __setitem__(self, key, val):
        self.components[key] = val

    def __contains__(self, key):
        return key in self.components

    def __len__(self):
        return len(self.components)

    def __iter__(self):
        return self.components.__iter__()


class Linker:

    def __init__(self, get_last_component):
        # links: [(feedercomponentname, feeder,
        #          eatercomponentname, eater), ...]
        self.links = []
        self._tmp = None
        self.get_last_component = get_last_component

    def pending(self):
        return bool(self._tmp)

    def link(self, feedercompname=None, feeder=None, eatercompname=None,
             eater=None):
        if feedercompname:
            assert not self._tmp
            self._tmp = [feedercompname, feeder, eatercompname, eater]
        elif feeder:
            err('how did i get here?')
        elif eatercompname:
            if not self._tmp:
                err('Invalid grammar: trying to link, but no feeder component')
            self._tmp[2] = eatercompname
            if eater:
                self._tmp[3] = eater
        elif eater:
            if not self._tmp:
                err('Invalid grammar: trying to link, but no feeder component')
            self._tmp[3] = eater
        else:
             # no args, which is what happens when ! is seen
            if not self._tmp:
                self._tmp = [self.get_last_component(), None, None, None]
            else:
                if not self._tmp[0]:
                    self._tmp[0] = self.get_last_component()

        if self._tmp and self._tmp[0] and self._tmp[2]:
            self.links.append(self._tmp)
            self._tmp = None

    def get_links(self):
        if self._tmp:
            err('Invalid grammar: uncompleted link from %s.%s' % self._tmp[:2])
        else:
            return self.links

    def resolve_links(self, component_types):
        for link in self.get_links():
            assert link[0] and link[2]
            if not link[0] in component_types:
                err('Invalid grammar: no feeder component %s to link from' % (
                    link[0], ))
            if not link[2] in component_types:
                err('Invalid grammar: no eater component %s to link to' % (
                    link[2], ))

        reg = registry.getRegistry()
        for link in self.get_links():
            compname = link[0]
            comptype = component_types[compname]
            compreg = reg.getComponent(comptype)
            if link[1]:
                if not link[1] in compreg.getFeeders():
                    err('Component %s has no feeder named %s' % (
                        compname, link[1]))
                # leave link[1] unchanged
            else:
                if not compreg.getFeeders():
                    err('Component %s has no feeders' % compname)
                link[1] = compreg.getFeeders()[0]

        for link in self.get_links():
            compname = link[2]
            comptype = component_types[compname]
            compreg = reg.getComponent(comptype)
            eaters = compreg.getEaters()
            if link[3]:
                if not link[3] in [x.getName() for x in eaters]:
                    err('Component %s has no eater named %s' % (
                        compname, link[3]))
                # leave link[1] unchanged
            else:
                if not eaters:
                    err('Component %s has no eaters' % compname)
                link[3] = eaters[0].getName()

        feeders = dict([(name, []) for name in component_types])
        for link in self.get_links():
            feeders[link[2]].append('%s:%s' % (link[0], link[1]))
        return feeders

    def get_sort_order(self):
        return [(link[0], link[2]) for link in self.get_links()]

    def dump(self):
        for link in self.links:
            print '%s:%s => %s:%s' % tuple(link)


def parse_plug(arg):
    plugargs = arg.split(',')
    plug = plugargs.pop(0)[1:]
    return plug, [parse_prop(arg) for arg in plugargs]


def parse_prop(arg):
    prop = arg[:arg.index('=')]
    val = arg[arg.index('=')+1:]
    if not prop or not val:
        err('Invalid property setting: %s' % arg)
    return prop, val


def parse_arg(arg, components, linker):

    def assert_in_component(msg):
        if linker.pending() or not components:
            err('Invalid grammar: %s' % msg)

    if arg == '!':
        if not components:
            err('Invalid grammar: `!\' without feeder component')
        linker.link()

    elif arg[0] == '/':
        assert_in_component('Plug %s does not follow a component' % arg)
        plug, props = parse_plug(arg)
        components.add_plug_to_current(plug, props)

    elif arg.find('=') != -1:
        assert_in_component('Property %s does not follow a component' % arg)
        prop, val = parse_prop(arg)
        components.add_prop_to_current(prop, val)

    elif arg.find('.') != -1:
        t = arg.split('.')
        if len(t) != 2:
            err('Invalid grammar: bad eater/feeder specification: %s' % arg)
        t = [z or None for z in t]
        if linker.pending():
            linker.link(eatercompname=t[0], eater=t[1])
        elif components:
            linker.link(feedercompname=t[0] or components.last(), feeder=t[1])
        else:
            err('Invalid grammar: trying to link from feeder %s but '
                'no feeder component' % arg)

    else:
        components.add(arg)
        if linker.pending():
            linker.link(eatercompname=components.last())


def parse_args(args):
    """Parse flumotion-launch arguments.

    Parse flumotion-launch arguments, returning a list of component
    configs.

    A component config is what we will pass to a component when we
    create it. It is a dict:

     - 'name':         component name
     - 'type':         component type
     - 'properties':   dict of property name => property value
     - 'feed':         list of [feeder name,...]
     - 'source':       list of [feeder name,...], (optional)
     - 'clock-master': clock master or None
     - 'plugs':        dict of socket name => plug config
    """

    if not args:
        err('Usage: flumotion-launch COMPONENT [! COMPONENT]...')

    components = ComponentStore()

    linker = Linker(components.last)

    args.reverse() # so we can pop from the tail
    while args:
        parse_arg(args.pop().strip(), components, linker)

    feeders = linker.resolve_links(dict([(name, components[name].type)
                                         for name in components]))

    for compname in feeders:
        components[compname].source = feeders[compname]
    components.complete_and_verify_configs()

    return components.sorted_configs(linker.get_sort_order())
