# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/manager/main.py: main function of manager
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

import optparse
import sys
import os

from twisted.internet import reactor

from flumotion.manager import manager
from flumotion.utils import log
import flumotion.config

class ServerContextFactory:
    def __init__(self, pemFile):
        self._pemFile = pemFile

    def getContext(self):
        """
        Create an SSL context.
        """
        from OpenSSL import SSL
        ctx = SSL.Context(SSL.SSLv23_METHOD)
        ctx.use_certificate_file(self._pemFile)
        ctx.use_privatekey_file(self._pemFile)
        return ctx

def _startSSL(vishnu, options):
    from twisted.internet import ssl

    pemFile = options.certificate
    # if no path in pemFile, then look for it in the config directory
    if not os.path.split(pemFile)[0]:
        pemFile = os.path.join(flumotion.config.configdir, 'manager', pemFile)
    if not os.path.exists(pemFile):
        log.error('manager', ".pem file %s does not exist" % pemFile)
    log.debug('manager', 'Using PEM certificate file %s' % pemFile)
    ctxFactory = ServerContextFactory(pemFile)
    
    log.info('manager', 'Starting on port %d using SSL' % options.port)
    reactor.listenSSL(options.port, vishnu.getFactory(), ctxFactory)
    reactor.run()

def _startTCP(vishnu, options):
    log.info('manager', 'Starting on port %d using TCP' % options.port)
    reactor.listenTCP(options.port, vishnu.getFactory())
    reactor.run()

def _loadConfig(vishnu, filename):
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
    group.add_option('-t', '--transport',
                     action="store", type="string", dest="transport",
                     default="ssl",
                     help="Transport protocol to use (tcp/ssl)")
    group.add_option('-C', '--certificate',
                     action="store", type="string", dest="certificate",
                     default="flumotion.pem",
                     help="specify PEM certificate file (for SSL)")
    parser.add_option_group(group)
    
    log.debug('manager', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    vishnu = manager.Vishnu()

    if len(args) <= 2:
        filename = args[1]
        log.debug('manager', 'Loading configuration file from (%s)' % filename)
        reactor.callLater(0, _loadConfig, vishnu, filename)
    
    if options.verbose:
        log.setFluDebug("*:4")

    if options.transport == "ssl":
        _startSSL(vishnu, options)
    elif options.transport == "tcp":
        _startTCP(vishnu, options)
    else:
        # FIXME
        raise
    return 0
