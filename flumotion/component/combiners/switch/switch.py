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

import gst
import gobject

from twisted.internet import defer, reactor

from flumotion.common import errors, messages, log, python
from flumotion.common.i18n import N_, gettexter
from flumotion.common.planet import moods
from flumotion.component import feedcomponent
from flumotion.component.base import scheduler
from flumotion.component.padmonitor import PadMonitor
from flumotion.component.plugs import base
from flumotion.worker.checks import check

__version__ = "$Rev$"
T_ = gettexter()


class SwitchMedium(feedcomponent.FeedComponentMedium):

    def remote_switchToMaster(self):
        return self.comp.switch_to("master")

    def remote_switchToBackup(self):
        return self.comp.switch_to("backup")

    def remote_switchTo(self, logicalFeed):
        return self.comp.switch_to(logicalFeed)


class ICalSwitchPlug(base.ComponentPlug):
    logCategory = "ical-switch"

    def start(self, component):
        self._sid = None
        self.sched = None
        try:

            def eventStarted(eventInstance):
                self.debug("event started %r", eventInstance.event.uid)
                component.switch_to("backup")

            def eventEnded(eventInstance):
                self.debug("event ended %r", eventInstance.event.uid)
                component.switch_to("master")

            # if an event starts, semantics are to switch to backup
            # if an event ends, semantics are to switch to master
            filename = self.args['properties']['ical-schedule']
            self.sched = scheduler.ICalScheduler(open(filename, 'r'))
            self._sid = self.sched.subscribe(eventStarted, eventEnded)
            if self.sched.getCalendar().getActiveEventInstances():
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

        # This structure maps logical feeds to sets of eaters. For
        # example, "master" and "backup" could be logical feeds, and
        # would be the keys in this dict, mapping to lists of eater
        # aliases corresponding to those feeds. The lengths of those
        # lists is equal to the number of feeders that the element has,
        # which is the number of individual streams in a logical feed.
        #
        # For example, {"master": ["audio-master", "video-master"],
        #               "backup": ["audio-backup", "video-backup"]}
        # logical feed name -> [eater alias]
        self.logicalFeeds = {}
        # logical feed names in order of preference
        self.feedsByPriority = []

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

        # store of new segment events consumed on switch pads
        # due to them having gone inactive
        # eater alias -> event
        self.newSegmentEvents = {}

        # probe ids
        # pad -> probe handler id
        self.eventProbeIds = {}
        self.bufferProbeIds = {}

        # pad monitors for switch sink pads
        self._padMonitors = {}

    def addWarning(self, id, format, *args, **kwargs):
        self.warning(format, *args)
        m = messages.Message(messages.WARNING, T_(format, *args),
                             mid=id, **kwargs)
        self.addMessage(m)

    def clearWarning(self, id):
        for m in self.state.get('messages')[:]:
            if m.id == id:
                self.state.remove('messages', m)

    def do_check(self):

        def checkSignal(fact):
            fact = fact.load()
            signals = gobject.signal_list_names(fact.get_element_type())
            return 'block' in signals

        def cb(result):
            for m in result.messages:
                self.addMessage(m)
            return result.value

        self.debug("checking for input-selector element")
        if gst.version() >= (0, 10, 32, 0):
            # In release 0.10.32 input-selector was moved to coreelements.
            d = check.checkPlugin('coreelements', 'gst-plugins',
                (0, 10, 5, 2), 'input-selector', checkSignal)
        else:
            d = check.checkPlugin('selector', 'gst-plugins-bad',
                (0, 10, 5, 2), 'input-selector', checkSignal)
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
                self.debug("idealFeed being set to %s", name)
                self.idealFeed = name
            self.feedsByPriority.append(name)

        return feedcomponent.MultiInputParseLaunchComponent.create_pipeline(
            self)

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
                self.log("Element: %s", e.get_name())
                pad, e = getDownstreamElement(e)
            self.debug('eater %s maps to pad %s', alias, pad)
            self.switchPads[alias] = pad, e

        # set active pad correctly on each of the switch elements
        # (pad, switch)
        pairs = [self.switchPads[alias]
                 for alias in self.logicalFeeds[self.idealFeed]]

        for p, s in pairs:
            s.set_property('active-pad', p)
        self.activeFeed = self.idealFeed
        self.uiState.set("active-eater", self.idealFeed)

        self.install_logical_feed_watches()

        self.do_switch()

    # add pad monitors on switch sink pads before we set them eaters active

    def install_logical_feed_watches(self):

        def eaterSetActive(eaterAlias):
            for feed, aliases in self.logicalFeeds.items():
                if eaterAlias in aliases:
                    if feed not in activeFeeds:
                        activeFeeds.append(feed)
                        self.feedSetActive(feed)
                    return

        def eaterSetInactive(eaterAlias):
            for feed, aliases in self.logicalFeeds.items():
                if eaterAlias in aliases and feed in activeFeeds:
                    activeFeeds.remove(feed)
                    self.feedSetInactive(feed)
                    # add an event and buffer probe to the switch pad
                    # so we can rewrite the newsegment that comes
                    # when eater is active again
                    # Not rewriting it causes the pad running time
                    # to be wrong due to the new segment having a start
                    # time being much lower than any subsequent buffers.
                    pad = self.switchPads[eaterAlias][0]
                    self.eventProbeIds[pad] = \
                        pad.add_event_probe(self._eventProbe)
                    self.bufferProbeIds[pad] = \
                        pad.add_buffer_probe(self._bufferProbe)
                    return

        activeFeeds = []
        for alias in self.eaters:
            self._padMonitors[alias] = PadMonitor(self.switchPads[alias][0],
                alias, eaterSetActive, eaterSetInactive)

    def _eventProbe(self, pad, event):
        # called from GStreamer threads
        ret = True
        if event.type == gst.EVENT_NEWSEGMENT:
            ret = False
            self.newSegmentEvents[pad] = event
        if self.eventProbeIds[pad]:
            pad.remove_event_probe(self.eventProbeIds[pad])
            del self.eventProbeIds[pad]
        return ret

    def _bufferProbe(self, pad, buffer):
        # called from GStreamer threads
        ts = buffer.timestamp
        if pad in self.newSegmentEvents:
            parsed = self.newSegmentEvents[pad].parse_new_segment()
            newEvent = gst.event_new_new_segment(parsed[0], parsed[1],
                parsed[2], ts, parsed[4], parsed[5])
            pad.push_event(newEvent)
            del self.newSegmentEvents[pad]
        if pad in self.bufferProbeIds:
            pad.remove_buffer_probe(self.bufferProbeIds[pad])
            del self.bufferProbeIds[pad]
        return True

    def get_switch_elements(self, pipeline):
        raise errors.NotImplementedError('subclasses should implement '
                                         'get_switch_elements')

    def is_active(self, feed):
        return python.all([self.eaters[alias].isActive()
                    for alias in self.logicalFeeds[feed]])

    def feedSetActive(self, feed):
        self.debug('feed %r is now active', feed)
        if feed == self.idealFeed:
            self.do_switch()

    def feedSetInactive(self, feed):
        self.debug('feed %r is now inactive', feed)

    # this function is used by the watchdogs

    def auto_switch(self):
        allFeeds = self.feedsByPriority[:]
        feed = None
        while allFeeds:
            feed = allFeeds.pop(0)
            if self.is_active(feed):
                self.debug('autoswitch selects feed %r', feed)
                self.do_switch(feed)
                break
            else:
                self.debug("could not select feed %r because not active", feed)
        if feed is None:
            feed = self.feedsByPriority.get(0, None)
            self.debug('no feeds active during autoswitch, choosing %r',
                       feed)
        self.do_switch(feed)

    # switch_to should only be called when the ideal feed is requested to be
    # changed, so not by watchdog reasons.

    def switch_to(self, feed):
        """
        @param feed: a logical feed
        """
        if feed not in self.logicalFeeds:
            self.warning("unknown logical feed: %s", feed)
            return None

        self.debug('scheduling switch to feed %s', feed)
        self.idealFeed = feed
        # here we should bump this feed above others in feedsByPriority
        self.feedsByPriority = [feed]
        for name, aliases in self.get_logical_feeds():
            if name != feed:
                self.feedsByPriority.append(name)

        if not self.pipeline:
            return

        if self.is_active(feed):
            self.do_switch()
        else:
            fmt = N_("Tried to switch to %s, but feed is unavailable. "
                     "Will retry when the feed is back.")
            self.addWarning("temporary-switch-problem", fmt, feed)

    # Switching multiple eaters is easy. The only trick is that we have
    # to close the previous segment at the same running time, on both
    # switch elements, and open the new segment at the same running
    # time. The block()/switch() signal API on switch elements lets us
    # do this. See the docs for switch's `block' and `switch' signals
    # for more information.

    def do_switch(self, feed=None):
        if feed == None:
            feed = self.idealFeed

        self.clearWarning('temporary-switch-problem')
        if feed == self.activeFeed:
            self.debug("already streaming from feed %r", feed)
            return
        if feed not in self.logicalFeeds:
            self.warning("unknown logical feed: %s", feed)
            return

        # (pad, switch)
        pairs = [self.switchPads[alias]
                 for alias in self.logicalFeeds[feed]]

        stop_times = [e.emit('block') for p, e in pairs]
        start_times = [p.get_property('running-time') for p, e in pairs]

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

        start_time = min(start_times)
        self.debug('start time = %s', gst.TIME_ARGS(start_time))

        self.debug('switching from %r to %r', self.activeFeed, feed)
        for p, e in pairs:
            self.debug("switching to pad %r", p)
            e.emit('switch', p, stop_time, start_time)

        self.activeFeed = feed
        self.uiState.set("active-eater", feed)


