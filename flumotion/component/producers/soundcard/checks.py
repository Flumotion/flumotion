# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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

from twisted.internet import defer

from flumotion.worker.checks import check
from flumotion.common import gstreamer, messages

from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

def checkPyGTK():
    """
    Check for a recent enough PyGTK to not leak python integers in message 
    processing (mostly affects soundcard, firewire)
    """
    result = messages.Result()
    import pygtk
    pygtk.require('2.0')
    import gtk
    (major, minor, nano) = gtk.pygtk_version
    if minor < 8 or (minor == 8 and nano <= 4):
        m = messages.Warning(T_(
            N_("Version %d.%d.%d of the PyGTK library contains a memory leak.\n"), 
            major, minor, nano),
            id = 'pygtk-check')
        m.add(T_(N_("The Soundcard and Firewire sources may leak a lot of " 
            "memory as a result, and need to be restarted frequently.\n")))
        m.add(T_(N_("Please upgrade PyGTK to version 2.8.5")))
        result.add(m)

    result.succeed(None)
    return defer.succeed(result)

def checkPyGST():
    result = messages.Result()
    import pygst
    pygst.require('0.10')
    import gst
    (major, minor, nano) = gst.pygst_version
    if major == 0 and minor == 10 and nano <= 3:
        m = messages.Warning(T_(
            N_("Version %d.%d.%d of the gst-python library contains a large memory leak.\n"), 
            major, minor, nano),
            id = 'pygst-check')
        m.add(T_(N_("The Soundcard and Firewire sources may leak a lot of " 
            "memory as a result, and need to be restarted frequently.\n")))
        m.add(T_(N_("Please upgrade gst-python to version 0.10.3 or later")))
        result.add(m)

    result.succeed(None)
    return defer.succeed(result)

