# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/worker/main.py: main function of flumotion-worker
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

import errno
import optparse
import os

from twisted.internet import reactor

from flumotion.common import log, keycards, common
from flumotion.worker import worker
from flumotion.twisted import credentials

def main(args):
    parser = optparse.OptionParser()
    parser.add_option('', '--version',
                      action="store_true", dest="version",
                      default=False,
                      help="show version information")

    group = optparse.OptionGroup(parser, "worker options")

    group.add_option('-H', '--host',
                     action="store", type="string", dest="host",
                     default="localhost",
                     help="manager to connect to [default localhost]")
    group.add_option('-P', '--port',
                     action="store", type="int", dest="port",
                     default=8890,
                     help="manager port to connect to [default 8890]")
    group.add_option('-T', '--transport',
                     action="store", type="string", dest="transport",
                     default="ssl",
                     help="transport protocol to use (tcp/ssl)")
    group.add_option('-D', '--daemonize',
                     action="store_true", dest="daemonize",
                     default=False,
                     help="run in background as a daemon")

    group.add_option('-u', '--username',
                     action="store", type="string", dest="username",
                     default="",
                     help="username to use")
    group.add_option('-p', '--password',
                     action="store", type="string", dest="password",
                     default="",
                     help="password to use, - for interactive")
     
    parser.add_option_group(group)
    
    log.debug('manager', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    if options.version:
        print common.version("flumotion-worker")
        return 0

    if options.daemonize:
        common.daemonize()

    # create a brain and have it remember the manager to direct jobs to
    brain = worker.WorkerBrain(options)

    # connect the brain to the manager
    log.info('worker',
             'Connecting to manager %s:%d (using %s)' % (options.host,
                                                         options.port,
                                                         options.transport))
    if options.transport == "tcp":
        reactor.connectTCP(options.host, options.port, brain.worker_client_factory)
    elif options.transport == "ssl":
        from twisted.internet import ssl
        reactor.connectSSL(options.host, options.port, brain.worker_client_factory,
                           ssl.ClientContextFactory())
    else:
        log.error('worker', 'Unknown transport protocol: %s' % options.transport)

    # FIXME: one without address maybe ? or do we want manager to set it ?
    # or do we set our guess and let manager correct ?
    keycard = keycards.KeycardUACPP(options.username, options.password, 'localhost')
    # FIXME: decide on a workername
    keycard.avatarId = "localhost"
    brain.login(keycard)

    log.debug('worker', 'Starting reactor')
    reactor.run()

    log.debug('worker', 'Reactor stopped, shutting down jobs')
    # XXX: Is this really necessary
    brain.job_heaven.shutdown()

    pids = [kid.getPid() for kid in brain.kindergarten.getKids()]
    
    log.debug('worker', 'Waiting for jobs to finish')
    while pids:
        try:
            pid = os.wait()[0]
	# FIXME: properly catch OSError: [Errno 10] No child processes
        except OSError, e:
            if e.errno == errno.ECHILD:
                continue
        
        pids.remove(pid)

    log.debug('worker', 'All jobs finished, closing down')
