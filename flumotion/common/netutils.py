# -*- Mode: Python; test-case-name: flumotion.test.test_common_messages -*-
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

"""
Miscellaneous network functions for use in flumotion.
"""

import socket
import fcntl
import struct
import array

# Thanks to Paul Cannon, see 
# http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/439093
# 
# WARNING: Horribly linux-specific. Horribly IPv4 specific. Also, just horrible.

def find_all_interface_names():
    """
    Find the names of all available network interfaces
    """
    max_possible = 128  # arbitrary. raise if needed.
    bytes = max_possible * 32
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    names = array.array('B', '\0' * bytes)
    outbytes = struct.unpack('iL', fcntl.ioctl(
        s.fileno(),
        0x8912,  # SIOCGIFCONF
        struct.pack('iL', bytes, names.buffer_info()[0])
    ))[0]
    namestr = names.tostring()
    return [namestr[i:i+32].split('\0', 1)[0] for i in range(0, outbytes, 32)]

def get_address_for_interface(ifname):
    """
    Get the IP address for an interface
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])

def guess_public_ip():
    """
    Attempt to guess a public IP for this system.
    Returns "127.0.0.1" if it can't come up with anything better.
    """
    # Iterate through them in some vaguely meaningful order.
    interfaces = find_all_interface_names()
    interfaces.sort()

    for interface in interfaces:
        # We have them sorted, so the first such we see will be eth0
        if interface.startswith('eth'):
            return get_address_for_interface(interface)

    return '127.0.0.1'

def guess_public_hostname():
    """
    Attempt to guess a public hostname for this system.
    """
    ip = guess_public_ip()

    try:
        return socket.gethostbyaddr(ip)[0]
    except:
        return ip

