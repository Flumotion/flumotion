# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/videotest/videotest.py: videotest producer
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

from flumotion.component.base import producer

def createComponent(config):
    pipeline = 'videotestsrc ! video/x-raw-yuv,format=(fourcc)I420'

    if config.has_key('width'):
        pipeline += ',width=%d' % config['width']
    if config.has_key('height'):
        pipeline += ',height=%d' % config['height']
    if config.has_key('framerate'):
        pipeline += ',framerate=%f' % config['framerate']

    config['pipeline'] = pipeline
    
    return producer.createComponent(config)


