# -*- Mode: Python -*-
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
#

import time
import sys
    
import gobject
import gst

if __name__ == '__main__':
    import gstreactor
    gstreactor.install()

from twisted.web import server, resource
from twisted.internet import reactor

class SimpleResource(resource.Resource):
    def __init__(self):
        resource.Resource.__init__(self)
        self.data = open('/home/jdahlin/Pictures/johan2.jpg').read()
        self.data2 = open('/home/jdahlin/Pictures/johan_guadec.jpg').read()

    def getChild(self, path, request):
        return self

    def writeOne(self, request):
        request.write('--ThisRandomString\n')
        request.write("Content-type: image/jpeg\n\n")
        request.write(self.data + '\n')

    def writeTwo(self, request):
        request.write('--ThisRandomString\n')
        request.write("Content-type: image/jpeg\n\n")
        request.write(self.data2 + '\n')
    
    def render(self, request):
        request.setHeader("Content-type", "multipart/x-mixed-replace;;boundary=ThisRandomString")
        request.setHeader('Cache-Control', 'no-cache')
        request.setHeader('Cache-Control', 'private')
        request.setHeader('Pragma', 'no-cache')

        for i in range(20):
            reactor.callLater(0.250 + 0.250*i, self.writeOne, request)
            reactor.callLater(0.250*i, self.writeTwo, request)
        reactor.callLater(105*0.250, request.finish)
        
        return server.NOT_DONE_YET

if __name__ == '__main__':
    reactor.listenTCP(8804, server.Site(resource=SimpleResource()))
    print 'Listening on *:8804'
    reactor.run()
