# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2009,2010 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.
# flumotion-fragmented-streaming - Flumotion Advanced fragmented streaming

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.


# Component specific errors


class FragmentNotFound(Exception):
    "The requested fragment is not found."


class FragmentNotAvailable(Exception):
    "The requested fragment is not available."


class PlaylistNotFound(Exception):
    "The requested playlist is not found."


class KeyNotFound(Exception):
    "The requested key is not found."
