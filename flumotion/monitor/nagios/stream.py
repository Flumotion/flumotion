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

import os
import sys
import tempfile
import re
import time
import datetime
import urlparse
import urllib2

import gst
import gobject

from twisted.internet import reactor, defer

from flumotion.admin import admin, connections
from flumotion.common import errors, keycards, python
from flumotion.monitor.nagios import util

URLFINDER = "http://[^\s'\"]*" # to search urls in playlists
PLAYLIST_SUFFIX = ('m3u', 'asx') # extensions for playlists
TIMEOUT = 5 # timeout in seconds

CHECKS = {'videowidth': 'video_width',
          'videoheight': 'video_height',
          'videoframerate': 'video_framerate',
          'videopar': 'video_pixel-aspect-ratio',
          'videomimetype': 'video_mime',
          'videomimetype': 'video_mime',
          'audiosamplerate': 'audio_rate',
          'audiochannels': 'audio_channels',
          'audiowidth': 'audio_width',
          'audiodepth': 'audio_depth',
          'audiomimetype': 'audio_mime'}


def gen_timed_link(relative_path, secret_key, timeout, type):
    start_time = '%08x' % (time.time() - 10)
    stop_time = '%08x' % (time.time() + int(timeout))
    hashable = secret_key + relative_path + start_time + stop_time
    if type == 'md5':
        hashed = python.md5(hashable).hexdigest()
    else:
        hashed = python.sha1(hashable).hexdigest()
    return '%s%s%s' % (hashed, start_time, stop_time)


def getURLFromPlaylist(url):
    try:
        playlist = urllib2.urlopen(url)
    except urllib2.URLError, e:
        raise util.NagiosCritical(e)

    urls = re.findall(URLFINDER, playlist.read())
    if urls:
        return urls[-1] # new (the last) url to check
    else:
        raise util.NagiosCritical('No URLs into the playlist.')


