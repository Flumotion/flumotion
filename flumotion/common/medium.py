# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from twisted.spread import pb
from twisted.internet import defer

from flumotion.twisted.defer import defer_generator_method
from flumotion.common import log, interfaces, bundleclient, errors, common

class BaseMedium(pb.Referenceable, log.Loggable):
    """
    I am a base interface for PB client-side mediums interfacing with
    manager-side avatars.
    """

    # subclasses will need to set this to the specific medium type
    # tho...
    __implements__ = interfaces.IMedium,

    remote = None
    bundleLoader = None

    def setRemoteReference(self, remoteReference):
        """
        @param remoteReference: L{twisted.spread.pb.RemoteReference}
        """
        self.debug('%r.setRemoteReference: %r' % (self, remoteReference))
        self.remote = remoteReference
        def nullRemote(x):
            self.info('%r: disconnected from %r' % (self, self.remote))
            self.remote = None
        self.remote.notifyOnDisconnect(nullRemote)

        self.bundleLoader = bundleclient.BundleLoader(self.remote)

        # figure out connection addresses if it's an internet address
        tarzan = None
        jane = None
        try:
            transport = remoteReference.broker.transport
            tarzan = transport.getHost()
            jane = transport.getPeer()
        except Exception, e:
            self.debug("could not get connection info, reason %r" % e)
        if tarzan and jane:
            self.debug("connection is from me on %s to manager on %s" % (
                common.addressGetHost(tarzan),
                common.addressGetHost(jane)))

    def hasRemoteReference(self):
        return self.remote != None

    def callRemote(self, name, *args, **kwargs):
        if not self.remote:
            self.warning('Tried to callRemote(%s), but we are disconnected'
                         % name)
            return None
        
        def errback(failure):
            # shouldn't be a warning, since this a common occurrence
            # when running worker tests
            self.debug('callRemote(%s) failed: %r' % (name, failure))
            failure.trap(pb.PBConnectionLost)
        d = self.remote.callRemote(name, *args, **kwargs)
        d.addErrback(errback)
        return d

    def loadModule(self, moduleName):
        return self.bundleLoader.loadModule(moduleName)

    def run_bundled_proc(self, modname, procname, *args, **kwargs):
        try:
            d = self.loadModule(modname)
            yield d
            mod = d.value()
        except Exception, e:
            import traceback
            traceback.print_exc()
            self.warning('Failed to load bundle %s: %s' % (modname, e))
            yield None

        try:
            proc = getattr(mod, procname)
        except AttributeError:
            self.warning('No procedure named %s in module %s' %
                         (procname, modname))
            yield None

        try:
            self.debug('calling %r(%r, %r)' % (proc, args, kwargs))
            d = proc(*args, **kwargs)
            yield d
            # only if d was actually a deferred will we get here
            # this is a bit nasty :/
            yield d.value()
        except Exception, e:
            msg = ('%s.%s(*args=%r, **kwargs=%r) failed: %s raised: %s'
                   % (modname, procname, args, kwargs,
                      e.__class__.__name__, e.__str__()))
            self.debug(msg)
            raise e
    run_bundled_proc = defer_generator_method(run_bundled_proc)
