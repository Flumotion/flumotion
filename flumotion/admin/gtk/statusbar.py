# -*- Mode: Python; test-case-name: flumotion.test.test_parts -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

"""statusbar widget used by in admin window"""

__version__ = "$Rev$"


class AdminStatusbar(object):
    """
    I implement the status bar used in the admin UI.
    """

    def __init__(self, widget):
        """
        @param widget: a gtk.Statusbar to wrap.
        """
        self._widget = widget

        self._cids = {} # hash of context -> context id
        self._mids = {} # hash of context -> message id lists
        self._contexts = ['main', 'notebook']

        for context in self._contexts:
            self._cids[context] = widget.get_context_id(context)
            self._mids[context] = []

    def clear(self, context=None):
        """
        Clear the status bar for the given context, or for all contexts
        if none specified.
        """
        if context:
            self._clearContext(context)
            return

        for context in self._contexts:
            self._clearContext(context)

    def push(self, context, message):
        """
        Push the given message for the given context.

        @returns: message id
        """
        mid = self._widget.push(self._cids[context], message)
        self._mids[context].append(mid)
        return mid

    def pop(self, context):
        """
        Pop the last message for the given context.

        @returns: message id popped, or None
        """
        if len(self._mids[context]):
            mid = self._mids[context].pop()
            self._widget.remove(self._cids[context], mid)
            return mid

        return None

    def set(self, context, message):
        """
        Replace the current top message for this context with this new one.

        @returns: the message id of the message pushed
        """
        self.pop(context)
        return self.push(context, message)

    def remove(self, context, mid):
        """
        Remove the message with the given id from the given context.

        @returns: whether or not the given mid was valid.
        """
        if not mid in self._mids[context]:
            return False

        self._mids[context].remove(mid)
        self._widget.remove(self._cids[context], mid)
        return True

    def _clearContext(self, context):
        if not context in self._cids.keys():
            return

        for mid in self._mids[context][:]:
            self.remove(context, mid)
