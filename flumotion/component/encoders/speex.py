# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/theora/theora.py: theora converter
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

class Speex(feedcomponent.ParseLaunchComponent):
    def __init__(self, name, feeders, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    ['default'],
                                                    feeders,
                                                    pipeline)

def createComponent(config):
    source = config['source']

    component = Speex(config['name'], [config['source']],
                       "speexenc name=encoder")
    
    element = component.pipeline.get_by_name('encoder')
    if config.has_key('bitrate'):
        element.set_property('bitrate', config['bitrate'])

    return component
