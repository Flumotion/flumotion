# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/worker/main.py: main function of flumotion-worker
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

import errno
import optparse
import os
import signal

from twisted.internet import reactor

from flumotion.configure import configure
from flumotion.common import log, keycards, common
from flumotion.worker import worker
from flumotion.twisted import credentials

def main(args):
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="be verbose")
    parser.add_option('', '--version',
                      action="store_true", dest="version",
                      default=False,
                      help="show version information")

    group = optparse.OptionGroup(parser, "worker options")
    group.add_option('-H', '--host',
                     action="store", type="string", dest="host",
                     default="localhost",
                     help="manager to connect to [default localhost]")
    defaultSSLPort = configure.defaultSSLManagerPort
    defaultTCPPort = configure.defaultTCPManagerPort
    group.add_option('-P', '--port',
                     action="store", type="int", dest="port",
                     default=None,
                     help="port to listen on [default %d (ssl) or %d (tcp)]" % (defaultSSLPort, defaultTCPPort))
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
    group.add_option('-w', '--worker-name',
                     action="store", type="string", dest="workerName",
                     default="",
                     help="worker name to use in the manager")
     
    parser.add_option_group(group)
    
    log.debug('manager', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    if options.version:
        print common.version("flumotion-worker")
        return 0

    if options.verbose:
        log.setFluDebug("*:3")

    if options.daemonize:
        if not os.path.exists(configure.logdir):
            try:
                os.makedirs(configure.logdir)
            except:
                sys.stderr.write("Could not create log file directory %d.\n" % configure.logdir)
                return -1

        logPath = os.path.join(configure.logdir, 'worker.log')
        common.daemonize(stdout=logPath, stderr=logPath)

    if not options.port:
        if options.transport == "tcp":
            options.port = defaultTCPPort
        elif options.transport == "ssl":
            options.port = defaultSSLPort

    # create a brain and have it remember the manager to direct jobs to
    brain = worker.WorkerBrain(options)

    # connect the brain to the manager
    if options.transport == "tcp":
        reactor.connectTCP(options.host, options.port,
            brain.worker_client_factory)
    elif options.transport == "ssl":
        from twisted.internet import ssl
        reactor.connectSSL(options.host, options.port,
            brain.worker_client_factory,
            ssl.ClientContextFactory())
    else:
        log.error('worker', 'Unknown transport protocol: %s' % options.transport)
    log.info('worker',
             'Connecting to manager %s:%d using %s' % (options.host,
                                                       options.port,
                                                       options.transport.upper()))

    if options.workerName:
        workerName = options.workerName
    else:
        if options.host == 'localhost':
            workerName = 'localhost'
        else:
            import socket
            workerName = socket.gethostname()

    keycard = keycards.KeycardUACPP(options.username, options.password,
                                    'localhost')
    # FIXME: decide on a workername
    keycard.avatarId = workerName
    brain.login(keycard)

    # the reactor needs to be able to reap its own children
    # but we also want ours reaped
    # so we install our own signal handler that first chains to twisted's,
    # then reaps children
    reactor.addSystemEventTrigger('after', 'startup', brain.installSIGCHLDHandler)
    log.debug('worker', 'Starting reactor')
    reactor.run()

    log.debug('worker', 'Reactor stopped, shutting down jobs')
    # XXX: Is this really necessary
    brain.job_heaven.shutdown()

    pids = [kid.getPid() for kid in brain.kindergarten.getKids()]
    
    log.debug('worker', 'Waiting for jobs to finish (pids %r)' % pids)
    while pids:
        try:
            pid = os.wait()[0]
        except OSError, e:
            if e.errno == errno.ECHILD:
                log.warning('No children left, but list of pids is %r' % pids)
                break
        
        log.debug('worker', 'Job with pid %d finished' % pid)
        pids.remove(pid)

    log.info('worker', 'All jobs finished, stopping worker')
