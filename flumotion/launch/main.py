# -*- Mode: Python -*-
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

import optparse
import sys

from twisted.python import reflect
from twisted.internet import reactor, defer

from flumotion.common import log, common, registry, dag, errors
from flumotion.twisted.defer import defer_generator

def err(x):
    sys.stderr.write(x + '\n')
    raise SystemExit(1)

def resolve_links(links, components):
    reg = registry.getRegistry()
    for link in links:
        compname = link[0]
        comptype = [x[1] for x in components if x[0]==compname][0]
        compreg = reg.getComponent(comptype)
        if link[1]:
            if not link[1] in compreg.getFeeders():
                err('Component %s has no feeder named %s' % (compname, link[1]))
            # leave link[1] unchanged
        else:
            if not compreg.getFeeders():
                err('Component %s has no feeders' % compname)
            link[1] = compreg.getFeeders()[0]
    
    for link in links:
        compname = link[2]
        comptype = [x[1] for x in components if x[0]==compname][0]
        compreg = reg.getComponent(comptype)
        eaters = compreg.getEaters()
        if link[3]:
            if not link[3] in [x.getName() for x in eaters]:
                err('Component %s has no eater named %s' % (compname, link[3]))
            # leave link[1] unchanged
        else:
            if not eaters:
                err('Component %s has no eaters' % compname)
            link[3] = eaters[0].getName()
    
    #for link in links:
    #    print '%s:%s => %s:%s' % tuple(link)

def find(l, pred):
    return filter(pred, l)[0]

def sort_components(links, components):
    sorted = dag.topological_sort([x[0] for x in components],
                                  [(x[0], x[2]) for x in links])
    sorted = [find(components, lambda p: p[0] == x) for x in sorted]
    return sorted

def parse_args(args):
    links = []
    components = []
    properties = {}
    plugs = {}

    if not args:
        err('Usage: flumotion-launch COMPONENT [! COMPONENT]...')

    # components: [(name, type), ...]
    # links: [(feedercomponentname, feeder, eatercomponentname, eater), ...]
    # properties: {componentname=>{prop=>value, ..}, ..}
    # plugs: {componentname=>[(plugtype,{prop=>value, ..}), ...], ...}

    _names = {}
    def add_component(type):
        i = _names.get(type, 0)
        _names[type] = i + 1
        name = '%s%d' % (type, i)
        components.append((name, type))
        properties[name] = {}
        plugs[name] = []
        
    def last_component():
        return components[-1][0]

    link_tmp = []
    def link(feedercompname=None, feeder=None, eatercompname=None, eater=None):
        if feedercompname:
            assert not link_tmp
            tmp = [feedercompname, feeder, eatercompname, eater]
            link_tmp.append(tmp)
        elif feeder:
            err('how did i get here?')
        elif eatercompname:
            if not link_tmp:
                err('Invalid grammar: trying to link, but no feeder component')
            link_tmp[0][2] = eatercompname
            if eater:
                link_tmp[0][3] = eater
        elif eater:
            if not link_tmp:
                err('Invalid grammar: trying to link, but no feeder component')
            link_tmp[0][3] = eater
        else:
             # no args, which is what happens when ! is seen
            if not link_tmp:
                link_tmp.append([last_component(), None, None, None])
            else:
                if not link_tmp[0][0]:
                    link_tmp[0][0] = last_component()
            
        if link_tmp and link_tmp[0][0] and link_tmp[0][2]:
            links.append(link_tmp[0])
            del link_tmp[0]

    args.reverse() # so we can pop from the tail

    while args:
        x = args.pop().strip()
        if x == '!':
            if not components:
                err('Invalid grammar: `!\' without feeder component')
            link()
        elif x[0] == '/':
            # a plug
            plugargs = x.split(',')
            plug = plugargs.pop(0)[1:]
            if link_tmp or not components:
                err('Invalid grammar: Plug %s does not follow a component'
                    % plug)
            props = {}
            for x in plugargs:
                prop = x[:x.index('=')]
                val = x[x.index('=')+1:]
                if not prop or not val:
                    err('Invalid plug property setting: %s' % x)
                props[prop] = val
            plugs[last_component()].append((plug, props))
        elif x.find('=') != -1:
            prop = x[:x.index('=')]
            val = x[x.index('=')+1:]
            if not prop or not val:
                err('Invalid property setting: %s' % x)
            if link_tmp or not components:
                err('Invalid grammar: Property %s does not follow a component'
                    % x)
            properties[last_component()][prop] = val
        elif x.find('.') != -1:
            t = x.split('.')
            if len(t) != 2:
                err('Invalid grammar: bad eater/feeder specification: %s' % x)
            t = [z or None for z in t]
            if link_tmp:
                link(eatercompname=t[0], eater=t[1])
            elif components:
                link(feedercompname=t[0] or last_component(), feeder=t[1])
            else:
                err('Invalid grammar: trying to link from feeder %s but '
                    'no feeder component' % x)
        else:
            add_component(x)
            if link_tmp:
                link(eatercompname=last_component())
    if link_tmp:
        err('Invalid grammar: uncompleted link from %s.%s')
        
    for x in links:
        assert x[0] and x[2]
        if not x[0] in properties.keys():
            err('Invalid grammar: no feeder component %s to link from' % x[0])
        if not x[2] in properties.keys():
            err('Invalid grammar: no eater component %s to link to' % x[2])

    resolve_links(links, components)

    components = sort_components(links, components)

    return components, links, properties, plugs

