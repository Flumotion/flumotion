# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# producer.py: producer base class
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

# FIXME: move out of manager
from flumotion.manager import component

__all__ = ['Producer']

class Producer(component.ParseLaunchComponent):
    logCategory = 'prod-pipe'
    def __init__(self, name, feeders, pipeline):
        component.ParseLaunchComponent.__init__(self, name, [],
                                                feeders, pipeline)

def createComponent(config):
    name = config['name']
    feeders = config.get('feed', ['default'])
    pipeline = config['pipeline']

    return Producer(name, feeders, pipeline)

    
