# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/manager/main.py: main function of manager
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

import optparse
import os
import sys

from twisted.internet import reactor, error

from flumotion.manager import manager
from flumotion.common import log, config, common, errors
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
    if not host == "":
        log.info('manager', 'Listening as host %s' % host)
    reactor.listenSSL(port, vishnu.getFactory(), ctxFactory, interface=host)

def _startTCP(vishnu, host, port):
    log.info('manager', 'Starting on port %d using TCP' % port)
    if not host == "":
        log.info('manager', 'Listening as host %s' % host)
    reactor.listenTCP(port, vishnu.getFactory(), interface=host)

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
        log.info('manager', 'Started manager bouncer')

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
        except errors.UnknownComponentError, reason:
            sys.stderr.write("ERROR: failed to load planet configuration '%s':\n" % path)
            sys.stderr.write("%s\n" % reason)
            # bypass reactor, because sys.exit gets trapped
            os._exit(-1)
     
def main(args):
    # XXX: gst_init should remove all options, like gtk_init
    args = [arg for arg in args if not arg.startswith('--gst')]
    
    parser = optparse.OptionParser()
    parser.add_option('-d', '--debug',
                      action="store", type="string", dest="debug",
                      help="set debug levels")
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
                     help="hostname to listen as")
    group.add_option('-P', '--port',
                     action="store", type="int", dest="port",
                     default=None,
                     help="port to listen on [default %d (ssl) or %d (tcp)]" % (defaultSSLPort, defaultTCPPort))
    group.add_option('-T', '--transport',
                     action="store", type="string", dest="transport",
                     help="transport protocol to use (tcp/ssl) [default ssl]")
    group.add_option('-C', '--certificate',
                     action="store", type="string", dest="certificate",
                     default="default.pem",
                     help="specify PEM certificate file (for SSL)")
    group.add_option('-n', '--name',
                     action="store", type="string", dest="name",
                     help="manager name")
    group.add_option('-D', '--daemonize',
                     action="store_true", dest="daemonize",
                     default=False,
                     help="run in background as a daemon")
    parser.add_option_group(group)
    
    log.debug('manager', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    # parse planet config file
    if len(args) <= 1:
        log.warning('manager', 'Please specify a planet configuration file')
        sys.stderr.write("Please specify a planet configuration file.\n")
        return -1

    planetFile = args[1]
    cfg = config.FlumotionConfigXML(planetFile)

    # now copy over stuff from config that is not set yet
    if not options.host and cfg.manager.host:
        options.host = cfg.manager.host
        log.debug('manager', 'Setting manager host to %s' % options.host)
    if not options.port and cfg.manager.port:
        options.port = cfg.manager.port
        log.debug('manager', 'Setting manager port to %s' % options.port)
    if not options.transport and cfg.manager.transport:
        options.transport = cfg.manager.transport
        log.debug('manager', 'Setting manager transport to %s' %
            options.transport)
    if not options.name and cfg.manager.name:
        options.name = cfg.manager.name
        log.debug('manager', 'Setting manager name to %s' % options.name)

    # set default values for all unset options
    if not options.host:
        options.host = "" # needed for bind to work
    if not options.transport:
        options.transport = 'ssl'
    if not options.port:
        if options.transport == "tcp":
            options.port = defaultTCPPort
        elif options.transport == "ssl":
            options.port = defaultSSLPort
    if not options.name:
        try:
            head, filename = os.path.split(planetFile)
            head, name = os.path.split(head)
            options.name = name
            log.debug('manager', 'Setting name to %s based on path' % name)
        except:
            options.name = 'default'
            log.debug('manager', 'Setting name to default')

    # check for wrong options/arguments
    if not options.transport in ['ssl', 'tcp']:
        sys.stderr.write('ERROR: wrong transport %s, must be ssl or tcp\n' %
            options.transport)
        return 1

    # handle options
    if options.version:
        print common.version("flumotion-manager")
        return 0

    if options.verbose:
        log.setFluDebug("*:3")

    if options.debug:
        log.setFluDebug(options.debug)

    vishnu = manager.Vishnu()

    paths = [os.path.abspath(filename) for filename in args[1:]]
    reactor.callLater(0, _initialLoadConfig, vishnu, paths)
    
    # set up server based on transport
    try:
        if options.transport == "ssl":
            _startSSL(vishnu, options.host, options.port, options.certificate)
        elif options.transport == "tcp":
            _startTCP(vishnu, options.host, options.port)
    except error.CannotListenError, (interface, port, e):
        # e is a socket.error()
        message = "Could not listen on port %d: %s" % (port, e.args[1])
        raise errors.SystemError, message

    log.info('manager', 'Starting manager "%s"' % options.name)
    if options.daemonize:
        common.ensureDir(configure.logdir, "log file")
        common.ensureDir(configure.rundir, "run file")
                
        if common.getPid('manager', options.name):
            raise errors.SystemError, \
                'A manager with name %s is already running' % options.name

        logPath = os.path.join(configure.logdir,
            'manager.%s.log' % options.name)

        # here we daemonize; so we also change our pid
        common.daemonize(stdout=logPath, stderr=logPath)
        log.info('manager', 'Started daemon')

        # from now on I should keep running, whatever happens
        log.debug('manager', 'writing pid file')
        common.writePidFile('manager', options.name)

    # go into the reactor main loop
    reactor.run()

    # we exited, so we're done
    if options.daemonize:
        log.debug('manager', 'deleting pid file')
        common.deletePidFile('manager', options.name)

    log.info('manager', 'Stopping manager "%s"' % options.name)

    return 0
