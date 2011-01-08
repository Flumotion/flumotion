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

import time

from flumotion.common import errors
from flumotion.component.plugs import base

__version__ = "$Rev$"


class AdminActionPlug(base.ManagerPlug):
    """
    Base class for plugs that can react to actions by an admin. For
    example, some plugs might want to check that the admin in question
    has the right permissions, and some others might want to log the
    action to a database. Defines the admin action API methods.
    """

    def action(self, identity, method, args, kwargs):
        """
        @type  identity: L{flumotion.common.identity.Identity}
        @type  method:   str
        @type  args:     list
        @type  kwargs:   dict
        """
        raise NotImplementedError('subclasses have to override me')


class AdminActionLoggerFilePlug(AdminActionPlug):
    filename = None
    file = None

    def start(self, vishnu):
        self.filename = self.args['properties']['logfile']
        try:
            self.file = open(self.filename, 'a')
        except IOError, data:
            raise errors.PropertyError('could not open log file %s '
                                         'for writing (%s)'
                                         % (self.filename, data[1]))

    def stop(self, vishnu):
        self.file.close()
        self.file = None

    def action(self, identity, method, args, kwargs):
        # gaaaaah
        s = ('[%04d-%02d-%02d %02d:%02d:%02d] %s: %s: %r %r\n'
             % (time.gmtime()[:6] +
                ((identity, method, args, kwargs))))
        self.file.write(s)
        self.file.flush()
