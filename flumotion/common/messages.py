# -*- Mode: Python; test-case-name: flumotion.test.test_common_messages -*-
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

"""
support for serializable messages from component/manager to admin
"""

from twisted.spread import pb

ERROR = 1
WARNING = 2
INFO = 3

class Message(pb.Copyable, pb.RemoteCopy):
    """
    I am a message to be shown in a UI.
    I can be proxied from a worker or component to managers and admins.
    """
    def __init__(self, level, text, debug=None, id=None, priority=50):
        """
        @param level:    ERROR, WARNING or INFO
        @param text:     a translateable text string, possibly with markup for
                         linking to documentation or running commands.
        @param debug:    further, untranslated, debug information, not always
                         shown
        @param priority: priority compared to other messages of the same level
        """
        self.level = level
        self.text = text
        self.debug = debug
        self.id = id
        self.priority = priority
pb.setUnjellyableForClass(Message, Message)

def Error(*args, **kwargs):
    return Message(ERROR, *args, **kwargs)

def Warning(*args, **kwargs):
    return Message(WARNING, *args, **kwargs)

def Info(*args, **kwargs):
    return Message(INFO, *args, **kwargs)