class CheckBase(util.LogCommand):
    '''Main class to perform the stream checks'''
    description = 'Check stream.'
    usage = '[options] url'

    def __init__(self, parentCommand=None, **kwargs):
        '''Initial values and pipeline setup'''
        self._expectAudio = False
        self._expectVideo = False
        self._playlist = False
        self._url = None
        self._streamurl = None
        self.managerDeferred = defer.Deferred()
        self.model = None
        self._path = ''
        self._tmpfile = ''
        self.token = ''
        util.LogCommand.__init__(self, parentCommand, **kwargs)

    def handleOptions(self, options):
        self.options = options

    def addOptions(self):
        '''Command line options'''
        # video options
        self.parser.add_option('-W', '--videowidth',
            action='store', dest='videowidth',
            help='Video width')
        self.parser.add_option('-H', '--videoheight',
            action='store', dest='videoheight',
            help='Video height')
        self.parser.add_option('-F', '--videoframerate',
            action='store', dest='videoframerate',
            help='Video framerate (fraction)')
        self.parser.add_option('-P', '--videopar',
            action='store', dest='videopar',
            help='Video pixel aspect ratio (fraction)')
        self.parser.add_option('-M', '--videomimetype',
            action='store', dest='videomimetype',
            help='Mime type of the encoded video')

        # audio options
        self.parser.add_option('-s', '--audiosamplerate',
            action='store', dest='audiosamplerate',
            help='Audio sample rate')
        self.parser.add_option('-c', '--audiochannels',
            action='store', dest='audiochannels',
            help='Audio channels')
        self.parser.add_option('-w', '--audiowidth',
            action='store', dest='audiowidth',
            help='Audio width')
        self.parser.add_option('-d', '--audiodepth',
            action='store', dest='audiodepth',
            help='Audio depth')
        self.parser.add_option('-m', '--audiomimetype',
            action='store', dest='audiomimetype',
            help='Mime type of the encoded audio')

        # general options
        self.parser.add_option('-T', '--timestamp',
            action='store', dest='timestamp',
            help='Check if timestamp is higher that this value.')
        self.parser.add_option('-D', '--duration',
            action='store', dest='duration', default='5',
            help='Minimum duration of decoded data (default 5 seconds)')
        self.parser.add_option('-t', '--timeout',
            action='store', dest='timeout', default='10',
            help='Number of seconds before timing out and failing '
                '(default 10 seconds)')
        self.parser.add_option('-p', '--playlist',
            action='store_true', dest='playlist',
            help='is a playlist')
        self.parser.add_option('', '--manager',
            dest='manager', default='user:test@localhost:7531',
            help='the manager connection string, in the form '
                 '[username[:password]@]host:port (defaults to '
                 'user:test@localhost:7531)')
        self.parser.add_option('', '--bouncer',
            action='store', dest='bouncer', help='bouncer path')
        self.parser.add_option('', '--ip',
            action='store', dest='ip', default='195.10.10.36',
            help='IP used to create the keycard [default 195.10.10.36]')
        self.parser.add_option('', '--transport',
            action='store', dest='transport', default='ssl',
            help='transport protocol to use (tcp/ssl) [default ssl]')

    def do(self, args):
        '''Check URL, IP and perfom the stream check'''
        if not args:
            return self.critical('Please specify the url to check the '
            'stream/playlist.')

        # Check url and get path from it
        self._url = args[0]
        try:
            parse = urlparse.urlparse(self._url)
        except ValueError:
            return self.critical('URL isn\'t valid.')
        if parse[0] != 'http':
            return self.critical('URL type is not valid.')
        self._path = parse[2]

        # use unique names for stream dumps
        if len(self._path) <= 1:
            self._path = 'unknown'
        elif self._path[0] == '/':
            self._path = self._path[1:]
        slug = self._path.replace('/', '_')
        if slug[-3:] in PLAYLIST_SUFFIX:
            slug = slug[:-4]
        (fd, self._tmpfile) = tempfile.mkstemp(
            suffix='.flumotion-nagios.%s-%s' % (
                datetime.datetime.now().strftime('%Y%m%dT%H%M%S'), slug))

        if self.options.bouncer:
            # Check for a valid IPv4 address with numbers and dots
            parts = self.options.ip.split('.')
            if len(parts) != 4:
                return self.critical('URL type is not valid.')
            for item in parts:
                if not 0 <= int(item) <= 255:
                    return self.critical('URL type is not valid.')
            result = self.connect(self.options)
            reactor.run()
            if reactor.exitStatus != 0:
                sys.exit(reactor.exitStatus)

        # Simple playlist detection
        if not self.options.playlist and self._url[-3:] in PLAYLIST_SUFFIX:
            self._url = getURLFromPlaylist(self._url)
            self.options.playlist = True
        # If it is a playlist, take the correct URL
        elif self.options.playlist:
            self._url = getURLFromPlaylist(self._url)

        # Determine if this stream would have audio/video
        if self.options.videowidth or self.options.videoheight or \
           self.options.videoframerate or self.options.videopar or \
           self.options.videomimetype:
            self._expectVideo = True
        if self.options.audiosamplerate or self.options.audiochannels or \
           self.options.audiowidth or self.options.audiodepth or \
           self.options.audiomimetype:
            self._expectAudio = True

        # Add token only if we need it
        if self.token:
            self._url += '?token=%s' % self.token

        result = self.checkStream()
        return result

    def checkStream(self):
        '''Check stream'''
        i = GstInfo(self._url, self.options, self._tmpfile)
        isAudio, isVideo, info, error = i.run()

        # is there an error?
        if error:
            return self.critical('GStreamer error: %s' % error[1])

        # is audio and/or video missing?
        if self._expectAudio != isAudio:
            if self._expectAudio:
                msg = 'Expected audio, but no audio in stream'
                return self.critical(msg)
            else:
                msg = 'Did not expect audio, but audio in stream'
                return self.critical(msg)
        if self._expectVideo != isVideo:
            if self._expectVideo:
                msg = 'Expected video, but no video in stream'
                return self.critical(msg)
            else:
                msg = 'Did not expect video, but video in stream'
                return self.critical(msg)

        # then we check options
        for i in CHECKS:
            expected = getattr(self.options, i)
            if expected:
                current = info[CHECKS[i]]
                if str(current) != expected:
                    return self.critical(
                        '%s fail: EXPECTED: %s, ACTUAL: %s' %
                        (i, expected, current))
        return self.ok('Got %s seconds of audio and video.' %
            self.options.duration)

    def critical(self, message):
        return util.critical('%s: %s [dump at %s]' %
            (self._url, message, self._tmpfile))

    def ok(self, message):
        # remove tempfile with the stream if all goes ok
        os.remove(self._tmpfile)
        return util.ok('%s: %s' % (self._url, message))

    def unknown(self, message):
        return util.unknown('%s: %s [dump at %s]' %
            (self._url, message, self._tmpfile))

    def connect(self, options):
        # code from main.py in this directory

        def _connectedCb(model):
            self.model = model
            self.debug('Connected to manager.')
            planet = model.planet
            components = planet.get('atmosphere').get('components')
            for c in components:
                ctype = c.get('type')
                # check if this component is a bouncer
                if 'bouncer' in ctype:
                    if c.get('name') == self.options.bouncer:
                        self.check_bouncer(c, ctype)

        def _connectedEb(failure):
            reactor.stop()
            if failure.check(errors.ConnectionFailedError):
                return self.unknown('Unable to connect to manager.')
            if failure.check(errors.ConnectionRefusedError):
                return self.critical('Manager refused connection.')

        connection = connections.parsePBConnectionInfoRecent(options.manager,
                                                 options.transport == 'ssl')

        # platform-3/trunk compatibility stuff
        try:
            # platform-3
            self.adminModel = admin.AdminModel(connection.authenticator)
            self.debug('code is platform-3')
            d = self.adminModel.connectToHost(connection.host, \
                connection.port, not connection.use_ssl)
        except TypeError:
            # trunk
            self.adminModel = admin.AdminModel()
            self.debug('code is trunk')
            d = self.adminModel.connectToManager(connection)
        except:
            self.debug('error connecting with manager')

        d.addCallback(_connectedCb)
        d.addErrback(_connectedEb)

    def check_bouncer(self, component, ctype):
        pass


