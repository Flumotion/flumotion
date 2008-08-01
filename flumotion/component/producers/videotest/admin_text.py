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

from flumotion.component.base.admin_text import BaseAdminText

import string

from twisted.internet import defer

__version__ = "$Rev$"


class VideoTestAdminText(BaseAdminText):
    commands = ['setpattern', 'getpattern']
    patterns = ['smpte', 'snow', 'black']

    def setup(self):
        pass

    def getCompletions(self, input):
        input_split = input.split()
        available_commands = []
        if input.endswith(' '):
            input_split.append('')
        if len(input_split) <= 1:
            for c in self.commands:
                if c.startswith(string.lower(input_split[0])):
                    available_commands.append(c)
        elif len(input_split) == 2:
            if string.lower(input_split[0]) == 'setpattern':
                for p in self.patterns:
                    if p.startswith(string.lower(input_split[1])):
                        available_commands.append(p)

        return available_commands

    def runCommand(self, command):
        command_split = command.split()
        if string.lower(command_split[0]) == 'setpattern':
            # set pattern
            if len(command_split) == 2:
                pattern = -1
                if string.lower(command_split[1]) == 'smpte':
                    pattern = 0
                elif string.lower(command_split[1]) == 'snow':
                    pattern = 1
                elif string.lower(command_split[1]) == 'black':
                    pattern = 2
                if pattern > -1:
                    d = self.callRemote("setPattern", pattern)
                    return d
        elif string.lower(command_split[0]) == 'getpattern':
            # get pattern

            def getpattern_cb(uiState):
                return self.patterns[uiState.get('pattern')]
            d = self.callRemote("getUIState")
            d.addCallback(getpattern_cb)
            return d
        else:
            return None


UIClass = VideoTestAdminText