def parse_properties(cname, strings, specs):
    # cname: string, name of the component
    # strings: {'name':'val', ...}
    # specs: list of flumotion.common.registry.RegistryEntryProperties
    def parse_fraction(v):
        split = v.split('/')
        assert len(split) == 2, \
               "Fraction values should be in the form N/D"
        return (int(split[0]), int(split[1]))

    ret = {}
    compprops = dict([(x.getName(), x) for x in specs])

    for k, v in strings.items():
        if k not in compprops:
            err('Component %s has no such property `%s\'' % (cname, k))

        t = compprops[k].getType()
        parsers = {'int': int,
                   'long': long,
                   'float': float,
                   'bool': bool,
                   'string': str,
                   'fraction': parse_fraction}

        try:
            parser = parsers[t]
        except KeyError:
            err('Unknown type `%s\' of property %s in component %s'
                % (t, k, cname))

        val = parser(v)

        if compprops[k].isMultiple():
            if not k in ret:
                ret[k] = []
            ret[k].append(val)
        else:
            ret[k] = val

    for k, v in compprops.items():
        if v.isRequired() and not k in ret:
            err('Component %s missing required property `%s\' of type %s'
                % (cname, k, v.getType()))

    return ret


# FIXME: this duplicates code from
# flumotion.common.config.ConfigEntryComponent, among other things. If
# the code from f.c.c could be factored into something more like a
# library that would be good.
class ComponentWrapper(object):
    name = None
    type = None
    prototype = None
    procedure = None
    config = None
    component = None
    feeders = None

    def __init__(self, name, type, properties, feeders, plugs):
        self.name = name
        self.type = type

        r = registry.getRegistry()
        if not r.hasComponent(type):
            err('Unknown component type: %s' % type)

        c = r.getComponent(type)
        config = {'name': name}
        
        self.feeders = c.getFeeders()

        config['properties'] = parse_properties(name, properties,
                                                c.getProperties())

        eaters = c.getEaters()
        if eaters:
            required = True in [x.getRequired() for x in eaters]
            multiple = True in [x.getMultiple() for x in eaters]
            if required and not feeders:
                err('Component %s wants to eat but you didn\'t give it '
                    'food' % name)
            if not multiple and len(feeders) > 1:
                err('Component %s can only eat from one feeder' % name)
            if feeders:
                config['source'] = feeders
            else:
                # don't even set config['source']
                pass
        else:
            if feeders:
                err('Component %s can\'t feed from anything' % name)
            
        self.config = config

        # fixme: 'feed' is not strictly necessary in config
        config['feed'] = c.getFeeders()

        # not used by the component -- see notes in _parseComponent in
        # config.py
        if c.getNeedsSynchronization():
            config['clock-master'] = c.getClockPriority()
        else:
            config['clock-master'] = None

        config['plugs'] = {}
        for socket in c.getSockets():
            config['plugs'][socket] = []
        for plugtype, plugprops in plugs:
            if not r.hasPlug(plugtype):
                err('Unknown plug type: %s' % plugtype)
            spec = r.getPlug(plugtype)
            socket = spec.getSocket()
            if not socket in config['plugs']:
                err('Cannot add plug %s to component %s: '
                    'sockets of type %s not supported'
                    % (plugtype, name, socket))
            props = parse_properties(plugtype, plugprops, spec.getProperties())
            plug = {'type': plugtype, 'socket': socket,
                    'properties': props}
            config['plugs'][socket].append(plug)
                
        try:
            entry = c.getEntryByType('component')
        except KeyError:
            err('Component %s has no component entry' % name)
        importname = entry.getModuleName(c.getBase())
        try:
            module = reflect.namedAny(importname)
        except Exception, e:
            err('Could not load module %s for component %s: %s'
                % (importname, name, e))
        self.procedure = getattr(module, entry.getFunction())

    def instantiate(self):
        self.component = self.procedure()
        return self.component.setup(self.config)

    def provideMasterClock(self, port):
        ret = self.component.provide_master_clock(port)
        # grrrrr! for some reason getting the ip requires being
        # connected? I suppose it *is* always my ip relative to ip X
        # though...
        if not ret[0]:
            ret = ("127.0.0.1", ret[1], ret[2])
        return ret

    def start(self, eatersdata, feedersdata, clocking):
        return self.component.start(eatersdata, feedersdata, clocking)

    def stop(self):
        return self.component.stop()

