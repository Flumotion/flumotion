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

import sets
import threading
import gst

from twisted.internet import defer, reactor

from flumotion.common import errors, messages, log
from flumotion.common.planet import moods
from flumotion.worker.checks import check
from flumotion.component import feedcomponent
from flumotion.component.base import scheduler
from flumotion.component.plugs import base

from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

def withlock(proc, lock):
    def locking(*args):
        lock.acquire()
        try:
            return proc(*args)
        finally:
            lock.release()
    return locking

def collect_single_shot_buffer_probe(pads, probe):
    def buffer_probe(pad, buffer):
        probe_id = probe_ids.pop(pad, None)
        if probe_id:
            pad.remove_buffer_probe(probe_id)
            ret.append(probe(pad, buffer))
            if not probe_ids:
                log.debug('switch', "have all probed values: %r", ret)
                reactor.callFromThread(d.callback, ret)
        else:
            log.warning('switch', "foo!")
        return True
    probe_lock = threading.Lock()
    buffer_probe = withlock(buffer_probe, probe_lock)

    d = defer.Deferred()
    ret = []
    probe_ids = {}

    log.debug('switch', "adding buffer probes for %r", pads)
    probe_lock.acquire()
    for pad in pads:
        probe_ids[pad] = pad.add_buffer_probe(buffer_probe)
    probe_lock.release()

    return d

class SwitchMedium(feedcomponent.FeedComponentMedium):
    def remote_switchToMaster(self):
        return self.comp.switch_to("master")

    def remote_switchToBackup(self):
        return self.comp.switch_to("backup")

    def remote_switchTo(self, logicalFeed):
        return self.comp.switch_to(logicalFeed)

class ICalSwitchPlug(base.ComponentPlug):
    def start(self, component):
        self._sid = None
        self.sched = None
        try:
            def eventStarted(event):
                self.debug("event started %r", event)
                component.switch_to("backup")
            def eventStopped(event):
                self.debug("event stopped %r", event)
                component.switch_to("master")

            # if an event starts, semantics are to switch to backup
            # if an event stops, semantics are to switch to master
            filename = self.args['properties']['ical-schedule']
            self.sched = scheduler.ICalScheduler(open(filename, 'r'))
            self._sid = self.sched.subscribe(eventStarted, eventStopped)
            if self.sched.getCurrentEvents():
                component.idealFeed = "backup"
        except ValueError:
            fmt = N_("Error parsing ical file %s, so not scheduling "
                     "any events.")
            component.addWarning("error-parsing-ical", fmt, filename)
        except ImportError, e:
            fmt = N_("An ical file has been specified for scheduling, "
                     "but the necessary modules are not installed.")
            component.addWarning("error-parsing-ical", fmt, debug=e.message)

    def stop(self, component):
        if self.sched:
            self.sched.unsubscribe(self._sid)

