# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/multipartjpeg/multipartjpeg.py: multipartjpeg converter
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
    # Since source in converter is a list, convert it to one
    config['source'] = [config['source']]
    
    # Set pipeline from the template
    config['pipeline'] = 'ffmpegcolorspace ! jpegenc name=jpegenc ! multipartmux'

    component = converter.createComponent(config)
    pipeline = component.get_pipeline()
    if config.has_key('quality'):
        jpeg = pipeline.get_by_name('jpegenc')
        jpeg.set_property('quality', int(config['quality']))
    return component


