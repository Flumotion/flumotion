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

"""command registry and command implementations"""

import os

from twisted.internet import defer

from flumotion.twisted.defer import defer_generator
from flumotion.admin.command import utils
from flumotion.common.planet import moods
from flumotion.common import errors, log, componentui, common

__all__ = ['commands']
__version__ = "$Rev$"


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

    def show_uistate(k, v, indent=0):
        if isinstance(v, list):
            show_uistate(k, '<list>', indent)
            for x in v:
                show_uistate(None, x, indent+4)
        elif isinstance(v, dict):
            show_uistate(k, '<dict>', indent)
            keys = v.keys()
            keys.sort()
            for k in keys:
                show_uistate(k, v[k], indent+4)
        elif isinstance(v, componentui.AdminComponentUIState):
            show_uistate(k, '<uistate>', indent)
            keys = v.keys()
            keys.sort()
            for k in keys:
                show_uistate(k, v.get(k), indent+4)
        else:
            print '%s%s%s' % (' '*indent, k and k+': ' or '', v)

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
        try:
            ui = d.value()
            if ui:
                print
                show_uistate('UI state', ui)
        except Exception, e:
            print 'Error while retrieving UI state:', \
                  log.getExceptionMessage(e)
    quit()
do_showcomponent = defer_generator(do_showcomponent)


class ParseException(Exception):
    pass


def _parse_typed_args(spec, args):

    def _readFile(filename):
        try:
            f = open(filename)
            contents = f.read()
            f.close()
            return contents
        except OSError:
            raise ParseException("Failed to read file %s" % (filename, ))

    def _do_parse_typed_args(spec, args):
        accum = []
        while spec:
            argtype = spec.pop(0)
            parsers = {'i': int, 's': str, 'b': common.strToBool,
                'F': _readFile}
            if argtype == ')':
                return tuple(accum)
            elif argtype == '(':
                accum.append(_do_parse_typed_args(spec, args))
            elif argtype == '}':
                return dict(accum)
            elif argtype == '{':
                accum.append(_do_parse_typed_args(spec, args))
            elif argtype == ']':
                return accum
            elif argtype == '[':
                accum.append(_do_parse_typed_args(spec, args))
            elif argtype not in parsers:
                raise ParseException('Unknown argument type: %r'
                                     % argtype)
            else:
                parser = parsers[argtype]
                try:
                    arg = args.pop(0)
                except IndexError:
                    raise ParseException('Missing argument of type %r'
                                         % parser)
                try:
                    accum.append(parser(arg))
                except Exception, e:
                    raise ParseException('Failed to parse %s as %r: %s'
                                         % (arg, parser, e))

    spec = list(spec) + [')']
    args = list(args)

    try:
        res = _do_parse_typed_args(spec, args)
    except ParseException, e:
        print e.args[0]
        return None

    if args:
        print 'Left over arguments:', args
        return None
    else:
        return res


def do_invoke(model, quit, avatarId, methodName, *args):
    d = model.callRemote('getPlanetState')
    yield d
    planet = d.value()
    c = utils.find_component(planet, avatarId)
    if not c:
        print "Could not find component %r" % avatarId
        quit()
        yield None

    if args:
        args = _parse_typed_args(args[0], args[1:])
        if args is None:
            quit()
            yield None

    d = model.componentCallRemote(c, methodName, *args)
    yield d

    try:
        v = d.value()
        print "Invoke of %s on %s was successful." % (methodName,
            avatarId[1])
        print v
    except errors.NoMethodError:
        print "No method '%s' on component '%s'" % (methodName, avatarId)
    except errors.SleepingComponentError:
        print "Component %s not running." % avatarId[1]

    quit()
do_invoke = defer_generator(do_invoke)


def do_workerinvoke(model, quit, workerName, moduleName, methodName, *args):
    if args:
        args = _parse_typed_args(args[0], args[1:])
        if args is None:
            quit()
            yield None

    d = model.callRemote('workerCallRemote', workerName, 'runFunction',
                         moduleName, methodName, *args)
    yield d

    try:
        v = d.value()
        print "Invoke of %s on %s was successful." % (methodName, workerName)
        print v
    except errors.NoMethodError:
        print "No method '%s' on component '%s'" % (methodName, workerName)

    quit()
do_workerinvoke = defer_generator(do_workerinvoke)


def do_workerremoteinvoke(model, quit, workerName, methodName, *args):
    if args:
        args = _parse_typed_args(args[0], args[1:])
        if args is None:
            quit()
            yield None

    d = model.callRemote('workerCallRemote', workerName, methodName, *args)
    yield d

    try:
        v = d.value()
        print "Invoke of %s on %s was successful." % (methodName, workerName)
        print v
    except errors.NoMethodError:
        print "No method '%s' on component '%s'" % (methodName, workerName)

    quit()
