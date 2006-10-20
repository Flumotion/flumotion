# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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

import gst

from flumotion.component import feedcomponent

class Icecast(feedcomponent.ParseLaunchComponent):

    def get_pipeline_string(self, properties):
        return "gnomevfssrc name=src ! typefind name=tf"
        
    def configure_pipeline(self, pipeline, properties):
        # Later, when the typefind element has successfully found the type
        # of the data, we'll rebuild the pipeline.
        def have_caps(tf, prob, caps):
            capsname = caps[0].get_name()
            if capsname == 'application/ogg':

                oggparse = gst.element_factory_make('oggparse')
                oggparse.set_state(gst.STATE_PLAYING)
                pipeline.add(oggparse)
                # Relink...
                pad = tf.get_pad('src')
                peer = pad.get_peer()
                pad.unlink(peer)
                tf.link(oggparse)
                oggparse.link(peer.get_parent())

        src = pipeline.get_by_name('src')
        src.set_property('location',  properties['url'])

        typefind = pipeline.get_by_name('tf')
        typefind.connect('have-type', have_caps)

