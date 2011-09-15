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


# IMPORTANT NOTE
# This module defines a pyhon implementation of the gstreamer hlssink element,
# which was not yet upstream the day it was released. It will also be used in
# cases where this element is missing too.


class Fragment(gobject.GObject):
    '''
    I am a Python implementation of the GstFragment
    '''
    index = 0
    name = 'fragment'
    duration = 0
    buf = None

    __gproperties__ = {
        'buffer': (gobject.TYPE_PYOBJECT,
            'Buffer', 'GstBuffer with the data of the fragment',
            gobject.PARAM_READABLE),
        'index': (gobject.TYPE_UINT, 'Index', 'Index of the fragment',
            0, gobject.G_MAXUINT, 0, gobject.PARAM_READABLE),
        'name': (gobject.TYPE_STRING, 'Name', 'Name of the fragment',
            'fragment', gobject.PARAM_READABLE),
        'duration': (gobject.TYPE_UINT64, 'duration',
            'Duration of the fragment in ns',
            0, gst.CLOCK_TIME_NONE, 0, gobject.PARAM_READABLE)}

    def __init__(self, index, buf):
        gobject.GObject.__init__(self)
        self.index = index
        self.name = "fragment-%s" % index
        self.duration = buf.duration
        self.buf = buf

    def do_get_property(self, prop):
        if prop.name == "name":
            return self.name
        if prop.name == "index":
            return self.index
        if prop.name == "duration":
            return self.duration
        if prop.name == "buffer":
            return self.buf
        else:
            raise AttributeError('unknown property %s' % property.name)


class HLSSink(gst.Element):
    '''
    I am a python implementation the gstreamer hlssink element.
    '''

    __gstdetails__ = ('HLSSink', 'Sink',
                      'Sink for HTTP Live Streaming',
                      'Flumotion Dev Team')

    __gsignals__ = {"new-fragment": (gobject.SIGNAL_RUN_LAST,
                                     gobject.TYPE_NONE, []),
                    "eos": (gobject.SIGNAL_RUN_LAST,
                            gobject.TYPE_NONE, []),
                    "pull-fragment": (gobject.SIGNAL_RUN_LAST |
                                      gobject.SIGNAL_ACTION,
                                      gobject.TYPE_OBJECT, [])}

    __gproperties__ = {
        'fragment': (gobject.TYPE_OBJECT,
            'fragment', 'last gstfragment',
            gobject.PARAM_READABLE),
        'sync': (gobject.TYPE_BOOLEAN,
            'sync', 'sync', False,
            gobject.PARAM_WRITABLE),
        'playlist-max-window': (gobject.TYPE_INT,
            'playlist max window', 'playlist max window',
            0, gobject.G_MAXINT, 0, gobject.PARAM_WRITABLE),
        'write-to-disk': (gobject.TYPE_BOOLEAN,
            'Write to disk', 'Write to disk', False,
            gobject.PARAM_WRITABLE)}

    _sinkpadtemplate = gst.PadTemplate("sink",
                                       gst.PAD_SINK,
                                       gst.PAD_ALWAYS,
                                       gst.caps_from_string("video/mpegts; "
                                                            "video/webm"))

    def __init__(self):
        gst.Element.__init__(self)

        self._reset_fragment()
        self._last_fragment = None

        self.sinkpad = gst.Pad(self._sinkpadtemplate, "sink")
        self.sinkpad.set_chain_function(self.chainfunc)
        self.sinkpad.set_event_function(self.eventfunc)
        self.add_pad(self.sinkpad)

    def chainfunc(self, pad, buf):
        if buf.flag_is_set(gst.BUFFER_FLAG_IN_CAPS):
            self._in_caps = True
            return gst.FLOW_OK

        if buf.timestamp != gst.CLOCK_TIME_NONE and \
                self._first_ts == gst.CLOCK_TIME_NONE:
            self._first_ts = buf.timestamp
        self._fragment.append(buf)
        return gst.FLOW_OK

    def eventfunc(self, pad, event):
        s = event.get_structure()
        if event.type != gst.EVENT_CUSTOM_DOWNSTREAM or \
                s.get_name() != 'GstForceKeyUnit':
            return True

        # Ignore the first GstForceKeyUnit event
        if len(self._fragment) == 0:
            return True

        self._finish_fragment(s['timestamp'], s['count'])
        return True

    def do_get_property(self, prop):
        if prop.name == "fragment":
            return self._last_fragment

    def do_set_property(self, prop, value):
        # Properties ignored, only added to replicate the ones
        # of the original sink
        pass

    def _reset_fragment(self):
        self._fragment = []
        self._in_caps = False
        self._first_ts = gst.CLOCK_TIME_NONE

    def _finish_fragment(self, timestamp, index):
        # Write streamheaders at the beginning of each fragment
        s = self.sinkpad.get_negotiated_caps()[0]
        frag = []
        if s.has_field('streamheader'):
            frag = list(s['streamheader'])
        frag.extend(self._fragment)

        # Create the GstBuffer
        data = ''.join([b.data for b in frag])
        buf = gst.Buffer(data)
        buf.timestamp = self._first_ts
        if buf.timestamp != gst.CLOCK_TIME_NONE:
            buf.duration = timestamp - buf.timestamp
        if self._in_caps:
            buf.flag_set(gst.BUFFER_FLAG_IN_CAPS)

        # Create the GstFragment and emit the new-fragment signal
        self._last_fragment = Fragment(index, buf)
        self.emit('new-fragment')
        self._reset_fragment()


def register():
    gobject.type_register(HLSSink)
    gst.element_register(HLSSink, 'hlssink', gst.RANK_MARGINAL)