def DeferredDelay(time, val):
    d = defer.Deferred()
    reactor.callLater(time, d.callback, val)
    return d

def start_components(wrappers, feed_ports, links, delay):
    # figure out the links and start the components

    # first phase: instantiation and setup
    def got_results(results):
        success = True
        for result, wrapper in zip(results, wrappers):
            if not result[0]:
                print ("Component %s failed to start, reason: %r"
                       % (wrapper, result[1]))
                success = False
        if not success:
            raise errors.ComponentStartError()

    def choose_clocking(unused):
        # second phase: clocking
        need_sync = [(x.config['clock-master'], x) for x in wrappers
                     if x.config['clock-master'] is not None]
        need_sync.sort()
        need_sync = [x[1] for x in need_sync]

        if need_sync:
            master = need_sync.pop(0)
            print "Telling", master.name, "to provide the master clock."
            clocking = master.provideMasterClock(7600 - 1) # hack!
            return need_sync, clocking
        else:
            return None, None

    def add_delay(val):
        if delay:
            print 'Delaying component startup by %f seconds...' % delay
            return DeferredDelay(delay, val)
        else:
            return defer.succeed(val)

    def do_start(synchronization, wrapper):
        need_sync, clocking = synchronization
        eatersdata = [('%s:%s' % (x[0], x[1]), 'localhost',
                       feed_ports[x[0]][x[1]])
                      for x in links if x[2] == wrapper.name]
        feedersdata = [('%s:%s' % (wrapper.name, x), 'localhost', p)
                       for x, p in feed_ports[wrapper.name].items()]

        # start it up, with clocking data only if it needs it
        d = wrapper.start(eatersdata, feedersdata,
                          wrapper in need_sync and clocking or None)
        d.addCallback(lambda val: synchronization)
        return d

    def do_stop(failure):
        for wrapper in wrappers:
            wrapper.stop()
        return failure

    d = defer.DeferredList([wrapper.instantiate() for wrapper in wrappers])
    d.addCallback(got_results)
    d.addCallback(choose_clocking)
    for wrapper in wrappers:
        d.addCallback(add_delay)
        d.addCallback(do_start, wrapper)
    d.addErrback(do_stop)
    return d

def main(args):
    from flumotion.common import setup
    setup.setupPackagePath()
    from flumotion.configure import configure
    log.debug('manager', 'Running Flumotion version %s' %
        configure.version)
    import twisted.copyright
    log.debug('manager', 'Running against Twisted version %s' %
        twisted.copyright.version)
    from flumotion.project import project
    for p in project.list():
        log.debug('manager', 'Registered project %s version %s' % (
            p, project.get(p, 'version')))

    parser = optparse.OptionParser()
    parser.add_option('-d', '--debug',
                      action="store", type="string", dest="debug",
                      help="set debug levels")
    parser.add_option('', '--delay',
                      action="store", type="float", dest="delay",
                      help="set debug levels")
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="be verbose")
    parser.add_option('', '--version',
                      action="store_true", dest="version",
                      default=False,
                      help="show version information")

    log.debug('worker', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    # verbose overrides --debug
    if options.verbose:
        options.debug = "*:3"
 
    # handle all options
    if options.version:
        print common.version("flumotion-launch")
        return 0

    if options.debug:
        log.setFluDebug(options.debug)

    if options.delay:
        delay = options.delay
    else:
        delay = 0.

    components, links, properties, plugs = parse_args(args[1:])

    # load the modules, make the component
    wrappers = []
    for name, type in components:
        feeders = ['%s:%s' % (x[0], x[1]) for x in links if x[2] == name]
        wrappers.append(ComponentWrapper(name, type, properties[name],
                                         feeders, plugs[name]))

    # assign feed ports
    port = 7600
    feed_ports = {}
    for wrapper in wrappers:
        feed_ports[wrapper.name] = {}
        for feeder in wrapper.feeders:
            feed_ports[wrapper.name][feeder] = port
            print '%s:%s feeds on port %d' % (wrapper.name, feeder, port)
            port += 1
    
    reactor.running = False
    reactor.failure = False
    reactor.callLater(0, lambda: setattr(reactor, 'running', True))

    d = start_components(wrappers, feed_ports, links, delay)
    def errback(failure):
        print "Error occurred: %s" % failure.getErrorMessage()
        failure.printDetailedTraceback()
        reactor.failure = True
        if reactor.running:
            print "Stopping reactor."
            reactor.stop()
    d.addErrback(errback)

    if not reactor.failure:
        print 'Running the reactor. Press Ctrl-C to exit.'

        log.debug('launch', 'Starting reactor')
        reactor.run()

        log.debug('launch', 'Reactor stopped')

    if reactor.failure:
        return 1
    else:
        return 0