class Check(CheckBase):

    def check_bouncer(self, component, ctype):

        def authenticate(result):
            self.authenticate = result

        def noauthenticate(result):
            util.critical('Error: %s' % result)
            reactor.stop()

        def success(result):
            self.enabled = result # True or False from bouncer status

        def failure(result):
            util.critical('Error: %s' % result)
            reactor.stop()

        # Read config and get correct properties for each bouncers
        k = keycards.KeycardGeneric()

        e = self.model.callRemote('componentCallRemote',
            component, 'getEnabled')
        e.addErrback(failure)
        e.addCallback(success)

        f = self.model.callRemote('componentCallRemote',
            component, 'authenticate', k)
        f.addErrback(noauthenticate)
        f.addCallback(authenticate)


class GstInfo:
    video = None
    audio = None
    audio_ts = None
    video_ts = None
    have_audio = False
    have_video = False
    video_done = False
    audio_done = False
    info = {}
    error = None

    def __init__(self, uri, options, tmpfile):
        # it's fine to not have any of them and then have pipeline parsing
        # fail trying to use the last option
        for factory in ['gnomevfssrc', 'neonhttpsrc', 'souphttpsrc']:
            try:
                gst.element_factory_make(factory)
                break
            except gst.PluginNotFoundError:
                pass
        PIPELINE = '%s name=input ! tee name = t ! \
            queue ! decodebin name=dbin t. ! \
            queue ! filesink location=%s' % (factory, tmpfile)

        if options.timeout:
            gobject.timeout_add(int(options.timeout) * 1000, self.timedOut)
        self.mainloop = gobject.MainLoop()
        self.pipeline = gst.parse_launch(PIPELINE)
        self.input = self.pipeline.get_by_name('input')
        self.input.props.location = uri
        self.dbin = self.pipeline.get_by_name('dbin')
        self.bus = self.pipeline.get_bus()
        self.bus.add_watch(self.onBusMessage)
        self.dbin.connect('new-decoded-pad', self.demux_pad_added)

    def run(self):
        self.pipeline.set_state(gst.STATE_PLAYING)

        self.mainloop.run()
        return self.have_audio, self.have_video, self.info, self.error

    def launch_eos(self):
        if self.have_audio and self.have_video:
            if self.audio_done and self.video_done:
                self.bus.post(gst.message_new_eos(self.pipeline))
        else:
            if self.audio_done or self.video_done:
                self.bus.post(gst.message_new_eos(self.pipeline))

    def get_audio_info_cb(self, sink, buffer, pad):
        '''Callback to get audio info'''
        timestamp = buffer.timestamp / gst.SECOND
        if not self.audio_ts:
            self.audio_ts = timestamp
        if (self.audio_ts + TIMEOUT) < timestamp:
            # get audio info
            caps = sink.sink_pads().next().get_negotiated_caps()
            for s in caps:
                for i in s.keys():
                    self.info['audio_%s' % i] = s[i]
            self.audio.disconnect(self.audio_cb)
            self.audio_done = True
            self.launch_eos()

    def get_video_info_cb(self, sink, buffer, pad):
        '''Callback to get video info'''
        timestamp = buffer.timestamp / gst.SECOND
        if not self.video_ts:
            self.video_ts = timestamp
        if (self.video_ts + TIMEOUT) < timestamp:
            # get video info
            caps = sink.sink_pads().next().get_negotiated_caps()
            for s in caps:
                for i in s.keys():
                    if i in ('pixel-aspect-ratio', 'framerate'):
                        self.info['video_%s' % i] = '%d/%d' % \
                        (s[i].num, s[i].denom)
                    elif i == 'format':
                        self.info['video_%s' % i] = s[i].fourcc
                    else:
                        self.info['video_%s' % i] = s[i]
            self.video.disconnect(self.video_cb)
            self.video_done = True
            self.launch_eos()

    def get_mime(self):
        '''Inspect source pads from decodebin to get mime info'''
        mime = None
        for e in self.dbin:
            # only check demuxer source pad
            if "Demuxer" in e.get_factory().get_klass():
                for pad in e.src_pads():
                    caps = pad.get_caps()
                    mime = caps[0].get_name()
                    if "audio" in mime:
                        self.info['audio_mime'] = mime
                    elif "video" in mime:
                        self.info['video_mime'] = mime
        # if audio only then there won't be a demuxer sometimes
        if not mime:
            for e in self.dbin:
                # check decoder sink pad
                if "Decoder" in e.get_factory().get_klass():
                    for pad in e.sink_pads():
                        caps = pad.get_caps()
                        mime = caps[0].get_name()
                        if "audio" in mime:
                            self.info["audio_mime"] = mime
                        elif "video" in mime:
                            self.info["video_mime"] = mime

        if not mime: # unknown
            if self.have_audio:
                self.info['audio_mime'] = "Unknown"
            if self.have_video:
                self.info['video_mime'] = "Unknown"

    def demux_pad_added(self, element, pad, bool):
        '''Add fake sink to get demux info'''
        caps = pad.get_caps()
        structure = caps[0]
        stream_type = structure.get_name()
        if stream_type.startswith('video'):
            self.have_video = True
            colorspace = gst.element_factory_make('ffmpegcolorspace')
            self.pipeline.add(colorspace)
            colorspace.set_state(gst.STATE_PLAYING)
            pad.link(colorspace.get_pad('sink'))
            self.video = gst.element_factory_make('fakesink')
            self.video.props.signal_handoffs = True
            self.pipeline.add(self.video)
            self.video.set_state(gst.STATE_PLAYING)
            colorspace.link(self.video)
            self.video_cb = self.video.connect('handoff',
                self.get_video_info_cb)
        elif stream_type.startswith('audio'):
            self.have_audio = True
            self.audio = gst.element_factory_make('fakesink')
            self.audio.props.signal_handoffs = True
            self.pipeline.add(self.audio)
            self.audio.set_state(gst.STATE_PLAYING)
            pad.link(self.audio.get_pad('sink'))
            self.audio_cb = self.audio.connect('handoff',
                self.get_audio_info_cb)

    def quit(self):
        self.get_mime()
        self.pipeline.set_state(gst.STATE_NULL)
        self.pipeline.get_state()
        self.mainloop.quit()

    def onBusMessage(self, bus, message):
        if message.src == self.pipeline and message.type == gst.MESSAGE_EOS:
            self.quit()
        elif message.type == gst.MESSAGE_ERROR:
            self.error = message.parse_error()
            self.mainloop.quit()
        return True

    def timedOut(self):
        """End of time to do the check"""
        self.mainloop.quit()
