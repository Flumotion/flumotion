# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# manager/component.py: manager-side objects to handle components
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

"""
Manager-side objects for components.

API Stability: semi-stable

Maintainer: U{Johan Dahlin <johan@fluendo.com>}
"""

__all__ = ['ComponentAvatar']

import gst

from twisted.internet import reactor
from twisted.python import components
from twisted.spread import pb

from flumotion.common import errors
from flumotion.twisted import pbutil
from flumotion.utils import gstutils, log

class Options:
    """dummy class for storing manager side options of a component"""

class ComponentAvatar(pb.Avatar, log.Loggable):
    """
    Manager-side avatar for a component.
    Each component that logs in to the manager gets an avatar created for it
    in the manager.
    """

    logCategory = 'comp-avatar'

    def __init__(self, manager, username):
        self.manager = manager
        self.username = username
        self.state = gst.STATE_NULL
        self.options = Options()
        self.listen_ports = {}
        self.started = False
        self.starting = False
        
    ### python methods
    def __repr__(self):
        return '<%s %s in state %s>' % (self.__class__.__name__,
                                        self.getName(),
                                        gst.element_state_get_name(self.state))

    ### log.Loggable methods
    def logFunction(self, arg):
        return self.getName() + ': ' + arg

    ### ComponentAvatar methods

    # mind functions
    def _mindCallRemote(self, name, *args, **kwargs):
        self.debug('calling remote method %s%r' % (name, args))
        try:
            return self.mind.callRemote(name, *args, **kwargs)
        except pb.DeadReferenceError:
            self.mind = None
            self.detached()
            return

    # general fallback for unhandled errors so we detect them
    # FIXME: we can't use this since we want a PropertyError to fall through
    # afger going through the PropertyErrback.
    def _mindErrback(self, failure, ignores = None):
        if ignores:
            for ignore in ignores:
                if isinstance(failure, ignore):
                    return failure
        self.warning("Unhandled remote call error: %s" % failure.getErrorMessage())
        self.warning("raising '%s'" % str(failure.type))
        return failure

    # we create this errback just so we can interject a message inbetween
    # to make it clear the Traceback line is fine.
    # When this is fixed in Twisted we can just remove the errback and
    # the error will still get sent back correctly to admin.
    def _mindPropertyErrback(self, failure):
        failure.trap(errors.PropertyError)
        print "Ignore the following Traceback line, issue in Twisted"
        return failure

    def _mindRegisterCallback(self, options):
        for key, value in options.items():
            setattr(self.options, key, value)
        self.options.dict = options
        
        self.manager.componentRegistered(self)
                
    def _mindPipelineErrback(self, failure):
        failure.trap(errors.PipelineParseError)
        self.error('Invalid pipeline for component')
        self._mindCallRemote('stop')
        return None

    def attached(self, mind):
        """
        Tell the avatar that the given mind has been attached.
        This gives the avatar a way to call remotely to the client that
        requested this avatar.
        This is scheduled by the portal after the client has logged in.

        @type mind: L{twisted.spread.pb.RemoteReference}
        """
        self.debug('mind attached, calling remote register()')
        self.mind = mind
        
        d = self._mindCallRemote('register')
        d.addCallback(self._mindRegisterCallback)
        d.addErrback(self._mindPipelineErrback)
        d.addErrback(self._mindErrback)
        
    def detached(self, mind=None):
        """
        Tell the avatar that the given mind has been detached.

        @type mind: L{twisted.spread.pb.RemoteReference}
        """
        self.debug('detached')
        name = self.getName()
        if self.manager.hasComponent(name):
            self.manager.removeComponent(self)

    # functions
    def getTransportPeer(self):
        """
        Get the IPv4 address of the machine the component runs on.
        """
        return self.mind.broker.transport.getPeer()

    def getEaters(self):
        """
        Returns a list of names of feeded elements.
        """
        return self.options.eaters
    
    def getFeeders(self, longname=False):
        """
        Returns a list of names of feeding elements.
        """
        if longname:
            return map(lambda feeder:
                       self.getName() + ':' + feeder, self.options.feeders)
        else:
            return self.options.feeders

    def getRemoteManagerIP(self):
        return self.options.ip

    def getName(self):
        return self.username

    def getListenHost(self):
        return self.getTransportPeer()[1]

    # This method should ask the component if the port is free
    def getListenPort(self, feeder):
        if feeder.find(':') != -1:
            feeder = feeder.split(':')[1]

        assert self.listen_ports.has_key(feeder), self.listen_ports
        assert self.listen_ports[feeder] != -1, self.listen_ports
        return self.listen_ports[feeder]

    def stop(self):
        """
        Tell the avatar to stop the component.
        """
        d = self._mindCallRemote('stop')
        d.addErrback(lambda x: None)
            
    def link(self, eaters, feeders):
        """
        Tell the component to link itself to other components.

        @type eaters: tuple of (name, host, port) tuples of feeded elements.
        @type feeders: tuple of (name, host, port) tuples of feeding elements.
        """
        def _getFreePortsCallback((feeders, ports)):
            self.listen_ports = ports
            d = self._mindCallRemote('link', eaters, feeders)
            d.addErrback(self._mindErrback)

        if feeders:
            d = self._mindCallRemote('getFreePorts', feeders)
            d.addCallbacks(_getFreePortsCallback, self._mindErrback)
        else:
            d = self._mindCallRemote('link', eaters, [])
            d.addErrback(self._mindErrback)
    
    def setElementProperty(self, element, property, value):
        """
        Set a property on an element.

        @type element: string
        @param element: the element to set the property on
        @type property: string
        @param property: the property to set
        @type value: mixed
        @param value: the value to set the property to
        """
        if not element:
            msg = "%s: no element specified" % self.getName()
            self.warning(msg)
            raise errors.PropertyError(msg)
        if not element in self.options.elements:
            msg = "%s: element '%s' does not exist" % (self.getName(), element)
            self.warning(msg)
            raise errors.PropertyError(msg)
        if not property:
            msg = "%s: no property specified" % self.getName()
            self.warning(msg)
            raise errors.PropertyError(msg)
        self.debug("setting property '%s' on element '%s'" % (property, element))
        
        cb = self._mindCallRemote('setElementProperty', element, property, value)
        cb.addErrback(self._mindPropertyErrback)
        cb.addErrback(self._mindErrback, (errors.PropertyError, ))
        return cb
        
    def getElementProperty(self, element, property):
        """
        Get a property of an element.

        @type element: string
        @param element: the element to get the property of
        @type property: string
        @param property: the property to get
        """
        if not element:
            msg = "%s: no element specified" % self.getName()
            self.warning(msg)
            raise errors.PropertyError(msg)
        if not element in self.options.elements:
            msg = "%s: element '%s' does not exist" % (self.getName(), element)
            self.warning(msg)
            raise errors.PropertyError(msg)
        if not property:
            msg = "%s: no property specified" % self.getName()
            self.warning(msg)
            raise errors.PropertyError(msg)
        self.debug("getting property %s on element %s" % (element, property))
        cb = self._mindCallRemote('getElementProperty', element, property)
        cb.addErrback(self._mindPropertyErrback)
        cb.addErrback(self._mindErrback, (errors.PropertyError, ))
        return cb

    def callComponentRemote(self, method, *args, **kwargs):
        """
        Call a remote method on the component.
        This is used so that admin clients can call methods from the interface
        to the component.

        @type method: string
        @param method: the method to call.  On the component, this calls
         component_(method)
        @type args: mixed
        @type kwargs: mixed
        """
        self.debug("calling component method %s" % method)
        cb = self._mindCallRemote('callMethod', method, *args, **kwargs)
        cb.addErrback(self._mindErrback, (Exception, ))
        return cb
        
    def _reloadComponentErrback(self, failure):
        import exceptions
        failure.trap(errors.ReloadSyntaxError)
        self.warning(failure.getErrorMessage())
        return failure

    def reloadComponent(self):
        """
        Tell the component to reload itself.

        @rtype: L{twisted.internet.defer.Deferred}
        """
        cb = self._mindCallRemote('reloadComponent')
        cb.addErrback(self._reloadComponentErrback)
        cb.addErrback(self._mindErrback, (errors.ReloadSyntaxError, ))
        return cb

    def getUIEntry(self):
        """
        Request the UI entry for the component's UI.
        The deferred returned will receive the code to run the UI.

        @rtype: L{twisted.internet.defer.Deferred}
        """
        self.debug('calling remote getUIEntry')
        cb = self._mindCallRemote('getUIEntry')
        cb.addErrback(self._mindErrback)
        return cb
    
    ### IPerspective methods
    def perspective_log(self, *msg):
        log.debug(self.getName(), *msg)
        
    def perspective_stateChanged(self, feeder, state):
        self.debug('stateChanged: %s %s' % (feeder, gst.element_state_get_name(state)))
        
        self.state = state
        if self.state == gst.STATE_PLAYING:
            self.info('is now playing')

        if self.getFeeders():
            self.manager.startPendingComponents(self, feeder)
            
    def perspective_error(self, element, error):
        self.error('error element=%s string=%s' % (element, error))
        self.manager.removeComponent(self)

    def perspective_uiStateChanged(self, component_name, state):
        self.manager.adminheaven.uiStateChanged(component_name, state)
