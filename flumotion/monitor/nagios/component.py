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


from twisted.internet import reactor, defer

from flumotion.common import common, planet, log
from flumotion.monitor.nagios import util


class Mood(util.LogCommand):
    description = "Check the mood of a component."
    usage = "[mood options] [component id]"

    def addOptions(self):
        default = "hungry"
        self.parser.add_option('-w', '--warning',
            action="store", dest="warning",
            help="moods to give a warning for (defaults to %s)" % (default),
            default=default)
        default = "sleeping,lost,sad"
        self.parser.add_option('-c', '--critical',
            action="store", dest="critical",
            help="moods to give a critical for (defaults to %s)" % (default),
            default=default)

    def handleOptions(self, options):
        self._warning = options.warning.split(',')
        self._critical = options.critical.split(',')

    def do(self, args):
        if not args:
            self.stderr.write(
                'Please specify a component to check the mood of.\n.')
            return 3

        self._component = args[0]
        # call our callback after connecting
        self.parentCommand.managerDeferred.addCallback(self._callback)

    def _callback(self, result):
        d = self.parentCommand.adminModel.callRemote('getPlanetState')

        def gotPlanetStateCb(result):
            self.debug('gotPlanetStateCb')
            c = util.findComponent(result, self._component)
            if not c:
                return util.unknown('Could not find component %s' %
                    self._component)

            moodValue = c.get('mood')
            moodName = planet.moods.get(moodValue).name

            if moodName in self._critical:
                return util.critical('Component %s is %s' % (self._component,
                    moodName))

            if moodName in self._warning:
                return util.warning('Component %s is %s' % (self._component,
                    moodName))

            return util.ok('Component %s is %s' % (self._component,
                moodName))

        d.addCallback(gotPlanetStateCb)
        d.addCallback(lambda e: setattr(reactor, 'exitStatus', e))
        return d


class FlipFlopDetector(object):

    def __init__(self, timeout, flipflops, mood_a, mood_b, state):
        self.timeout = timeout
        self.flipflops = flipflops
        self.mood_a = mood_a
        self.mood_b = mood_b
        self.state = state

        self.cancel = None
        self.flip_count = 0
        if state.get('mood') == self.mood_a:
            self.current_state = self.mood_a
        else:
            self.current_state = None
        self.waiting_d = defer.Deferred()

    def wait(self):
        return self.waiting_d

    def start(self):
        self.state.addListener(self, set_=self.state_set)
        self.cancel = reactor.callLater(self.timeout,
                                        self.success)

    def state_set(self, cs, key, value):
        if key != 'mood':
            return

        # the first time it goes to mood_a is not treated as a flip
        if value == self.mood_a and self.current_state is None:
            self.current_state = value
            return

        # mood_a -> mood_b and mood_a -> mood_b transitions are flips
        if (self.current_state, value) in ((self.mood_a, self.mood_b),
                                           (self.mood_b, self.mood_a)):
            self.current_state = value
            self.flip_count += 1

        if self.flip_count >= self.flipflops:
            self.failure()

    def success(self):
        self.state.removeListener(self)
        s = ''
        if self.flip_count != 1:
            s = 's'
        self.waiting_d.callback("%d mood change%s detected" %
                                (self.flip_count, s))

    def failure(self):
        self.state.removeListener(self)
        if self.cancel:
            self.cancel.cancel()
        s = ''
        if self.flip_count != 1:
            s = 's'
        self.waiting_d.errback(Exception("%d mood change%s detected" %
                                         (self.flip_count, s)))


class FlipFlop(util.LogCommand):
    """
    This check connects to the manager and watches the state of a component for
    a given amout of time. Raises a critical if the mood alternates between two
    extremes (by default: happy and hungry) more than the given number of
    times.
    """

    description = "Check if the mood of a component is flipflopping."

    def addOptions(self):
        self.parser.add_option('-i', '--component-id',
                               action="store",
                               help="component id of the component")
        self.parser.add_option('-t', '--timeout', type="int",
                               action="store", default=15,
                               help="how long to test for flopflops")
        self.parser.add_option('-f', '--flipflops', type="int",
                               action="store", default=2,
                               help=("how many mood changes should "
                                     "be considered a flipflop"))
        self.parser.add_option('-a', '--mood-a',
                               action="store", default="happy",
                               help=("the initial mood of the flipflop"))
        self.parser.add_option('-b', '--mood-b',
                               action="store", default="hungry",
                               help=("the final mood of the flipflop"))

    def handleOptions(self, options):
        if not options.component_id:
            raise util.NagiosUnknown("Please specify a component id "
                                     "with '-i [component-id]'")

        try:
            self.mood_a = getattr(planet.moods, options.mood_a).value
        except AttributeError:
            raise util.NagiosUnknown("Invalid mood name '%s'" % options.mood_a)
        try:
            self.mood_b = getattr(planet.moods, options.mood_b).value
        except AttributeError:
            raise util.NagiosUnknown("Invalid mood name '%s'" % options.mood_b)

        self.component_id = options.component_id
        self.timeout = options.timeout
        self.flipflops = options.flipflops

    def do(self, args):
        self.parentCommand.managerDeferred.addCallback(self._get_planet_state)
        self.parentCommand.managerDeferred.addCallback(self._got_planet_state)

    def _get_planet_state(self, _):
        return self.parentCommand.adminModel.callRemote('getPlanetState')

    def _got_planet_state(self, planet_state):
        c = util.findComponent(planet_state, self.component_id)
        if not c:
            return util.unknown('Could not find component %s' %
                                self.component_id)
        return self._detect_flipflops(c)

    def _detect_flipflops(self, component_state):
        f = FlipFlopDetector(self.timeout, self.flipflops, self.mood_a,
                             self.mood_b, component_state)
        f.start()
        d = f.wait()
        return d.addCallbacks(util.ok, lambda f:
                                  util.critical(f.getErrorMessage()))
