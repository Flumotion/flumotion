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
import os
import sys

from twisted.internet import reactor

from flumotion.manager import manager
from flumotion.common import log, config, common
from flumotion.configure import configure

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

def _startSSL(vishnu, host, port, pemFile):
    # if no path in pemFile, then look for it in the config directory
    if not os.path.split(pemFile)[0]:
        pemFile = os.path.join(configure.configdir, 'managers', 'default', pemFile)
    if not os.path.exists(pemFile):
        log.error('manager', ".pem file %s does not exist" % pemFile)
    log.debug('manager', 'Using PEM certificate file %s' % pemFile)
    ctxFactory = ServerContextFactory(pemFile)
    
    log.info('manager', 'Starting on port %d using SSL' % port)
    reactor.listenSSL(port, vishnu.getFactory(), ctxFactory, interface=host)
    reactor.run()

def _startTCP(vishnu, host, port):
    log.info('manager', 'Starting on port %d using TCP' % port)
    reactor.listenTCP(port, vishnu.getFactory(), interface=host)
    reactor.run()

def _loadConfig(vishnu, filename):
    # FIXME: this might be used for loading additional config, so maybe
    # unprivatize and cleanup ?

    # scan filename for a bouncer component in the manager

    conf = config.FlumotionConfigXML(filename)

    if conf.manager and conf.manager.bouncer:
        if vishnu.bouncer:
            vishnu.warning("manager already had a bouncer")

        vishnu.debug('going to start manager bouncer %s of type %s' % (
            conf.manager.bouncer.name, conf.manager.bouncer.type))
        from flumotion.common.registry import registry
        defs = registry.getComponent(conf.manager.bouncer.type)
        configDict = conf.manager.bouncer.getConfigDict()
        import flumotion.worker.job
        vishnu.setBouncer(flumotion.worker.job.getComponent(configDict, defs))
        vishnu.bouncer.debug('started')

    # make the workerheaven load the config
    vishnu.workerHeaven.loadConfiguration(filename)


def _initialLoadConfig(vishnu, paths):
    # this is used with a callLater for the initial config loading
    for path in paths:
        log.debug('manager', 'Loading configuration file from (%s)' % path)
        try:
            _loadConfig(vishnu, path)
        except config.ConfigError, reason:
            sys.stderr.write("ERROR: failed to load planet configuration '%s':\n" % path)
            sys.stderr.write("%s\n" % reason)
            # bypass reactor, because sys.exit gets trapped
            os._exit(-1)
    
def main(args):
    # XXX: gst_init should remove all options, like gtk_init
    args = [arg for arg in args if not arg.startswith('--gst')]
    
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="be verbose")
    parser.add_option('', '--version',
                      action="store_true", dest="version",
                      default=False,
                      help="show version information")
  
    group = optparse.OptionGroup(parser, "manager options")
    defaultSSLPort = configure.defaultSSLManagerPort
    defaultTCPPort = configure.defaultTCPManagerPort
    group.add_option('-H', '--hostname',
                     action="store", type="string", dest="host",
                     default="",
                     help="hostname to listen to [default ""]")
    group.add_option('-P', '--port',
                     action="store", type="int", dest="port",
                     default=None,
                     help="port to listen on [default %d (ssl) or %d (tcp)]" % (defaultSSLPort, defaultTCPPort))
    group.add_option('-T', '--transport',
                     action="store", type="string", dest="transport",
                     default="ssl",
                     help="transport protocol to use (tcp/ssl) [default ssl]")
    group.add_option('-C', '--certificate',
                     action="store", type="string", dest="certificate",
                     default="default.pem",
                     help="specify PEM certificate file (for SSL)")
    group.add_option('-D', '--daemonize',
                     action="store_true", dest="daemonize",
                     default=False,
                     help="run in background as a daemon")
    parser.add_option_group(group)
    
    log.debug('manager', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    if options.version:
        print common.version("flumotion-manager")
        return 0

    if len(args) <= 1:
        log.warning('manager', 'Please specify a planet configuration file')
        sys.stderr.write("Please specify a planet configuration file.\n")
        return -1

    vishnu = manager.Vishnu()

    paths = [os.path.abspath(filename) for filename in args[1:]]
    reactor.callLater(0, _initialLoadConfig, vishnu, paths)
    
    if options.verbose:
        log.setFluDebug("*:3")

    if options.daemonize:
        if not os.path.exists(configure.logdir):
            try:
                os.makedirs(configure.logdir)
            except:
                sys.stderr.write("Could not create log file directory %d.\n" % configure.logdir)
                return -1
                
        logPath = os.path.join(configure.logdir, 'manager.log')
        common.daemonize(stdout=logPath, stderr=logPath)

    if options.transport == "ssl":
        port = options.port or defaultSSLPort
        _startSSL(vishnu, options.host, port, options.certificate)
    elif options.transport == "tcp":
        port = options.port or defaultTCPPort
        _startTCP(vishnu, options.host, port)
    else:
        print >> sys.stderr, \
              'ERROR: unsupported transport: %s, must be ssl or tcp' % options.transport
        return 1
    return 0
