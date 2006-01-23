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


from flumotion.twisted.defer import defer_generator
from flumotion.common import componentui, errors


def avatarId(string):
    split = string.split('/')
    assert len(split) == 3
    assert not split[0]
    return split[1:]

def find_component(planet, avatarId):
    for f in planet.get('flows'):
        if f.get('name') == avatarId[0]:
            for c in f.get('components'):
                if c.get('name') == avatarId[1]:
                    return c
    print ('Could not find component named %s in flow %s'
           % (avatarId[1], avatarId[0]))
    return None

def get_component_uistate(model, avatarId, component=None, quiet=False):
    if not component:
        d = model.callRemote('getPlanetState')
        yield d
        planet = d.value()
        component = find_component(planet, avatarId)
    if component:
        d = model.componentCallRemote(component, 'getUIState')
        yield d
        try:
            uistate = d.value()
            yield uistate
        except errors.SleepingComponentError:
            if not quiet:
                print ('Error: Component %s in flow %s is sleeping'
                       % (avatarId[1], avatarId[0]))
get_component_uistate = defer_generator(get_component_uistate)