class Switch(feedcomponent.MultiInputParseLaunchComponent):
    logCategory = 'switch'
    componentMediumClass = SwitchMedium

    def init(self):
        self.uiState.addKey("active-eater")
        self.icalScheduler = None

        # foo
        self._started = False

        # This structure maps logical feeds to sets of eaters. For
        # example, "master" and "backup" could be logical feeds, and
        # would be the keys in this dict, mapping to lists of eater
        # aliases corresponding to those feeds. The lengths of those
        # lists is equal to the number of feeders that the element has,
        # which is the number of individual streams in a logical feed.
        # 
        # For example, {"master": ["audio-master", "video-master"],
        #               "backup": ["audio-backup", "video-backup"]}
        self.logicalFeeds = {}

        # eater alias -> (sink pad, switch element)
        self.switchPads = {}

        # Two variables form the state of the switch component.
        #    idealFeed
        #        The feed that we would like to provide, as chosen by
        #        the user, either by the UI, an ical file, a pattern
        #        detection, etc.
        #    activeFeed
        #        The feed currently being provided
        self.idealFeed = None
        self.activeFeed = None

        # Additionally, the boolean flag _switching indicates that a
        # switch is in progress.
        self._switching = False

        # All instance variables may only be accessed from the main
        # thread.

    def addWarning(self, id, format, *args, **kwargs):
        self.warning(format, *args)
        m = messages.Message(messages.WARNING, T_(format, *args),
                             id=id, **kwargs)
        self.addMessage(m)

    def clearWarning(self, id):
        for m in self.state.get('messages')[:]:
            if m.id == id:
                self.state.remove('messages', m)

    def do_check(self):
        def cb(result):
            for m in result.messages:
                self.addMessage(m)
            return result.value

        self.debug("checking for switch element")
        d = check.checkPlugin('switch', 'gst-plugins-bad')
        d.addCallback(cb)
        return d

    def do_setup(self):
        ical = self.config['properties'].get('ical-schedule', None)
        if ical:
            args = {'properties': {'ical-schedule': ical}}
            self.icalScheduler = ICalSwitchPlug(args)
            self.icalScheduler.start(self)

    def create_pipeline(self):
        for name, aliases in self.get_logical_feeds():
            assert name not in self.logicalFeeds
            for alias in aliases:
                assert alias in self.eaters
            self.logicalFeeds[name] = aliases
            if self.idealFeed is None:
                self.idealFeed = name

        return feedcomponent.MultiInputParseLaunchComponent.create_pipeline(self)

    def get_logical_feeds(self):
        raise errors.NotImplementedError('subclasses should implement '
                                         'get_logical_feeds')

    def configure_pipeline(self, pipeline, properties):
        def getDownstreamElement(e):
            for pad in e.pads():
                if pad.get_direction() is gst.PAD_SRC:
                    peer = pad.get_peer()
                    return peer, peer.get_parent()
            raise AssertionError('failed to find the switch')

        switchElements = self.get_switch_elements(pipeline)
        for alias in self.eaters:
            e = pipeline.get_by_name(self.eaters[alias].elementName)
            pad = None
            while e not in switchElements:
                pad, e = getDownstreamElement(e)
            self.switchPads[alias] = pad, e

        for alias in self.eaters:
            self.eaters[alias].addWatch(self.eaterSetActive,
                                        self.eaterSetInactive)

        self.try_switch(checkActive=False)

    def get_switch_elements(self, pipeline):
        raise errors.NotImplementedError('subclasses should implement '
                                         'get_switch_elements')

    def is_active(self, feed):
        all = lambda seq: reduce(bool.__and__, seq, True)
        return all([self.eaters[alias].isActive()
                    for alias in self.logicalFeeds[feed]])

    def do_pipeline_playing(self):
        feedcomponent.MultiInputParseLaunchComponent.do_pipeline_playing(self)
        # needed to stop the flapping between master and backup on startup
        # in the watchdogs if the starting state is backup
        self._started = True

    def eaterSetActive(self, eaterAlias):
        if not self._started and moods.get(self.getMood()) == moods.happy:
            # need to just set _started to True if False and mood is happy
            # FIXME: why?
            self._started = True

        if self.activeFeed != self.idealFeed:
            self.try_switch()

    def eaterSetInactive(self, eaterAlias):
        pass

    def switch_to(self, feed):
        """
        @param feed: a logical feed
        """
        if feed not in self.logicalFeeds:
            self.warning("unknown logical feed: %s", feed)
            return None

        self.debug('scheduling switch to feed %s', feed)
        self.idealFeed = feed

        if not self.pipeline:
            return

        success = self.try_switch()
        if not success:
            fmt = N_("Tried to switch to %s, but feed is unavailable. "
                     "Will retry when the feed is back.")
            self.addWarning("temporary-switch-problem", fmt, feed)

    # So switching multiple eaters is not that easy.
    # 
    # We have to make sure the current segment on both the switch
    # elements has the same stop value, and the next segment on both to
    # have the same start value to maintain sync.
    #
    # In order to do this:
    # 1) we need to block all src pads of elements connected
    #    to the switches' sink pads
    # 2) we need to set the property "stop-value" on both the
    #    switches to the highest value of "last-timestamp" on the two
    #    switches.
    # 3) the pads should be switched (ie active-pad set) on the two switched
    # 4) the switch elements should be told to queue buffers coming on their
    #    active sinkpads by setting the queue-buffers property to TRUE
    # 5) pad buffer probes should be added to the now active sink pads of the
    #    switch elements, so that the start value of the enxt new segment can
    #    be determined
    # 6) the src pads we blocked in 1) should be unblocked
    # 7) when both pad probes have fired once, use the lowest timestamp
    #    received as the start value for the switch elements
    # 8) set the queue-buffers property on the switch elements to FALSE

    def try_switch(self, checkActive=True):
        def set_switching(switching):
            if switching and self._switching:
                self.warning("Switch already in progress")
                return False
            elif not switching and not self._switching:
                self.warning('something went terribly wrong')
                # fall thru
            self._switching = switching
            return True

        def set_blocked(blocked):
            for pad, e in switchPads:
                pad.set_blocked_async(blocked, lambda x, y: None)

        def set_stop_time():
            times = [e.get_property('last-timestamp')
                     for pad, e in switchPads]
            stop_time = max(times)

            if stop_time != gst.CLOCK_TIME_NONE:
                self.debug('stop time = %u', stop_time)
                for pad, e in switchPads:
                    e.set_property('stop-value', stop_time)

                diff = max(times) - min(times)
                if diff > gst.SECOND * 10:
                    fmt = N_("When switching to %s, feed timestamps out"
                             " of sync by %u")
                    self.addWarning('large-timestamp-difference', fmt,
                                    feed, diff, priority=40)

        def set_queueing(queueing, start_time=None):
            for pad, e in switchPads:
                if start_time:
                    e.set_property("start-value", start_time)
                e.set_property("queue-buffers", queueing)

        def switch():
            for pad, e in switchPads:
                e.set_property('active-pad', pad.get_name())
            self.activeFeed = feed
            self.uiState.set("active-eater", feed)

        def get_new_start_times():
            return collect_single_shot_buffer_probe(
                [pad for pad, e in switchPads],
                lambda pad, buffer: buffer.timestamp)

        feed = self.idealFeed

        if feed == self.activeFeed:
            self.debug("feed %s is already active", feed)
            self.clearWarning('temporary-switch-problem')
            return True

        if checkActive and not self.is_active(feed):
            return False

        if not set_switching(True):
            return False

        switchPads = [self.switchPads[alias]
                      for alias in self.logicalFeeds[feed]]
        set_blocked(True) # (1)
        set_stop_time() # (2)
        switch() # (3)
        set_queueing(True) # (4)
        d = get_new_start_times() # (5)
        set_blocked(False) # (6)
        d.addCallback(lambda times: set_queueing(False, min(times))) # (7, 8)
        d.addCallback(lambda _: set_switching(False))
        # in self.idealEater was changed in the meantime, also to clear
        # the warning message if everything is ok
        d.addCallback(lambda _: self.try_switch())
        return True

