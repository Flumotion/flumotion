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

import time

import gst
from twisted.internet import defer, reactor

from flumotion.common import messages, fxml, gstreamer, documentation
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent
from flumotion.component.base import watcher

import smartscale
import singledecodebin
import playlistparser

__version__ = "$Rev$"
T_ = gettexter()


def _tsToString(ts):
    """
    Return a string in local time from a gstreamer timestamp value
    """
    return time.ctime(ts/gst.SECOND)


def videotest_gnl_src(name, start, duration, priority, pattern=None):
    src = gst.element_factory_make('videotestsrc')
    if pattern:
        src.props.pattern = pattern
    else:
        # Set videotestsrc to all black.
        src.props.pattern = 2
    gnlsrc = gst.element_factory_make('gnlsource', name)
    gnlsrc.props.start = start
    gnlsrc.props.duration = duration
    gnlsrc.props.media_start = 0
    gnlsrc.props.media_duration = duration
    gnlsrc.props.priority = priority
    gnlsrc.add(src)

    return gnlsrc


def audiotest_gnl_src(name, start, duration, priority, wave=None):
    src = gst.element_factory_make('audiotestsrc')
    if wave:
        src.props.wave = wave
    else:
        # Set audiotestsrc to use silence.
        src.props.wave = 4
    gnlsrc = gst.element_factory_make('gnlsource', name)
    gnlsrc.props.start = start
    gnlsrc.props.duration = duration
    gnlsrc.props.media_start = 0
    gnlsrc.props.media_duration = duration
    gnlsrc.props.priority = priority
    gnlsrc.add(src)

    return gnlsrc


def file_gnl_src(name, uri, caps, start, duration, offset, priority):
    src = singledecodebin.SingleDecodeBin(caps, uri)
    gnlsrc = gst.element_factory_make('gnlsource', name)
    gnlsrc.props.start = start
    gnlsrc.props.duration = duration
    gnlsrc.props.media_start = offset
    gnlsrc.props.media_duration = duration
    gnlsrc.props.priority = priority
    gnlsrc.props.caps = caps
    gnlsrc.add(src)

    return gnlsrc


class PlaylistProducerMedium(feedcomponent.FeedComponentMedium):

    def __init__(self, comp):
        feedcomponent.FeedComponentMedium.__init__(self, comp)

    def remote_add_playlist(self, data):
        self.comp.addPlaylist(data)


