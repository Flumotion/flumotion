# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/producers/dv/dv.py: firewire producer
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

from flumotion.component import producer

def createComponent(config):
    width = config.get('width', 720)
    height = config.get('height', 576)
    dropfactor = config.get('drop-factor', 1)
    
    pipeline = ('dv1394src ! dvdec drop-factor=%d ! '
                'videoscale ! video/x-raw-yuv,width=%d,height=%d') % (
        drop_factor, width, height)
    
    config['pipeline'] = pipeline
    
    return producer.createComponent(config)