class SingleSwitch(Switch):
    logCategory = "single-switch"

    def get_logical_feeds(self):
        return [('master', ['master']),
                ('backup', ['backup'])]

    def get_muxer_string(self, properties):
        return ("switch name=muxer ! "
                "identity silent=true single-segment=true name=iden ")

    def get_switch_elements(self, pipeline):
        return [pipeline.get_by_name('muxer')]

class AVSwitch(Switch):
    logCategory = "av-switch"

    def init(self):
        # property name -> caps property name
        self.vparms = {'video-width': 'width', 'video-height': 'height',
                       'framerate': 'framerate', 'pixel-aspect-ratio': 'par'}
        self.aparms = {'audio-channels': 'channels',
                       'audio-samplerate': 'samplerate'}

    def get_logical_feeds(self):
        return [('master', ['video-master', 'audio-master']),
                ('backup', ['video-backup', 'audio-backup'])]

    def get_switch_elements(self, pipeline):
        # these have to be in the same order as the lists in
        # get_logical_feeds
        return [pipeline.get_by_name('vswitch'),
                pipeline.get_by_name('aswitch')]

    def addError(self, id, format, *args, **kwargs):
        self.warning(format, *args)
        m = messages.Message(messages.ERROR, T_(format, *args),
                             id=id, **kwargs)
        self.addMessage(m)
        raise errors.ComponentSetupHandledError()

    def do_check(self):
        propkeys = sets.Set(self.config['properties'].keys())
        vparms = sets.Set(self.vparms.keys())
        aparms = sets.Set(self.aparms.keys())

        for kind, parms in ('Video', vparms), ('Audio', aparms):
            missing = parms - (propkeys & parms)
            if missing and missing != parms:
                fmt = N_("%s parameter(s) were specified but not all. "
                         "Missing parameters are: %r")
                self.addError("video-params-not-specified", fmt, kind,
                              missing)

    def get_pipeline_string(self, properties):
        def i420caps(framerate, par, width, height):
            return ("video/x-raw-yuv,width=%d,height=%d,framerate=%d/%d,"
                    ",pixel-aspect-ratio=%d/%d,format=(fourcc)I420"
                    % (width, height, framerate[0], framerate[1],
                       par[0], par[1]))
            
        def audiocaps(channels, samplerate):
            return ("audio/x-raw-int,channels=%d,samplerate=%d,width=16,"
                    "depth=16,signed=true" % (channels, samplerate))

        def props2caps(proc, parms, prefix, suffix=' ! '):
            kw = dict([(parms[prop], properties[prop])
                       for prop in properties if prop in parms])
            if kw:
                return prefix + proc(**kw) + suffix
            else:
                return ''

        vforce = props2caps(i420caps, self.vparms,
                            "ffmpegcolorspace ! videorate ! videoscale "
                            "! capsfilter caps=")
        aforce = props2caps(audiocaps, self.aparms,
                            "audioconvert ! audioconvert ! capsfilter caps=")

        pipeline = ("switch name=vswitch"
                    " ! identity silent=true single-segment=true"
                    " ! @feeder:video@ "
                    "switch name=aswitch"
                    "! identity silent=true single-segment=true "
                    "! @feeder:audio@ ")
        for alias in self.eaters:
            if "video" in alias:
                pipeline += '@eater:%s@ ! %s vswitch. ' % (alias, vforce)
            elif "audio" in alias:
                pipeline += '@eater:%s@ ! %s aswitch. ' % (alias, aforce)
            else:
                raise AssertionError()

        return pipeline

__version__ = "$Rev$"
