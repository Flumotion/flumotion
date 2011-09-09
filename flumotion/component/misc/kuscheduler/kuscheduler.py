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

import gst

from flumotion.common.i18n import gettexter
from flumotion.component import feedcomponent
from flumotion.component.effects.kuscheduler import kuscheduler

__all__ = ['KeyUnitsScheduler']
__version__ = "$Rev$"
T_ = gettexter()


class KeyUnitsScheduler(feedcomponent.ParseLaunchComponent):
    logCategory = 'keyunits-scheduler'

    def get_pipeline_string(self, properties):
        return 'identity silent=true name=identity'

    def configure_pipeline(self, pipeline, properties):
        self.interval = properties.get('interval', 10000) * gst.MSECOND

        identity = pipeline.get_by_name("identity")
        # Add key units scheduler
        scheduler = kuscheduler.KeyUnitsScheduler('video-kuscheduler',
            identity.get_pad("src"), pipeline, self.interval)
        self.addEffect(scheduler)
        scheduler.plug()
