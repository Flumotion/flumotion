# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/worker/worker.py: flumotion-worker objects handling component jobs
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

import os
import signal
import sys

from twisted.cred import portal
from twisted.internet import protocol, reactor
from twisted.spread import pb

# We want to avoid importing gst, otherwise --help fails
# so be very careful when adding imports
from flumotion.common import errors, interfaces
from flumotion.twisted import cred, pbutil
from flumotion.utils import log

#factoryClass = pbutil.ReconnectingPBClientFactory
factoryClass = pbutil.FMClientFactory
class WorkerClientFactory(factoryClass):
    """
    I am a client factory for the worker to log in to the manager.
    """
    #__super_login = factoryClass.startLogin
    __super_login = factoryClass.login
    def __init__(self, parent):
        self.view = parent.worker_view
        # doing this as a class method triggers a doc error
        factoryClass.__init__(self)
        
    def login(self, credentials):
        return self.__super_login(credentials,
                                  self.view,
                                  interfaces.IWorkerView)
        
    def gotPerspective(self, perspective):
        self.view.cb_gotPerspective(perspective)

class WorkerView(pb.Referenceable, log.Loggable):
    """
    I present a view of the worker to the manager.
    """
    logCategory = 'worker-view'
    def __init__(self, brain):
        self.brain = brain
        
    def cb_gotPerspective(self, perspective):
        self.info('got perspective: %s' % perspective)

    def cb_processFinished(self, *args):
        self.info('processFinished %r' % args)

    def cb_processFailed(self, *args):
        self.info('processFailed %r' % args)

    ### pb.Referenceable method for the manager's WorkerAvatar
    def remote_start(self, name, type, config):
        """
        Start a component of the given type with the given config.

        @param name: name of the component to start
        @type name: string
        @param type: type of the component
        @type type: string
        @param config: a configuration dictionary for the component
        @type config: dict
        """
        self.info('remote_start(): manager asked me to start, name %s, type %s, config %r' % (name, type, config))
        self.brain.kindergarten.play(name, type, config)
        
class Kid:
    def __init__(self, protocol, name, type, config):
        self.protocol = protocol 
        self.name = name
        self.type = type
        self.config = config

    # pid = protocol.transport.pid
    def getPid(self):
        return self.protocol.pid
    
class Kindergarten:
    """
    I spawn job processes.
    I live in the worker brain.
    """
    def __init__(self):
        dirname = os.path.split(os.path.abspath(sys.argv[0]))[0]
        self.program = os.path.join(dirname, 'flumotion-worker')
        self.kids = {}
        
    def play(self, name, type, config):
        ### FIXME: move this to the worker brain, since this is the unix
        ### domain socket
        worker_filename = '/tmp/flumotion.%d' % os.getpid()
        args = [self.program,
                '--job', name,
                '--worker', worker_filename]
        log.debug('worker', 'Launching process %s' % name)
        p = reactor.spawnProcess(protocol.ProcessProtocol(),
                                 self.program, args,
                                 env=os.environ,
                                 childFDs={ 0: 0, 1: 1, 2: 2})
        self.kids[name] = Kid(p, name, type, config)

        return p

    def getKid(self, name):
        return self.kids[name]
    
    def getKids(self):
        return self.kids.values()
    
# Similar to Vishnu, but for worker related classes
class WorkerBrain:
    """
    I manage jobs and everything related.
    I live in the main worker process.
    """
    def __init__(self, host, port):
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        self.manager_host = host
        self.manager_port = port
        
        self.kindergarten = Kindergarten()
        self.job_server_factory, self.job_heaven = self.setup()

        self.worker_view = WorkerView(self)
        self.worker_client_factory = WorkerClientFactory(self)

    def login(self, credentials):
        d = self.worker_client_factory.login(credentials)
        d.addErrback(self._cb_accessDenied)
        d.addErrback(self._cb_loginFailed)
                                 
    def setup(self):
        root = JobHeaven(self)
        dispatcher = JobDispatcher(root)
        checker = cred.FlexibleCredentialsChecker()
        checker.allowAnonymous(True)
        p = portal.Portal(dispatcher, [checker])
        job_server_factory = pb.PBServerFactory(p)
        reactor.listenUNIX('/tmp/flumotion.%d' % os.getpid(),
                           job_server_factory)

        return job_server_factory, root

    def _cb_accessDenied(self, failure):
        failure.trap(cred.error.UnauthorizedLogin)
        print 'ERROR: Access denied.'
        reactor.stop()
    
    def _cb_loginFailed(self, failure):
        print 'Login failed, reason: %s' % str(failure)

