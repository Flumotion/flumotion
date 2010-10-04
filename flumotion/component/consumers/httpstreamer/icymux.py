# -*- Mode: Python; test-case-name: flumotion.test.test_ts_segmenter -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2009,2010 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.
# flumotion-fragmented-streaming - Flumotion Advanced fragmented streaming

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

import gst
import gobject
import time


class IcyMux(gst.Element):
    '''
    I mux the metadata with title changes into audio stream.
    '''

    _DEFAULT_FRAMESIZE = 256
    _DEFAULT_NUMFRAMES = 16
    _MAX_INT = int(1 << 31 - 1)


    __gproperties__ = {
        'frame-size': (int,
            'size of the frame in bytes',
            'The size in bytes of the frame',
            1, _MAX_INT, _DEFAULT_FRAMESIZE,
            gobject.PARAM_READWRITE),
        'num-frames': (int,
            'number of frames per data block',
            'The number of frames per data block',
            1, _MAX_INT, _DEFAULT_NUMFRAMES,
            gobject.PARAM_READWRITE),
        'icy-metaint': (int,
            'number of bytes per data block',
            'The length of data block',
            1, _MAX_INT, _DEFAULT_FRAMESIZE * _DEFAULT_NUMFRAMES,
            gobject.PARAM_READABLE),
        'iradio-title': (str,
            'title of currently playing song',
            'Title of currently playing song',
             None, gobject.PARAM_READABLE),
        'iradio-timestamp': (int,
            'last title timestamp',
            'Epoch time of last title change',
            -_MAX_INT, _MAX_INT, -1, gobject.PARAM_READABLE)}

    __gsignals__ = {"broadcast-title": (gobject.SIGNAL_RUN_LAST,\
                                        gobject.TYPE_NONE, [])}

    __gstdetails__ = ('IcyMux', 'Codec/Muxer',
                      'Icy format muxer',
                      'Flumotion Dev Team')

    _sinkpadtemplate = gst.PadTemplate("sink",
                           gst.PAD_SINK,
                           gst.PAD_ALWAYS,
                           gst.caps_from_string("audio/mpeg;application/ogg"))

    _srcpadtemplate = gst.PadTemplate("src",
                          gst.PAD_SRC,
                          gst.PAD_ALWAYS,
                          gst.caps_from_string("application/x-icy, " +\
                                    "metadata-interval= (int)[0, MAX]"))

    def __init__(self):
        gst.Element.__init__(self)

        self.sinkpad = gst.Pad(self._sinkpadtemplate, "sink")
        self.sinkpad.set_chain_function(self.chainfunc)
        self.add_pad(self.sinkpad)
        self.sinkpad.add_event_probe(self._tag_event_cb)

        self.srcpad = gst.Pad(self._srcpadtemplate, "src")
        self.add_pad(self.srcpad)

        self._frameSize = self._DEFAULT_FRAMESIZE
        self._numFrames = self._DEFAULT_NUMFRAMES
        self._recountMetaint()

        self.connect('broadcast-title', self._broadcast_title_handler)

        self._reset()

    def _reset(self):
        self.adapter = gst.Adapter()
        self._frameCount = 0
        self._shouldOutputMetadata = False
        self._lastTitle = None
        self._lastTitleTimestamp = -1

    def _broadcast_title_handler(self, object):
        self.debug("Will broadcast title.")
        self._shouldOutputMetadata = True

    def _tag_event_cb(self, pad, event):
        self.debug("Received event %r" % event)
        if event.type == gst.EVENT_TAG:
            struc = event.get_structure()
            if 'title' in struc.keys():
                self._lastTitle = struc['title']
                self._lastTitleTimestamp = int(time.time())
                self.debug("Stored title: %r on timestamp %r" %\
                        (self._lastTitle, self._lastTitleTimestamp))
                self._shouldOutputMetadata = True
        return True

    def _recountMetaint(self):
        self._icyMetaint = self._frameSize * self._numFrames
        self.debug("Metaint recount: %d" % self._icyMetaint)

    def do_get_property(self, property):
        if property.name == "frame-size":
            return self._frameSize
        elif property.name == "num-frames":
            return self._numFrames
        elif property.name == "icy-metaint":
            return self._icyMetaint
        elif property.name == "iradio-title":
            return self._lastTitle
        elif property.name == 'iradio-timestamp':
            return self._lastTitleTimestamp
        else:
            raise AttributeError('unknown property %s' % property.name)

    def do_set_property(self, property, value):
        if property.name == "frame-size":
            self.debug("Setting frame-size to %s" % value)
            self._frameSize = int(value)
            self._recountMetaint()
        elif property.name == "num-frames":
            self.debug("Setting num-frames to %s" % value)
            self._numFrames = int(value)
            self._recountMetaint()
        elif property.name == "icy-metaint":
            raise AttributeError("readonly property %s" % property.name)
        else:
            raise AttributeError('unknown property %s' % property.name)

    def do_change_state(self, transition):
        if transition == gst.STATE_CHANGE_PAUSED_TO_READY:
            self._reset()
        return gst.Element.do_change_state(self, transition)

    def chainfunc(self, pad, buffer):
        self.adapter.push(buffer)
        while self.adapter.available() >= self._frameSize:
            frame = self.adapter.take_buffer(self._frameSize)
            self._setCapsAndFlags(frame)
            if self._frameCount == 0:
                #mark as key frame
                frame.flag_unset(gst.BUFFER_FLAG_DELTA_UNIT)
                self.log('marked as keyframe')

            self.srcpad.push(frame)
            self.log('Pushed frame of size %d' % frame.size)
            self._frameCount += 1

            if self._frameCount == self._numFrames:
                self.outputMetadata()
                self._frameCount = 0
        return gst.FLOW_OK

    def _getTitleForMetadata(self):
        if self._shouldOutputMetadata:
            self.info("Will output title: %r" % self._lastTitle)
            self._shouldOutputMetadata = False
            return self._lastTitle
        else:
            return None

    def outputMetadata(self):
        buf = MetadataBuffer(title=self._getTitleForMetadata())
        self._setCapsAndFlags(buf)
        self.srcpad.push(buf)
        self.log('Pushed metadata')

    def _setCapsAndFlags(self, buf):
        buf.set_caps(gst.caps_from_string("application/x-icy, " +\
               "metadata-interval=%d" % self._icyMetaint))
        buf.flag_set(gst.BUFFER_FLAG_DELTA_UNIT)


gst.element_register(IcyMux, "icymux")


class MetadataBuffer(gst.Buffer):

    def __init__(self, title=None):
        self.title = title

        payload = ""
        if title:
            title = title.encode("utf-8", "replace")
            payload = "StreamTitle='%s';" % title
            if not (len(payload) % 16 == 0):
                toAdd = 16 - (len(payload) % 16)
                payload = payload + "\0" * toAdd
        gst.Buffer.__init__(self, chr(len(payload) / 16) + payload)
