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

from flumotion.component.base.admin_text import BaseAdminText

import string

from twisted.internet import defer

__version__ = "$Rev$"


class DiskerAdminText(BaseAdminText):
    commands = ['changefile']
    filename_change_defers = []

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
        return available_commands

    def runCommand(self, command):
        command_split = command.split()
        if string.lower(command_split[0]) == 'changefile':
            # change filename and wait for new filename
            self.callRemote("changeFilename")
            newd = defer.Deferred()
            self.filename_change_defers.append(newd)
            return newd
        else:
            return None

    def component_filenameChanged(self, filename):
        for i in self.filename_change_defers:
            i.callback(filename)
        self.filename_change_defers = []

UIClass = DiskerAdminText
