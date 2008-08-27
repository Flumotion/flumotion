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

import sys

from flumotion.common import log, common, registry
from flumotion.common.options import OptionParser

__version__ = "$Rev$"


def printMultiline(indent, data):
    maxLen = 76 - indent # Limit to 80 cols; but we add in 4 extra spaces.
    frags = data.split(' ')
    while frags:
        segment = frags.pop(0)
        while frags and len(segment) + len(frags[0]) + 1 <= maxLen:
            segment += " %s" % frags.pop(0)
        print '  %s  %s' % (' ' * indent, segment)


def printProperty(prop, indent):
    pname = prop.getName()
    desc = prop.getDescription()
    print ('  %s%s: type %s, %s%s'
           % (' '*(indent-len(pname)), pname, prop.getType(),
              prop.isRequired() and 'required' or 'optional',
              prop.isMultiple() and ', multiple ok' or ''))
    if desc:
        printMultiline(indent, desc)
    if isinstance(prop, registry.RegistryEntryCompoundProperty):
        subprop_names = [sp.getName() for sp in prop.getProperties()]
        subprop_names.sort()
        printMultiline(indent, 'subproperties: %s' %
                       ', '.join(subprop_names))


def printProperties(props, indent):
    properties = [(p.getName(), p) for p in props]
    properties.sort()
    if properties:
        indent = max([len(p[0]) for p in properties])
        for _, p in properties:
            printProperty(p, indent)


class _NestedPropertyError(Exception):
    pass


def getNestedProperty(c, ppath):
    obj_class = 'Component'
    obj_type = c.getType()
    if not isinstance(c, registry.RegistryEntryComponent):
        obj_class = 'Plug'
    if not c.hasProperty(ppath[0]):
        raise _NestedPropertyError("%s `%s' has no property `%s'." %
                                   (obj_class, obj_type, ppath[0]))
    cobj = c
    found = []
    while ppath:
        cname = ppath.pop(0)
        try:
            cobj = cobj.properties[cname]
        except:
            raise _NestedPropertyError("%s `%s': property `%s' has no"
                                       " subproperty `%s'." %
                                       (obj_class, obj_type,
                                        ':'.join(found), cname))
        found.append(cname)
    return cobj


def main(args):
    from flumotion.common import setup
    setup.setupPackagePath()

    usage_str = ('Usage: %prog [options] [COMPONENT-OR-PLUG'
                 ' [FULL-PROPERTY-NAME]]')
    fpname_str = ("FULL-PROPERTY-NAME: represents a fully qualified"
                  " property name, including the names of the containing"
                  " properties: "
                  "...[property-name:]property-name")
    parser = OptionParser(usage=usage_str, description=fpname_str,
                          domain="flumotion-inspect")

    log.debug('inspect', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

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
            print '\nProperties:'
            printProperties(c.getProperties(), 0)
            sockets = c.getSockets()
            print '\nClocking:'
            print '  Needs synchronisation: %r' % c.getNeedsSynchronization()
            if (c.getClockPriority() is not None and
                c.getNeedsSynchronization()):
                print '  Clock priority: %d' % c.getClockPriority()
            print '\nSockets:'
            for socket in sockets:
                print '  %s' % socket
            print
        if r.hasPlug(cname):
            handled = True
            p = r.getPlug(cname)
            print '\nPlug type:'
            print '  %s' % cname
            print '\nEntry:'
            e = p.getEntry()
            print '  %s() in %s' % (e.getFunction(), e.getModuleName())
            print '\nProperties:'
            printProperties(p.getProperties(), 0)
            print
        if not handled:
            parser.exit(status=1, msg=('Unknown component or plug `%s\'\n' %
                                       cname))
    elif len(args) == 3:
        cname = args[1]
        pname = args[2]
        ppath = pname.split(':')
        handled = False
        if r.hasComponent(cname):
            handled = True
            c = r.getComponent(cname)
            try:
                prop = getNestedProperty(c, ppath)
            except _NestedPropertyError, npe:
                parser.exit(status=1, msg='%s\n' % npe.message)
            print '\nComponent:'
            print '  %s' % cname
            desc = c.getDescription()
            if desc:
                print '  %s' % desc
            print '\nProperty:'
            printProperty(prop, len(prop.getName()))
            print
        if r.hasPlug(cname):
            handled = True
            p = r.getPlug(cname)
            try:
                prop = getNestedProperty(p, ppath)
            except _NestedPropertyError, npe:
                parser.exit(status=1, msg='%s\n' % npe.message)
            print '\nPlug:'
            print '  %s' % cname
            print '\nType:'
            print '  %s' % p.getType()
            print '\nProperty:'
            printProperty(prop, len(prop.getName()))
            print
        if not handled:
            parser.exit(status=1, msg=('Unknown component or plug `%s\'\n' %
                                       cname))
    else:
        parser.error('Could not process arguments, try "-h" option.')

    return 0
