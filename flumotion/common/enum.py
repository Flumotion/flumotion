# -*- Mode: Python; test-case-name: flumotion.test.test_enum -*-
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

"""simple enum and implementation
"""

from twisted.python.reflect import qual
from twisted.spread import jelly

__version__ = "$Rev$"
_enumClassRegistry = {}


class EnumMetaClass(type):
    # pychecker likes this attribute to be there since we use it in this class
    __enums__ = {}

    def __len__(self):
        return len(self.__enums__)

    def __getitem__(self, value):
        try:
            return self.__enums__[value]
        except KeyError:
            raise StopIteration

    def __setitem__(self, value, enum):
        self.__enums__[value] = enum
        setattr(self, enum.name, enum)


class Enum(object, jelly.Jellyable):

    __metaclass__ = EnumMetaClass
    def __init__(self, value, name, nick=None):
        self.value = value
        self.name = name

        if nick == None:
            nick = name

        self.nick = nick
        self._enumClassName = self.__class__.__name__

    def __repr__(self):
        return '<enum %s of type %s>' % (self.name,
                                         self.__class__.__name__)

    def get(klass, value):
        return klass.__enums__[value]
    get = classmethod(get)

    def set(klass, value, item):
        klass[value] = item
    set = classmethod(set)

    def jellyFor(self, jellier):
        sxp = jellier.prepare(self)
        sxp.extend([
            qual(Enum),
            self._enumClassName,
            self.value, self.name, self.nick])
        return jellier.preserve(self, sxp)


class EnumClass(object):
    def __new__(klass, type_name, names=(), nicks=(), **extras):
        if nicks:
            if len(names) != len(nicks):
                raise TypeError("nicks must have the same length as names")
        else:
            nicks = names

        for extra in extras.values():
            if not isinstance(extra, (tuple, list)):
                raise TypeError('extra must be a sequence, not %s' % type(extra))

            if len(extra) != len(names):
                raise TypeError("extra items must have a length of %d" %
                                len(names))

        # we reset __enums__ to {} otherwise it retains the other registered
        # ones
        etype = EnumMetaClass(type_name, (Enum, ), {'__enums__': {}})
        for value, name in enumerate(names):
            enum = etype(value, name, nicks[value])
            for extra_key, extra_values in extras.items():
                assert not hasattr(enum, extra_key)
                setattr(enum, extra_key, extra_values[value])
            etype[value] = enum

        _enumClassRegistry[type_name] = etype
        return etype


# Enum unjellyer should not be a new style class,
# otherwise Twsited 2.0.1 will not recognise it.
class EnumUnjellyer(jelly.Unjellyable):

    def unjellyFor(self, unjellier, jellyList):
        enumClassName, value, name, nick = jellyList[1:]
        enumClass = _enumClassRegistry.get(enumClassName, None)
        if enumClass:
            # Retrieve the enum singleton
            enum = enumClass.get(value)
            assert enum.name == name, "Inconsistent Enum Name"
        else:
            # Create a generic Enum container
            enum = Enum(value, name, nick)
            enum._enumClassName = enumClassName
        return enum


jelly.setUnjellyableForClass(qual(Enum), EnumUnjellyer)
