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
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.
 
import optparse
import sys

from twisted.internet import reactor

from flumotion.manager import manager
from flumotion.utils import log

def load_config(vishnu, filename):
    vishnu.workerheaven.loadConfiguration(filename)
    
def main(args):
    args = [arg for arg in args if not arg.startswith('--gst')]
    
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="Be verbose")
    group = optparse.OptionGroup(parser, "Manager options")
    group.add_option('-p', '--port',
                     action="store", type="int", dest="port",
                     default=8890,
                     help="Port to listen on [default 8890]")
    parser.add_option_group(group)
    
    log.debug('manager', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    vishnu = manager.Vishnu()

    if len(args) <= 2:
        filename = args[1]
        log.debug('manager', 'Loading configuration file from (%s)' % filename)
        reactor.callLater(0, load_config, vishnu, filename)
    
    if options.verbose:
        log.setFluDebug("*:4")

    log.debug('manager', 'Starting at port %d' % options.port)
    reactor.listenTCP(options.port, vishnu.getFactory())
    reactor.run()

    return 0
