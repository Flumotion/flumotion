# -*- Mode: Python; -*-
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

"""jelliers for State shared between worker, manager and admin
"""

# FIXME: Users of this module relies heavily on side effects,
#        this should be addressed so they have to call a function
#        to register the unjelliers, imports should have as few
#        side effects as possible

from twisted.spread import pb

from flumotion.twisted import flavors
from flumotion.common import registry

__version__ = "$Rev$"


# state of a component used for UI purposes


class WorkerComponentUIState(flavors.StateCacheable):
    pass


class ManagerComponentUIState(flavors.StateCacheable,
                              flavors.StateRemoteCache):

    def processUniqueID(self):
        # Make sure proxies for the same object are the same, if we are
        # later cached by someone else. See bug #519.
        return id(self.__dict__)


class AdminComponentUIState(flavors.StateRemoteCache):
    pass


pb.setUnjellyableForClass(WorkerComponentUIState, ManagerComponentUIState)
pb.setUnjellyableForClass(ManagerComponentUIState, AdminComponentUIState)


class WizardEntryState(pb.RemoteCopy):

    def getAcceptedMediaTypes(self):
        """
        Fetches a list of media types this components accepts.
        @returns: a list of strings
        """
        return [format.media_type for format in self.accepts]

    def getProvidedMediaTypes(self):
        """
        Fetches a list of media types this components provides.
        @returns: a list of strings
        """
        return [format.media_type for format in self.provides]

pb.setUnjellyableForClass(registry.RegistryEntryWizard, WizardEntryState)


class WizardEntryFormatState(pb.RemoteCopy):
    pass

pb.setUnjellyableForClass(registry.RegistryEntryWizardFormat,
                          WizardEntryFormatState)
