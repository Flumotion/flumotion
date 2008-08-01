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

import gst

from flumotion.component import feedcomponent

__version__ = "$Rev$"


class Icecast(feedcomponent.ParseLaunchComponent):

    def get_pipeline_string(self, properties):
        return "gnomevfssrc name=src ! typefind name=tf"

    def configure_pipeline(self, pipeline, properties):
        # Later, when the typefind element has successfully found the type
        # of the data, we'll rebuild the pipeline.
        def have_caps(tf, prob, caps):
            capsname = caps[0].get_name()
            # We should add appropriate parsers for any given format here. For
            # some it's critical for this to work at all, for others
            # it's needed for timestamps (thus for things like
            # time-based burst-on-connect) Currently, we only handle ogg.
            parser = None
            if capsname == 'application/ogg':
                parser = gst.element_factory_make('oggparse')
            elif capsname == 'audio/mpeg':
                parser = gst.element_factory_make('mp3parse')

            if parser:
                parser.set_state(gst.STATE_PLAYING)
                pipeline.add(parser)
                # Relink - unlink typefind from the bits that follow it (the
                # gdp payloader), link in the parser, relink to the payloader.
                pad = tf.get_pad('src')
                peer = pad.get_peer()
                pad.unlink(peer)
                tf.link(parser)
                parser.link(peer.get_parent())

        src = pipeline.get_by_name('src')
        src.set_property('location', properties['url'])

        typefind = pipeline.get_by_name('tf')
        typefind.connect('have-type', have_caps)
