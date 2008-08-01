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

"""
manager main function
"""

import os
import sys

from twisted.internet import reactor, error

from flumotion.manager import manager, config
from flumotion.common import log, errors, setup
from flumotion.common import server
from flumotion.common.options import OptionGroup, OptionParser
from flumotion.common.process import startup
from flumotion.configure import configure

__version__ = "$Rev$"
defaultSSLPort = configure.defaultSSLManagerPort
defaultTCPPort = configure.defaultTCPManagerPort


def _createParser():
    usagemessage = "usage: %prog [options] manager.xml flow1.xml [...]"
    desc = "The manager is the core component of the Flumotion streaming\
 server. It takes its configuration from one or more planet configuration\
 files. The first file is mandatory, and contains base configuration \
 information for the manager. Zero or more additional configuration files\
 can be provided, these are used to configure flows that the manager should\
 run on available workers."

    parser = OptionParser(usage=usagemessage, description=desc,
                          domain="flumotion-manager")

    group = OptionGroup(parser, "manager options")
    group.add_option('-H', '--hostname',
                     action="store", type="string", dest="host",
                     help="hostname to listen as")
    group.add_option('-P', '--port',
                     action="store", type="int", dest="port",
                     default=None,
                     help="port to listen on [default %d (ssl) or %d (tcp)]" %
                     (defaultSSLPort, defaultTCPPort))
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
    group.add_option('-s', '--service-name',
                     action="store", type="string", dest="serviceName",
                     help="name to use for log and pid files "
                          "when run as a daemon")
    group.add_option('-D', '--daemonize',
                     action="store_true", dest="daemonize",
                     default=False,
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

    parser.add_option_group(group)

    return parser


def _initialLoadConfig(vishnu, paths):
    # this is used with a callLater for the initial config loading
    # since this is run after daemonizing, it should show errors, but not stop
    for path in paths:
        log.debug('manager', 'Loading configuration file from (%s)' % path)
        vishnu.loadComponentConfigurationXML(path, manager.LOCAL_IDENTITY)


def main(args):
    parser = _createParser()

    log.debug('manager', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    # Force options down configure's throat
    for d in ['logdir', 'rundir']:
        o = getattr(options, d, None)
        if o:
            log.debug('manager', 'Setting configure.%s to %s' % (d, o))
            setattr(configure, d, o)

    # parse planet config file
    if len(args) <= 1:
        log.warning('manager', 'Please specify a planet configuration file')
        sys.stderr.write("Please specify a planet configuration file.\n")
        return 1

    planetFile = args[1]
    try:
        cfg = config.ManagerConfigParser(planetFile)
    except IOError, e:
        sys.stderr.write("ERROR: Could not read configuration from '%s':\n" %
            planetFile)
        sys.stderr.write("ERROR: %s\n" % e.strerror)
        return 1
    except errors.ConfigError, e:
        sys.stderr.write("ERROR: Could not read configuration from '%s':\n" %
            planetFile)
        sys.stderr.write("ERROR: %s\n" % e.args[0])
        return 1

    managerConfigDir = os.path.abspath(os.path.dirname(planetFile))

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
            and not 'FLU_DEBUG' in os.environ:
            options.debug = cfg.manager.fludebug
            log.debug('manager',
                      'Setting debug level to config file value %s' %
                options.debug)

    # set debug level as soon as we can after deciding
    if options.debug:
        log.setFluDebug(options.debug)

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
        # if the file is in a directory under a 'managers' directory,
        # use the parent directory name
        head, filename = os.path.split(os.path.abspath(planetFile))
        head, name = os.path.split(head)
        head, managers = os.path.split(head)
        if managers != 'managers':
            options.name = 'unnamed'
            log.debug('manager', 'Setting name to unnamed')
        else:
            options.name = name
            log.debug('manager', 'Setting name to %s based on path' % name)

    # check for wrong options/arguments
    if not options.transport in ['ssl', 'tcp']:
        sys.stderr.write('ERROR: wrong transport %s, must be ssl or tcp\n' %
            options.transport)
        return 1

    # register package path
    setup.setupPackagePath()

    # log our standardized starting marker
    log.info('manager', "Starting manager '%s'" % options.name)

    log.debug('manager', 'Running Flumotion version %s' %
        configure.version)
    import twisted.copyright
    log.debug('manager', 'Running against Twisted version %s' %
        twisted.copyright.version)
    from flumotion.project import project
    for p in project.list():
        log.debug('manager', 'Registered project %s version %s' % (
            p, project.get(p, 'version')))

    vishnu = manager.Vishnu(options.name, configDir=managerConfigDir)
    for managerConfigFile in args[1:]:
        vishnu.loadManagerConfigurationXML(managerConfigFile)

    paths = [os.path.abspath(filename) for filename in args[1:]]
    reactor.callLater(0, _initialLoadConfig, vishnu, paths)
    reactor.callLater(0, vishnu.startManagerPlugs)

    # set up server based on transport
    myServer = server.Server(vishnu)
    try:
        if options.transport == "ssl":
            myServer.startSSL(options.host, options.port, options.certificate,
                configure.configdir)
        elif options.transport == "tcp":
            myServer.startTCP(options.host, options.port)
    except error.CannotListenError, e:
        # e is a socket.error()
        message = "Could not listen on port %d: %s" % (
            e.port, e.socketError.args[1])
        raise errors.FatalError, message

    if options.daemonizeTo and not options.daemonize:
        sys.stderr.write(
            'ERROR: --daemonize-to can only be used with -D/--daemonize.\n')
        return 1

    if options.serviceName and not options.daemonize:
        sys.stderr.write(
            'ERROR: --service-name can only be used with -D/--daemonize.\n')
        return 1

    name = options.name

    if options.daemonize:
        if options.serviceName:
            name = options.serviceName
        if not options.daemonizeTo:
            options.daemonizeTo = "/"

    startup("manager", name, options.daemonize, options.daemonizeTo)

    reactor.run()

    return 0
