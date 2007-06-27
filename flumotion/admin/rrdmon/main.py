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
from flumotion.common import connection
from flumotion.admin.rrdmon import rrdmon, config
from flumotion.twisted import pb

# more standard helper functions necessary...
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

    group = optparse.OptionGroup(parser, "rrdmon options")
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
    parser.add_option_group(group)

    return parser

def _readConfig(confXml, options):
    # modifies options dict in-place
    log.info('rrdmon', 'Reading configuration from %s' % confXml)
    cfg = config.ConfigParser(confXml).parse()
    # command-line debug > environment debug > config file debug
    if not options.debug and cfg['debug'] \
        and not os.environ.has_key('FLU_DEBUG'):
        options.debug = cfg['debug']
    return cfg
    
def main(args):
    parser = _createParser()
    log.debug('rrdmon', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    # Force options down configure's throat
    for d in ['logdir', 'rundir']:
        o = getattr(options, d, None)
        if o:
            log.debug('rrdmon', 'Setting configure.%s to %s' % (d, o))
            setattr(configure, d, o)

    # handle all options
    if options.version:
        print common.version("flumotion-rrdmon")
        return 0

    if options.verbose:
        log.setFluDebug("*:3")
 
    # apply the command-line debug level if is given through --verbose or -d
    if options.debug:
        log.setFluDebug(options.debug)

    # check if a config file was specified; if so, parse config and copy over
    if len(args) != 2:
        raise SystemExit('usage: flumotion-rrdtool [OPTIONS] CONFIG-FILE')

    confXml = args[1]
    cfg = _readConfig(confXml, options)

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

    monitor = rrdmon.RRDMonitor(cfg['sources'])

    name = 'rrdmon'
    if options.daemonize:
        if options.serviceName:
            name = options.serviceName

    common.startup("rrdmon", name, options.daemonize, options.daemonizeTo)

    log.debug('rrdmon', 'Running Flumotion version %s' %
        configure.version)
    import twisted.copyright
    log.debug('rrdmon', 'Running against Twisted version %s' %
        twisted.copyright.version)

    # go into the reactor main loop
    reactor.run()

    return 0
