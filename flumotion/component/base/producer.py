# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/base/producer.py: base Producer class
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

__all__ = ['Producer']

class Producer(feedcomponent.ParseLaunchComponent):
    logCategory = 'prod-pipe'
    def __init__(self, name, feeders, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name, [],
                                                feeders, pipeline)

def createComponent(config):
    name = config['name']
    feeders = config.get('feed', ['default'])
    pipeline = config['pipeline']

    return Producer(name, feeders, pipeline)

    
