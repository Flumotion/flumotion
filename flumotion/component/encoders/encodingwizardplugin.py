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

from flumotion.component.encoders.encodingprofile import Profile


class EncodingWizardPlugin(object):
    """
    I am a base class used to write encoding plugins which
    are going to diplay profiles and user configurable values
    in the wizard
    @ivar wizard: the wizard
    @type wizard: L{flumotion.wizard.configurationwizard.ConfigurationWizard}
    """
    def __init__(self, wizard):
        """
        Creates a new encoding wizard plugin
        @param wizard: the wizard
        @type wizard: L{flumotion.wizard.configurationwizard.ConfigurationWizard}
        """
        self._profiles = self._create_profiles()
        self.wizard = wizard

    def _create_profiles(self):
        profiles = []
        for args in self.get_profile_presets():
            profiles.append(self.create_profile(*args))
        return profiles

    # Public API

    def get_default_profile(self):
        """
        Fetch the default profile.
        @returns: the default profile
        @rtype: L{flumotion.component.encoders.encodingprofile.Profile} list
        """
        for p in self._profiles:
            if p.isdefault:
                return p
        raise AssertionError("No default profile")

    def get_profiles(self):
        """
        Fetches the encoding profiles for the plugin.
        @returns: available profiles
        @rtype: L{flumotion.component.encoders.encodingprofile.Profile} list
        """
        return self._profiles

    # Overridable in subclasses

    def get_profile_presets(self):
        """
        This is called to get a list of values which should be used to create
        the profiles.
        For instance::

          def get_profile_presets(self):
              return [
                  (_('Default'), 96, True),
                  (_('Best'), 1024, False)
                  ]

        @returns: the profile presets
        @rtype: a list of (name, bitrate, isdefault) tuples
        """
        raise NotImplementedError

    def create_profile(self, name, bitrate, isdefault):
        """
        Creates a new profile based upon the values set
        in get_profile_presets().
        This can be overriden in a subclass if values apart
        from bitrate should be included in a profile.

        @param name: name of the profile
        @param bitrate: the bitrate of the profile
        @param isdefault: if this profile should be the default
        @returns: a newly created profile
        @rtype: L{flumotion.component.encoders.encodingprofile.Profile}
        """
        properties = dict(bitrate=bitrate)
        return Profile(name, isdefault, properties)

    def get_custom_properties(self):
        """
        This is called to get a list properties which can be set when
        the user select the custom profile option
        @returns: a list of properties
        @rtype: L{flumotion.component.encoders.encodingprofile.Property} list
        """
        raise NotImplementedError

    def get_custom_property_columns(self):
        """
        This is called to find out how many columns the properties
        should be displayed in.
        Default is 2, but some plugins with short or long property labels
        want to change this.
        @returns: the number of custom property columns
        @rtype: int
        """
        return 2

    def worker_changed(self, worker):
        """
        This is called when the wizard changes the worker
        for the step.
        Component and Gstreamer Element checks are usually done here.
        @param worker: the current worker
        @rtype worker:
        """
