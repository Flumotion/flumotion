# -*- Mode: Python; test-case-name:flumotion.test.test_worker_worker -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/worker/worker.py: flumotion-worker objects handling component jobs
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

"""
Worker-side objects to handle worker clients.
"""

import os
import signal
import sys

import gst
from twisted.cred import portal
from twisted.internet import protocol, reactor
from twisted.spread import pb
import twisted.cred.error
import twisted.internet.error

# We want to avoid importing gst, otherwise --help fails
# so be very careful when adding imports
from flumotion.common import errors, interfaces, log
from flumotion.twisted import checkers
from flumotion.twisted import pb as fpb
from flumotion.worker import job
from flumotion.configure import configure

#factoryClass = fpb.ReconnectingPBClientFactory
factoryClass = fpb.FPBClientFactory
class WorkerClientFactory(factoryClass):
    """
    I am a client factory for the worker to log in to the manager.
    """
    #__super_login = factoryClass.startLogin
    __super_login = factoryClass.login
    def __init__(self, brain):
        """
        @type brain: L{flumotion.worker.worker.WorkerBrain}
        """
        self.medium = brain.medium
        # doing this as a class method triggers a doc error
        factoryClass.__init__(self)
        
    def login(self, keycard):
        return self.__super_login(keycard,
                                  self.medium,
                                  interfaces.IWorkerMedium)
        
    def gotPerspective(self, remoteReference):
        self.medium.setRemoteReference(remoteReference)

class WorkerMedium(pb.Referenceable, log.Loggable):
    """
    I am a medium interfacing with the manager-side WorkerAvatar.
    """
    
    logCategory = 'workermedium'

    __implements__ = interfaces.IWorkerMedium,
    
    def __init__(self, brain):
        self.brain = brain
        self.remote = None
        
    def cb_processFinished(self, *args):
        self.debug('processFinished %r' % args)

    def cb_processFailed(self, *args):
        self.debug('processFailed %r' % args)

    ### IMedium methods
    def setRemoteReference(self, remoteReference):
        self.debug('setRemoteReference: %r' % remoteReference)
        self.remote = remoteReference

    def hasRemoteReference(self):
        return self.remote != None

    ### pb.Referenceable method for the manager's WorkerAvatar
    def remote_start(self, name, type, config):
        """
        Start a component of the given type with the given config.

        @param name:   name of the component to start
        @type name:    string
        @param type:   type of the component to start
        @type type:    string
        @param config: a configuration dictionary for the component
        @type config:  dict
        """
        self.info('Starting component "%s" of type "%s"' % (name, type))
        self.debug('remote_start(): manager asked me to start, name %s, type %s, config %r' % (name, type, config))
        self.brain.kindergarten.play(name, type, config)

    def remote_checkElements(self, elementNames):
        """
        Checks if one or more GStreamer elements are present and can be
        instantiated.

        @param elementNames:   names of the Gstreamer elements
        @type elementNames:    list of strings
        """
        self.debug('remote_checkElements: names %r' % (elementNames,))

        return [name for name in elementNames
                         if gst.element_factory_make(name) is not None]

    def remote_runCode(self, codeSegment, variableName):
        """
        runs a segment of code and returns a variable from its namespace

        @param codeSegment:   a piece of code
        @type codeSegment:    string
        @param variableName:  name of variable to return from code executed
        @type variableName:   string
        """
        
        namespace = {}
        exec (codeSegment, globals(), namespace)
        return namespace.get(variableName, None)
        
    
class Kid:
    def __init__(self, pid, name, type, config):
        self.pid = pid 
        self.name = name
        self.type = type
        self.config = config

    # pid = protocol.transport.pid
    def getPid(self):
        return self.pid
    
class Kindergarten(log.Loggable):
    """
    I spawn job processes.
    I live in the worker brain.
    """

    logCategory = 'workerbrain' # thomas: I don't like Kindergarten

    def __init__(self, options):
        """
        @param options: the optparse option instance of command-line options
        @type  options: dict
        """
        dirname = os.path.split(os.path.abspath(sys.argv[0]))[0]
        self.program = os.path.join(dirname, 'flumotion-worker')
        self.kids = {}
        self.options = options
        
    def play(self, name, type, config):
        """
        Make a kid play.
        Starts a component with the given name, of the given type, and
        the given config dictionary.

        @param name:      name of component to start
        @type  name:      string
        @param type:      type of component to start
        @type  type:      string
        """
        
        # This forks and returns the pid
        pid = job.run(name, self.options)
        
        self.kids[name] = Kid(pid, name, type, config)

    def getKid(self, name):
        return self.kids[name]
    
    def getKids(self):
        return self.kids.values()

    def removeKidByPid(self, pid):
        """
        Remove the kid from the kindergarten based on the pid.
        Called by the signal handler in the brain.

        @returns: whether or not a kid with that pid was removed
        @rtype: boolean
        """
        for name, kid in self.kids.items():
            if kid.getPid() == pid:
                self.debug('Removing kid with name %s and pid %d' % (
                    name, pid))
                del self.kids[name]
                return True

        self.warning('Asked to remove kid with pid %d but not found' % pid)
        return False
    
