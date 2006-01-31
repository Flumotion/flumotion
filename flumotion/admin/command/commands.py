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


from flumotion.twisted.defer import defer_generator
from flumotion.admin.command import utils
from flumotion.common.planet import moods
from flumotion.common import errors


__all__ = ['commands']


# it's probably time to move this stuff into classes...

# command-list := (command-spec, command-spec...)
# command-spec := (command-name, command-desc, arguments, command-proc)
# command-name := str
# command-desc := str
# command-proc := f(model, quit, *args) -> None
# arguments := (arg-spec, arg-spec...)
# arg-spec := (arg-name, arg-parser)
# arg-name := str
# arg-parser := f(x) -> Python value or exception


def do_getprop(model, quit, avatarId, propname):
    d = utils.get_component_uistate(model, avatarId)
    yield d
    uistate = d.value()
    if uistate:
        if uistate.hasKey(propname):
            print uistate.get(propname)
        else:
            print ('Component %s in flow %s has no property called %s'
                   % (avatarId[1], avatarId[0], propname))
    quit()
do_getprop = defer_generator(do_getprop)

def do_listprops(model, quit, avatarId):
    d = utils.get_component_uistate(model, avatarId)
    yield d
    uistate = d.value()
    if uistate:
        for k in uistate.keys():
            print k
    quit()
do_listprops = defer_generator(do_listprops)

def do_showplanet(model, quit):
    d = model.callRemote('getPlanetState')
    yield d
    planet = d.value()

    for f in planet.get('flows'):
        print 'flow: %s' % f.get('name')
        for c in f.get('components'):
            print '  %s' % c.get('name')

    a = planet.get('atmosphere')
    print 'atmosphere: %s' % a.get('name')
    for c in a.get('components'):
        print '  %s' % c.get('name')

    quit()
do_showplanet = defer_generator(do_showplanet)

def do_getmood(model, quit, avatarId):
    d = model.callRemote('getPlanetState')
    yield d
    planet = d.value()
    c = utils.find_component(planet, avatarId)
    if c:
        mood = c.get('mood')
        try:
            import os
            os.spawnlp(os.P_WAIT, 'cowsay', 'cowsay',
                       "%s is %s" % (c.get('name'), moods[mood].name))
        except Exception:
            print "%s is %s" % (c.get('name'), moods[mood].name)

    quit()
do_getmood = defer_generator(do_getmood)

def do_showcomponent(model, quit, avatarId):
    d = model.callRemote('getPlanetState')
    yield d
    planet = d.value()
    c = utils.find_component(planet, avatarId)
    if c:
        print 'Component state:'
        keys = c.keys()
        keys.sort()
        for k in keys:
            print '    %s: %r' % (k, c.get(k))
        d = utils.get_component_uistate(model, avatarId, c, quiet=True)
        yield d
        ui = d.value()
        if ui:
            print '\nUI state:'
            keys = ui.keys()
            keys.sort()
            for k in keys:
                print '    %s: %r' % (k, ui.get(k))
    quit()
do_showcomponent = defer_generator(do_showcomponent)

def do_invoke(model, quit, avatarId, methodName):
    d = model.callRemote('getPlanetState')
    yield d
    planet = d.value()
    c = utils.find_component(planet, avatarId)
    if not c:
        print "Could not find component %r" % avatarId
        yield None

    d = model.componentCallRemote(c, methodName)
    yield d

    try:
        d.value()
    except errors.NoMethodError:
        print "No method '%s' on component '%s'" % (methodName, avatarId)
    except Exception, e:
        raise

    quit()
do_invoke = defer_generator(do_invoke)

commands = (('getprop',
             'gets a property on a component',
             (('component-path', utils.avatarId),
              ('property-name', str)),
             do_getprop),
            ('listprops',
             'lists the properties a component has',
             (('component-path', utils.avatarId),
              ),
             do_listprops),
            ('showplanet',
             'shows the flows, atmosphere, and components in the planet',
             (),
             do_showplanet),
            ('getmood',
             'gets the mood of a component',
             (('component-path', utils.avatarId),
              ),
             do_getmood),
            ('showcomponent',
             'shows everything we know about a component',
             (('component-path', utils.avatarId),
              ),
             do_showcomponent),
            ('invoke',
             'invoke a component method',
             (('component-path', utils.avatarId),
              ('method-name', str)),
             do_invoke),
            )

