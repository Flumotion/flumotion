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

import gtk

from flumotion.configure import configure

__all__ = ['register_icons']

def _register_stock_icons(names):
    ifact = gtk.IconFactory()
    sizes = {gtk.ICON_SIZE_MENU:16, gtk.ICON_SIZE_SMALL_TOOLBAR:24}
    for name in names:
        iset = gtk.IconSet()
        for size, px in sizes.items():
            isource = gtk.IconSource()
            f = os.path.join(configure.imagedir, '%dx%d' % (px,px),
                             name + '.png')
            isource.set_filename(f)
            isource.set_size(size)
            iset.add_source(isource)
        ifact.add('flumotion-' + name, iset)
    ifact.add_default()

def register_icons():
    iconfile = os.path.join(configure.imagedir, 'fluendo.png')
    gtk.window_set_default_icon_from_file(iconfile)

    _register_stock_icons(['wizard', 'play', 'pause', 'about'])
