# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# worker/worker.py: client-side objects to handle launching of components
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

from twisted.internet import reactor
from twisted.spread import pb

from flumotion.common import interfaces
from flumotion.common.config import ConfigEntry
from flumotion.common.registry import registry
from flumotion.twisted import pbutil
from flumotion.utils import log
from flumotion.worker import launcher

class WorkerFactory(pbutil.ReconnectingPBClientFactory):
    __super_login = pbutil.ReconnectingPBClientFactory.startLogin
    def __init__(self, view):
        self.view = view
        # doing this as a class method triggers a doc error
        pbutil.ReconnectingPBClientFactory.__init__(self)
        
    def login(self, username):
        self.__super_login(pbutil.Username(username),
                           self.view,
                           interfaces.IWorkerComponent)
        
    def gotPerspective(self, perspective):
        self.view.cb_gotPerspective(perspective)

class WorkerView(pb.Referenceable, log.Loggable):
    logCategory = 'worker-view'
    def __init__(self, host, port):
        self.launcher = launcher.Launcher(host, port)
        
    def cb_gotPerspective(self, perspective):
        self.info('got perspective: %s' % perspective)

    def remote_start(self, name, type, config):
        self.info('start called')
        defs = registry.getComponent(type)
        entry = ConfigEntry(name, type, config, defs)

        self.launcher.launch_component(entry)

    def run(self, factory):
        self.launcher.run(factory)

def main(args):
    parser = optparse.OptionParser()
    parser.add_option('', '--run',
                     action="store", type="string", dest="run",
                     default='',
                     help="Run component")
    parser.add_option('', '--parent-fd',
                     action="store", type="int", dest="parent_fd",
                     fdefault='',
                     help="Fd of parent")
    
    options, args = parser.parse_args(args)

    if options.run:
        launcher.run(options.run, options.parent_fd)
        reactor.run()
    else:
        host = 'localhost'
        port = 8890

        view = WorkerView(host, port)
        factory = WorkerFactory(view)
        factory.login('Foobar')

        view.run(factory)
    
