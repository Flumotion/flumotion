# -*- Mode: Python; test-case-name: flumotion.test.test_bouncers_ipbouncer -*-
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

"""
A bouncer that authenticates based on the IP address of the remote side,
as seen by the bouncer.
"""

from flumotion.common import keycards, messages, errors, log, netutils
from flumotion.common.i18n import N_, gettexter
from flumotion.component.bouncers.algorithms import base

__all__ = ['IPBouncerAlgorithm']
__version__ = "$Rev$"
T_ = gettexter()


class IPBouncerAlgorithm(base.BouncerAlgorithm):

    logCategory = 'ip-bouncer'
    volatile = False

    def get_namespace(self):
        return 'ipbouncer'

    def start(self, component):
        self.props = self.args['properties']
        self.deny_default = self.props.get('deny-default', True)

        self.allows = netutils.RoutingTable()
        self.denies = netutils.RoutingTable()
        for p, t in (('allow', self.allows), ('deny', self.denies)):
            for s in self.props.get(p, []):
                try:
                    ip, mask = s.split('/')
                    t.addSubnet(True, ip, int(mask))
                except Exception, e:
                    m = messages.Error(
                        T_(N_("Invalid value for property %r: %s"), p, s),
                        log.getExceptionMessage(e),
                        mid='match-type')
                    component.addMessage(m)
                    raise errors.ComponentSetupHandledError()

    def authenticate(self, keycard):
        ip = keycard.getData()['address']
        self.debug('authenticating keycard from requester %s', ip)

        if ip is None:
            self.warning('could not get address of remote')
            allowed = False
        elif self.deny_default:
            allowed = (self.allows.route(ip)
                       and not self.denies.route(ip))
        else:
            allowed = (self.allows.route(ip)
                       or not self.denies.route(ip))

        if not allowed:
            self.info('denied login from ip address %s',
                      keycard.address)
            return None
        else:
            keycard.state = keycards.AUTHENTICATED
            self.debug('allowed login from ip address %s',
                       keycard.address)
            return keycard
