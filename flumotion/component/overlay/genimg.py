# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/overlay/genimg.py: overlay image generator
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

import os

from PIL import Image
from PIL import ImageChops
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageOps

directory = os.path.split(os.path.abspath(__file__))[0]
fontpath = os.path.join(directory, 'Vera.ttf')
logopath = directory

fluendoLogoPath = os.path.join(logopath, 'fluendo_24x24.png')
ccLogoPath = os.path.join(logopath, 'cc_24x24.png')
xiphLogoPath = os.path.join(logopath, 'xiph_24x24.png')

TEXT_XOFFSET = 4
TEXT_YOFFSET = 4
WIDTH = 24
BORDER = 4
FONT_SIZE = 22

def generate_overlay(filename, text, show_fluendo, show_cc, show_xiph,
                     width, height):
    image = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(image) # inheriting color mode

    font = ImageFont.truetype(fontpath, FONT_SIZE)
    draw.text((TEXT_XOFFSET+2, TEXT_YOFFSET+2),
              text, font=font, fill='black')
    draw.text((TEXT_XOFFSET, TEXT_YOFFSET),
              text, font=font)

    # How many logos we're going to show
    logos = len([i for i in (show_fluendo, show_cc, show_xiph) if i])

    # This is really *NOT* the optimal way of doing this.
    # We should really find out a better way of adding an image on
    # another image (with an offset)

    imax = max(width, height)
    y_corr = -(abs(width - height) + WIDTH + BORDER)

    if show_xiph:
        xiph = Image.open(xiphLogoPath)
        xiph = ImageOps.expand(xiph, imax)
        xiph = ImageChops.offset(xiph, logos * -(WIDTH + BORDER), y_corr)
        image = ImageChops.add_modulo(image, xiph)
        logos -= 1
        
    if show_cc:
        cc = Image.open(ccLogoPath)
        cc = ImageOps.expand(cc, imax)
        cc = ImageChops.offset(cc, logos * -(WIDTH + BORDER), y_corr)
        image = ImageChops.add_modulo(image, cc)
        logos -= 1

    if show_fluendo:
        fluendo = Image.open(fluendoLogoPath)
        fluendo = ImageOps.expand(fluendo, imax)
        fluendo = ImageChops.offset(fluendo, -(WIDTH + BORDER), y_corr)
        image = ImageChops.add_modulo(image, fluendo)

    if os.path.exists(filename):
        os.unlink(filename)
        
    image.save(filename, 'png')

if __name__ == '__main__':    
    generate_overlay('test.png', 'Testing', True, True, True, 320, 240)
