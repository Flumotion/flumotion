# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/component.py: basic component functionality
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
import socket

import gobject

from twisted.internet import reactor
from twisted.spread import pb

from flumotion.common import interfaces, errors
from flumotion.twisted import cred, pbutil
from flumotion.utils import log, gstutils
from flumotion.utils.gstutils import gsignal

class ComponentClientFactory(pbutil.ReconnectingPBClientFactory):
    __super_login = pbutil.ReconnectingPBClientFactory.startLogin
    def __init__(self, component):
        # doing this as a class method triggers a doc error
        super_init = pbutil.ReconnectingPBClientFactory.__init__
        super_init(self)
        
        # get the component's view class, defaulting to the base one
        klass = getattr(component, 'component_view_class', BaseComponentView)
        self.view = klass(component)
        # get the interfaces implemented by the component view class
        self.interfaces = getattr(klass, '__implements__', ())
        
    def login(self, username):
        self.__super_login(cred.Username(username),
                           self.view,
                           pb.IPerspective,
                           *self.interfaces)
        
    def gotPerspective(self, perspective):
        self.view.cb_gotPerspective(perspective)
    
# needs to be before BaseComponent because BaseComponent references it
class BaseComponentView(pb.Referenceable, log.Loggable):
    """
    I implement a worker-side view on a BaseComponent for the managing
    ComponentAvatar to call upon.
    """
    __implements__ = interfaces.IComponentView,
    logCategory = 'basecomponentview'

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

    # call function on remote perspective in manager
    def callRemoteErrback(self, reason):
            self.warning('callRemote failed because of %s' % reason)

    def callRemote(self, name, *args, **kwargs):
        if not self.hasPerspective():
            self.debug('skipping %s, no perspective' % name)
            return

        def errback(reason):
            self.warning('stopping pipeline because of %s' % reason)
            self.comp.pipeline_stop()

        try:
            cb = self.remote.callRemote(name, *args, **kwargs)
        except pb.DeadReferenceError:
            return
        
        cb.addErrback(self.callRemoteErrback)

    def cb_gotPerspective(self, perspective):
        self.remote = perspective
        
    def hasPerspective(self):
        return self.remote != None

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
        
    ### Referenceable remote methods which can be called from manager
    def remote_getUIZip(self, style):
        return self.comp.getUIZip(style)
    
    def remote_getUIMD5Sum(self, style):
        return self.comp.getUIMD5Sum(style)

    def remote_register(self):
        # FIXME: we need to properly document this; manager calls me to
        # "get some info"
        if not self.hasPerspective():
            self.warning('We are not ready yet, waiting 250 ms')
            reactor.callLater(0.250, self.remote_register)
            return None

        return {'ip' : self.getIP(),
                'pid' :  os.getpid()}
        
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

    __remote_interfaces__ = interfaces.IComponentView,
    logCategory = 'basecomponent'

    gsignal('log', object)

    component_view_class = BaseComponentView
    
    def __init__(self, name):
        """
        @param name: unique name of the component
        @type name: string
        """
        self.__gobject_init__()
        
        # FIXME: rename to .name
        self.component_name = name

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
    def get_name(self):
        return self.component_name
gobject.type_register(BaseComponent)
