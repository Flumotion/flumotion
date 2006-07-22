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

from twisted.internet import defer

from flumotion.common import log

from flumotion.component import feedcomponent
from flumotion.component.converters.overlay import genimg

import tempfile

class Overlay(feedcomponent.ParseLaunchComponent):
    _filename = None

    def get_pipeline_string(self, properties):
        # due to createComponent entry pointism, we have to import inside our
        # function.  PLEASE MAKE THE PAIN GO AWAY ? <- might not be
        # necessary still

        # we need an element that does RGBA -> AYUV so we can overlay png
        # this got added to ffmpegcolorspace in 0.8.5
        addalpha = 'ffmpegcolorspace'

        source = self.config['source'][0]
        eater = '@ eater:%s @' % source

        # the order here is important; to have our eater be the reference
        # stream for videomixer it needs to be specified last
        pipeline = (
            'filesrc name=source blocksize=100000 ! pngdec ! alphacolor ! '
            'videomixer name=mix ! @ feeder:: @ '
            '%(eater)s ! %(addalpha)s ! mix.' % locals())
        
        return pipeline

    def configure_pipeline(self, pipeline, properties):
        # create temp file
        (fd, self._filename) = tempfile.mkstemp('flumotion.png')
        os.close(fd)

        text = None
        if properties.get('show_text', False):
            text = properties.get('text', 'set the "text" property')
        genimg.generate_overlay(self._filename,
                                text,
                                properties.get('fluendo_logo', False),
                                properties.get('cc_logo', False),
                                properties.get('xiph_logo', False),
                                properties['width'],
                                properties['height'])
        
        source = self.get_element('source')
        source.set_property('location', self._filename)

    def do_stop(self):
        # clean up our temp file
        if self._filename:
            self.debug('Removing temporary overlay file %s' % self._filename)
            os.unlink(self._filename)
            self._filename = None
        else:
            self.debug("Temporary overlay already gone, " \
                "did we not start up correctly ?")
        return defer.succeed(None)
        
