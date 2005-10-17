# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from flumotion.common import log

from flumotion.component import feedcomponent
from flumotion.component.converters.overlay import genimg

import tempfile

class Overlay(feedcomponent.ParseLaunchComponent):
    def __init__(self, name, eaters, pipeline, config):
        self._filename = None
        self._config = config
        feedcomponent.ParseLaunchComponent.__init__(self, name,
                                                    eaters,
                                                    ['default'],
                                                    pipeline)

    def start(self, eatersData, feedersData):
        # create temp file
        (fd, self._filename) = tempfile.mkstemp('flumotion.png')
        os.close(fd)

        text = None
        if self._config['show_text']:
            text = self._config['text']
        genimg.generate_overlay(self._filename,
                                text,
                                self._config.get('fluendo_logo', False),
                                self._config.get('cc_logo', False),
                                self._config.get('xiph_logo', False),
                                self._config['width'],
                                self._config['height'])
        
        source = self.get_element('source')
        source.set_property('location', self._filename)

        return feedcomponent.ParseLaunchComponent.start(self,
            eatersData, feedersData)

    def stop(self):
        # clean up our temp file
        # FIXME: it would probably be nicer to implement this through hooks
        # since now I do this before chaining, while FeedComp does it after
        # chaining, so it's messy
        feedcomponent.ParseLaunchComponent.stop(self)
        if self._filename:
            self.debug('Removing temporary overlay file %s' % self._filename)
            os.unlink(self._filename)
            self._filename = None
        else:
            self.debug('Temporary overlay already gone, did we not start up correctly ?')
        
def createComponent(config):
    source = config['source']
    eater = '@ eater:%s @' % source

    # AYUV conversion got added to ffmpegcolorspace in 0.8.5
    # alphacolor element works too, but has bugs for non-multiples of 4 or eight
    alpha = 'ffmpegcolorspace ! alpha'

    # due to createComponent entry pointism, we have to import inside our
    # function.  PLEASE MAKE THE PAIN GO AWAY ?
    import gst
    if gst.gst_version < (0,9):
        from flumotion.worker.checks import video
        if video.check_ffmpegcolorspace_AYUV():
            alpha = 'ffmpegcolorspace'
        else:
            log.info('Using gst-plugins older than 0.8.5, consider upgrading if you notice a diagonal green line in your video output.')
        pipeline = ('filesrc name=source blocksize=100000 ! pngdec '
                    ' ! alphacolor ! videomixer name=mix '
                    ' ! @ feeder:: @ %(eater)s ! %(alpha)s ! mix.' % locals())
    else:
        pipeline = ('filesrc name=source blocksize=100000 ! pngdec '
                    ' ! ffmpegcolorspace ! videomixer name=mix '
                    ' ! @ feeder:: @ %(eater)s ! ffmpegcolorspace ! mix.' % locals())
    
    return Overlay(config['name'], [source], pipeline, config)
