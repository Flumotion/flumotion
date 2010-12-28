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

from twisted.internet import reactor

from flumotion.configure import configure
from flumotion.common import log, keycards, common, errors
from flumotion.job import job
from flumotion.twisted import credentials, fdserver
from flumotion.common.options import OptionParser

__version__ = "$Rev$"


def main(args):
    parser = OptionParser(domain="flumotion-job")

    log.debug('job', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    # check if a config file was specified; if so, parse config and copy over
    if len(args) != 3:
        parser.error("must pass an avatarId and a path to the socket: %r" %
            args)
    avatarId = args[1]
    socket = args[2]

    # log our standardized starting marker
    log.info('job', "Starting job '%s'" % avatarId)

    # register all package paths (FIXME: this should go away when
    # components and all deps come from manager)
    # this is still necessary so that code from other projects can be imported
    from flumotion.common import setup
    setup.setupPackagePath()

    log.info('job', 'Connecting to worker on socket %s' % (socket))

    job_factory = job.JobClientFactory(avatarId)
    reactor.connectWith(fdserver.FDConnector, socket, job_factory,
        10, checkPID=False)

    reactor.addSystemEventTrigger('before', 'shutdown',
        job_factory.medium.shutdownHandler)

    # log our standardized started marker
    log.info('job', "Started job '%s'" % avatarId)

    reactor.run()

    # log our standardized stopping marker
    log.info('job', "Stopping job '%s'" % avatarId)
    # log our standardized stopped marker
    log.info('job', "Stopped job '%s'" % avatarId)

    return 0
