# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

import optparse
import os
import sys

from twisted.internet import reactor

from flumotion.configure import configure
from flumotion.common import log, keycards, common, errors
from flumotion.worker import worker, config
from flumotion.twisted import pb

def _createParser():
    parser = optparse.OptionParser()
    parser.add_option('-d', '--debug',
                      action="store", type="string", dest="debug",
                      help="set debug levels")
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="be verbose")
    parser.add_option('', '--version',
                      action="store_true", dest="version",
                      help="show version information")

    group = optparse.OptionGroup(parser, "worker options")
    group.add_option('-H', '--host',
                     action="store", type="string", dest="host",
                     help="manager host to connect to [default localhost]")
    group.add_option('-P', '--port',
                     action="store", type="int", dest="port",
                     help="manager port to connect to " \
                        "[default %d (ssl) or %d (tcp)]" % (
                        configure.defaultSSLManagerPort,
                        configure.defaultTCPManagerPort))
    group.add_option('-T', '--transport',
                     action="store", type="string", dest="transport",
                     help="transport protocol to use (tcp/ssl) [default ssl]")
    group.add_option('-n', '--name',
                     action="store", type="string", dest="name",
                     help="worker name to use in the manager")
    group.add_option('-s', '--service-name',
                     action="store", type="string", dest="serviceName",
                     help="name to use for log and pid files "
                          "when run as a daemon")
    group.add_option('-D', '--daemonize',
                     action="store_true", dest="daemonize",
                     help="run in background as a daemon")
    group.add_option('', '--daemonize-to',
                     action="store", dest="daemonizeTo",
                     help="what directory to run from when daemonizing")

    parser.add_option('-L', '--logdir',
                      action="store", dest="logdir",
                      help="flumotion log directory (default: %s)" %
                        configure.logdir)
    parser.add_option('-R', '--rundir',
                      action="store", dest="rundir",
                      help="flumotion run directory (default: %s)" %
                        configure.rundir)

    group.add_option('-u', '--username',
                     action="store", type="string", dest="username",
                     default="",
                     help="username to use")
    group.add_option('-p', '--password',
                     action="store", type="string", dest="password",
                     default="",
                     help="password to use")

    group.add_option('-F', '--feederports',
                     action="store", type="string", dest="feederports",
                     help="range of feeder ports to use")

    parser.add_option_group(group)

    return parser

def _readConfig(workerFile, options):
    log.info('worker', 'Reading configuration from %s' % workerFile)
    try:
        cfg = config.WorkerConfigXML(workerFile)
    except config.ConfigError, value:
        raise errors.SystemError(
            "Could not load configuration from %s: %s" % (
            workerFile, value))
    except IOError, e:
        raise errors.SystemError(
            "Could not load configuration from %s: %s" % (
            workerFile, e.strerror))

    # now copy over stuff from config that is not set yet
    if not options.name and cfg.name:
        log.debug('worker', 'Setting worker name %s' % cfg.name)
        options.name = cfg.name

    # manager
    if not options.host and cfg.manager.host:
        options.host = cfg.manager.host
        log.debug('worker', 'Setting manager host to %s' % options.host)
    if not options.port and cfg.manager.port:
        options.port = cfg.manager.port
        log.debug('worker', 'Setting manager port to %s' % options.port)
    if not options.transport and cfg.manager.transport:
        options.transport = cfg.manager.transport
        log.debug('worker', 'Setting manager transport to %s' %
            options.transport)

    # authentication
    if not options.username and cfg.authentication.username:
        options.username = cfg.authentication.username
        log.debug('worker', 'Setting username %s' % options.username)
    if not options.password and cfg.authentication.password:
        options.password = cfg.authentication.password
        log.debug('worker',
            'Setting password [%s]' % ("*" * len(options.password)))

    # feederports: list of allowed ports
    # XML could specify it as empty, meaning "don't use any"
    if not options.feederports and cfg.feederports is not None:
        options.feederports = cfg.feederports
    if options.feederports is not None:
        log.debug('worker', 'Using feederports %r' % options.feederports)

    # general
    # command-line debug > environment debug > config file debug
    if not options.debug and cfg.fludebug \
        and not os.environ.has_key('FLU_DEBUG'):
        options.debug = cfg.fludebug
    
