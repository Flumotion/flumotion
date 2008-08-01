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


import pygst
pygst.require('0.10')
import gst

import gobject
gobject.threads_init()


def make_pipeline():
    s = ('audiotestsrc num-buffers=1000 ! audio/x-raw-int,channels=1,rate=8000'
         ' ! audioresample name=ar ! audioconvert ! capsfilter name=cf'
         ' ! vorbisenc name=enc ! oggmux ! filesink location=foo.ogg')

    return gst.parse_launch(s)

handle = None


def buffer_probe(pad, buffer, cf):
    # this comes from another thread
    caps = buffer.get_caps()
    in_rate = caps[0]['rate']

    print 'hey'

    caps_str = 'audio/x-raw-float, rate=%d' % in_rate
    cf.set_property('caps',
                    gst.caps_from_string(caps_str))
    pad.remove_buffer_probe(handle)
    return True


def setup_pipeline():
    global handle

    p = make_pipeline()

    enc = p.get_by_name('enc')
    cf = p.get_by_name('cf')
    ar = p.get_by_name('ar')

    enc.set_property('quality', 0.6)

    pad = ar.get_pad('sink')

    handle = pad.add_buffer_probe(buffer_probe, cf)

    return p

if __name__ == '__main__':
    p = setup_pipeline()

    p.set_state(gst.STATE_PLAYING)

    p.get_bus().poll(gst.MESSAGE_EOS, -1)
