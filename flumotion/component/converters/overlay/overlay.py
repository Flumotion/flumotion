# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/converters/overlay/overlay.py: overlay converter
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

from flumotion.component import feedcomponent
from flumotion.component.overlay import genimg

FILENAME = '/tmp/flumotion-overlay.png'

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