class SingleSwitch(Switch):
    logCategory = "single-switch"

    def get_logical_feeds(self):
        return [('master', ['master']),
                ('backup', ['backup'])]

    def get_muxer_string(self, properties):
        return ("input-selector name=muxer ! "
                "identity silent=true single-segment=true name=iden ")

    def get_switch_elements(self, pipeline):
        return [pipeline.get_by_name('muxer')]


class AVSwitch(Switch):
    logCategory = "av-switch"

    def init(self):
        # property name -> caps property name
        self.vparms = {'video-width': 'width', 'video-height': 'height',
                       'video-framerate': 'framerate',
                       'video-pixel-aspect-ratio': 'par'}
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
        propkeys = python.set(self.config['properties'].keys())
        vparms = python.set(self.vparms.keys())
        aparms = python.set(self.aparms.keys())

        for kind, parms in ('Video', vparms), ('Audio', aparms):
            missing = parms - (propkeys & parms)
            if missing and missing != parms:
                fmt = N_("%s parameter(s) were specified but not all. "
                         "Missing parameters are: %r")
                self.addError("video-params-not-specified", fmt, kind,
                              list(missing))

    def get_pipeline_string(self, properties):

        def i420caps(framerate, par, width, height):
            return ("video/x-raw-yuv,width=%d,height=%d,framerate=%d/%d,"
                    "pixel-aspect-ratio=%d/%d,format=(fourcc)I420"
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

        pipeline = ("input-selector name=vswitch"
                    " ! identity silent=true single-segment=true"
                    " ! @feeder:video@ "
                    "input-selector name=aswitch"
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
