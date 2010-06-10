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
import cairo
import pango
import pangocairo

__version__ = "$Rev$"
directory = os.path.split(os.path.abspath(__file__))[0]
logopath = directory
FONT = 'sans'
FONT_PROPS = 'normal 22'
TEXT_XOFFSET = 6
TEXT_YOFFSET = 6
BORDER = 4
FONT_SIZE = 22528


def generateOverlay(text,
                    font,
                    showFlumotion,
                    showCC,
                    showXiph,
                    width, height):
    """Generate an transparent image with text + logotypes rendered on top
    of it suitable for mixing into a video stream
    @param text: text to put in the top left corner
    @type text: str
    @param font: font description used to render the text
    @type: str
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
    from cairo import ImageSurface
    from cairo import Context

    image = ImageSurface(cairo.FORMAT_ARGB32, width, height)
    context = Context(image)

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
        sub = ImageSurface.create_from_png(subPath)
        subX = sub.get_width()
        subY = sub.get_height()
        offsetY = height - subY - BORDER
        context.set_source_surface(sub, offsetX, offsetY)
        context.paint()
        if (offsetX + subX) > width:
            imagesOverflowed = True
        offsetX += subX + BORDER

    textOverflowed = False
    if text:
        pcContext = pangocairo.CairoContext(context)
        pangoLayout = pcContext.create_layout()
        if font is not None:
            font = pango.FontDescription(font)
            if not font.get_family() or \
               not font.get_family().lower() in [family.get_name().lower()
                    for family in pangoLayout.get_context().list_families()]:
                font.set_family(FONT)
            if font.get_size() == 0:
                font.set_size(FONT_SIZE)
        else:
            font = pango.FontDescription('%s %s' % (FONT, FONT_PROPS))
        pangoLayout.set_font_description(font)

        context.move_to(TEXT_XOFFSET+2, TEXT_YOFFSET+2)
        pangoLayout.set_markup('<span foreground="black" >%s</span>' % text)
        pcContext.show_layout(pangoLayout)
        context.move_to(TEXT_XOFFSET, TEXT_YOFFSET)
        pangoLayout.set_markup('<span foreground="white" >%s</span>' % text)
        pcContext.show_layout(pangoLayout)

        textWidth, textHeight = pangoLayout.get_pixel_size()
        if textWidth > width:
            textOverflowed = True

    if cairo.version < '1.2.6':
        buf = image.get_data_as_rgba()
    else:
        buf = image.get_data()

    return buf, imagesOverflowed, textOverflowed

if __name__ == '__main__':
    print generateOverlay('Testing', 'sans normal 22',
            True, True, True, 128, 196)[0]
