# -*- Mode: Python -*-
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

import optparse
import sys

from twisted.internet import reactor

from flumotion.common import log, common, registry


def err(x):
    sys.stderr.write(x + '\n')
    raise SystemExit(1)

def parse_args(args):
    link_left = None
    links = []
    components = []
    _properties = []

    args.reverse()

    while args:
        x = args.pop().strip()
        if x == '!':
            if not components:
                err('Invalid grammar: `!\' without left-hand-side')
            link_left = components[-1]
        elif x.find('=') != -1:
            prop = x[:x.index('=')]
            val = x[x.index('=')+1:]
            if not prop or not val:
                err('Invalid property setting: %s' % x)
            if link_left or not components:
                err('Invalid grammar: Property %s does not follow a component'
                    % x)
            _properties.append((components[-1], prop, val))
        else:
            if x in components:
                err('component appears twice, -ETOOLAME: %s' % x)
            components.append(x)
            if link_left:
                links.append((link_left, x))
                link_left = None
    if link_left:
        err('Invalid grammar: `!\' without right-hand-side')
        
    properties = {}
    for x in components:
        properties[x] = []
    for x in _properties:
        properties[x[0]].append((x[1], x[2]))

    print links
    print components
    print properties
    return components, links, properties

def main(args):
    parser = optparse.OptionParser()
    parser.add_option('-d', '--debug',
                      action="store", type="string", dest="debug",
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

    components, links, properties = parse_args(args[1:])

    r = registry.getRegistry()
    bb = r.makeBundlerBasket()
    for x in components:
        if not r.hasComponent(x):
            err('Unknown component: %s' % x)
        c = r.getComponent(x)
        compprops = dict([(p.getName(), p) for p in c.getProperties()])
        for k, v in properties[x]:
            if k not in compprops.keys():
                err('Component %s has no such property `%s\'' % (x, k))
            # FIXME: how to verify type?
        for k, v in compprops.items():
            if v.isRequired() and not k in properties:
                err('Component %s missing required property `%s\' of type %s'
                    % (x, k, v.getType()))
        
    if not args:
        err('Usage: flumotion-launch COMPONENT [! COMPONENT]...')

    # register all package paths (FIXME: this should go away when
    # components come from manager)
    from flumotion.common import setup
    setup.setupPackagePath()

    log.debug('launch', 'Starting reactor')
    # FIXME: sort-of-ugly, but twisted recommends globals, and this is as
    # good as a global
    reactor.killed = False
    reactor.run()

    log.debug('launch', 'Reactor stopped')

    return 0
