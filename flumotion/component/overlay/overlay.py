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

from flumotion.component.base import converter

def createComponent(config):
    source = config['source']
    location = config['location']
    
    # Since source in converter is a list, convert it to one
    config['source'] = [source]

    # Set pipeline from the template
    pipeline = "filesrc location=%s blocksize=100000 !" % location + \
               "pngdec ! alphacolor ! videomixer name=mix ! :default " + \
               "@%s ! ffmpegcolorspace ! alpha ! mix." % source
    config['pipeline'] = pipeline

    return converter.createComponent(config)
