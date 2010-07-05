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
component commands
"""

from twisted.python import failure

from flumotion.common import errors, planet, log
from flumotion.common import common as fccommon
from flumotion.monitor.nagios import util
from flumotion.common.planet import moods

from flumotion.admin.command import common

__version__ = "$Rev: 6562 $"


class Delete(common.AdminCommand):
    description = "Delete a component."

    def doCallback(self, args):
        if not self.parentCommand.componentId:
            common.errorRaise("Please specify a component id "
                "with 'component -i [component-id]'")

        d = self.getRootCommand().medium.callRemote('deleteComponent',
            self.parentCommand.componentState)

        def cb(result):
            self.stdout.write("Deleted component.\n")

        def eb(failure):
            if failure.check(errors.ComponentMoodError,
                             errors.BusyComponentError):
                common.errorRaise("Component '%s' is in the wrong mood." %
                    self.parentCommand.componentId)
            else:
                common.errorRaise(log.getFailureMessage(failure))

        d.addCallback(cb)
        d.addErrback(eb)

        return d


class Invoke(common.AdminCommand):
    usage = "[method-name] [arguments]"
    summary = "invoke a method on a component"
    description = """Invoke a method on a component.
%s
For a list of methods that can be invoked, see the component's medium class
and its remote_* methods.

Examples: getConfig, setFluDebug""" % common.ARGUMENTS_DESCRIPTION

    def addOptions(self):
        self.parser.add_option('-r', '--raw-output',
                               action="store_true", dest="rawOutput",
                               help="do not pretty print the output")

    def handleOptions(self, options):
        self.rawOutput = options.rawOutput

    def doCallback(self, args):
        if not self.parentCommand.componentId:
            common.errorRaise("Please specify a component id "
                "with 'component -i [component-id]'")

        try:
            methodName = args[0]
        except IndexError:
            common.errorRaise('Please specify a method name to invoke.')
        if len(args) > 1:
            args = common.parseTypedArgs(args[1], args[2:])
            if args is None:
                common.errorRaise('Could not parse arguments.')
        else:
            args = []

        p = self.parentCommand
        d = self.getRootCommand().medium.componentCallRemote(
            self.parentCommand.componentState, methodName, *args)

        def cb(result):
            if self.rawOutput:
                self.stdout.write(str(result))
            else:
                import pprint
                self.stdout.write("Invoking '%s' on '%s' returned:\n%s\n" % (
                        methodName, p.componentId, pprint.pformat(result)))

        def eb(failure):
            if failure.check(errors.NoMethodError):
                common.errorRaise("No method '%s' on component '%s'." % (
                    methodName, p.componentId))
            elif failure.check(errors.SleepingComponentError):
                common.errorRaise(
                    "Component '%s' is sleeping." % p.componentId)
            else:
                common.errorRaise(log.getFailureMessage(failure))

        d.addCallback(cb)
        d.addErrback(eb)

        return d


class List(common.AdminCommand):
    description = "List components."

    def doCallback(self, args):
        p = self.parentCommand
        a = p.planetState.get('atmosphere')
        if a.get('components'):
            self.stdout.write('atmosphere:\n')
            for c in a.get('components'):
                self.stdout.write('    ' + c.get('name') + '\n')

        for f in p.planetState.get('flows'):
            if f.get('components'):
                self.stdout.write('%s flow:\n' % f.get('name'))
                for c in f.get('components'):
                    self.stdout.write('    ' + c.get('name') + '\n')


class DetailedList(common.AdminCommand):
    description = "List components with types and worker hosts."

    def doCallback(self, args):
        p = self.parentCommand
        a = p.planetState.get('atmosphere')
        s = p.workerHeavenState
        workers = s.get('workers')
        a_comps = a.get('components')
        if a_comps:
            self.stdout.write('atmosphere:\n')
            self.parentCommand.print_components(a_comps, workers)

        for f in p.planetState.get('flows'):
            f_comps = f.get('components')
            if f_comps:
                self.stdout.write('%s flow:\n' % f.get('name'))
                self.parentCommand.print_components(f_comps, workers)


class UpstreamList(common.AdminCommand):
    description = """List a component and its upstream components along
