# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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


__all__ = ['commands']


# command-list := (command-spec, command-spec...)
# command-spec := (command-name, command-desc, arguments, command-proc)
# command-name := str
# command-desc := str
# command-proc := f(model, quit, *args) -> None
# arguments := (arg-spec, arg-spec...)
# arg-spec := (arg-name, arg-parser)
# arg-name := str
# arg-parser := f(x) -> Python value or exception

def do_getprop(model, quit, path, propname):
    print 'foo'
    quit()

commands = (('getprop',
             'gets a property on a component',
             (('component-path', str),
              ('property-name', str)),
             do_getprop),
            )

