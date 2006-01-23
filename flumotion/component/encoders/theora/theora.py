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

from flumotion.component import feedcomponent

class Theora(feedcomponent.ParseLaunchComponent):
    def get_pipeline_string(self, properties):
        return "ffmpegcolorspace ! theoraenc name=encoder"

    def configure_pipeline(self, pipeline, properties):
        element = pipeline.get_by_name('encoder')

        props = ('bitrate',
                 'quality',
                 'keyframe-threshold',
                 'keyframe-mindistance', 
                 ('quick-compress', 'quick'),
                 ('keyframe-maxdistance', 'keyframe-freq'),
                 ('keyframe-maxdistance', 'keyframe-force'),
                 'noise-sensitivity')

        for p in props:
            pproperty = isinstance(p, tuple) and p[0] or p
            eproperty = isinstance(p, tuple) and p[1] or p

            if pproperty in properties:
                element.set_property(eproperty, properties[pproperty])
