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

from twisted.internet import defer

from flumotion.common import errors, messages
from flumotion.common.planet import moods
from flumotion.worker.checks import check
from flumotion.component import feedcomponent
from flumotion.component.base import scheduler

from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

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

        # _idealEater is used to determine what the ideal eater at the current
        # time is.
        self._idealEater = "master"

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
                self._idealEater = "backup"
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
        for name, aliases in self.get_logical_feeds().items():
            assert name not in self.logicalFeeds
            for alias in aliases:
                assert alias in self.eaters
            self.logicalFeeds[name] = aliases

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

        for alias in self.logicalFeeds[self._idealEater]:
            pad, e = self.switchPads[alias]
            e.set_property('active-pad', pad)
        self.uiState.set("active-eater", self._idealEater)

    def get_switch_elements(self, pipeline):
        raise errors.NotImplementedError('subclasses should implement '
                                         'get_switch_elements')

    def switch_to(self, feed):
        if self.is_active(feed):
            for alias in self.logicalFeeds[feed]:
                pad, e = self.switchPads[alias]
                e.set_property('active-pad', pad)
            self.uiState.set("active-eater", feed)
            return True
        else:
            self.warning("Could not switch to %s because the %s eater "
                         "is not active.", feed, feed)
            return False

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
        self._idealEater = feed
        d = defer.maybeDeferred(self.switch_to, feed)
        d.addCallback(switch_to_cb)
        return d

class SingleSwitch(Switch):
    logCategory = "single-switch"

    def get_logical_feeds(self):
        return {'master': ['master'], 'backup': ['backup']}

    def get_muxer_string(self, properties):
        return ("switch name=muxer ! "
                "identity silent=true single-segment=true name=iden ")

    def get_switch_elements(self, pipeline):
        return [pipeline.get_by_name('muxer')]

