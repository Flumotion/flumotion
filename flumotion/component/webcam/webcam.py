# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/webcam/webcam.py: webcam producer
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

class WebCamera(feedcomponent.ParseLaunchComponent):
    def __init__(self, name, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    [],
                                                    ['default'],
                                                    pipeline)
                                       
def createComponent(config):
    component = WebCamera(config['name'], 'v4lsrc name=camera copy-mode=1')

    # XXX: Width and height through filtered caps.
    #element.set_property('width', config['width'])
    #element.set_property('height', config['height'])

    return component