do_workerremoteinvoke = defer_generator(do_workerremoteinvoke)


def do_managerinvoke(model, quit, methodName, *args):
    if args:
        args = _parse_typed_args(args[0], args[1:])
        if args is None:
            quit()
            yield None

    d = model.callRemote(methodName, *args)
    yield d

    try:
        v = d.value()
        print "Invoke of %s was successful." % (methodName, )
        print v
    except errors.NoMethodError:
        print "No method '%s' on manager" % (methodName, )

    quit()
do_managerinvoke = defer_generator(do_managerinvoke)


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


class MoodListener(defer.Deferred):

    def __init__(self, moods, state):
        defer.Deferred.__init__(self)
        self._moodsFinal = moods
        state.addListener(self, set_=self.stateSet)

    def stateSet(self, object, key, value):
        if key == 'mood' and moods[value] in self._moodsFinal:
            self.callback(moods[value])

# FIXME: nicer to rewrite do_stop, do_start and do_delete to run some common
# code


def do_avatar_action(model, quit, avatarPath, action):
    """
    @type action: a tuple of (actionName, remoteCall, moods, checkMoodFunc)
    """
    d = model.callRemote('getPlanetState')
    yield d
    planet = d.value()
    components = []
    if avatarPath[0] == 'flow':
        flows = planet.get('flows')
        flow_to_act = None
        for f in flows:
            if avatarPath[1] == f.get('name'):
                flow_to_act = f
        if flow_to_act == None:
            print "The flow %s is not found." % avatarPath[1]
            quit()
        else:
            components = flow_to_act.get('components')
    elif avatarPath[0] == 'atmosphere':
        components = planet.get('atmosphere').get('components')
    elif avatarPath[0] == 'root':
        flows = planet.get('flows')
        for f in flows:
            components = components + f.get('components')
        components = components + planet.get('atmosphere').get('components')
    else:
        c = utils.find_component(planet, avatarPath[1:])
        if c:
            components.append(c)
        # else: message already printed in find_component()

    if len(components) > 0:

        def actionComponent(c):
            if action[3](moods[c.get('mood')]):
                return model.callRemote(action[1], c)
            else:
                print "Cannot %s component /%s/%s, it is in mood: %s." % (
                    action[0],
                    c.get("parent").get("name"), c.get("name"),
                    moods[c.get("mood")].name)
                return None
        dl = []
        for comp in components:
            actD = actionComponent(comp)
            # maybeDeferred won't work here due to python lexicals
            if actD:
                dl.append(actD)
                if action[2]:
                    # wait for component to be in certain moods
                    dl.append(MoodListener(action[2], comp))
        d = defer.DeferredList(dl)
        yield d
        d.value()
        if avatarPath[0] == 'flow':
            print "Components in flow now completed action %s." % action[0]
        elif avatarPath[0] == 'atmosphere':
            print "Components in atmosphere now completed action %s." % (
                action[0], )
        elif avatarPath[0] == 'root':
            print "Components in / now completed action %s." % action[0]
        else:
            print "Component now completed action %s." % action[0]
    quit()
do_avatar_action = defer_generator(do_avatar_action)


def do_stop(model, quit, avatarPath):
    return do_avatar_action(model, quit, avatarPath, ('stop', 'componentStop',
        (moods.sleeping, ), moods.can_stop))


def do_start(model, quit, avatarPath):
    return do_avatar_action(model, quit, avatarPath, (
        'start', 'componentStart',
        (moods.happy, moods.sad), moods.can_start))


def do_delete(model, quit, avatarPath):
    return do_avatar_action(model, quit, avatarPath, ('delete',
        'deleteComponent', None, lambda m: not moods.can_stop(m)))

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
              ('method-name', str),
              ('args', str, None, True)),
             do_invoke),
            ('workerinvoke',
             'invoke an arbitrary function on a worker',
             (('worker-name', str),
              ('module-name', str),
              ('method-name', str),
              ('args', str, None, True)),
             do_workerinvoke),
            ('workerremoteinvoke',
             'invoke a remote function on a manager',
             (('method-name', str),
              ('args', str, None, True)),
             do_workerremoteinvoke),
            ('managerinvoke',
             'invoke a function on a manager',
             (('method-name', str),
              ('args', str, None, True)),
             do_managerinvoke),
            ('loadconfiguration',
             'load configuration into the manager',
             (('conf-file', str),
              ('save-as', str, None),
              ),
             do_loadconfiguration),
            ('stop',
             'stops a component, flow or all flows',
             (('path', utils.avatarPath),
             ),
             do_stop),
            ('start',
             'starts a componment, all components in a flow or all flows',
             (('path', utils.avatarPath),
             ),
             do_start),
            ('delete',
             'deletes a component, all components in a flow or all flows',
             (('path', utils.avatarPath),
             ),
             do_delete)
            )
