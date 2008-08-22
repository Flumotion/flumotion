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
check streams for flumotion-nagios
"""
import urllib
import urlparse
import re
import time
import gst
import gobject
from flumotion.monitor.nagios import util

URLFINDER = 'http://[^\s"]*' # to search urls in playlists


class Check(util.LogCommand):
    """Main class to perform the stream checks"""
    description = 'Check stream.'
    usage = 'check [options] url'

    def __init__(self, parentCommand=None, **kwargs):
        """Initial values and pipeline setup"""
        self._expectAudio = False
        self._expectVideo = False
        self._isAudio = False
        self._isVideo = False
        self._isPlaylist = True
        self._url = None

        util.LogCommand.__init__(self, parentCommand, **kwargs)

    def addOptions(self):
        """Command line options"""
        # video options
        self.parser.add_option('-W', '--videowidth',
            action="store", dest="videowidth",
            help='Video width')
        self.parser.add_option('-H', '--videoheight',
            action="store", dest="videoheight",
            help='Video height')
        self.parser.add_option('-F', '--videoframerate',
            action="store", dest="videoframerate",
            help='Video framerate (fraction)')
        self.parser.add_option('-P', '--videopar',
            action="store", dest="videopar",
            help='Video pixel aspect ratio (fraction)')
        self.parser.add_option('-M', '--videomimetype',
            action="store", dest="videomimetype",
            help='Video mimetype')

        # audio options
        self.parser.add_option('-s', '--audiosamplerate',
            action="store", dest="audiosamplerate",
            help='Audio sample rate')
        self.parser.add_option('-c', '--audiochannels',
            action="store", dest="audiochannels",
            help='Audio channels')
        self.parser.add_option('-w', '--audiowidth',
            action="store", dest="audiowidth",
            help='Audio width')
        self.parser.add_option('-d', '--audiodepth',
            action="store", dest="audiodepth",
            help='Audio depth')
        self.parser.add_option('-m', '--audiomimetype',
            action="store", dest="audiomimetype",
            help='Audio mimetype')

        # general option
        self.parser.add_option('-D', '--duration',
            action="store", dest="duration", default='5',
            help='Check duration (default 5 seconds)')
        self.parser.add_option('-t', '--timeout',
            action="store", dest="timeout", default='10',
            help='Number of seconds to timeout.')
        self.parser.add_option('-p', '--playlist',
            action="store_true", dest="playlist",
            help='is a playlist')

    def handleOptions(self, options):
        #Determine if this stream would have audio/video
        self.options = options
        if options.videowidth or options.videoheight or \
           options.videoframerate or options.videopar or \
           options.videomimetype:
            self._expectVideo = True
        if options.audiosamplerate or options.audiochannels or \
           options.audiowidth or options.audiodepth or \
           options.audiomimetype:
            self._expectAudio = True

    def critical(self, message):
        return util.critical('%s: %s' % (self._url, message))

    def ok(self, message):
        return util.ok('%s: %s' % (self._url, message))

    def do(self, args):
        """Check URL and perfom the stream check"""
        if not args:
            return self.critical('Please specify the url to check the '
            'stream/playlist.')

        self._url = args[0]
        # check url and get path from it
        try:
            parse = urlparse.urlparse(self._url)
        except ValueError:
            return self.critical("URL isn't valid.")
        if parse[0] != 'http':
            return self.critical('URL type is not valid.')

        # Simple playlist detection.
        if self._url.endswith('.m3u') or self._url.endswith('.asx'):
            self.options.playlist = True

        if self.options.playlist:
            self._url = self.getURLFromPlaylist(self._url)

        result = self.checkStream()
        return result

    def getURLFromPlaylist(self, url):
        playlist = urllib.urlopen(self._url).read()
        if playlist.startswith('404'):
            return util.critical(playlist)
        urls = re.findall(URLFINDER, playlist)
        return urls[-1] # new (the last) url to check

    def checkStream(self):
        """Launch the pipeline and compare values with the expecteds"""
        while self._isPlaylist: #use gstreamer to detect the playlist
            gstinfo = GSTInfo(int(self.options.timeout),
                              int(self.options.duration), self._url)
            elements = gstinfo.getElements()
            self._isPlaylist = gstinfo.isPlaylist()
            if self._isPlaylist:
                self._url = self.getURLFromPlaylist(self._url) #replace the url

        running = gstinfo.getRunning() # seconds running gstinfo
        counter = gstinfo.getCounter() # seconds getting media data

        for i in elements['typefinder'].src_pads():
            caps = i.get_caps()
            if caps == 'ANY' or not caps:
                if gstinfo.getError():
                    return self.critical(gstinfo.getError())
                else:
                    return self.critical("There aren't caps in this stream.")

        for i in elements['decoder'].src_pads():
            caps = i.get_caps()
            mime = caps.to_string().split(', ')[0]
            # tests for audio
            if 'audio' in caps.to_string():
                self._isAudio = True
                if self.options.audiomimetype:
                    if self.options.audiomimetype != mime:
                        return self.critical('Audio mime type fail: '
                        'EXPECTED: %s, ACTUAL: %s' %
                        (self.options.audiomimetype, mime))
                if self.options.audiosamplerate:
                    if int(self.options.audiosamplerate) != caps[0]['rate']:
                        return self.critical('Audio sample rate fail: '
                        'EXPECTED: %s, ACTUAL: %s' %
                        (self.options.audiosamplerate, caps[0]['rate']))
                if self.options.audiowidth:
                    if int(self.options.audiowidth) != caps[0]['width']:
                        return self.critical('Audio width fail: '
                        'EXPECTED: %s, ACTUAL: %s' %
                        (self.options.audiowidth, caps[0]['width']))
                if self.options.audiodepth:
                    if int(self.options.audiodepth) != caps[0]['depth']:
                        return self.critical('Audio depth fail: '
                        'EXPECTED: %s, ACTUAL: %s' %
                        (self.options.audiodepth, caps[0]['depth']))
                if self.options.audiochannels:
                    if int(self.options.audiochannels) != caps[0]['channels']:
                        return self.critical('Audio channels fail: '
                        'EXPECTED: %s, ACTUAL: %s' %
                        (self.options.audiochannels, caps[0]['channels']))
            # tests for video
            if 'video' in caps.to_string():
                self._isVideo = True
                if self.options.videomimetype:
                    if self.options.videomimetype != mime:
                        return self.critical('Video mime type fail: '
                        'EXPECTED: %s, ACTUAL: %s' %
                        (self.options.videomimetype, mime))
                if self.options.videowidth:
                    if int(self.options.videowidth) != caps[0]['width']:
                        return self.critical('Video width fail: '
                        'EXPECTED: %s, ACTUAL: %s' %
                        (self.options.videowidth, caps[0]['width']))
                if self.options.videoheight:
                    if int(self.options.videoheight) != caps[0]['height']:
                        return self.critical('Video height fail: '
                        'EXPECTED: %s, ACTUAL: %s' %
                        (self.options.videoheight, caps[0]['height']))
                if self.options.videoframerate:
                    value = caps[0]['framerate']
                    if self.options.videoframerate != '%i/%i' % \
                        (value.num, value.denom):
                        return self.critical('Video framerate fail: '
                        'EXPECTED: %s, ACTUAL: %i/%i' %
                        (self.options.videoframerate, value.num, value.denom))
                if self.options.videopar:
                    value = caps[0]['pixel-aspect-ratio']
                    if self.options.videopar != '%i/%i' % \
                        (value.num, value.denom):
                        return self.critical('Video height fail: '
                        'EXPECTED: %s, ACTUAL: %i/%i' %
                        (self.options.videopar, value.num, value.denom))

        # is audio and/or video missing?
        if self._expectAudio != self._isAudio:
            if self._expectAudio:
                return self.critical('Expected audio, but no audio in stream')
            else:
                return self.critical('Did not expect audio, '
                    'but audio in stream')
        if self._expectVideo != self._isVideo:
            if self._expectVideo:
                return self.critical('Expected video, but no video in stream')
            else:
                return self.critical('Did not expect video, '
                    'but video in stream')

        gstinfo.setState(gst.STATE_NULL)
        if self._expectAudio and self._expectVideo:
            return self.ok('Got %i seconds of audio and video in '
                           '%i seconds of runtime.' % (counter, running))
        elif self._expectAudio:
            return self.ok('Got %i seconds of audio in '
                           '%i seconds of runtime.' % (counter, running))
        elif self._expectVideo:
            return self.ok('Got %i seconds of video in '
                           '%i seconds of runtime.' % (counter, running))
        else: # impossible condition?
            return self.critical("All appears OK, but the stream haven't"
                                 "audio or video data.")


class GSTInfo:
    """Get info from stream using a gstreamer pipeline"""

    def __init__(self, timeout, duration, url):
        self._mainloop = gobject.MainLoop()
        self._counter = 0 # counter to track the playing state
        _pipeline = 'souphttpsrc name=httpsrc ! ' \
                    'typefind name=typefinder ! ' \
                    'decodebin name=decoder ! ' \
                    'fakesink'
        self._duration = duration
        self._url = url
        self._error = ''
        self._playlist = False
        self._timeout = True
        self._startime = time.time()
        self._running = 0
        self._pipeline = gst.parse_launch(_pipeline)
        self._elements = dict((e.get_name(), e) for e in \
                                              self._pipeline.elements())
        bus = self._pipeline.get_bus()
        bus.add_watch(self.busWatch)
        self._elements['httpsrc'].set_property('location', url)
        self._pipeline.set_state(gst.STATE_PLAYING)
        gobject.timeout_add(timeout * 1000, self.endTimeout)

        self._mainloop.run()

    def setState(self, state):
        self._pipeline.set_state(state)

    def getElements(self):
        return self._elements

    def getError(self):
        return self._error

    def isPlaylist(self):
        return self._playlist

    def getRunning(self):
        return self._running

    def getCounter(self):
        return self._counter

    def quit(self):
        self._running = int(time.time() - self._startime)
        self._mainloop.quit()

    def busWatch(self, bus, message):
        """Capture messages in pipeline bus"""
        if message.type == gst.MESSAGE_EOS:
            self._pipeline.set_state(gst.STATE_NULL)
        elif message.type == gst.MESSAGE_ERROR:
            self._error = message.parse_error()[0].message
            self._pipeline.set_state(gst.STATE_NULL)
            code = message.parse_error()[0].code
            if code == gst.STREAM_ERROR_CODEC_NOT_FOUND:
                if 'text/uri-list' in message.parse_error()[0].message:
                    self._playlist = True
            self.quit()
        elif message.type == gst.MESSAGE_STATE_CHANGED:
            new = message.parse_state_changed()[1]
            if message.src == self._pipeline and new == gst.STATE_PLAYING:
                self._timeout = False
                gobject.timeout_add(1000, self.isPlaying)
        return True

    def isPlaying(self):
        """Check the stream is playing every second"""
        ret, cur, pen = self._pipeline.get_state()
        if ret == gst.STATE_CHANGE_SUCCESS and cur == gst.STATE_PLAYING:
            self._counter += 1
            if self._counter == self._duration:
                self.quit()
        return True

    def endTimeout(self):
        """End of time to do the check"""
        if self._timeout:
            self.quit()
