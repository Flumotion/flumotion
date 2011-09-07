# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

import os
import sys

from flumotion.common import common, log
from flumotion.configure import configure
from flumotion.service import service
from flumotion.common.options import OptionParser


def main(args):
    parser = OptionParser(domain=configure.PACKAGE)

    parser.add_option('-l', '--logfile',
                      action="store", dest="logfile",
                      help="flumotion service log file")
    parser.add_option('-C', '--configdir',
                      action="store", dest="configdir",
                      help="flumotion configuration directory (default: %s)" %
                        configure.configdir)
    parser.add_option('-L', '--logdir',
                      action="store", dest="logdir",
                      help="flumotion log directory (default: %s)" %
                        configure.logdir)
    parser.add_option('-R', '--rundir',
                      action="store", dest="rundir",
                      help="flumotion run directory (default: %s)" %
                        configure.rundir)

    options, args = parser.parse_args(args)

    # Force options down configure's throat
    for d in ['configdir', 'logdir', 'rundir']:
        o = getattr(options, d, None)
        if o:
            log.debug('service', 'Setting configure.%s to %s' % (d, o))
            setattr(configure, d, o)

    # if log file is specified, redirect stdout and stderr
    if options.logfile:
        try:
            out = open(options.logfile, 'a+')
            err = open(options.logfile, 'a+', 0)
        except IOError, e:
            sys.stderr.write("Could not open file '%s' for writing:\n%s\n" % (
                options.logfile, e.strerror))
            sys.exit(1)

        os.dup2(out.fileno(), sys.stdout.fileno())
        os.dup2(err.fileno(), sys.stderr.fileno())

    servicer = service.Servicer(options.configdir, options.logdir,
        options.rundir)
    try:
        command = args[1]
    except IndexError:
        print "Usage: flumotion " \
            "{list|start|stop|restart|condrestart|status|clean|" \
            "enable|disable} [which]"
        sys.exit(0)

    if command == "list":
        return servicer.list()
    elif command == "start":
        return servicer.start(args[2:])
    elif command == "stop":
        return servicer.stop(args[2:])
    elif command == "restart":
        return servicer.stop(args[2:]) + servicer.start(args[2:])
    elif command == "condrestart":
        return servicer.condrestart(args[2:])
    elif command == "status":
        return servicer.status(args[2:])
    elif command == "create":
        return servicer.create(args[2:])
    elif command == "clean":
        return servicer.clean(args[2:])
    elif command == "enable":
        return servicer.enable(args[2:])
    elif command == "disable":
        return servicer.disable(args[2:])

    sys.stderr.write("No such command '%s'\n" % command)
    return 1
