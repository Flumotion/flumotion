# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/component.py: basic component functionality
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
Worker-side objects for components.
"""

import os
import sys
import socket

import gobject

from twisted.internet import reactor, error
from twisted.cred import error as crederror
from twisted.spread import pb

from flumotion.common import interfaces, errors, log
from flumotion.twisted import credentials
from flumotion.twisted import pb as fpb
from flumotion.utils import gstutils
from flumotion.utils.gstutils import gsignal

# FIXME: make the superklass reconnecting ?
superklass = fpb.FPBClientFactory
# the client factory logging in to the manager
class ComponentClientFactory(superklass):
    """
    I am a client factory for a component logging in to the manager.
    """
    logCategory = 'component'
    __super_login = superklass.login
    def __init__(self, component):
        """
        @param component: L{flumotion.component.component.BaseComponent}
        """
        # doing this as a class method triggers a doc error
        super_init = superklass.__init__
        super_init(self)
        
        # get the component's medium class, defaulting to the base one
        klass = getattr(component, 'component_medium_class', BaseComponentMedium)
        # instantiate the medium, giving it the component it's a medium for
        self.medium = klass(component)
        component.setMedium(self.medium)

        # get the interfaces implemented by the component medium class
        self.interfaces = getattr(klass, '__implements__', ())
        
    # override log.Loggable method so we don't traceback
    def error(self, message):
        self.warning('Shutting down because of %s' % message)
        print >> sys.stderr, 'ERROR: %s' % message
        # FIXME: do we need to make sure that this cannot shut down the
        # manager if it's the manager's bouncer ?
        reactor.stop()

    def login(self, keycard):
        d = self.__super_login(keycard, self.medium,
                               interfaces.IComponentMedium)
        d.addCallback(self._loginCallback)
        d.addErrback(self._unauthorizedLoginErrback)
        d.addErrback(self._connectionRefusedErrback)
        d.addErrback(self._loginErrback)
        return d
        
    # this method receives a RemoteReference
    # it can't tell if it's from an IPerspective implementor, Viewpoint or
    # Referenceable
    def _loginCallback(self, remoteReference):
        """
        @param remoteReference: an object on which we can callRemote to the
                                manager's avatar
        @type remoteReference: L{twisted.spread.pb.RemoteReference}
        """
        self.medium.setRemoteReference(remoteReference)

    def _unauthorizedLoginErrback(self, failure):
        failure.trap(crederror.UnauthorizedLogin)
        self.error('Unauthorized login.')
                                                                                
    def _connectionRefusedErrback(self, failure):
        failure.trap(error.ConnectionRefusedError)
        self.error('Connection to %s:%d refused.' % (self.manager_host,
                                                     self.manager_port))
                                                                                
    def _loginErrback(self, failure):
        self.error('Login failed, reason: %r' % failure)
    
# needs to be before BaseComponent because BaseComponent references it
class BaseComponentMedium(pb.Referenceable, log.Loggable):
    """
    I am a medium interfacing with a manager-side avatar.
    I implement a Referenceable for the manager's avatar to call on me.
    I have a remote reference to the manager's avatar to call upon.
    """

    __implements__ = interfaces.IComponentMedium,
    logCategory = 'basecomponentmedium'

    def __init__(self, component):
        """
        @param component: L{flumotion.component.component.BaseComponent}
        """
        self.comp = component
        self.comp.connect('log', self._component_log_cb)
        
        self.remote = None # the perspective we have on the other side (?)
        
    ### log.Loggable methods
    def logFunction(self, arg):
        return self.comp.get_name() + ':' + arg

    ### IMedium methods
    def setRemoteReference(self, remoteReference):
        self.remote = remoteReference
        
    def hasRemoteReference(self):
        return self.remote != None

    # call function on remote perspective in manager
    def callRemoteErrback(self, failure):
        self.warning('callRemote failed because of %r' % failure)
        failure.trap(pb.PBConnectionLost)
        
    def callRemote(self, name, *args, **kwargs):
        """
        @returns: a deferred
        """
        if not self.hasRemoteReference():
            self.debug('skipping %s, no perspective' % name)
            return

        #def errback(reason):
        #    self.warning('stopping pipeline because of %s' % reason)
        #    self.comp.pipeline_stop()

        try:
            d = self.remote.callRemote(name, *args, **kwargs)
        except pb.DeadReferenceError:
            return
        
        d.addErrback(self.callRemoteErrback)
        return d

    ### our methods
    def getIP(self):
        assert self.remote
        peer = self.remote.broker.transport.getPeer()
        try:
            host = peer.host
        except AttributeError:
            host = peer[1]

        return socket.gethostbyname(host)

    def _component_log_cb(self, component, args):
        self.callRemote('log', *args)
        
    ### pb.Referenceable remote methods
    ### called from manager by our avatar
    def remote_getUIZip(self, domain, style):
        return self.comp.getUIZip(domain, style)
    
    def remote_getUIMD5Sum(self, domain, style):
        return self.comp.getUIMD5Sum(domain, style)

    def remote_register(self):
        """
        @rtype:   dict
        @returns: options
        """
        # FIXME: we need to properly document this; manager calls me to
        # "get some info"
        if not self.hasRemoteReference():
            self.warning('We are not ready yet, waiting 250 ms')
            reactor.callLater(0.250, self.remote_register)
            return None

        options = {'ip' : self.getIP(),
                   'pid' :  os.getpid()}

        return options
        
    def remote_reloadComponent(self):
        """Reload modules in the component."""
        import sys
        from twisted.python.rebuild import rebuild
        from twisted.python.reflect import filenameToModuleName
        name = filenameToModuleName(__file__)

        # reload ourselves first
        rebuild(sys.modules[name])

        # now rebuild relevant modules
        import flumotion.utils.reload
        rebuild(sys.modules['flumotion.utils'])
        try:
            flumotion.utils.reload.reload()
        except SyntaxError, msg:
            raise errors.ReloadSyntaxError(msg)
        self._reloaded()

    # separate method so it runs the newly reloaded one :)
    def _reloaded(self):
        self.info('reloaded module code for %s' % __name__)

    def remote_callMethod(self, method_name, *args, **kwargs):
        method = getattr(self.comp, 'remote_' + method_name, None)
        if method:
            return method(*args, **kwargs)

        # XXX: Raise

class BaseComponent(log.Loggable, gobject.GObject):
    """
    I am the base class for all Flumotion components.
    """

    __remote_interfaces__ = interfaces.IComponentMedium,
    logCategory = 'basecomponent'

    gsignal('log', object)

    component_medium_class = BaseComponentMedium
    
    def __init__(self, name):
        """
        @param name: unique name of the component
        @type name: string
        """
        self.__gobject_init__()
        
        # FIXME: rename to .name
        self.component_name = name
        self.medium = None # the medium connecting us to the manager's avatar
        self._uiBundlers = {}

    ### Loggable methods
    def logFunction(self, arg):
        return self.get_name() + ' ' + arg

    ### GObject methods
    def emit(self, name, *args):
        if 'uninitialized' in str(self):
            self.warning('Uninitialized object!')
            #self.__gobject_init__()
        else:
            gobject.GObject.emit(self, name, *args)
        
    ### BaseComponent methods
    # FIXME: rename to getName
    def get_name(self):
        return self.component_name

    def setMedium(self, medium):
        assert isinstance(medium, BaseComponentMedium)
        self.medium = medium

    def addUIBundler(self, bundler, domain, style):
        """
        Add a bundler of UI files for the given domain and style.

        @type bundler: L{flumotion.common.bundle.Bundler}
        @type domain: string
        @type style: string
        """
        if not self._uiBundlers.has_key(domain):
            self._uiBundlers[domain] = {}
        self._uiBundlers[domain][style] = bundler

    def getUIMD5Sum(self, domain, style):
        if not self._uiBundlers.has_key(domain):
            return None
        if not self._uiBundlers[domain].has_key(style):
            return None
        return self._uiBundlers[domain][style].bundle().md5sum

    def getUIZip(self, domain, style):
        if not self._uiBundlers.has_key(domain):
            return None
        if not self._uiBundlers[domain].has_key(style):
            return None
        return self._uiBundlers[domain][style].bundle().zip

gobject.type_register(BaseComponent)
