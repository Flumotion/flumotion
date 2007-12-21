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

__version__ = "$Rev: 5969 $"

import gettext

_ = gettext.gettext


class Property(object):
    """
    I am an object representing a component property.
    I can be used to construct a user interface based, which
    is done in the encoder part of the wizard

    @ivar name: name
    @ivar nick: description of the property
    @ivar default: default value
    @ivar datatype: the python data type of the property
    """
    def __init__(self, name, nick, default, datatype):
        self.name = name
        self.nick = nick
        self.default = default
        self.datatype = datatype

    def save(self, value):
        """
        This is used to be able to override the value which is going to be
        saved in the configuration xml when saving a property from the wizard.
        @param value: value displayed in the wizard
        @returns: value to be written in the configuration
        """
        return value


class Int(Property):
    """
    I am an integer property
    """
    def __init__(self, name, nick, default, minimum, maximum):
        Property.__init__(self, name, nick, default, datatype=int)
        self.minimum = minimum
        self.maximum = maximum


class Profile(object):
    """
    @ivar name: the name of the profile
    @type name: string
    @ivar isdefault: if this is the prefered profile
    @type isdefault: bool
    @ivar properties: element properties this profile represents
    @type properties: dict name -> string value
    """

    def __init__(self, name, isdefault=False, properties=None):
        self.name = name
        self.isdefault = isdefault
        self.properties = properties or {}