# Similar to Vishnu, but for worker related classes
class WorkerBrain(log.Loggable):
    """
    I manage jobs and everything related.
    I live in the main worker process.
    """

    logCategory = 'workerbrain'

    def __init__(self, options):
        """
        @param options: the optparsed dictionary of command-line options
        @type  options: an object with attributes
        """
        self._oldSIGCHLDHandler = None # stored by installSIGCHLDHandler

        signal.signal(signal.SIGINT, signal.SIG_IGN)

        self.manager_host = options.host
        self.manager_port = options.port
        self.manager_transport = options.transport
        
        self.kindergarten = Kindergarten(options)
        self.job_server_factory, self.job_heaven = self.setup()

        self.medium = WorkerMedium(self)
        self.worker_client_factory = WorkerClientFactory(self)

    def login(self, keycard):
        d = self.worker_client_factory.login(keycard)
        d.addCallback(self._loginCallback)
        d.addErrback(self._cb_accessDenied)
        d.addErrback(self._cb_connectionRefused)
        d.addErrback(self._cb_loginFailed)
                                 
    def setup(self):
        root = JobHeaven(self)
        dispatcher = JobDispatcher(root)
        checker = checkers.FlexibleCredentialsChecker()
        checker.allowAnonymous(True)
        p = portal.Portal(dispatcher, [checker])
        job_server_factory = pb.PBServerFactory(p)
        # FIXME: this is too ugly for words, and doesn't get cleaned up nicely
        reactor.listenUNIX('/tmp/flumotion.%d' % os.getpid(),
                           job_server_factory)

        return job_server_factory, root

    # override log.Loggable method so we don't traceback
    def error(self, message):
        self.warning('Shutting down worker because of error:')
        self.warning(message)
        print >> sys.stderr, 'ERROR: %s' % message
        reactor.stop()
        
    def _loginCallback(self, reference):
        self.info("Logged in to manager")
        self.debug("remote reference %r" % reference)

    def _cb_accessDenied(self, failure):
        failure.trap(twisted.cred.error.UnauthorizedLogin)
        self.error('Access denied.')
        
    def _cb_connectionRefused(self, failure):
        failure.trap(twisted.internet.error.ConnectionRefusedError)
        self.error('Connection to %s:%d refused.' % (self.manager_host,
                                                     self.manager_port))
                                                      
    def _cb_loginFailed(self, failure):
        self.error('Login failed, reason: %s' % str(failure))

    def installSIGCHLDHandler(self):
        """
        Install our own signal handler for SIGCHLD.
        This will call the currently installed one first, then reap
        any leftover zombies.
        """
        handler = signal.signal(signal.SIGCHLD, self._SIGCHLDHandler)
        if handler not in (signal.SIG_IGN, signal.SIG_DFL, None):
            self._oldSIGCHLDHandler = handler

    def _SIGCHLDHandler(self, signal, frame):
        self.debug("handling SIGCHLD")
        if self._oldSIGCHLDHandler:
            self.debug("calling Twisted handler")
            self._oldSIGCHLDHandler(signal, frame)
        (pid, status) = os.waitpid(-1, os.WNOHANG)
        if pid:
            # remove from the kindergarten
            self.kindergarten.removeKidByPid(pid)

            # check if it exited nicely
            if os.WIFEXITED(status):
                retval = os.WEXITSTATUS(status)
                self.info("Reaped child job with pid %d, exit value %d" % (
                    pid, retval))
            else:
                self.info("Reaped job child with pid %d and unhandled status %d" % (
                    pid, status))
        

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
        return self.used is False

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
        @param mind: reference to the job's JobMedium on which we can call
        @type mind: L{twisted.spread.pb.RemoteReference}
        
        I am scheduled from the dispatcher's requestAvatar method.
        """
        self.mind = mind
        self.log('Client attached mind %s' % mind)
        host = self.heaven.brain.manager_host
        port = self.heaven.brain.manager_port
        transport = self.heaven.brain.manager_transport
        cb = self.mind.callRemote('initial', host, port, transport)
        cb.addCallback(self._cb_afterInitial)

    def _getFreePort(self):
        for port in self.heaven.ports:
            if port.isFree():
                port.use()
                return port

        # XXX: Raise better error message
        raise AssertionError
    
    def _defaultErrback(self, failure):
        self.warning('unhandled remote error: type %s, message %s' % (
            failure.type, failure.getErrorMessage()))
        
    def _startErrback(self, failure, name, type):
        failure.trap(errors.ComponentStart)
        self.warning('could not start component %s of type %s: %r' % (
            name, type, failure.getErrorMessage()))

    def _cb_afterInitial(self, unused):
        kid = self.heaven.brain.kindergarten.getKid(self.name)
        # we got kid.config through WorkerMedium.remote_start from the manager
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
        d = self.mind.callRemote('start', kid.name, kid.type,
                                 kid.config, feedPorts)
        d.addErrback(self._startErrback, kid.name, kid.type)
        d.addErrback(self._defaultErrback)
                                          
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

        # FIXME: use and option from the command line for port range
        # Allocate ports
        self.ports = []
        for port in configure.defaultGstPortRange:
            self.ports.append(Port(port))
        
    def createAvatar(self, avatarId):
        avatar = JobAvatar(self, avatarId)
        self.avatars[avatarId] = avatar
        return avatar

    def shutdown(self):
        for avatar in self.avatars.values():
            avatar.stop()

