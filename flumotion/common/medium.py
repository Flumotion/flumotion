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

from flumotion.common import log, interfaces, bundleclient, errors


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
        self.debug('%r.setRemoteReference: %r' % (self, remoteReference))
        self.remote = remoteReference
        def nullRemote(x):
            self.info('%r: disconnected from %r' % (self, self.remote))
            self.remote = None
        self.remote.notifyOnDisconnect(nullRemote)
        self.bundleLoader = bundleclient.BundleLoader(self.remote)

    def hasRemoteReference(self):
        return self.remote != None

    def callRemote(self, name, *args, **kwargs):
        if not self.remote:
            self.warning('Tried to callRemote(%s), but we are disconnected'
                         % name)
            return None
        
        def errback(failure):
            self.warning('callRemote(%s) failed: %r' % (name, failure))
            failure.trap(pb.PBConnectionLost)
        d = self.remote.callRemote(name, *args, **kwargs)
        d.addErrback(errback)
        return d
