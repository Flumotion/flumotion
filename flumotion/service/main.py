# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

import os
import sys
import optparse

from flumotion.common import common, log
from flumotion.configure import configure
from flumotion.service import service

def main(args):
    parser = optparse.OptionParser()
    parser.add_option('-d', '--debug',
                      action="store", type="string", dest="debug",
                      help="set debug levels")
    parser.add_option('', '--version',
                      action="store_true", dest="version",
                      default=False,
                      help="show version information")

    parser.add_option('-c', '--configdir',
                      action="store", dest="configdir",
                      help="flumotion configuration directory")
    parser.add_option('-l', '--logfile',
                      action="store", dest="logfile",
                      help="flumotion service log file")

    options, args = parser.parse_args(args)

    if not options.configdir:
        options.configdir = configure.configdir

    if options.version:
        print common.version("flumotion")
        return 0

    if options.debug:
        log.setFluDebug(options.debug)

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

    servicer = service.Servicer(options.configdir)
    try:
        command = args[1]
    except IndexError:
        print "Usage: flumotion {list|start|stop|restart|status|clean} [which]"
        sys.exit(0)
    
    if command == "list":
        return servicer.list()
    elif command == "start":
        return servicer.start(args[2:])
    elif command == "stop":
        return servicer.stop(args[2:])
    elif command == "restart":
        return servicer.stop(args[2:]) + servicer.start(args[2:])
    elif command == "status":
        return servicer.status(args[2:])
    elif command == "clean":
        return servicer.clean(args[2:])

    sys.stderr.write("No such command '%s'\n" % command)
    return 1
