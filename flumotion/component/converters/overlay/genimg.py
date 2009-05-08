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
TEXT_XOFFSET = 6
TEXT_YOFFSET = 6
WIDTH = 36
BORDER = 4
FONT_SIZE = 22


def generateOverlay(text,
                    showFlumotion,
                    showCC,
                    showXiph,
                    width, height):
    """Generate an transparent image with text + logotypes rendered on top
    of it suitable for mixing into a video stream
    @param text: text to put in the top left corner
    @type text: str
    @param showFlumotion: if we should show the flumotion logo
    @type showFlumotion: bool
    @param showCC: if we should show the Creative Common logo
    @type showCC: bool
    @param showXiph: if we should show the xiph logo
    @type showXiph: bool
    @param width: width of the image to generate
    @type width: int
    @param height: height of the image to generate
    @type height: int
    @returns: raw image and if images or if text overflowed
    @rtype: 3 sized tuple of string and 2 booleans
    """
    from PIL import Image
    from PIL import ImageDraw
    from PIL import ImageFont

    image = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(image) # inheriting color mode

    subImages = []
    if showXiph:
        subImages.append(os.path.join(logopath, 'xiph.36x36.png'))
    if showCC:
        subImages.append(os.path.join(logopath, 'cc.36x36.png'))
    if showFlumotion:
        subImages.append(os.path.join(logopath, 'fluendo.36x36.png'))

    imagesOverflowed = False

    offsetX = BORDER
    for subPath in subImages:
        sub = Image.open(subPath)
        subX, subY = sub.size
        offsetY = height - subY - BORDER
        image.paste(sub, (offsetX, offsetY), sub)
        if (offsetX + subX) > width:
            imagesOverflowed = True
        offsetX += subX + BORDER

    textOverflowed = False
    if text:
        font = ImageFont.truetype(fontpath, FONT_SIZE)
        draw.text((TEXT_XOFFSET+2, TEXT_YOFFSET+2),
                  text, font=font, fill='black')
        draw.text((TEXT_XOFFSET, TEXT_YOFFSET),
                  text, font=font)
        textWidth = draw.textsize(text, font=font)[0] + TEXT_XOFFSET
        if textWidth > width:
            textOverflowed = True

    buf = image.tostring()

    return buf, imagesOverflowed, textOverflowed

if __name__ == '__main__':
    print generateOverlay('Testing', True, True, True, 128, 196)[0]
