# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/consumers/shout2/shout2.py: stream to icecast2
#
# Flumotion - a streaming media server
# Copyright (C) 2005,2007 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from flumotion.component import feedcomponent

__version__ = "$Rev$"


class Shout2Consumer(feedcomponent.ParseLaunchComponent):

    def get_pipeline_string(self, properties):
        pipestr = 'shout2send name=shout2-streamer sync=1 protocol=3'

        elprops = (('mount-point', 'mount'),
                   ('port', 'port'),
                   ('ip', 'ip'),
                   ('password', 'password'),
                   ('description', 'description'),
                   ('url', 'url'),
                   ('short-name', 'streamname'))
        for k, v in elprops:
            if k in properties:
                # mind the gap, quote the values
                pipestr += ' %s="%s"' % (v, properties[k])

        return pipestr

    def configure_pipeline(self, pipeline, properties):

        def _connection_problem(self, error):
            # apparently error is an int
            self.warning('Connection problem: %r', error)

        element = pipeline.get_by_name('shout2-streamer')
        element.connect('connection-problem', _connection_problem)
