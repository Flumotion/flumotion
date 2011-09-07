# -*- Mode: Python; test-case-name: flumotion.test.test_ui_fgtk -*-
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

"""
I am a collection of extended GTK widgets for use in Flumotion.
"""

import gobject
from kiwi.ui.widgets.checkbutton import ProxyCheckButton
from kiwi.ui.widgets.combo import ProxyComboBox
from kiwi.ui.widgets.entry import ProxyEntry
from kiwi.ui.widgets.radiobutton import ProxyRadioButton
from kiwi.ui.widgets.spinbutton import ProxySpinButton

__version__ = "$Rev$"


class FProxyComboBox(ProxyComboBox):

    def set_enum(self, enum_class, value_filter=()):
        """
        Set the given enum_class on the combobox.
        As a side effect, this makes the combobox an enum-based one.
        This also sets the combobox to the first enum value.
        """

        values = []
        for enum in enum_class:
            # If values are specified, filter them out
            if value_filter and not enum in value_filter:
                continue
            values.append((enum.nick, enum))
        self.prefill(values)


class ProxyWidgetMapping:
    # In PyGTK 2.4.0 gtk.glade.XML type_dict parameter is buggy
    # If it can't find the name it raises a silent KeyError which
    # will be raised at random point later (as soon some code call
    # PyErr_Occurred()), to avoid this, we reimplement the function
    # as it is internally, eg failback to the real GType, by doing
    # this PyMapping_GetItemString will never set the error.

    types = {'GtkCheckButton': ProxyCheckButton,
             'GtkComboBox': FProxyComboBox,
             'GtkEntry': ProxyEntry,
             'GtkRadioButton': ProxyRadioButton,
             'GtkSpinButton': ProxySpinButton}

    def __getitem__(self, name):
        if name in self.types:
            return self.types[name]
        else:
            return gobject.type_from_name(name)
