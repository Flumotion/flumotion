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

from flumotion.common.i18n import gettexter
from flumotion.component.common.avproducer import avproducer
from flumotion.component.common.avproducer import admin_gtk

__version__ = "$Rev$"
T_ = gettexter()


class BlackMagic(avproducer.AVProducerBase):

    def get_pipeline_template(self):
        return ('mmtblackmagicsrc name=src video-format=%s'
                    '  src.src_video ! queue '
                    '    ! @feeder:video@'
                    '  src.src_audio ! queue '
                    '    ! volume name=setvolume'
                    '    ! level name=volumelevel message=true '
                    '    ! @feeder:audio@' % (self.video_format, ))

    def get_pipeline_string(self, props):
        self.video_format = props.get('video-format', 8)
        return avproducer.AVProducerBase.get_pipeline_string(self, props)

GUIClass = admin_gtk.AVProducerAdminGtk