class AVSwitch(Switch):
    logCategory = "av-switch"

    def init(self):
        self.audioSwitchElement = None
        self.videoSwitchElement = None
        # property name -> caps property name
        self.vparms = {'video-width': 'width', 'video-height': 'height',
                       'framerate': 'framerate', 'pixel-aspect-ratio': 'par'}
        self.aparms = {'audio-channels': 'channels',
                       'audio-samplerate': 'samplerate'}
        # eater name -> name of sink pad on switch element
        self.switchPads = {}
        self._startTimes = {}
        self._startTimeProbeIds = {}
        self._padProbeLock = threading.Lock()
        self._switchLock = threading.Lock()
        self.pads_awaiting_block = []
        self.padsBlockedDefer = None

    def get_logical_feeds(self):
        return {'master': ['video-master', 'audio-master'],
                'backup': ['video-backup', 'audio-backup']}

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

    def configure_pipeline(self, pipeline, properties):
        self.videoSwitchElement = vsw = pipeline.get_by_name("vswitch")
        self.audioSwitchElement = asw = pipeline.get_by_name("aswitch")

        # figure out how many pads should be connected for the eaters
        # 1 + number of eaters with eaterName *-backup
        numVideoPads = 1 + len(self.config["eater"]["video-backup"])
        numAudioPads = 1 + len(self.config["eater"]["audio-backup"])
        padPeers = {} # peer element name -> (switchSinkPadName, switchElement)
        for sinkPadNumber in range(0, numVideoPads):
            padPeers[vsw.get_pad("sink%d" % (
                    sinkPadNumber)).get_peer().get_parent().get_name()] = \
                ("sink%d" % sinkPadNumber, vsw)
        for sinkPadNumber in range(0, numAudioPads):
            padPeers[asw.get_pad("sink%d" % (
                    sinkPadNumber)).get_peer().get_parent().get_name()] = \
                ("sink%d" % sinkPadNumber, asw)

        # Figure out for each eater what switch sink pad is associated.
        for eaterAlias in self.eaters:
            # The eater depayloader is linked to our switch.
            peer = self.eaters[eaterAlias].depayName
            if peer in padPeers:
                self.switchPads[eaterAlias] = padPeers[peer]
            else:
                self.warning("could not find sink pad for eater %s",
                             eaterAlias)

        # make sure switch has the correct sink pad as active
        self.debug("Setting video switch's active-pad to %s",
            self.switchPads["video-%s" % self._idealEater])
        vsw.set_property("active-pad",
            self.switchPads["video-%s" % self._idealEater])
        self.debug("Setting audio switch's active-pad to %s",
            self.switchPads["audio-%s" % self._idealEater])
        asw.set_property("active-pad",
            self.switchPads["audio-%s" % self._idealEater])
        self.uiState.set("active-eater", self._idealEater)
        self.debug("active-eater set to %s", self._idealEater)

    # So switching audio and video is not that easy
    # We have to make sure the current segment on both
    # the audio and video switch element have the same
    # stop value, and the next segment on both to have
    # the same start value to maintain sync.
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
    def switch_to(self, eater):
        if not (self.videoSwitchElement and self.audioSwitchElement):
            self.warning("switch_to called with eater %s but before pipeline "
                "configured")
            return False
        if eater not in [ "master", "backup" ]:
            self.warning("%s is not master or backup", eater)
            return False
        if self._switchLock.locked():
            self.warning("Told to switch to %s while a current switch is going on.", eater)
            return False
        # Lock is acquired here and released once buffers are told to queue again
        self._switchLock.acquire()
        if self.is_active(eater) and self._startTimes == {} and \
           self.uiState.get("active-eater") != eater:
            self._startTimes = {"abc":None}
            self.padsBlockedDefer = defer.Deferred()
            self.debug("eaterSwitchingTo switching to %s", eater)
            self.eaterSwitchingTo = eater
            self._block_switch_sink_pads(True)
            return self.padsBlockedDefer
        else:
            self._switchLock.release()
            if self.uiState.get("active-eater") == eater:
                self.warning("Could not switch to %s because it is already active",
                    eater)
            elif self._startTimes == {}:
                self.warning("Could not switch to %s because at least "
                    "one of the %s eaters is not active." % (eater, eater))
                m = messages.Warning(T_(N_(
                    "Could not switch to %s because at least "
                    "one of the %s eaters is not active." % (eater, eater))),
                    id="cannot-switch",
                    priority=40)
                self.state.append('messages', m)
            else:
                self.warning("Could not switch because startTimes is %r",
                    self._startTimes)
                m = messages.Warning(T_(N_(
                    "Could not switch to %s because "
                    "startTimes is %r." % (eater, self._startTimes))),
                    id="cannot-switch",
                    priority=40)
                self.state.append('messages', m)
        return False

    def _set_last_timestamp(self):
        vswTs = self.videoSwitchElement.get_property("last-timestamp")
        aswTs = self.audioSwitchElement.get_property("last-timestamp")
        tsToSet = vswTs
        if aswTs > vswTs:
            tsToSet = aswTs
        self.log("Setting stop-value on video switch to %u",
            tsToSet)
        self.log("Setting stop-value on audio switch to %u",
            tsToSet)
        self.videoSwitchElement.set_property("stop-value",
            tsToSet)
        self.audioSwitchElement.set_property("stop-value",
            tsToSet)
        message = None
        if (aswTs > vswTs) and (aswTs - vswTs > gst.SECOND * 10):
            message = "When switching to %s the other source's video" \
                " and audio timestamps differ by %u" % (self.eaterSwitchingTo,
                aswTs - vswTs)
        elif (vswTs > aswTs) and (vswTs - aswTs > gst.SECOND * 10):
            message = "When switching to %s the other source's video" \
                " and audio timestamps differ by %u" % (self.eaterSwitchingTo,
                vswTs - aswTs)
        if message:
            m = messages.Warning(T_(N_(
                message)),
                id="large-timestamp-difference",
                priority=40)
            self.state.append('messages', m)

    def _block_cb(self, pad, blocked):
        self.log("here with pad %r and blocked %d", pad, blocked)
        if blocked:
            if not pad in self.pads_awaiting_block:
                return
            self.pads_awaiting_block.remove(pad)
            self.log("Pads awaiting block are: %r", self.pads_awaiting_block)

    def _block_switch_sink_pads(self, block):
        if block:
            self.pads_awaiting_block = []
            for eaterName in self.switchPads:
                if "audio" in eaterName:
                    pad = self.audioSwitchElement.get_pad(
                        self.switchPads[eaterName]).get_peer()
                else:
                    pad = self.videoSwitchElement.get_pad(
                        self.switchPads[eaterName]).get_peer()
                if pad:
                    self.pads_awaiting_block.append(pad)

        for eaterName in self.switchPads:
            if "audio" in eaterName:
                pad = self.audioSwitchElement.get_pad(
                    self.switchPads[eaterName]).get_peer()
            else:
                pad = self.videoSwitchElement.get_pad(
                    self.switchPads[eaterName]).get_peer()
            if pad:
                self.debug("Pad: %r blocked being set to: %d", pad, block)
                ret = pad.set_blocked_async(block, self._block_cb)
                self.debug("Return of pad block is: %d", ret)
                self.debug("Pad %r is blocked: %d", pad, pad.is_blocked())
        if block:
            self.on_pads_blocked()

    def on_pads_blocked(self):
        eater = self.eaterSwitchingTo
        if not eater:
            self.warning("Eaterswitchingto is None, crying time")
        self.log("Block callback")
        self._set_last_timestamp()
        self.videoSwitchElement.set_property("active-pad",
        self.switchPads["video-%s" % eater])
        self.audioSwitchElement.set_property("active-pad",
        self.switchPads["audio-%s" % eater])
        self.videoSwitchElement.set_property("queue-buffers",
            True)
        self.audioSwitchElement.set_property("queue-buffers",
            True)
        self.uiState.set("active-eater", eater)
        self._add_pad_probes_for_start_time(eater)
        self._block_switch_sink_pads(False)
        if self.padsBlockedDefer:
            self.padsBlockedDefer.callback(True)
        else:
            self.warning("Our pad block defer is None, inconsistency time to cry")
        self.padsBlockedDefer = None

    def _add_pad_probes_for_start_time(self, activeEater):
        self.debug("adding buffer probes here for %s", activeEater)
        for eaterName in ["video-%s" % activeEater, "audio-%s" % activeEater]:
            if "audio" in eaterName:
                pad = self.audioSwitchElement.get_pad(
                    self.switchPads[eaterName])
            else:
                pad = self.videoSwitchElement.get_pad(
                    self.switchPads[eaterName])
            self._padProbeLock.acquire()
            self._startTimeProbeIds[eaterName] = pad.add_buffer_probe(
                self._start_time_buffer_probe, eaterName)
            self._padProbeLock.release()

    def _start_time_buffer_probe(self, pad, buffer, eaterName):
        self.debug("start time buffer probe for %s buf ts: %u",
            eaterName, buffer.timestamp)
        self._padProbeLock.acquire()
        if eaterName in self._startTimeProbeIds:
            self._startTimes[eaterName] = buffer.timestamp
            pad.remove_buffer_probe(self._startTimeProbeIds[eaterName])
            del self._startTimeProbeIds[eaterName]
            self.debug("pad probe for %s", eaterName)
            self._check_start_times_received()
        self._padProbeLock.release()
        return True

    def _check_start_times_received(self):
        self.debug("here")
        activeEater = self.uiState.get("active-eater")
        haveAllStartTimes = True
        lowestTs = 0
        for eaterName in ["video-%s" % activeEater, "audio-%s" % activeEater]:
            haveAllStartTimes = haveAllStartTimes and \
                (eaterName in self._startTimes)
            if eaterName in self._startTimes and \
                (lowestTs == 0 or self._startTimes[eaterName] < lowestTs):
                lowestTs = self._startTimes[eaterName]
                self.debug("lowest ts received from buffer probes: %u",
                    lowestTs)

        if haveAllStartTimes:
            self.debug("have all start times")
            self.videoSwitchElement.set_property("start-value", lowestTs)
            self.audioSwitchElement.set_property("start-value", lowestTs)
            self._startTimes = {}
            # we can also turn off the queue-buffers property
            self.audioSwitchElement.set_property("queue-buffers", False)
            self.videoSwitchElement.set_property("queue-buffers", False)
            self.log("eaterSwitchingTo becoming None from %s",
                self.eaterSwitchingTo)
            self.eaterSwitchingTo = None
            self._switchLock.release()
