# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/converters/overlay/overlay.py: overlay converter
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
from flumotion.component.converters.overlay import genimg

import tempfile

FILENAME = tempfile.mktemp('flumotion.png')

class Overlay(feedcomponent.ParseLaunchComponent):
    def __init__(self, name, eaters, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    eaters,
                                                    ['default'],
                                                    pipeline)


def createComponent(config):
    source = config['source']

    eater = '@ eater:%s @' % source
    component = Overlay(config['name'], [source],
                        "filesrc name=source blocksize=100000 ! " + \
                        "pngdec ! alphacolor ! videomixer name=mix ! @ feeder:: @ " + \
                        "%s ! ffmpegcolorspace ! alpha ! mix." % eater)
    

    text = config.get('text', None)

    genimg.generate_overlay(FILENAME, text,
                            config.get('fluendo_logo', False),
                            config.get('cc_logo', False),
                            config.get('xiph_logo', False),
                            config['width'], config['height'])
    
    source = component.get_element('source')
    source.set_property('location', FILENAME)
    
    return component

