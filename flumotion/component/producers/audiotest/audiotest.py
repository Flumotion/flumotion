# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/producers/audiotest/audiotest.py
# a test audio producer
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from flumotion.component import feedcomponent

class AudioTest(feedcomponent.ParseLaunchComponent):
    def __init__(self, name, pipeline):
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    [],
                                                    ['default'],
                                                    pipeline)

def createComponent(config):
    rate = config.get('rate', 8000)
    volume = config.get('volume', 1.0)

    component = AudioTest(config['name'],
        'sinesrc name=source sync=1 ! audio/x-raw-int,rate=%d ! volume volume=%f' % (rate, volume))
    element = component.get_element('source')
    if config.has_key('freq'):
        element.set_property('freq', config['freq'])
        
    return component