with types and worker hosts."""

    def get_eaters_ids(self, eaters_dic):
        avatars = []
        for flow in eaters_dic.keys():
            comps = eaters_dic[flow]
            for c in comps:
                (name, what) = c[0].split(':')
                avatars.append('/%s/%s' % (flow, name))
        return avatars

    def doCallback(self, args):
        p = self.parentCommand
        s = p.workerHeavenState
        workers = s.get('workers')

        if not p.componentId:
            common.errorRaise("Please specify a component id "
                "with 'component -i [component-id]'")

        eaters = p.componentState.get('config').get('eater', {})
        eaters_id = self.get_eaters_ids(eaters)
        comps = [p.componentState]
        while len(eaters_id) > 0:
            eaters = {}
            for i in eaters_id:
                try:
                    compState = util.findComponent(p.planetState, i)
                    comps.append(compState)
                    eaters.update(compState.get('config').get('eater', {}))
                except Exception, e:
                    self.debug(log.getExceptionMessage(e))
                    common.errorRaise("Error retrieving component '%s'" % i)
            eaters_id = self.get_eaters_ids(eaters)

        self.stdout.write('Upstream Components:\n')
        self.parentCommand.print_components(comps, workers)


class Mood(common.AdminCommand):
    description = "Check the mood of a component."

    def doCallback(self, args):
        if not self.parentCommand.componentId:
            common.errorRaise("Please specify a component id "
                "with 'component -i [component-id]'")

        p = self.parentCommand
        moodValue = p.componentState.get('mood')
        moodName = planet.moods.get(moodValue).name
        self.stdout.write("Component '%s' is %s.\n" % (p.componentId,
            moodName))


class PropertyGet(common.AdminCommand):
    description = "Get a property of a component."
    name = 'get'

    def do(self, args):
        if not args:
            return common.errorReturn('Please specify a property to get.')

        self._propertyName = args[0]

        return common.AdminCommand.do(self, args)

    def doCallback(self, args):
        u = self.parentCommand.uiState
        name = self._propertyName

        if not u.hasKey(name):
            common.errorRaise("Component '%s' does not have property '%s'." % (
                self.parentCommand.parentCommand.componentId, name))

        self.stdout.write("Property '%s' is '%r'.\n" % (
            name, u.get(name)))


class PropertyList(common.AdminCommand):
    description = "List properties of a component."
    name = 'list'

    def doCallback(self, args):
        l = self.parentCommand.uiState.keys()
        l.sort()
        self.stdout.write('Properties:\n')
        for p in l:
            self.stdout.write('- %s\n' % p)

# FIXME: why is this called property when it really is about ui state ?


class Property(util.LogCommand):
    """
    @param uiState: the ui state of the component; set after logging in.
    """

    description = "Act on properties of a component."

    subCommandClasses = [PropertyGet, PropertyList]

    def handleOptions(self, options):
        if not self.parentCommand.componentId:
            common.errorRaise("Please specify a component id "
                "with 'component -i [component-id]'")

        # call our callback after connecting
        d = self.getRootCommand().loginDeferred
        d.addCallback(self._callback)
        d.addErrback(self._errback)

    def _callback(self, result):

        def getUIStateCb(uiState):
            self.uiState = uiState

        componentCommand = self.parentCommand
        model = componentCommand.parentCommand.medium
        d = model.componentCallRemote(
            componentCommand.componentState, 'getUIState')
        d.addCallback(getUIStateCb)
        return d

    def _errback(self, failure):
        failure.trap(errors.SleepingComponentError)
        common.errorRaise("Component '%s' is sleeping." %
            self.parentCommand.componentId)


class Start(common.AdminCommand):
    description = "Start a component."

    def doCallback(self, args):
        if not self.parentCommand.componentId:
            common.errorRaise("Please specify a component id "
                "with 'component -i [component-id]'")

        p = self.parentCommand
        moodValue = p.componentState.get('mood')
        if moodValue == moods.happy.value:
            self.stdout.write("Component is already happy.\n")
            return 0

        d = self.getRootCommand().medium.callRemote('componentStart',
            self.parentCommand.componentState)

        def cb(result):
            self.stdout.write("Started component.\n")

        def eb(failure):
            if failure.trap(errors.ComponentMoodError):
                common.errorRaise("Component '%s' is in the wrong mood." %
                    self.parentCommand.componentId)
            else:
                common.errorRaise(log.getFailureMessage(failure))

        d.addCallback(cb)
        d.addErrback(eb)

        return d


class Stop(common.AdminCommand):
    description = "Stop a component."

    def doCallback(self, args):
        if not self.parentCommand.componentId:
            common.errorRaise("Please specify a component id "
                "with 'component -i [component-id]'")

        p = self.parentCommand
        moodValue = p.componentState.get('mood')
        if moodValue == moods.sleeping.value:
            self.stdout.write("Component is already sleeping.\n")
            return 0

        d = self.getRootCommand().medium.callRemote('componentStop',
            self.parentCommand.componentState)

        def cb(result):
            self.stdout.write("Stopped component.\n")

        def eb(failure):
            if failure.trap(errors.ComponentMoodError):
                common.errorRaise("Component '%s' is in the wrong mood." %
                    self.parentCommand.componentId)
            else:
                common.errorRaise(log.getFailureMessage(failure))

        d.addCallback(cb)
        d.addErrback(eb)

        return d


class Component(util.LogCommand):
    """
    @ivar  componentId:    the component id, passed as an argument
    @ivar  componentState: the component state; set when logged in to manager.
    @type  componentState: L{flumotion.common.state.AdminComponentState}
    @ivar  planetState:    the planet state; set when logged in to manager.
    @type  planetState:    L{flumotion.common.state.AdminPlanetState}
    """
    description = "Act on a component."
    usage = "-i [component id]"

    subCommandClasses = [Delete, Invoke, List, DetailedList,
                         UpstreamList, Mood, Property, Start, Stop]

    componentId = None
    componentState = None
    planetState = None
    workerHeavenState = None

    def addOptions(self):
        self.parser.add_option('-i', '--component-id',
            action="store", dest="componentId",
            help="component id of the component")

    def handleOptions(self, options):
        self.componentId = options.componentId
        # call our callback after connecting
        self.getRootCommand().loginDeferred.addCallback(self._callback)

    def _callback(self, result):
        d = self.parentCommand.medium.callRemote('getPlanetState')

        def gotPlanetStateCb(result):
            self.planetState = result
            self.debug('gotPlanetStateCb')

            # only get componentState if we got passed an argument for it
            if not self.componentId:
                return

            try:
                self.componentState = util.findComponent(result,
                    self.componentId)
            except Exception, e:
                self.debug(log.getExceptionMessage(e))
                common.errorRaise("Invalid component id '%s'" %
                    self.componentId)
            self.debug('gotPlanetStateCb')
            if not self.componentState:
                common.errorRaise('Could not find component %s' %
                    self.componentId)

        def getWorkerHeavenStateCb(result):
            d = self.parentCommand.medium.callRemote('getWorkerHeavenState')
            return d

        def gotWorkerHeavenStateCb(result):
            self.workerHeavenState = result

        d.addCallback(gotPlanetStateCb)
        d.addCallback(getWorkerHeavenStateCb)
        d.addCallback(gotWorkerHeavenStateCb)
        return d

    def pprint(self, comps):
        tab = 4
        cols = [[c[i] for c in comps] for i in xrange(len(comps[0]))]
        max_widths = [max(map(len, c)) for c in cols]
        for c in comps:
            s = "    "
            for i in xrange(len(c)):
                width = "%d" % (max_widths[i] + tab)
                s += ('%-' + width + "s") % c[i]
            self.stdout.write(s + "\n")

    def print_components(self, components, workers):
        comps = []
        for c in components:
            workerName = c.get('workerName')
            host = "unknown"
            for w in workers:
                if workerName == w.get('name'):
                    host = w.get('host')
                    break
            comps.append((c.get('name'), c.get('type'), host))
        self.pprint(comps)