def main(args):
    parser = _createParser()
    log.debug('worker', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    # Force options down configure's throat
    for d in ['logdir', 'rundir']:
        o = getattr(options, d, None)
        if o:
            log.debug('worker', 'Setting configure.%s to %s' % (d, o))
            setattr(configure, d, o)

    # verbose overrides --debug; is only a command-line option
    if options.verbose:
        options.debug = "*:3"
 
    # apply the command-line debug level if is given through --verbose or -d
    if options.debug:
        log.setFluDebug(options.debug)

    # translate feederports string to range
    if options.feederports:
        if not '-' in options.feederports:
            raise errors.OptionError("feederports '%s' does not contain '-'" %
                options.feederports)
        (lower, upper) = options.feederports.split('-')
        options.feederports = range(int(lower), int(upper) + 1)

    # check if a config file was specified; if so, parse config and copy over
    if len(args) > 1:
        workerFile = args[1]
        _readConfig(workerFile, options)

    # set default values for all unset options
    if not options.host:
        options.host = 'localhost'
    if not options.transport:
        options.transport = 'ssl'
    if not options.port:
        if options.transport == "tcp":
            options.port = configure.defaultTCPManagerPort
        elif options.transport == "ssl":
            options.port = configure.defaultSSLManagerPort

    # set a default name if none is given
    if not options.name:
        if options.host == 'localhost':
            options.name = 'localhost'
            log.debug('worker', 'Setting worker name localhost')
        else:
            import socket
            options.name = socket.gethostname()
            log.debug('worker', 'Setting worker name %s (from hostname)' %
                options.name)

    if options.feederports is None:
        options.feederports = configure.defaultGstPortRange
        log.debug('worker', 'Using default feederports %r' %
            options.feederports)

    # check for wrong options/arguments
    if not options.transport in ['ssl', 'tcp']:
        sys.stderr.write('ERROR: wrong transport %s, must be ssl or tcp\n' %
            options.transport)
        return 1

    # handle all options
    if options.version:
        print common.version("flumotion-worker")
        return 0

    # reset FLU_DEBUG which could be different after parsing XML file
    if options.debug:
        log.setFluDebug(options.debug)

    if options.daemonizeTo and not options.daemonize:
        sys.stderr.write(
            'ERROR: --daemonize-to can only be used with -D/--daemonize.\n')
        return 1

    if options.serviceName and not options.daemonize:
        sys.stderr.write(
            'ERROR: --service-name can only be used with -D/--daemonize.\n')
        return 1

    brain = worker.WorkerBrain(options)

    # Now bind and listen to our unix and tcp sockets
    if not brain.listen():
        sys.stderr.write('ERROR: Failed to listen on worker ports.\n')
        return 1

    name = options.name
    if options.daemonize:
        if options.serviceName:
            name = options.serviceName

    common.startup("worker", name, options.daemonize, options.daemonizeTo)

    log.debug('worker', 'Running Flumotion version %s' %
        configure.version)
    import twisted.copyright
    log.debug('worker', 'Running against Twisted version %s' %
        twisted.copyright.version)
    log.debug('worker', 'Running against GStreamer version %s' %
        configure.gst_version)

    # register all package paths (FIXME: this should go away when
    # components come from manager)
    from flumotion.common import setup
    setup.setupPackagePath()

    # create a brain and have it remember the manager to direct jobs to
    # connect the brain to the manager
    if options.transport == "tcp":
        reactor.connectTCP(options.host, options.port,
            brain.workerClientFactory)
    elif options.transport == "ssl":
        from twisted.internet import ssl
        reactor.connectSSL(options.host, options.port,
            brain.workerClientFactory,
            ssl.ClientContextFactory())

    log.info('worker',
             'Connecting to manager %s:%d using %s' % (options.host,
                                                       options.port,
                                                       options.transport.upper()))

    authenticator = pb.Authenticator(
        username=options.username,
        password=options.password,
        address='localhost', # FIXME: why localhost ?
        avatarId=options.name
    )
    brain.login(authenticator)

    reactor.addSystemEventTrigger('before', 'shutdown', brain.shutdownHandler)

    # go into the reactor main loop
    reactor.run()

    return 0
