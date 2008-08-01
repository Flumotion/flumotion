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

import os
import tempfile

from twisted.internet import defer

from flumotion.common import log, messages, gstreamer
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent
from flumotion.component.converters.overlay import genimg

__version__ = "$Rev$"
T_ = gettexter()


class Overlay(feedcomponent.ParseLaunchComponent):
    checkTimestamp = True
    checkOffset = True
    _filename = None

    def get_pipeline_string(self, properties):
        # the order here is important; to have our eater be the reference
        # stream for videomixer it needs to be specified last
        pipeline = (
            'filesrc name=source blocksize=100000 ! pngdec ! alphacolor ! '
            'videomixer name=mix ! @feeder:default@ '
            '@eater:default@ ! ffmpegcolorspace ! mix.')

        return pipeline

    def configure_pipeline(self, pipeline, properties):
        p = properties
        self.fixRenamedProperties(p, [
                ('show_text', 'show-text'),
                ('fluendo_logo', 'fluendo-logo'),
                ('cc_logo', 'cc-logo'),
                ('xiph_logo', 'xiph-logo')])

        # create temp file
        (fd, self._filename) = tempfile.mkstemp('flumotion.png')
        os.close(fd)

        text = None
        if p.get('show-text', False):
            text = p.get('text', 'set the "text" property')
        overflow = genimg.generate_overlay(self._filename,
                                           text,
                                           p.get('fluendo-logo', False),
                                           p.get('cc-logo', False),
                                           p.get('xiph-logo', False),
                                           p['width'],
                                           p['height'])
        if overflow:
            m = messages.Warning(
                T_(N_("Overlayed text '%s' too wide for the video image."),
                   text), id = "text-too-wide")
            self.addMessage(m)

        source = self.get_element('source')
        source.set_property('location', self._filename)

        if gstreamer.get_plugin_version('videomixer') == (0, 10, 7, 0):
            m = messages.Warning(
                T_(N_("The 'videomixer' GStreamer element has a bug in this "
                      "version (0.10.7). You may see many errors in the debug "
                      "output, but it should work correctly anyway.")),
                id = "videomixer-bug")
            self.addMessage(m)

    def do_stop(self):
        # clean up our temp file
        if self._filename:
            self.debug('Removing temporary overlay file %s' % self._filename)
            os.unlink(self._filename)
            self._filename = None
        else:
            self.debug("Temporary overlay already gone, " \
                "did we not start up correctly ?")
