# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# bin/flumotion-admin: graphical administration client for Flumotion
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

# XXX: move this to flumotion.common.setup

'''
Exports configure-time variables for installed and uninstalled operation.
\n
defines datadir, gladedir
'''

import os
import flumotion.config

global datadir

# where am I on the disk ?
__thisdir = os.path.dirname(os.path.abspath(__file__))

if os.path.exists(os.path.join(__thisdir, 'uninstalled.py')):
    from flumotion.config import uninstalled as config
else:
    from flumotion.config import installed as config

config_dict = config.get()
for key, value in config_dict.items():
    setattr(flumotion.config, key, value)
