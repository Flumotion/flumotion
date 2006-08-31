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
import os

from flumotion.twisted.defer import defer_generator
from flumotion.admin.command import utils
from flumotion.common.planet import moods
from flumotion.common import errors


__all__ = ['commands']

# copied from flumotion/twisted/integration.py
class CommandNotFoundException(Exception):
    def __init__(self, command):
        Exception.__init__(self)
        self.command = command
    def __str__(self):
        return 'Command %r not found in the PATH.' % self.command

def _which(executable):
    if os.sep in executable:
        if os.access(os.path.abspath(executable), os.X_OK):
            return os.path.abspath(executable)
    elif os.getenv('PATH'):
        for path in os.getenv('PATH').split(os.pathsep):
            if os.access(os.path.join(path, executable), os.X_OK):
                return os.path.join(path, executable)
    raise CommandNotFoundException(executable)


# it's probably time to move this stuff into classes...

# command-list := (command-spec, command-spec...)
# command-spec := (command-name, command-desc, arguments, command-proc)
# command-name := str
# command-desc := str
# command-proc := f(model, quit, *args) -> None
# arguments := (arg-spec, arg-spec...)
# arg-spec := (arg-name, arg-parser, arg-default?)
# arg-name := str
# arg-parser := f(x) -> Python value or exception
# arg-default := any python value


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
            _which('cowsay')
            os.spawnlp(os.P_WAIT, 'cowsay', 'cowsay',
                       "%s is %s" % (c.get('name'), moods[mood].name))
        except CommandNotFoundException:
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
        print "Invoke of %s on %s was successful." % (methodName, 
            avatarId[1])
    except errors.NoMethodError:
        print "No method '%s' on component '%s'" % (methodName, avatarId)
    except Exception, e:
        raise

    quit()
do_invoke = defer_generator(do_invoke)

def do_loadconfiguration(model, quit, confFile, saveAs):
    print 'Loading configuration from file: %s' % confFile

    f = open(confFile, 'r')
    configurationXML = f.read()
    f.close()

    d = model.callRemote('loadConfiguration', configurationXML,
                         saveAs=saveAs)
    yield d
    d.value()
    print 'Configuration loaded successfully.'
    if saveAs:
        print 'Additionally, the configuration XML was saved on the manager.'

    quit()
do_loadconfiguration = defer_generator(do_loadconfiguration)

def do_showworkers(model, quit):
    d = model.callRemote('getWorkerHeavenState')
    yield d
    whs = d.value()

    for worker in whs.get('workers'):
        print "%s: %s" % (worker.get('name'), worker.get('host'))
    quit()
do_showworkers = defer_generator(do_showworkers)

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
            ('showworkers',
             'shows all the workers that are logged into the manager',
             (),
             do_showworkers),
            ('invoke',
             'invoke a component method',
             (('component-path', utils.avatarId),
              ('method-name', str)),
             do_invoke),
            ('loadconfiguration',
             'load configuration into the manager',
             (('conf-file', str),
              ('save-as', str, None),
              ),
             do_loadconfiguration),
            )

