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

from flumotion.common import errors, messages
from flumotion.common.planet import moods
from flumotion.worker.checks import check
from flumotion.component import feedcomponent
from flumotion.component.base import scheduler

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

class SwitchMedium(feedcomponent.FeedComponentMedium):
    def remote_switchToMaster(self):
        return self.comp.switch_to("master")

    def remote_switchToBackup(self):
        return self.comp.switch_to("backup")

class Switch(feedcomponent.MultiInputParseLaunchComponent):
    logCategory = 'switch'
    componentMediumClass = SwitchMedium

    def init(self):
        self.uiState.addKey("active-eater")
        self.icalScheduler = None

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

        self._switchLock = threading.Lock()
        self._switchingToFeed = None # with _switchLock
        self._activeFeed = None

        # Dict of logical feed name to deferred for feeds that we would
        # like to switch to, but are waiting for eaters to become
        # active.
        self._feedReadyDefers = {}
        self._started = False

    def addWarning(self, id, format, *args, **kwargs):
        self.warning(format, *args)
        m = messages.Message(messages.WARNING, T_(format, *args),
                             id=id, **kwargs)
        self.addMessage(m)

    def _create_scheduler(self, filename):
        try:
            def eventStarted(event):
                self.debug("event started %r", event)
                self.switch_to_for_event("backup", True)
            def eventStopped(event):
                self.debug("event stopped %r", event)
                self.switch_to_for_event("master", False)

            # if an event starts, semantics are to switch to backup
            # if an event stops, semantics are to switch to master
            sched = scheduler.ICalScheduler(open(filename, 'r'))
            sched.subscribe(eventStarted, eventStopped)
            if sched.getCurrentEvents():
                self._switchingToFeed = "backup"
        except ValueError:
            fmt = N_("Error parsing ical file %s, so not scheduling "
                     "any events.")
            self.addWarning("error-parsing-ical", fmt, filename)
        except ImportError, e:
            fmt = N_("An ical file has been specified for scheduling, "
                     "but the necessary modules are not installed.")
            self.addWarning("error-parsing-ical", fmt, debug=e.message)
        else:
            return sched
        
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
        icalFileName = self.config['properties']['ical-schedule']
        if icalFileName:
            self.icalScheduler = self._create_scheduler(icalFileName)

    def create_pipeline(self):
        for name, aliases in self.get_logical_feeds():
            assert name not in self.logicalFeeds
            for alias in aliases:
                assert alias in self.eaters
            self.logicalFeeds[name] = aliases
            if self._switchingToFeed is None:
                self._switchingToFeed = name

        return feedcomponent.MultiInputParseLaunchComponent.create_pipeline()

    def get_logical_feeds(self):
        raise errors.NotImplementedError('subclasses should implement '
                                         'get_logical_feeds')

    def configure_pipeline(self, pipeline, properties):
        def getDownstreamElement(e):
            for pad in e.pads:
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

        self.switch_to(self._switchingToFeed, checkActive=False)

    def get_switch_elements(self, pipeline):
        raise errors.NotImplementedError('subclasses should implement '
                                         'get_switch_elements')

    def is_active(self, feed):
        all = lambda seq: reduce(int.__mul__, seq, True)
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

        for feed, aliases in self.logicalFeeds.items():
            if (eaterAlias in aliases
                and feed in self._feedReadyDefers
                and self.is_active(feed)):
                d = self._feedReadyDefers.pop(feed)
                d.callback(True)
                break

    def eaterSetInactive(self, eaterAlias):
        pass

    def switch_to_for_event(self, feed, started):
        """
        @param feed: a logical feed
        @param started: True if start of event, False if stop
        """
        def switch_to_cb(success):
            if not success:
                feed_unavailable()

        def feed_unavailable():
            if started:
                fmt = N_("Event started but could not switch to %s, "
                         "will switch when %s is back")
            else:
                fmt = N_("Event stopped but could not switch to %s, "
                         "will switch when %s is back")
            self.addWarning("error-scheduling-event", fmt, feed, feed)

            while self._feedReadyDefers:
                self._feedReadyDefers.pop()

            self._feedReadyDefers[feed] = d2 = defer.Deferred()
            d2.addCallback(lambda x: self.switch_to(feed))

        if not self.pipeline:
            return
        if feed not in self.logicalFeeds:
            self.warning("unknown logical feed: %s", feed)
            return None
        d = defer.maybeDeferred(self.switch_to, feed)
        d.addCallback(switch_to_cb)
        return d

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

    def _prepare_switch(self, feed, checkActive):
        def setSwitching():
            if self._switchingToFeed:
                return False
            self._switchingToFeed = feed
        setSwitching = withlock(setSwitching, self._switchLock)
        
        if feed == self._activeFeed:
            self.warning("Feed %s is already active", feed)
            return False
        if checkActive and not self.is_active(feed):
            # setActive/setInactive called from main thread, no chance
            # for race
            fmt = N_("Could not switch to %s because at least "
                     "one of the %s eaters is not active.")
            self.addWarning('cannot-switch', fmt, feed, feed, priority=40)
            return False
        if not setSwitching():
            self.warning("Switch already in progress")
            return False

        last_times = []
        for alias in self.logicalFeeds[feed]:
            pad, e = self.switchPads[alias]
            pad.set_blocked_async(True, lambda x, y: None) # (1)
            last_times.append(e.get_property('last-timestamp'))

        last_time = max(last_times)
        self.debug('last time = %u', last_time)
        
        for alias in self.logicalFeeds[feed]:
            pad, e = self.switchPads[alias]
            e.set_property('stop-value', last_time) # (2)

        diff = max(last_times) - min(last_times)
        if diff > gst.SECOND * 10:
            fmt = N_("When switching to %s, feed timestamps out of sync"
                     " by %u")
            self.addWarning('large-timestamp-difference', fmt, feed,
                            diff, priority=40)

    def switch_to(self, feed, checkActive=True):
        if not self._prepare_switch(feed, checkActive):
            return False

        for alias in self.logicalFeeds[feed]:
            pad, e = self.switchPads[alias]
            e.set_property('active-pad', pad) # (3)
        self.uiState.set("active-eater", feed)
        self._activeFeed = feed

        return self._finish_switch(feed)

    def _finish_switch(self, feed):
        def unsetSwitching():
            assert self._switchingToFeed
            self._switchingToFeed = None
        unsetSwitching = withlock(unsetSwitching, self._switchLock)

        for alias in self.logicalFeeds[feed]:
            pad, e = self.switchPads[alias]
            e.set_property("queue-buffers", True) # (4)

        self.uiState.set("active-eater", feed)

        def gotStartTimes(startTimes):
            self.debug("have all start times: %u - %u", min(startTimes),
                       max(startTimes))
            for alias in self.logicalFeeds[feed]:
                pad, e = self.switchPads[alias]
                e.set_property("start-value", min(startTimes)) # (7)
                e.set_property("queue-buffers", False) # (8)
            unsetSwitching()
            
        d = self._get_new_start_times(feed) # (4)
        d.addCallback(gotStartTimes)

        for alias in self.logicalFeeds[feed]:
            pad, e = self.switchPads[alias]
            pad.set_blocked_async(False, lambda x, y: None) # (6)

    def _get_new_start_times(self, feed):
        def buffer_probe(pad, buffer):
            self.debug("start time buffer probe ts: %u", buffer.timestamp)
            probe_id = probe_ids.pop(pad, None)
            if probe_id:
                pad.remove_buffer_probe(probe_id)
                times.append(buffer.timestamp)
                if not probe_ids:
                    reactor.callFromThread(d.callback, times)
            else:
                self.warning("foo!")
            return True
        probe_lock = threading.Lock()
        buffer_probe = withlock(buffer_probe, probe_lock)

        d = defer.Deferred()
        times = []
        probe_ids = {}

        self.debug("adding buffer probes here for %s", feed)
        probe_lock.acquire()
        for alias in self.logicalFeeds[feed]:
            pad, e = self.switchPads[alias]
            probe_ids[pad] = pad.add_buffer_probe(buffer_probe)
        probe_lock.release()

        return d

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
