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

import gst


if gst.gst_version < (0, 9):
    from vorbis08 import Vorbis
else:
    from vorbis09 import Vorbis


def createComponent(config):
    channels = config.get('channels', 2)
    bitrate = config.get('bitrate', -1)
    quality = config.get('quality', 0.3)
            
    component = Vorbis(config['name'], config['source'], bitrate,
                    quality, channels)
              
    return component
