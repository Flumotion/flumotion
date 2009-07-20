# -*- Mode: Python -*-
# -*- Encoding: UTF-8 -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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
import urllib

from flumotion.common import python
from flumotion.component.plugs import base

__version__ = "$Rev$"


class RequestModifierPlug(base.ComponentPlug):
    """
    Base class for HTTP request modifier plug implementations.
    """

    def modify(self, request):
        """
        Modify an HTTP request.
        Can be used to modify the HTTP response.

        @param request: the request to modify
        @type request: twisted.web.server.Request
        """
        pass


class RequestModifierForceDownloadPlug(RequestModifierPlug):

    logCategory = 'forcedownload'

    def start(self, component):
        properties = self.args['properties']
        self._argument = properties['argument-name']
        self._triggers = python.set(properties.get('trigger-value', ['1']))
        self.log("Argument name: %s", self._argument)
        self.log("Trigger values: %s", self._triggers)

    def modify(self, request):
        if self._argument in request.args:
            if self._triggers & python.set(request.args[self._argument]):
                filename = os.path.basename(urllib.unquote_plus(request.path))
                filename = filename.encode('UTF-8')
                filename = urllib.quote(filename)
                header = "attachment; filename*=utf-8''%s" % filename
                request.setHeader('Content-Disposition', header)
