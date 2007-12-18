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

__version__ = "$Rev$"

import sets
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
        d = check.checkPlugin('switch', 'gst-plugins-bad', (0, 10, 5, 1))
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
            self.debug('eater %s maps to pad %s', alias, pad)
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
    # 1) we need to block the switch from processing more data
    # 2) we need to query the last_stop on all stream segments of the
    #    previously active stream, and take the maximum to set as the
    #    stop_time of the old segments
    # 3) we need to query the last_stop on all stream segments of the
    #    new stream, and take the minimum to set as the start_time of
    #    the new segments
    # 4) tell the switches to switch, with the stop_time and start_time

    def try_switch(self, checkActive=True):
        feed = self.idealFeed

        if feed == self.activeFeed:
            self.debug("feed %s is already active", feed)
            self.clearWarning('temporary-switch-problem')
            return True

        if checkActive and not self.is_active(feed):
            return False

        # (pad, switch)
        pairs = [self.switchPads[alias]
                 for alias in self.logicalFeeds[feed]]

        stop_times = [e.emit('block') for p, e in pairs]
        start_times = [p.get_property('running-time') for p, e in pairs]
        
        # FIXME: I don't know what to do if we get a GST_CLOCK_TIME_NONE
        # for one of the stop_times. E.g. if we get audio data but no
        # video data. The two options would be (1) to open and close
        # e.g. a video segment of equal extent to the audio segment, or
        # to (2) not open and close a video segment, relying on the
        # future segment setting things right. (1) would certainly be
        # correct, but (2) might be fine also.

        stop_time = max(stop_times)
        self.debug('stop time = %d', stop_time)
        self.debug('stop time = %s', gst.TIME_ARGS(stop_time))

        if stop_time != gst.CLOCK_TIME_NONE:
            diff = float(max(stop_times) - min(stop_times))
            if diff > gst.SECOND * 10:
                fmt = N_("When switching to %s, feed timestamps out"
                         " of sync by %us")
                self.addWarning('large-timestamp-difference', fmt,
                                feed, diff / gst.SECOND, priority=40)

        # FIXME: I don't know what to do if we get a GST_CLOCK_TIME_NONE
        # in the start_times. For now I am punting on this one. Yick.

        start_time = min(start_times)
        self.debug('start time = %s', gst.TIME_ARGS(start_time))

        self.debug('switching from %r to %r', self.activeFeed, feed)
        for p, e in pairs:
            e.emit('switch', p.get_name(), stop_time, start_time)

        self.activeFeed = feed
        self.uiState.set("active-eater", feed)
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
                    " ! identity silent=true single-segment=true"
                    " ! @feeder:audio@ ")
        for alias in self.eaters:
            if "video" in alias:
                pipeline += '@eater:%s@ ! %s vswitch. ' % (alias, vforce)
            elif "audio" in alias:
                pipeline += '@eater:%s@ ! %s aswitch. ' % (alias, aforce)
            else:
                raise AssertionError()

        return pipeline
