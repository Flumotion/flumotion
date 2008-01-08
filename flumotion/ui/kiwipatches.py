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
# Streaming Server license may use this file in accordance with th
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

import os

from gtk import glade
from kiwi.environ import environ
from kiwi.__version__ import version as kiwi_version
from kiwi.utils import PropertyMeta, PropertyObject
from kiwi.ui import views
from kiwi.ui.widgets.entry import ProxyEntry

__version__ = "$Rev$"


# Kiwi monkey patch, allows us to specify a
# glade_typedict on the View.
class FluLibgladeWidgetTree(glade.XML):
    def __init__(self, view, gladefile, domain=None):
        self._view = view
        glade.XML.__init__(self, gladefile, domain,
                           typedict=view.glade_typedict or {})

        for widget in self.get_widget_prefix(''):
            setattr(self._view, widget.get_name(), widget)

    def get_widget(self, name):
        name = name.replace('.', '_')
        widget = glade.XML.get_widget(self, name)
        if widget is None:
            raise AttributeError(
                  "Widget %s not found in view %s" % (name, self._view))
        return widget

    def get_widgets(self):
        return self.get_widget_prefix('')

    def get_sizegroups(self):
        return []

def _open_glade(view, gladefile, domain):
    if not gladefile:
        raise ValueError("A gladefile wasn't provided.")
    elif not isinstance(gladefile, basestring):
        raise TypeError(
              "gladefile should be a string, found %s" % type(gladefile))

    if not '/' in gladefile:
        filename = os.path.splitext(os.path.basename(gladefile))[0]
        gladefile = environ.find_resource("glade", filename + '.glade')
    return FluLibgladeWidgetTree(view, gladefile, domain)

# Fixing bug #3259, fixed in kiwi 1.99.15

old_proxy_entry_init = ProxyEntry.__init__
def proxy_entry_init(slf, data_type=None, *args, **kwargs):
    try:
        old_proxy_entry_init(slf, *args, **kwargs)
    except TypeError:
        pass

def install_patches():
    views._open_glade = _open_glade

    if kiwi_version <= (1, 99, 14):
        ProxyEntry.__init__ = proxy_entry_init