class JobDispatcher:
    __implements__ = portal.IRealm
    
    def __init__(self, root):
        """
        @type root: L{flumotion.worker.worker.JobHeaven}
        """
        self.root = root
        
    ### portal.IRealm methods
    # flumotion-worker job processes log in to us.
    # The mind is a RemoteReference which allows the brain to call back into
    # the job.
    def requestAvatar(self, avatarId, mind, *interfaces):
        if pb.IPerspective in interfaces:
            avatar = self.root.createAvatar(avatarId)
            reactor.callLater(0, avatar.attached, mind)
            return pb.IPerspective, avatar, avatar.shutdown
        else:
            raise NotImplementedError("no interface")

class Port:
    """
    I am an abstraction of a local TCP port which will be used by GStreamer.
    """
    def __init__(self, number):
        self.number = number
        self.used = False

    def free(self):
        self.used = False

    def use(self):
        self.used = True

    def isFree(self):
        return self.used == False

    def getNumber(self):
        return self.number

    def __repr__(self):
        if self.isFree():
            return '<Port %d (unused)>' % self.getNumber()
        else:
            return '<Port %d (used)>' % self.getNumber()
            
class JobAvatar(pb.Avatar, log.Loggable):
    """
    I am an avatar for the job living in the worker.
    """
    logCategory = 'job-avatar'
    def __init__(self, heaven, name):
        """
        @type heaven: L{flumotion.worker.worker.JobHeaven}
        @type name: string
        """
        
        self.heaven = heaven
        self.name = name
        self.mind = None
        self.debug("created new JobAvatar")
        
        self.feeds = []
            
    def hasRemoteReference(self):
        """
        Check if the avatar has a remote reference to the peer.

        @rtype: boolean
        """
        return self.mind != None

    def attached(self, mind):
        """
        @param mind: reference to the job's JobView on which we can call
        @type mind: L{twisted.spread.pb.RemoteReference}
        
        I am scheduled from the dispatcher's requestAvatar method.
        """
        self.mind = mind
        self.log('Client attached mind %s' % mind)
        host = self.heaven.brain.manager_host
        port = self.heaven.brain.manager_port
        cb = self.mind.callRemote('initial', host, port)
        cb.addCallback(self._cb_afterInitial)

    def _getFreePort(self):
        for port in self.heaven.ports:
            if port.isFree():
                port.use()
                return port

        # XXX: Raise better error message
        raise AssertionError
    
    def _cb_afterInitial(self, unused):
        kid = self.heaven.brain.kindergarten.getKid(self.name)
        # we got kid.config through WorkerView.remote_start from the manager
        feedNames = kid.config.get('feed', [])
        self.log('_cb_afterInitial(): feedNames %r' % feedNames)

        # This is going to be sent to the component
        feedPorts = {} # feedName -> port number
        # This is saved, so we can unmark the ports when shutting down
        self.feeds = []
        for feedName in feedNames:
            port = self._getFreePort()
            feedPorts[feedName] = port.getNumber()
            self.debug('reserving port %r for feed %s' % (port, feedName))
            self.feeds.append((feedName, port))
            
        self.debug('asking job to start with config %r and feedPorts %r' % (kid.config, feedPorts))
        self.mind.callRemote('start', kid.name, kid.type,
                             kid.config, feedPorts)
                                          
    def shutdown(self):
        self.log('%s disconnected' % self.name)
        self.mind = None
        for feed, port in self.feeds:
            port.free()
        self.feeds = []
        
    def stop(self):
        if not self.mind:
            return
        
        return self.mind.callRemote('stop')
        
    def remote_ready(self):
        pass

### this is a different kind of heaven, not IHeaven, for now...
class JobHeaven(pb.Root, log.Loggable):
    logCategory = "job-heaven"
    def __init__(self, brain):
        self.avatars = {}
        self.brain = brain

        # Allocate ports
        start = 5500
        self.ports = []
        for i in range(50):
            self.ports.append(Port(start+i))
        
    def createAvatar(self, avatarId):
        avatar = JobAvatar(self, avatarId)
        self.avatars[avatarId] = avatar
        return avatar

    def shutdown(self):
        cb = None
        for avatar in self.avatars.values():
            new = avatar.stop()
            if cb:
                cb.chainDeferred(new)
                cb = new
        return cb

