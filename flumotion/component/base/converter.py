# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/base/converter.py: base Converter class
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

from flumotion.component import component

__all__ = ['Converter']

class Converter(component.ParseLaunchComponent):
    logCategory = 'conv-pipe'

def createComponent(config):
    name = config['name']
    feeders = config.get('feed', ['default'])
    eaters = config.get('source', [])
    pipeline = config['pipeline']

    component = Converter(name, eaters, feeders, pipeline)

    return component
