# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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
import string

from flumotion.component import component
from flumotion.common import log, messages, errors
from flumotion.component.component import moods
from flumotion.component.misc.porter import porterclient
from twisted.web import resource, static, server
from twisted.internet import defer, reactor, error
from flumotion.twisted import fdserver
from twisted.cred import credentials

from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

class HTTPFileStreamer(component.BaseComponent, log.Loggable):
    def init(self):
        self.mountPoint = None
        self.type = None
        self.port = None

    def do_setup(self):
        props = self.config['properties']
        mountPoint = props.get('mount_point', '')
        if not mountPoint.startswith('/'):
            mountPoint = '/' + mountPoint
        self.mountPoint = mountPoint
        self.filePath = props.get('path')
        self.type = props.get('type', 'master')
        self.port = props.get('port', None)
        if self.type == 'slave':
            # already checked for these in do_check
            self._porterPath = props['porter_socket_path']
            self._porterUsername = props['porter_username']
            self._porterPassword = props['porter_password']
        
    def do_stop(self):
        if self.type == 'slave':
            return self._pbclient.deregisterPath(self.mountPoint)
        return component.BaseComponent.do_stop(self)

    def do_start(self, *args, **kwargs):
        #root = HTTPRoot()
        root = resource.Resource()
        # TwistedWeb wants the child path to not include the leading /
        mount = self.mountPoint[1:]
        # split path on / and add iteratively twisted.web resources
        children = string.split(mount, '/')
        current_resource = root
        for child in children[:-1]:
            res = resource.Resource()
            current_resource.putChild(child, res)
            current_resource = res
        current_resource.putChild(children[-1:][0], static.File(self.filePath))
        #root.putChild(mount, HTTPStaticFile(self.filePath))
        d = defer.Deferred()
        if self.type == 'slave':
            # Streamer is slaved to a porter.
            self._pbclient = porterclient.HTTPPorterClientFactory(
                server.Site(resource=root), [self.mountPoint], d)
            # This will eventually cause d to fire
            reactor.connectWith(fdserver.FDConnector, self._porterPath, 
                self._pbclient, 10, checkPID=False)
            creds = credentials.UsernamePassword(self._porterUsername, 
                self._porterPassword)
            self.debug("Starting porter login!")
            self._pbclient.startLogin(creds, self.medium)
        else:
            # File Streamer is standalone.
            try:
                self.debug('Listening on %s' % self.port)
                iface = ""
                reactor.listenTCP(self.port, server.Site(resource=root), 
                    interface=iface)
            except error.CannotListenError:
                t = 'Port %d is not available.' % self.port
                self.warning(t)
                m = messages.Error(T_(N_(
                    "Network error: TCP port %d is not available."), self.port))
                self.addMessage(m)
                self.setMood(moods.sad)
                return defer.fail(errors.ComponentStartHandledError(t))
            # fire callback so component gets happy
            d.callback(None)
        # we are responsible for setting component happy
        def setComponentHappy(result):
            self.setMood(moods.happy)
            return result
        d.addCallback(setComponentHappy)
        return d

    def do_check(self):
        props = self.config['properties']
        if props.get('type', 'master') == 'slave':
            for k in 'socket_path', 'username', 'password':
                if not 'porter_' + k in props:
                    msg = ' slave mod, missing required property %s' % k
                    return defer.fail(errors.ConfigError(msg))
        else:
            if not 'port' in props:
                msg = "master mode, missing required property 'port'"
                return defer.fail(errors.ConfigError(msg))

        if props.get('mount_point', None) is not None: 
            path = props.get('path', None) 
            if path is None: 
                msg = "missing required property 'path'"
                return defer.fail(errors.ConfigError(msg)) 
            if not os.path.isfile(path):
                msg = "the file specified in 'path': %s does not" \
                    "exist or is not a file" % path
                return defer.fail(errors.ConfigError(msg)) 
