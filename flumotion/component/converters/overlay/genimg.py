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

import os

__version__ = "$Rev$"

directory = os.path.split(os.path.abspath(__file__))[0]
fontpath = os.path.join(directory, 'Vera.ttf')
logopath = directory

fluendoLogoPath = os.path.join(logopath, 'fluendo.36x36.png')
ccLogoPath = os.path.join(logopath, 'cc.36x36.png')
xiphLogoPath = os.path.join(logopath, 'xiph.36x36.png')

TEXT_XOFFSET = 6
TEXT_YOFFSET = 6
WIDTH = 36
BORDER = 8
FONT_SIZE = 22


def generate_overlay(filename, text, show_fluendo, show_cc, show_xiph,
                     width, height):
    from PIL import Image
    from PIL import ImageChops
    from PIL import ImageDraw
    from PIL import ImageFont
    from PIL import ImageOps

    image = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(image) # inheriting color mode

    if text:
        font = ImageFont.truetype(fontpath, FONT_SIZE)
        draw.text((TEXT_XOFFSET+2, TEXT_YOFFSET+2),
                  text, font=font, fill='black')
        draw.text((TEXT_XOFFSET, TEXT_YOFFSET),
                  text, font=font)

    # How many logos we're going to show
    logos = len([i for i in (show_fluendo, show_cc, show_xiph) if i]) - 1

    # This is really *NOT* the optimal way of doing this.
    # We should really find out a better way of adding an image on
    # another image (with an offset)

    imax = max(width, height)
    y_corr = -(abs(width - height) + WIDTH + BORDER)

    if show_xiph:
        xiph = Image.open(xiphLogoPath)
        xiph = ImageOps.expand(xiph, imax)
        xiph = ImageChops.offset(xiph, -width + (WIDTH*logos), y_corr)
        image = ImageChops.add_modulo(image, xiph)
        logos -= 1

    if show_cc:
        cc = Image.open(ccLogoPath)
        cc = ImageOps.expand(cc, imax)
        cc = ImageChops.offset(cc, -width + (WIDTH*logos), y_corr)
        image = ImageChops.add_modulo(image, cc)
        logos -= 1

    if show_fluendo:
        fluendo = Image.open(fluendoLogoPath)
        fluendo = ImageOps.expand(fluendo, imax)
        fluendo = ImageChops.offset(fluendo, -width, y_corr)
        image = ImageChops.add_modulo(image, fluendo)

    if os.path.exists(filename):
        os.unlink(filename)

    image.save(filename, 'png')

    if text:
        return (draw.textsize(text, font=font)[0] + TEXT_XOFFSET > width)
    else:
        return False

if __name__ == '__main__':
    #generate_overlay('test.png', 'Testing', True, True, True, 320, 240)
    generate_overlay('test.png', 'Testing', True, True, True, 320, 240)
