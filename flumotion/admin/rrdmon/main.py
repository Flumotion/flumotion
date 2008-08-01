# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

"""flumotion-rrdmon entry point, command line parsing and invokation"""

import os
import sys

from twisted.internet import reactor

from flumotion.admin.rrdmon import rrdmon, config
from flumotion.common import log
from flumotion.common.options import OptionGroup, OptionParser
from flumotion.common.process import startup
from flumotion.configure import configure

__version__ = "$Rev$"

# more standard helper functions necessary...


def _createParser():
    parser = OptionParser(domain="flumotion-rrdmon")

    group = OptionGroup(parser, "rrdmon")
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
        and not 'FLU_DEBUG' in os.environ:
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
        if not options.daemonizeTo:
            options.daemonizeTo = "/"

    startup("rrdmon", name, options.daemonize, options.daemonizeTo)

    log.debug('rrdmon', 'Running Flumotion version %s' %
        configure.version)
    import twisted.copyright
    log.debug('rrdmon', 'Running against Twisted version %s' %
        twisted.copyright.version)

    # go into the reactor main loop
    reactor.run()

    return 0
