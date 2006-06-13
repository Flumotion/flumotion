# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

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

"""
manager main function
"""

import optparse
import os
import sys
import traceback

from twisted.internet import reactor, error

from flumotion.manager import manager
from flumotion.common import log, config, common, errors, setup
from flumotion.configure import configure

class ServerContextFactory(log.Loggable):

    logCategory = "SSLServer"
    
    def __init__(self, pemFile):
        self._pemFile = pemFile

    def getContext(self):
        """
        Create an SSL context.
        """
        from OpenSSL import SSL
        ctx = SSL.Context(SSL.SSLv23_METHOD)
        try:
            ctx.use_certificate_file(self._pemFile)
            ctx.use_privatekey_file(self._pemFile)
        except SSL.Error, e:
            self.warning('SSL error: %r' % e.args)
            self.error('Could not open certificate %s' % self._pemFile)
        return ctx

def _startSSL(vishnu, host, port, pemFile):
    # if no path in pemFile, then look for it in the config directory
    if not os.path.split(pemFile)[0]:
        pemFile = os.path.join(configure.configdir, pemFile)
    if not os.path.exists(pemFile):
        log.error('manager', ".pem file %s does not exist.\n" \
            "For more information, see \n" \
            "http://www.flumotion.net/doc/flumotion/manual/html/chapter-security.html" % pemFile)
    log.debug('manager', 'Using PEM certificate file %s' % pemFile)
    ctxFactory = ServerContextFactory(pemFile)
    
    log.info('manager', 'Starting on port %d using SSL' % port)
    if not host == "":
        log.info('manager', 'Listening as host %s' % host)
    vishnu.setConnectionInfo(host, port, True)
    reactor.listenSSL(port, vishnu.getFactory(), ctxFactory, interface=host)

def _startTCP(vishnu, host, port):
    log.info('manager', 'Starting on port %d using TCP' % port)
    if not host == "":
        log.info('manager', 'Listening as host %s' % host)
    vishnu.setConnectionInfo(host, port, False)
    reactor.listenTCP(port, vishnu.getFactory(), interface=host)

def _error(message, reason):
    msg = message
    if reason:
        msg += "\n%s" % reason
    # since our SystemError is going to be lost in the reactor, we may as well
    # trap it here
    # FIXME: maybe we should stop making this raise SystemErrror ?
    try:
        log.error('manager', msg)
    except errors.SystemError:
        pass

def _initialLoadConfig(vishnu, paths):
    # this is used with a callLater for the initial config loading
    # since this is run after daemonizing, it should show errors, but not stop
    for path in paths:
        log.debug('manager', 'Loading configuration file from (%s)' % path)
        try:
            vishnu.loadConfiguration(path)
        except config.ConfigError, reason:
            _error(
                "configuration error in configuration file\n'%s':" % path,
                reason.args[0])
        except errors.UnknownComponentError, reason:
            _error(
                "unknown component in configuration file\n'%s':" % path,
                reason.args[0])
        except Exception, e:
            # a re-raise here would be caught by twisted and only shows at
            # debug level 4 because that's where we hooked up twisted logging
            # so print a traceback before stopping the program
            traceback.print_tb(sys.exc_traceback)
            _error("failed to load planet configuration '%s':" % path,
                "%s: %s" % (e.__class__, str(e)))

