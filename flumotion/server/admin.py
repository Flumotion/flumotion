# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

from twisted.spread import pb

from flumotion.twisted import pbutil

class ComponentView(pb.Copyable):
    def __init__(self, component):
        self.name = component.getName()
        self.state = component.state
        self.sources = component.getSources()
        self.feeds = component.getFeeds()
        self.options = component.options.dict

class RemoteComponentView(pb.RemoteCopy):
    def __repr__(self):
        return '<RemoteComponentView %s>' % self.name
pb.setUnjellyableForClass(ComponentView, RemoteComponentView)

class AdminPerspective(pbutil.NewCredPerspective):
    def __init__(self, controller):
        self.controller = controller

    def getClients(self):
        return map(ComponentView,
                   self.controller.components.values())
    
    def attached(self, mind):
        self.mind = mind

        self.mind.callRemote('initial', self.getClients())

    def perspective_hello(self):
        print 'hello from client'

class Admin(pb.Root):
    def __init__(self, controller):
        self.controller = controller

    def getPerspective(self):
        return AdminPerspective(self.controller)
    
