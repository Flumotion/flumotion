# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/muxers/ogg.py: ogg multiplexer
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

class Ogg(feedcomponent.ParseLaunchComponent):
    def __init__(self, name, sources, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    sources,
                                                    ['default'],
                                                    pipeline)

def createComponent(config):
    pipeline = 'oggmux name=muxer '
    for eater in config['sources']:
        pipeline += '{ @ eater:%s @ ! mux. } ' % name
        
    component = Ogg(config['name'], sources, pipeline)
    
    return component
