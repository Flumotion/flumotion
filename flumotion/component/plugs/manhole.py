# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2006 Fluendo, S.L. (www.fluendo.com).
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

import os
from twisted.internet import defer

from flumotion.component.plugs import base
from flumotion.common.manhole import openSSHManhole
from flumotion.common.manhole import openAnonymousTelnetManhole

__version__ = "$Rev$"


class ManholeMixin(object):
    """
    """

    def __init__(self, args):

        self.useSSH = False
        self.authorizedKeysFile = None
        self.port = None
        self.requestedPortNum = None
        self.namespace = {}

    def start(self, namespace):
        self.namespace.update(namespace)
        props = self.args['properties']
        if 'ssh-authorized-keys-file' in props:
            self.useSSH = True
            self.authorizedKeysFile = os.path.expanduser(
                props['ssh-authorized-keys-file'])

        self.requestedPortNum = props.get('port', -1)

        self._insinuate()

        if props.get('initially-open', False):
            self.openManhole()

    def stop(self, obj):
        self.closeManhole()

    def _insinuate(self):
        # "And I wish you didn't have the devil's curly hair!"
        from flumotion.manager.admin import AdminAvatar
        AdminAvatar.perspective_openManhole = self.openManhole
        AdminAvatar.perspective_closeManhole = self.closeManhole

    def openManhole(self):
        if not self.port:
            if self.useSSH:
                self.port = openSSHManhole(self.authorizedKeysFile,
                                           self.namespace,
                                           self.requestedPortNum)
            else:
                self.port = openAnonymousTelnetManhole(self.namespace,
                                                       self.requestedPortNum)

        return self.port.getHost().port

    def closeManhole(self):
        if self.port:
            ret = self.port.loseConnection()
        else:
            ret = defer.succeed(None)
        self.port = None
        return ret


class ManagerManholePlug(base.ManagerPlug, ManholeMixin):

    def __init__(self, args):
        base.ManagerPlug.__init__(self, args)
        ManholeMixin.__init__(self, args)

    def start(self, vishnu):
        namespace = {'vishnu': vishnu}
        ManholeMixin.start(self, namespace)


class ComponentManholePlug(base.ComponentPlug, ManholeMixin):

    def __init__(self, args):
        base.ComponentPlug.__init__(self, args)
        ManholeMixin.__init__(self, args)

    def start(self, component):
        namespace = {'component': component}
        ManholeMixin.start(self, namespace)
