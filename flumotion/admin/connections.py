# -*- Mode: Python; fill-column: 80 -*-
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
# Streaming Server license may use this file in accordance with th
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.


import os
from xml.dom import minidom, Node

from flumotion.configure import configure
from flumotion.common import connection
from flumotion.twisted import pb as fpb

def get_recent_connections():
    def parse_connection(f):
        tree = minidom.parse(f)
        state = {}
        for n in [x for x in tree.documentElement.childNodes
                    if x.nodeType != Node.TEXT_NODE
                       and x.nodeType != Node.COMMENT_NODE]:
            state[n.nodeName] = n.childNodes[0].wholeText
        state['port'] = int(state['port'])
        state['use_insecure'] = (state['use_insecure'] != '0')
        authenticator = fpb.Authenticator(username=state['user'],
                                          password=state['passwd'])
        return connection.PBConnectionInfo(state['host'], state['port'],
                                           not state['use_insecure'],
                                           authenticator)

    try:
        # DSU, or as perl folks call it, a Schwartz Transform
        files = os.listdir(configure.registrydir)
        files = [os.path.join(configure.registrydir, f) for f in files]
        files = [(os.stat(f).st_mtime, f) for f in files
                                          if f.endswith('.connection')]
        files.sort()
        files.reverse()

        ret = []
        for f in [x[1] for x in files]:
            try:
                state = parse_connection(f)
                ret.append({'name': str(state),
                            'file': f,
                            'info': state})
            except Exception, e:
                print 'Error parsing %s: %r' % (f, e)
                raise
        return ret
    except OSError, e:
        print 'Error: %s: %s' % (e.strerror, e.filename)
        return []


