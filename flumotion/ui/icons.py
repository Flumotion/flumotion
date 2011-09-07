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

import os

import gtk

from flumotion.configure import configure

__all__ = ['register_icons']
__version__ = "$Rev$"


def _register_stock_icons(names):
    ifact = gtk.IconFactory()
    for stock_name, filenames in names:
        iset = gtk.IconSet()
        for filename in filenames:
            isource = gtk.IconSource()
            f = os.path.join(configure.imagedir, filename)
            isource.set_filename(f)
            if filename.startswith('16x16'):
                size = gtk.ICON_SIZE_MENU
            elif filename.startswith('24x24'):
                size = gtk.ICON_SIZE_SMALL_TOOLBAR
            else:
                size = None
            if size:
                isource.set_size(size)
            iset.add_source(isource)
        ifact.add(stock_name, iset)
    ifact.add_default()


def register_icons():
    iconfile = os.path.join(configure.imagedir, 'flumotion.png')
    gtk.window_set_default_icon_from_file(iconfile)

    _register_stock_icons([
        ('flumotion.admin.gtk', ['16x16/wizard.png',
                              '24x24/wizard.png']),
        ('flumotion-mood-happy', ['mood-happy.png']),
        ('flumotion-mood-hungry', ['mood-hungry.png']),
        ('flumotion-mood-lost', ['mood-lost.png']),
        ('flumotion-mood-sad', ['mood-sad.png']),
        ('flumotion-mood-sleeping', ['mood-sleeping.png']),
        ('flumotion-mood-waking', ['mood-waking.png']),
        ])
