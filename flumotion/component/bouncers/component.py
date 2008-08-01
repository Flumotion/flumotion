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

from flumotion.component import component

__all__ = ['Bouncer']
__version__ = "$Rev$"


class BouncerMedium(component.BaseComponentMedium):

    logCategory = 'bouncermedium'

    def remote_authenticate(self, keycard):
        """
        Authenticates the given keycard.

        @type  keycard: L{flumotion.common.keycards.Keycard}
        """
        return self.comp.authenticate(keycard)

    def remote_keepAlive(self, issuerName, ttl):
        """
        Resets the expiry timeout for keycards issued by issuerName.

        @param issuerName: the issuer for which keycards should be kept
                           alive; that is to say, keycards with the
                           attribute 'issuerName' set to this value will
                           have their ttl values reset.
        @type  issuerName: str
        @param ttl: the new expiry timeout
        @type  ttl: number
        """
        return self.comp.keepAlive(issuerName, ttl)

    def remote_removeKeycardId(self, keycardId):
        try:
            self.comp.removeKeycardId(keycardId)
        # FIXME: at least have an exception name please
        except KeyError:
            self.warning('Could not remove keycard id %s' % keycardId)

    def remote_expireKeycardId(self, keycardId):
        """
        Called by bouncer views to expire keycards.
        """
        return self.comp.expireKeycardId(keycardId)

    def remote_setEnabled(self, enabled):
        return self.comp.setEnabled(enabled)


BOUNCER_SOCKET = 'flumotion.component.bouncers.plug.BouncerPlug'


class Bouncer(component.BaseComponent):
    """
    I am the base class for all bouncers.
    """
    componentMediumClass = BouncerMedium
    logCategory = 'bouncer'

    def init(self):
        self.plug = None

    def do_setup(self):
        assert len(self.plugs[BOUNCER_SOCKET]) == 1
        self.plug = self.plugs[BOUNCER_SOCKET][0]

    def setMedium(self, medium):
        component.BaseComponent.setMedium(self, medium)
        self.plug.setMedium(self.medium)

    def authenticate(self, keycard):
        return self.plug.authenticate(keycard)

    def setEnabled(self, enabled):
        self.plug.setEnabled(enabled)

    def hasKeycard(self, keycard):
        return self.plug.hasKeycard(keycard)

    def removeKeycard(self, keycard):
        self.plug.removeKeycard(keycard)

    def removeKeycardId(self, id):
        self.plug.removeKeycardId(id)

    def keepAlive(self, issuerName, ttl):
        self.plug.keepAlive(issuerName, ttl)
