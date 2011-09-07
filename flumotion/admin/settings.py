# -*- Mode: Python; fill-column: 80 -*-
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


"""Save and restore the settings of the mainwindow"""

import os
from xml.dom import minidom, Node
from xml.parsers.expat import ExpatError

from flumotion.common import log
from flumotion.configure import configure

__version__ = "$Rev$"


class Settings(object):
    """
    Sets up the settings. Expects a filename where settings
    will be stored
    """

    def __init__(self, filename=None):
        if filename is None:
            self._filename = os.path.join(
                                configure.cachedir,
                                'gtk-admin-state')
        else:
            self._filename = filename
        self._values = {}
        self.read()

    def read(self):
        try:
            tree = minidom.parse(self._filename)
            node = tree.getElementsByTagName('gtk-admin-state')[0]
            for elem in node.childNodes:
                self._values[elem.nodeName] = elem.firstChild.data
        except (IOError, IndexError, ExpatError), e:
            log.warning('Cannot read gtl-admin-state %s',
                        log.getExceptionMessage(e))

    def save(self):
        try:
            f = open(self._filename, 'w')
            doc = minidom.Document()
            root = doc.createElement('gtk-admin-state')
            doc.appendChild(root)
            for key, value in self._values.iteritems():
                self._append(doc, root, key, value)
            doc.writexml(f)
            f.close()
        except IOError, e:
            log.warning('Cannot find gtk-admin-state: %s',
                        log.getExceptionMessage(e))

    def _append(self, doc, root, key, value):
        element = doc.createElement(key)
        root.appendChild(element)
        value = doc.createTextNode(value)
        element.appendChild(value)

    def setValue(self, key, value):
        self._values[key] = value

    def getValue(self, key, default=None):
        return self._values.get(key, default)

    def hasValue(self, key):
        return key in self._values


def getSettings():
    return Settings()
