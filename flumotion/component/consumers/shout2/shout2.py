# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
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
