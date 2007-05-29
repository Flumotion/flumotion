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

import optparse
import sys

from flumotion.common import log, common, registry


def err(x):
    sys.stderr.write(x + '\n')
    raise SystemExit(1)

def printMultiline(indent, data):
    maxLen = 76 - indent # Limit to 80 cols; but we add in 4 extra spaces.
    frags = data.split(' ')
    while frags:
        segment = frags.pop(0)
        while frags and len(segment) + len(frags[0]) + 1 <= maxLen:
            segment += " %s" % frags.pop(0)
        print '  %s  %s' % (' ' * indent, segment)

def main(args):
    from flumotion.common import setup
    setup.setupPackagePath()

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

    log.debug('inspect', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    # verbose overrides --debug
    if options.verbose:
        options.debug = "*:3"
 
    # handle all options
    if options.version:
        print common.version("flumotion-inspect")
        return 0

    if options.debug:
        log.setFluDebug(options.debug)

    r = registry.getRegistry()

    if len(args) == 1:
        # print all components
        components = [(c.getType(), c) for c in r.getComponents()]
        components.sort()
        print '\nAvailable components:\n'
        for name, c in components:
            print '  %s' % name
        plugs = [(p.getType(), p) for p in r.getPlugs()]
        plugs.sort()
        print '\nAvailable plugs:\n'
        for name, p in plugs:
            print '  %s' % name
        print
    elif len(args) == 2:
        cname = args[1]
        handled = False
        if r.hasComponent(cname):
            handled = True
            c = r.getComponent(cname)
            print '\nComponent:'
            print '  %s' % cname
            desc = c.getDescription()
            if desc:
                print '  %s' % desc
            print '\nSource:'
            print '  %s' % c.getSource()
            print '  in %s' % c.getBase()
            print '\nEaters:'
            if c.getEaters():
                for e in c.getEaters():
                    print ('  %s (%s%s)'
                           % (e.getName(),
                              e.getRequired() and 'required' or 'optional',
                              (e.getMultiple() and ', multiple ok' or '')))
            else:
                print '  (None)'
            print '\nFeeders:'
            if c.getFeeders():
                for e in c.getFeeders():
                    print '  %s' % e
            else:
                print '  (None)'
            print '\nFeatures:'
            features = [(p.getType(), p) for p in c.getEntries()]
            features.sort()
            if features:
                for k, v in features:
                    print '  %s: %s:%s' % (k, v.getLocation(), v.getFunction())
            else:
                print '  (None)'
            properties = [(p.getName(), p) for p in c.getProperties()]
            properties.sort()
            print '\nProperties:'
            if properties:
                indent = max([len(p[0]) for p in properties])
                for k, v in properties:
                    desc = v.getDescription()
                    print ('  %s%s: type %s, %s%s'
                           % (' '*(indent-len(k)), k, v.getType(),
                              v.isRequired() and 'required' or 'optional',
                              v.isMultiple() and ', multiple ok' or ''))
                    if desc:
                        printMultiline(indent, desc)
            sockets = c.getSockets()
            print '\nClocking:'
            print '  Needs synchronisation: %r' % c.getNeedsSynchronization()
            if c.getClockPriority() is not None and c.getNeedsSynchronization():
                print '  Clock priority: %d' % c.getClockPriority()
            print '\nSockets:'
            for socket in sockets:
                print '  %s' % socket
            print
        if r.hasPlug(cname):
            handled = True
            p = r.getPlug(cname)
            print '\nPlug:'
            print '  %s' % cname
            print '\nType:'
            print '  %s' % p.getType()
            print '\nEntry:'
            e = p.getEntry()
            print '  %s() in %s' % (e.getFunction(), e.getModuleName())
            print '\nProperties:'
            properties = [(x.getName(), x) for x in p.getProperties()]
            properties.sort()
            if properties:
                for k, v in properties:
                    print ('  %s: type %s, %s%s'
                           % (k, v.getType(),
                              v.isRequired() and 'required' or 'optional',
                              v.isMultiple() and ', multiple ok' or ''))
            print
        if not handled:
            err('Unknown component or plug `%s\'' % cname)
    else:
        err('Usage: flumotion-inspect [COMPONENT-OR-PLUG]')

    return 0
