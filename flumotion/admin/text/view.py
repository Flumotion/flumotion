# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.
4
"""main interface for the cursor admin client"""

import curses
import os
import string

import gobject
from twisted.internet import reactor
from twisted.python import rebuild
from zope.interface import implements

from flumotion.common import log, errors, common
from flumotion.twisted import flavors, reflect
from flumotion.common.planet import moods

from flumotion.admin.text import misc_curses

__version__ = "$Rev$"


class AdminTextView(log.Loggable, gobject.GObject, misc_curses.CursesStdIO):

    implements(flavors.IStateListener)

    logCategory = 'admintextview'

    global_commands = ['startall', 'stopall', 'clearall', 'quit']

    LINES_BEFORE_COMPONENTS = 5
    LINES_AFTER_COMPONENTS = 6

    def __init__(self, model, stdscr):
        self.initialised = False
        self.stdscr = stdscr
        self.inputText = ''
        self.command_result = ""
        self.lastcommands = []
        self.nextcommands = []
        self.rows, self.cols = self.stdscr.getmaxyx()
        self.max_components_per_page = self.rows - \
            self.LINES_BEFORE_COMPONENTS - \
            self.LINES_AFTER_COMPONENTS
        self._first_onscreen_component = 0

        self._components = {}
        self._comptextui = {}
        self._setAdminModel(model)
        # get initial info we need
        self.setPlanetState(self.admin.planet)

    def _setAdminModel(self, model):
        self.admin = model

        self.admin.connect('connected', self.admin_connected_cb)
        self.admin.connect('disconnected', self.admin_disconnected_cb)
        self.admin.connect('connection-refused',
                           self.admin_connection_refused_cb)
        self.admin.connect('connection-failed',
                           self.admin_connection_failed_cb)
        #self.admin.connect('component-property-changed',
        #    self.property_changed_cb)
        self.admin.connect('update', self.admin_update_cb)

    # show the whole text admin screen

    def show(self):
        self.initialised = True
        self.stdscr.addstr(0, 0, "Main Menu")
        self.show_components()
        self.display_status()
        self.stdscr.move(self.lasty, 0)
        self.stdscr.clrtoeol()
        self.stdscr.move(self.lasty+1, 0)
        self.stdscr.clrtoeol()
        self.stdscr.addstr(self.lasty+1, 0, "Prompt: %s" % self.inputText)
        self.stdscr.refresh()
        #gobject.io_add_watch(0, gobject.IO_IN, self.keyboard_input_cb)

    # show the view of components and their mood
    # called from show

    def show_components(self):
        if self.initialised:
            self.stdscr.addstr(2, 0, "Components:")
            # get a dictionary of components
            names = self._components.keys()
            names.sort()

            cury = 4

            # if number of components is less than the space add
            # "press page up for previous components" and
            # "press page down for next components" lines
            if len(names) > self.max_components_per_page:
                if self._first_onscreen_component > 0:
                    self.stdscr.move(cury, 0)
                    self.stdscr.clrtoeol()
                    self.stdscr.addstr(cury, 0,
                        "Press page up to scroll up components list")
                    cury=cury+1
            cur_component = self._first_onscreen_component
            for name in names[self._first_onscreen_component:len(names)]:
                # check if too many components for screen height
                if cury - self.LINES_BEFORE_COMPONENTS >= \
                        self.max_components_per_page:
                    self.stdscr.move(cury, 0)
                    self.stdscr.clrtoeol()
                    self.stdscr.addstr(cury, 0,
                        "Press page down to scroll down components list")
                    cury = cury + 1
                    break

                component = self._components[name]
                mood = component.get('mood')
                # clear current component line
                self.stdscr.move(cury, 0)
                self.stdscr.clrtoeol()
                # output component name and mood
                self.stdscr.addstr(cury, 0, "%s: %s" % (
                    name, moods[mood].name))
                cury = cury + 1
                cur_component = cur_component + 1

            self.lasty = cury
            #self.stdscr.refresh()

    def gotEntryCallback(self, result, name):
        entryPath, filename, methodName = result
        filepath = os.path.join(entryPath, filename)
        self.debug('Got the UI for %s and it lives in %s' % (name, filepath))
        self.uidir = os.path.split(filepath)[0]
        #handle = open(filepath, "r")
        #data = handle.read()
        #handle.close()

        # try loading the class
        moduleName = common.pathToModuleName(filename)
        statement = 'import %s' % moduleName
        self.debug('running %s' % statement)
        try:
            exec(statement)
        except SyntaxError, e:
            # the syntax error can happen in the entry file, or any import
            where = getattr(e, 'filename', "<entry file>")
            lineno = getattr(e, 'lineno', 0)
            msg = "Syntax Error at %s:%d while executing %s" % (
                where, lineno, filename)
            self.warning(msg)
            raise errors.EntrySyntaxError(msg)
        except NameError, e:
            # the syntax error can happen in the entry file, or any import
            msg = "NameError while executing %s: %s" % (filename,
                " ".join(e.args))
            self.warning(msg)
            raise errors.EntrySyntaxError(msg)
        except ImportError, e:
            msg = "ImportError while executing %s: %s" % (filename,
                " ".join(e.args))
            self.warning(msg)
            raise errors.EntrySyntaxError(msg)

        # make sure we're running the latest version
        module = reflect.namedAny(moduleName)
        rebuild.rebuild(module)

        # check if we have the method
        if not hasattr(module, methodName):
            self.warning('method %s not found in file %s' % (
                methodName, filename))
            raise #FIXME: something appropriate
        klass = getattr(module, methodName)

        # instantiate the GUIClass, giving ourself as the first argument
        # FIXME: we cheat by giving the view as second for now,
        # but let's decide for either view or model
        instance = klass(self._components[name], self.admin)
        self.debug("Created entry instance %r" % instance)

        #moduleName = common.pathToModuleName(fileName)
        #statement = 'import %s' % moduleName
        self._comptextui[name] = instance

    def gotEntryNoBundleErrback(self, failure, name):
        failure.trap(errors.NoBundleError)
        self.debug("No admin ui for component %s" % name)

    def gotEntrySleepingComponentErrback(self, failure):
        failure.trap(errors.SleepingComponentError)

    def getEntry(self, componentState, type):
        """
        Do everything needed to set up the entry point for the given
        component and type, including transferring and setting up bundles.

        Caller is responsible for adding errbacks to the deferred.

        @returns: a deferred returning (entryPath, filename, methodName) with
                  entryPath: the full local path to the bundle's base
                  fileName:  the relative location of the bundled file
                  methodName: the method to instantiate with
        """
        lexicalVariableHack = []

        def gotEntry(res):
            fileName, methodName = res
            lexicalVariableHack.append(res)
            self.debug("entry for %r of type %s is in file %s and method %s",
                       componentState, type, fileName, methodName)
            return self.admin.bundleLoader.getBundles(fileName=fileName)

        def gotBundles(res):
            name, bundlePath = res[-1]
            fileName, methodName = lexicalVariableHack[0]
            return (bundlePath, fileName, methodName)

        d = self.admin.callRemote('getEntryByType',
                                  componentState.get('type'), type)
        d.addCallback(gotEntry)
        d.addCallback(gotBundles)
        return d

    def update_components(self, components):
        for name in self._components.keys():
            component = self._components[name]
            try:
                component.removeListener(self)
            except KeyError:
                # do nothing
                self.debug("silly")

        def compStateSet(state, key, value):
            self.log('stateSet: state %r, key %s, value %r' % (
                state, key, value))

            if key == 'mood':
                # this is needed so UIs load if they change to happy
                # get bundle for component
                d = self.getEntry(state, 'admin/text')
                d.addCallback(self.gotEntryCallback, state.get('name'))
                d.addErrback(self.gotEntryNoBundleErrback, state.get('name'))
                d.addErrback(self.gotEntrySleepingComponentErrback)

                self.show()
            elif key == 'name':
                if value:
                    self.show()

        self._components = components
        for name in self._components.keys():
            component = self._components[name]
            component.addListener(self, set_=compStateSet)

            # get bundle for component
            d = self.getEntry(component, 'admin/text')
            d.addCallback(self.gotEntryCallback, name)
            d.addErrback(self.gotEntryNoBundleErrback, name)
            d.addErrback(self.gotEntrySleepingComponentErrback)

        self.show()

    def setPlanetState(self, planetState):

        def flowStateAppend(state, key, value):
            self.debug('flow state append: key %s, value %r' % (key, value))
            if state.get('name') != 'default':
                return
            if key == 'components':
                self._components[value.get('name')] = value
                # FIXME: would be nicer to do this incrementally instead
                self.update_components(self._components)

        def flowStateRemove(state, key, value):
            if state.get('name') != 'default':
                return
            if key == 'components':
                name = value.get('name')
                self.debug('removing component %s' % name)
                del self._components[name]
                # FIXME: would be nicer to do this incrementally instead
                self.update_components(self._components)

        def atmosphereStateAppend(state, key, value):
            if key == 'components':
                self._components[value.get('name')] = value
                # FIXME: would be nicer to do this incrementally instead
                self.update_components(self._components)

        def atmosphereStateRemove(state, key, value):
            if key == 'components':
                name = value.get('name')
                self.debug('removing component %s' % name)
                del self._components[name]
                # FIXME: would be nicer to do this incrementally instead
                self.update_components(self._components)

        def planetStateAppend(state, key, value):
            if key == 'flows':
                if value.get('name') != 'default':
                    return
                #self.debug('default flow started')
                value.addListener(self, append=flowStateAppend,
                                  remove=flowStateRemove)
                for c in value.get('components'):
                    flowStateAppend(value, 'components', c)

        def planetStateRemove(state, key, value):
            self.debug('something got removed from the planet')

        self.debug('parsing planetState %r' % planetState)
        self._planetState = planetState

        # clear and rebuild list of components that interests us
        self._components = {}

        planetState.addListener(self, append=planetStateAppend,
                                remove=planetStateRemove)

        a = planetState.get('atmosphere')
        a.addListener(self, append=atmosphereStateAppend,
                      remove=atmosphereStateRemove)
        for c in a.get('components'):
            atmosphereStateAppend(a, 'components', c)

        for f in planetState.get('flows'):
            planetStateAppend(f, 'flows', f)

    def _component_stop(self, state):
        return self._component_do(state, 'Stop', 'Stopping', 'Stopped')

    def _component_start(self, state):
        return self._component_do(state, 'Start', 'Starting', 'Started')

    def _component_do(self, state, action, doing, done):
        name = state.get('name')
        if not name:
            return None

        self.admin.callRemote('component'+action, state)

    def run_command(self, command):
        # this decides whether startall, stopall and clearall are allowed
        can_stop = True
        can_start = True
        for x in self._components.values():
            mood = moods.get(x.get('mood'))
            can_stop = can_stop and (mood != moods.lost and
                                     mood != moods.sleeping)
            can_start = can_start and (mood == moods.sleeping)
        can_clear = can_start and not can_stop

        if string.lower(command) == 'quit':
            reactor.stop()
        elif string.lower(command) == 'startall':
            if can_start:
                for c in self._components.values():
                    self._component_start(c)
                self.command_result = 'Attempting to start all components'
            else:
                self.command_result = (
                    'Components not all in state to be started')


        elif string.lower(command) == 'stopall':
            if can_stop:
                for c in self._components.values():
                    self._component_stop(c)
                self.command_result = 'Attempting to stop all components'
            else:
                self.command_result = (
                    'Components not all in state to be stopped')
        elif string.lower(command) == 'clearall':
            if can_clear:
                self.admin.cleanComponents()
                self.command_result = 'Attempting to clear all components'
            else:
                self.command_result = (
                    'Components not all in state to be cleared')
        else:
            command_split = command.split()
            # if at least 2 tokens in the command
            if len(command_split)>1:
                # check if the first is a component name
                for c in self._components.values():
                    if string.lower(c.get('name')) == (
                        string.lower(command_split[0])):
                        # bingo, we have a component
                        if string.lower(command_split[1]) == 'start':
                            # start component
                            self._component_start(c)
                        elif string.lower(command_split[1]) == 'stop':
                            # stop component
                            self._component_stop(c)
                        else:
                            # component specific commands
                            try:
                                textui = self._comptextui[c.get('name')]

                                if textui:
                                    d = textui.runCommand(
                                        ' '.join(command_split[1:]))
                                    self.debug(
                                        "textui runcommand defer: %r" % d)
                                    # add a callback
                                    d.addCallback(self._runCommand_cb)

                            except KeyError:
                                pass

    def _runCommand_cb(self, result):
        self.command_result = result
        self.debug("Result received: %s" % result)
        self.show()

    def get_available_commands(self, input):
        input_split = input.split()
        last_input=''
        if len(input_split) >0:
            last_input = input_split[len(input_split)-1]
        available_commands = []
        if len(input_split) <= 1 and not input.endswith(' '):
            # this decides whether startall, stopall and clearall are allowed
            can_stop = True
            can_start = True
            for x in self._components.values():
                mood = moods.get(x.get('mood'))
                can_stop = can_stop and (mood != moods.lost and
                                         mood != moods.sleeping)
                can_start = can_start and (mood == moods.sleeping)
            can_clear = can_start and not can_stop

            for command in self.global_commands:
                command_ok = (command != 'startall' and
                              command != 'stopall' and
                              command != 'clearall')
                command_ok = command_ok or (command == 'startall' and
                                            can_start)
                command_ok = command_ok or (command == 'stopall' and
                                            can_stop)
                command_ok = command_ok or (command == 'clearall' and
                                            can_clear)

                if (command_ok and string.lower(command).startswith(
                    string.lower(last_input))):
                    available_commands.append(command)
        else:
            available_commands = (available_commands +
                                  self.get_available_commands_for_component(
                input_split[0], input))

        return available_commands

    def get_available_commands_for_component(self, comp, input):
        self.debug("getting commands for component %s" % comp)
        commands = []
        for c in self._components:
            if c == comp:
                component_commands = ['start', 'stop']
                textui = None
                try:
                    textui = self._comptextui[comp]
                except KeyError:
                    self.debug("no text ui for component %s" % comp)

                input_split = input.split()

                if len(input_split) >= 2 or input.endswith(' '):
                    for command in component_commands:
                        if len(input_split) == 2:
                            if command.startswith(input_split[1]):
                                commands.append(command)
                        elif len(input_split) == 1:
                            commands.append(command)
                    if textui:
                        self.debug(
                            "getting component commands from ui of %s" % comp)
                        comp_input = ' '.join(input_split[1:])
                        if input.endswith(' '):
                            comp_input = comp_input + ' '
                        commands = commands + textui.getCompletions(comp_input)

        return commands

    def get_available_completions(self, input):
        completions = self.get_available_commands(input)

        # now if input has no spaces, add the names of each component that
        # starts with input
        if len(input.split()) <= 1:
            for c in self._components:
                if c.startswith(input):
                    completions.append(c)

        return completions

    def display_status(self):
        availablecommands = self.get_available_commands(self.inputText)
        available_commands = ' '.join(availablecommands)
        #for command in availablecommands:
        #    available_commands = '%s %s' % (available_commands, command)
        self.stdscr.move(self.lasty+2, 0)
        self.stdscr.clrtoeol()

        self.stdscr.addstr(self.lasty+2, 0,
            "Available Commands: %s" % available_commands)
        # display command results
        self.stdscr.move(self.lasty+3, 0)
        self.stdscr.clrtoeol()
        self.stdscr.move(self.lasty+4, 0)
        self.stdscr.clrtoeol()

        if self.command_result != "":
            self.stdscr.addstr(self.lasty+4,
                               0, "Result: %s" % self.command_result)
        self.stdscr.clrtobot()

    ### admin model callbacks

    def admin_connected_cb(self, admin):
        self.info('Connected to manager')

        # get initial info we need
        self.setPlanetState(self.admin.planet)

        if not self._components:
            self.debug('no components detected, running wizard')
            # ensure our window is shown
            self.show()

    def admin_disconnected_cb(self, admin):
        message = "Lost connection to manager, reconnecting ..."
        print message

    def admin_connection_refused_cb(self, admin):
        log.debug('textadminclient', "handling connection-refused")
        #reactor.callLater(0, self.admin_connection_refused_later, admin)
        log.debug('textadminclient', "handled connection-refused")

    def admin_connection_failed_cb(self, admin):
        log.debug('textadminclient', "handling connection-failed")
        #reactor.callLater(0, self.admin_connection_failed_later, admin)
        log.debug('textadminclient', "handled connection-failed")

    def admin_update_cb(self, admin):
        self.update_components(self._components)

    def connectionLost(self, why):
        # do nothing
        pass

    def whsStateAppend(self, state, key, value):
        if key == 'names':
            self.debug('Worker %s logged in.' % value)

    def whsStateRemove(self, state, key, value):
        if key == 'names':
            self.debug('Worker %s logged out.' % value)

    # act as keyboard input

    def doRead(self):
        """ Input is ready! """
        c = self.stdscr.getch() # read a character

        if c == curses.KEY_BACKSPACE or c == 127:
            self.inputText = self.inputText[:-1]
        elif c == curses.KEY_STAB or c == 9:
            available_commands = self.get_available_completions(self.inputText)
            if len(available_commands) == 1:
                input_split = self.inputText.split()
                if len(input_split) > 1:
                    if not self.inputText.endswith(' '):
                        input_split.pop()
                    self.inputText = (
                        ' '.join(input_split) + ' ' + available_commands[0])
                else:
                    self.inputText = available_commands[0]

        elif c == curses.KEY_ENTER or c == 10:
            # run command
            self.run_command(self.inputText)
            # re-display status
            self.display_status()
            # clear the prompt line
            self.stdscr.move(self.lasty+1, 0)
            self.stdscr.clrtoeol()
            self.stdscr.addstr(self.lasty+1, 0, 'Prompt: ')
            self.stdscr.refresh()
            if len(self.nextcommands) > 0:
                self.lastcommands = self.lastcommands + self.nextcommands
                self.nextcommands = []
            self.lastcommands.append(self.inputText)
            self.inputText = ''
            self.command_result = ''
        elif c == curses.KEY_UP:
            lastcommand = ""
            if len(self.lastcommands) > 0:
                lastcommand = self.lastcommands.pop()
            if self.inputText != "":
                self.nextcommands.append(self.inputText)
            self.inputText = lastcommand
        elif c == curses.KEY_DOWN:
            nextcommand = ""
            if len(self.nextcommands) > 0:
                nextcommand = self.nextcommands.pop()
            if self.inputText != "":
                self.lastcommands.append(self.inputText)
            self.inputText = nextcommand
        elif c == curses.KEY_PPAGE: # page up
            if self._first_onscreen_component > 0:
                self._first_onscreen_component = \
                    self._first_onscreen_component - 1
                self.show()
        elif c == curses.KEY_NPAGE: # page down
            if self._first_onscreen_component < len(self._components) - \
                    self.max_components_per_page:
                self._first_onscreen_component = \
                    self._first_onscreen_component + 1
                self.show()

        else:
            # too long
            if len(self.inputText) == self.cols-2:
                return
            # add to input text
            if c<=256:
                self.inputText = self.inputText + chr(c)

        # redisplay status
        self.display_status()

        self.stdscr.move(self.lasty+1, 0)
        self.stdscr.clrtoeol()

        self.stdscr.addstr(self.lasty+1, 0, 'Prompt: %s' % self.inputText)
        self.stdscr.refresh()


    # remote calls
    # eg from components notifying changes

    def componentCall(self, componentState, methodName, *args, **kwargs):
        # FIXME: for now, we only allow calls to go through that have
        # their UI currently displayed.  In the future, maybe we want
        # to create all UI's at startup regardless and allow all messages
        # to be processed, since they're here now anyway
        self.log("componentCall received for %r.%s ..." % (
            componentState, methodName))
        localMethodName = "component_%s" % methodName
        name = componentState.get('name')

        try:
            textui = self._comptextui[name]
        except KeyError:
            return

        if not hasattr(textui, localMethodName):
            self.log("... but does not have method %s" % localMethodName)
            self.warning("Component view %s does not implement %s" % (
                name, localMethodName))
            return
        self.log("... and executing")
        method = getattr(textui, localMethodName)

        # call the method, catching all sorts of stuff
        try:
            result = method(*args, **kwargs)
        except TypeError:
            msg = ("component method %s did not"
                   " accept *a %s and **kwa %s (or TypeError)") % (
                methodName, args, kwargs)
            self.debug(msg)
            raise errors.RemoteRunError(msg)
        self.log("component: returning result: %r to caller" % result)
        return result