class PlaylistProducer(feedcomponent.FeedComponent):
    logCategory = 'playlist-prod'
    componentMediumClass = PlaylistProducerMedium

    def init(self):
        self.basetime = -1

        self._hasAudio = True
        self._hasVideo = True

        # The gnlcompositions for audio and video
        self.videocomp = None
        self.audiocomp = None

        self.videocaps = gst.Caps("video/x-raw-yuv;video/x-raw-rgb")
        self.audiocaps = gst.Caps("audio/x-raw-int;audio/x-raw-float")

        self._vsrcs = {} # { PlaylistItem -> gnlsource }
        self._asrcs = {} # { PlaylistItem -> gnlsource }

        self.uiState.addListKey("playlist")

    def _buildAudioPipeline(self, pipeline, src):
        audiorate = gst.element_factory_make("audiorate")
        audioconvert = gst.element_factory_make('audioconvert')
        resampler = 'audioresample'
        if gstreamer.element_factory_exists('legacyresample'):
            resampler = 'legacyresample'
        audioresample = gst.element_factory_make(resampler)
        outcaps = gst.Caps(
            "audio/x-raw-int,channels=%d,rate=%d,width=16,depth=16" %
            (self._channels, self._samplerate))

        capsfilter = gst.element_factory_make("capsfilter")
        capsfilter.props.caps = outcaps

        pipeline.add(audiorate, audioconvert, audioresample, capsfilter)
        src.link(audioconvert)
        audioconvert.link(audioresample)
        audioresample.link(audiorate)
        audiorate.link(capsfilter)

        return capsfilter.get_pad('src')

    def _buildVideoPipeline(self, pipeline, src):
        outcaps = gst.Caps(
            "video/x-raw-yuv,width=%d,height=%d,framerate=%d/%d,"
            "pixel-aspect-ratio=1/1" %
                (self._width, self._height, self._framerate[0],
                 self._framerate[1]))

        cspace = gst.element_factory_make("ffmpegcolorspace")
        scaler = smartscale.SmartVideoScale()
        scaler.set_caps(outcaps)
        videorate = gst.element_factory_make("videorate")
        capsfilter = gst.element_factory_make("capsfilter")
        capsfilter.props.caps = outcaps

        pipeline.add(cspace, scaler, videorate, capsfilter)

        src.link(cspace)
        cspace.link(scaler)
        scaler.link(videorate)
        videorate.link(capsfilter)
        return capsfilter.get_pad('src')

    def _buildPipeline(self):
        pipeline = gst.Pipeline()

        for mediatype in ['audio', 'video']:
            if (mediatype == 'audio' and not self._hasAudio) or (
                mediatype == 'video' and not self._hasVideo):
                continue

            # For each of audio, video, we build a pipeline that looks roughly
            # like:
            #
            # gnlcomposition ! identity sync=true !
            # identity single-segment=true ! audio/video-elements ! sink

            composition = gst.element_factory_make("gnlcomposition",
                mediatype + "-composition")

            segmentidentity = gst.element_factory_make("identity")
            segmentidentity.set_property("single-segment", True)
            segmentidentity.set_property("silent", True)
            syncidentity = gst.element_factory_make("identity")
            syncidentity.set_property("silent", True)
            syncidentity.set_property("sync", True)

            pipeline.add(composition, segmentidentity, syncidentity)

            def _padAddedCb(element, pad, target):
                self.debug("Pad added, linking")
                pad.link(target)
            composition.connect('pad-added', _padAddedCb,
                syncidentity.get_pad("sink"))
            syncidentity.link(segmentidentity)

            if mediatype == 'audio':
                self.audiocomp = composition
                srcpad = self._buildAudioPipeline(pipeline, segmentidentity)
            else:
                self.videocomp = composition
                srcpad = self._buildVideoPipeline(pipeline, segmentidentity)

            feedername = self.feeders[mediatype].elementName
            #FIXME: rethink how we expose the feeder pipeline strings
            feederchunk = \
              feedcomponent.ParseLaunchComponent.FEEDER_TMPL \
              % {'name': feedername}

            binstr = "bin.("+feederchunk+" )"
            self.debug("Parse for media composition is %s", binstr)

            bin = gst.parse_launch(binstr)
            pad = bin.find_unconnected_pad(gst.PAD_SINK)
            ghostpad = gst.GhostPad(mediatype + "-feederpad", pad)
            bin.add_pad(ghostpad)

            pipeline.add(bin)
            srcpad.link(ghostpad)

        return pipeline

    def _createDefaultSources(self, properties):
        if self._hasVideo:
            vsrc = videotest_gnl_src("videotestdefault", 0, 2**63 - 1,
                2**31 - 1, properties.get('video-pattern', None))
            self.videocomp.add(vsrc)

        if self._hasAudio:
            asrc = audiotest_gnl_src("videotestdefault", 0, 2**63 - 1,
                2**31 - 1, properties.get('audio-wave', None))
            self.audiocomp.add(asrc)

    def set_master_clock(self, ip, port, base_time):
        raise NotImplementedError("Playlist producer doesn't support slaving")

    def provide_master_clock(self, port):
        # Most of this copied from feedcomponent010, but changed in various
        # ways. Refactor the base class?
        if self.medium:
            ip = self.medium.getIP()
        else:
            ip = "127.0.0.1"

        clock = self.pipeline.get_clock()
        self.clock_provider = gst.NetTimeProvider(clock, None, port)
        # small window here but that's ok
        self.clock_provider.set_property('active', False)

        self._master_clock_info = (ip, port, self.basetime)

        return defer.succeed(self._master_clock_info)

    def get_master_clock(self):
        return self._master_clock_info

    def _setupClock(self, pipeline):
        # Configure our pipeline to use a known basetime and clock.
        clock = gst.SystemClock()
        # It doesn't matter too much what this basetime is, so long as we know
        # the value.
        self.basetime = clock.get_time()

        # We force usage of the system clock.
        pipeline.use_clock(clock)
        # Now we disable default basetime distribution
        pipeline.set_new_stream_time(gst.CLOCK_TIME_NONE)
        # And we choose our own basetime...
        self.debug("Setting basetime of %d", self.basetime)
        pipeline.set_base_time(self.basetime)

    def timeReport(self):
        ts = self.pipeline.get_clock().get_time()
        self.debug("Pipeline clock is now at %d -> %s", ts, _tsToString(ts))
        reactor.callLater(10, self.timeReport)

    def getCurrentPosition(self):
        return self.pipeline.query_position(gst.FORMAT_TIME)[0]

    def scheduleItem(self, item):
        """
        Schedule a given playlist item in our playback compositions.
        """
        start = item.timestamp - self.basetime
        self.debug("Starting item %s at %d seconds from start: %s", item.uri,
            start/gst.SECOND, _tsToString(item.timestamp))

        # If we schedule things to start before the current pipeline position,
        # gnonlin will adjust this to start now. However, it does this
        # separately for audio and video, so we start from different points,
        # thus we're out of sync.
        # So, always start slightly in the future... 5 seconds seems to work
        # fine in practice.
        now = self.getCurrentPosition()
        neareststarttime = now + 5 * gst.SECOND

        if start < neareststarttime:
            if start + item.duration < neareststarttime:
                self.debug("Item too late; skipping entirely")
                return False
            else:
                change = neareststarttime - start
                self.debug("Starting item with offset %d", change)
                item.duration -= change
                item.offset += change
                start = neareststarttime

        end = start + item.duration
        timeuntilend = end - now
        # After the end time, remove this item from the composition, otherwise
        # it will continue to use huge gobs of memory and lots of threads.
        reactor.callLater(timeuntilend/gst.SECOND + 5,
            self.unscheduleItem, item)

        if self._hasVideo and item.hasVideo:
            self.debug("Adding video source with start %d, duration %d, "
                "offset %d", start, item.duration, item.offset)
            vsrc = file_gnl_src(None, item.uri, self.videocaps,
                start, item.duration, item.offset, 0)
            self.videocomp.add(vsrc)
            self._vsrcs[item] = vsrc
        if self._hasAudio and item.hasAudio:
            self.debug("Adding audio source with start %d, duration %d, "
                "offset %d", start, item.duration, item.offset)
            asrc = file_gnl_src(None, item.uri, self.audiocaps,
                start, item.duration, item.offset, 0)
            self.audiocomp.add(asrc)
            self._asrcs[item] = asrc
        self.debug("Done scheduling: start at %s, end at %s",
            _tsToString(start + self.basetime),
            _tsToString(start + self.basetime + item.duration))

        self.uiState.append("playlist", (item.timestamp,
                                         item.uri,
                                         item.duration,
                                         item.offset,
                                         item.hasAudio,
                                         item.hasVideo))
        return True

    def unscheduleItem(self, item):
        self.debug("Unscheduling item at uri %s", item.uri)
        if self._hasVideo and item.hasVideo and item in self._vsrcs:
            vsrc = self._vsrcs.pop(item)
            self.videocomp.remove(vsrc)
            vsrc.set_state(gst.STATE_NULL)
        if self._hasAudio and item.hasAudio and item in self._asrcs:
            asrc = self._asrcs.pop(item)
            self.audiocomp.remove(asrc)
            asrc.set_state(gst.STATE_NULL)
        for entry in self.uiState.get("playlist"):
            if entry[0] == item.timestamp:
                self.uiState.remove("playlist", entry)

    def adjustItemScheduling(self, item):
        if self._hasVideo and item.hasVideo:
            vsrc = self._vsrcs[item]
            vsrc.props.start = item.timestamp - self.basetime
            vsrc.props.duration = item.duration
            vsrc.props.media_duration = item.duration
        if self._hasAudio and item.hasAudio:
            asrc = self._asrcs[item]
            asrc.props.start = item.timestamp - self.basetime
            asrc.props.duration = item.duration
            asrc.props.media_duration = item.duration

    def addPlaylist(self, data):
        self.playlistparser.parseData(data)

    def create_pipeline(self):
        props = self.config['properties']

        self._playlistfile = props.get('playlist', None)
        self._playlistdirectory = props.get('playlist-directory', None)
        self._baseDirectory = props.get('base-directory', None)

        self._width = props.get('width', 320)
        self._height = props.get('height', 240)
        self._framerate = props.get('framerate', (15, 1))
        self._samplerate = props.get('samplerate', 44100)
        self._channels = props.get('channels', 2)

        self._hasAudio = props.get('audio', True)
        self._hasVideo = props.get('video', True)

        pipeline = self._buildPipeline()
        self._setupClock(pipeline)

        self._createDefaultSources(props)

        return pipeline

    def _watchDirectory(self, dir):
        self.debug("Watching directory %s", dir)
        self._filesAdded = {}

        self._directoryWatcher = watcher.DirectoryWatcher(dir)
        self._directoryWatcher.subscribe(fileChanged=self._watchFileChanged,
            fileDeleted=self._watchFileDeleted)

        # in the start call watcher should find all the existing
        # files, so we block discovery while the watcher starts
        self.playlistparser.blockDiscovery()
        try:
            self._directoryWatcher.start()
        finally:
            self.playlistparser.unblockDiscovery()

    def _watchFileDeleted(self, file):
        self.debug("File deleted: %s", file)
        if file in self._filesAdded:
            self.playlistparser.playlist.removeItems(file)
            self._filesAdded.pop(file)

            self._cleanMessage(file)

    def _cleanMessage(self, file):
        # There's no message removal API! We have to do this instead. Ick?
        msgid = ("playlist-parse-error", file)
        for m in self.state.get('messages'):
            if m.id == msgid:
                self.state.remove('messages', m)

    def _watchFileChanged(self, file):
        self.debug("File changed: %s", file)
        if file in self._filesAdded:
            self.debug("Removing existing items for changed playlist")
            self.playlistparser.playlist.removeItems(file)

        self._filesAdded[file] = None
        self._cleanMessage(file)
        try:
            self.debug("Parsing file: %s", file)
            self.playlistparser.parseFile(file, piid=file)
        except fxml.ParserError, e:
            self.warning("Failed to parse playlist file: %r", e)
            # Since this isn't done directly via the remote method, add a
            # message so people can find out that it failed...
            # Use a tuple including the filename to identify the warning, so we
            # can add/remove one per file
            msgid = ("playlist-parse-error", file)
            self.addMessage(
                messages.Warning(T_(N_(
                    "Failed to parse a playlist from file %s: %s" %
                        (file, e))), mid=msgid))

    def do_check(self):

        def check_gnl(element):
            exists = gstreamer.element_factory_exists(element)
            if not exists:
                m = messages.Error(T_(N_(
                    "%s is missing. Make sure your gnonlin "
                    "installation is complete."), element))
                documentation.messageAddGStreamerInstall(m)
                self.debug(m)
                self.addMessage(m)

        for el in ["gnlsource", "gnlcomposition"]:
            check_gnl(el)

    def do_setup(self):
        playlist = playlistparser.Playlist(self)
        self.playlistparser = playlistparser.PlaylistXMLParser(playlist)
        if self._baseDirectory:
            self.playlistparser.setBaseDirectory(self._baseDirectory)

        if self._playlistfile:
            try:
                self.playlistparser.parseFile(self._playlistfile)
            except fxml.ParserError, e:
                self.warning("Failed to parse playlist file: %r", e)

        if self._playlistdirectory:
            self._watchDirectory(self._playlistdirectory)

        reactor.callLater(10, self.timeReport)
