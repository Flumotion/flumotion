# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

from flumotion.component.base import converter

def createComponent(config):
    source = config['source']
    location = config['location']
    
    # Since source in converter is a list, convert it to one
    config['source'] = [source]

    # Set pipeline from the template
    pipeline = "filesrc location=%s blocksize=100000 !" % location + \
               "pngdec ! alphacolor ! videomixer name=mix ! :default " + \
               "@%s ! ffmpegcolorspace ! alpha ! mix." % source
    config['pipeline'] = pipeline

    return converter.createComponent(config)
