# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/overlay/overlay.py: overlay converter
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

import os

from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw

directory = os.path.split(os.path.abspath(__file__))[0]
fontpath = os.path.join(directory, 'Vera.ttf')
logopath = directory

fluendoLogoPath = os.path.join(logopath, 'fluendo_24x24.png')
ccLogoPath = os.path.join(logopath, 'cc_24x24.png')
xiphLogoPath = os.path.join(logopath, 'xiph_24x24.png')

FILENAME = '/tmp/flumotion-overlay.png'

class Overlay(feedcomponent.ParseLaunchComponent):
    def __init__(self, name, eaters, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    eaters,
                                                    ['default'],
                                                    pipeline)


def generate_overlay(text, logo, width, height, size=22, x=4, y=4):
    image = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(image)

    if logo:
        print 'JOHAN: fix colors'
        fluendo = Image.open(fluendoLogoPath)
        cc = Image.open(ccLogoPath)
        xiph = Image.open(xiphLogoPath)
        draw.bitmap((width-24, height-24), fluendo)
        draw.bitmap((width-48, height-24), cc)
        draw.bitmap((width-72, height-24), xiph)
        
    if text:
        font = ImageFont.truetype(fontpath, size)
        draw.text((x+2, y+2), text, font=font, fill='black')
        draw.text((x, y), text, font=font)

    if os.path.exists(FILENAME):
        os.unlink(FILENAME)
        
    image.save(FILENAME)

def createComponent(config):
    source = config['source']

    eater = '@ eater:%s @' % source
    component = Overlay(config['name'], [source],
                        "filesrc name=source blocksize=100000 ! " + \
                        "pngdec ! alphacolor ! videomixer name=mix ! @ feeder:: @ " + \
                        "%s ! ffmpegcolorspace ! alpha ! mix." % eater)
    

    text = config.get('text', None)
    logo = config.get('logo', None)
    
    generate_overlay(text, logo, config['width'], config['height'])
    
    source = component.get_element('source')
    source.set_property('location', FILENAME)
    
    return component