def main(args):
    # XXX: gst_init should remove all options, like gtk_init
    args = [arg for arg in args if not arg.startswith('--gst')]
    
    usagemessage = "usage: %prog [options] manager.xml flow1.xml flow2.xml [...]"
    desc = "The manager is the core component of the Flumotion streaming\
 server. It takes its configuration from one or more planet configuration\
 files. The first file is mandatory, and contains base configuration \
 information for the manager. Zero or more additional configuration files\
 can be provided, these are used to configure flows that the manager should run\
 on available workers."

    parser = optparse.OptionParser(usage=usagemessage, description=desc)
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
                     default=None,
                     help="PEM certificate file (for SSL) "
                     "[default default.pem]")
    group.add_option('-n', '--name',
                     action="store", type="string", dest="name",
                     help="manager name")
    group.add_option('-D', '--daemonize',
                     action="store_true", dest="daemonize",
                     default=False,
                     help="run in background as a daemon")
    group.add_option('', '--daemonize-to',
                     action="store", dest="daemonizeTo",
                     help="what directory to run from when daemonizing")
    parser.add_option_group(group)
    
    log.debug('manager', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    # verbose overrides --debug
    if options.verbose:
        options.debug = "*:3"

    # Handle options that don't require a configuration file.
    if options.version:
        print common.version("flumotion-manager")
        return 0

    # parse planet config file
    if len(args) <= 1:
        log.warning('manager', 'Please specify a planet configuration file')
        sys.stderr.write("Please specify a planet configuration file.\n")
        return -1

    planetFile = args[1]
    try:
        cfg = config.FlumotionConfigXML(planetFile)
    except IOError, e:
        sys.stderr.write("ERROR: Could not read configuration from '%s':\n" %
            planetFile)
        sys.stderr.write("ERROR: %s\n" % e.strerror)
        return -1
    except errors.ConfigError, e:
        sys.stderr.write("ERROR: Could not read configuration from '%s':\n" %
            planetFile)
        sys.stderr.write("ERROR: %s\n" % e.args[0])
        return -1

    # now copy over stuff from config that is not set yet
    if cfg.manager:
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
        if not options.certificate and cfg.manager.certificate:
            options.certificate = cfg.manager.certificate
            log.debug('manager', 'Using certificate %s' %
                options.certificate)
        if not options.name and cfg.manager.name:
            options.name = cfg.manager.name
            log.debug('manager', 'Setting manager name to %s' % options.name)
        # environment debug > command-line debug > config file debug
        if not options.debug and cfg.manager.fludebug \
            and not os.environ.has_key('FLU_DEBUG'):
            options.debug = cfg.manager.fludebug
            log.debug('manager', 'Setting debug level to config file value %s' %
                options.debug)

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
    if not options.certificate and options.transport == 'ssl':
        options.certificate = 'default.pem'
    if not options.name:
        try:
            # if the file is in a directory under a 'managers' directory,
            # use the parent directory name
            head, filename = os.path.split(os.path.abspath(planetFile))
            head, name = os.path.split(head)
            head, managers = os.path.split(head)
            if managers != 'managers':
                raise
            options.name = name
            log.debug('manager', 'Setting name to %s based on path' % name)
        except:
            options.name = 'unnamed'
            log.debug('manager', 'Setting name to unnamed')

    # check for wrong options/arguments
    if not options.transport in ['ssl', 'tcp']:
        sys.stderr.write('ERROR: wrong transport %s, must be ssl or tcp\n' %
            options.transport)
        return 1

    # handle all other options
    if options.debug:
        log.setFluDebug(options.debug)

    # register package path
    setup.setupPackagePath()
    
    log.debug('manager', 'Running Flumotion version %s' %
        configure.version)
    import twisted.copyright
    log.debug('manager', 'Running against Twisted version %s' %
        twisted.copyright.version)
    log.debug('manager', 'Running against GStreamer version %s' %
        configure.gst_version)
    from flumotion.project import project
    for p in project.list():
        log.debug('manager', 'Registered project %s version %s' % (
            p, project.get(p, 'version')))

    vishnu = manager.Vishnu(options.name)

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

    if options.daemonizeTo and not options.daemonize:
        sys.stderr.write(
            'ERROR: --daemonize-to can only be used with -D/--daemonize.\n')
        return 1

    if options.daemonize:
        log.info('manager', 'Daemonizing')
        common.ensureDir(configure.logdir, "log file")
        common.ensureDir(configure.rundir, "run file")
                
        if common.getPid('manager', options.name):
            raise errors.SystemError, \
                'A manager with name %s is already running' % options.name

        logPath = os.path.join(configure.logdir,
            'manager.%s.log' % options.name)
        log.debug('manager', 'Further logging will be done to %s' % logPath)

        # here we daemonize; so we also change our pid
        if not options.daemonizeTo:
            options.daemonizeTo = '/'
        common.daemonize(stdout=logPath, stderr=logPath,
            directory=options.daemonizeTo)

        log.info('manager', 'Started daemon')

        # from now on I should keep running, whatever happens
        log.debug('manager', 'writing pid file')
        common.writePidFile('manager', options.name)

    # go into the reactor main loop
    log.info('manager', 'Started manager "%s"' % options.name)

    # let SystemError be handled normally, without exiting or tracebacking
    try:
        reactor.run()
    except:
        print "THOMAS WAS HERE"
        raise

    # we exited, so we're done
    if options.daemonize:
        log.debug('manager', 'deleting pid file')
        common.deletePidFile('manager', options.name)

    log.info('manager', 'Stopping manager "%s"' % options.name)

    return 0
