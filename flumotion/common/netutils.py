# -*- Mode: Python; test-case-name: flumotion.test.test_common_messages -*-
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

"""miscellaneous network functions.
"""

import array
import errno
import fcntl
import re
import socket
import struct
import platform

from twisted.internet import address

from flumotion.common import avltree

__version__ = "$Rev$"


# Thanks to Paul Cannon, see
# http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/439093
#
# WARNING: Horribly linux-specific. Horribly IPv4 specific.
#          Also, just horrible.


# ioctl calls are platform specific
system = platform.system()
if system == 'SunOS':
    SIOCGIFCONF = 0xC008695C
    SIOCGIFADDR = 0xC020690D
else: #FIXME: to find these calls for other OSs (default Linux)
    SIOCGIFCONF = 0x8912
    SIOCGIFADDR = 0x8915


def find_all_interface_names():
    """
    Find the names of all available network interfaces
    """
    ptr_size = len(struct.pack('P', 0))
    size = 24 + 2 * (ptr_size)
    max_possible = 128  # arbitrary. raise if needed.
    bytes = max_possible * size
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    names = array.array('B', '\0' * bytes)
    outbytes = struct.unpack('iP', fcntl.ioctl(
        s.fileno(),
        SIOCGIFCONF,
        struct.pack('iP', bytes, names.buffer_info()[0])))[0]
    namestr = names.tostring()
    return [namestr[i:i+size].split('\0', 1)[0]
            for i in range(0, outbytes, size)]


def get_address_for_interface(ifname):
    """
    Get the IP address for an interface
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        SIOCGIFADDR,
        struct.pack('256s', ifname[:15]))[20:24])


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
    except socket.error:
        return ip


def ipv4StringToInt(s):
    try:
        b1, b2, b3, b4 = map(int, s.split('.'))
    except TypeError:
        raise ValueError(s)

    ret = 0
    for n in b1, b2, b3, b4:
        ret <<= 8
        if n < 0 or n > 255:
            raise ValueError(s)
        ret += n
    return ret


def ipv4IntToString(n):
    l = []
    for i in range(4):
        l.append((n>>(i*8)) & 0xff)
    l.reverse()
    return '.'.join(map(str, l))


def countTrailingZeroes32(n):
    tz = 0
    if n == 0:
        # max of 32 bits
        tz = 32
    else:
        while not (n & (1<<tz)):
            tz += 1
    return tz


class RoutingTable(object):

    def fromFile(klass, f, requireNames=True, defaultRouteName='*default*'):
        """
        Make a new routing table, populated from entries in an open
        file object.

        The entries are expected to have the form:
        IP-ADDRESS/MASK-BITS ROUTE-NAME

        The `#' character denotes a comment. Empty lines are allowed.

        @param f: file from whence to read a routing table
        @type  f: open file object
        @param requireNames: whether to require route names in the file
        @type  requireNames: boolean, default to True
        @param defaultRouteName: default name to give to a route if it
                                 does not have a name in the file; only
                                 used if requireNames is False
        @type  defaultRouteName: anything, defaults to '*default*'
        """
        comment = re.compile(r'^\s*#')
        empty = re.compile(r'^\s*$')
        entry = re.compile(r'^\s*'
                           r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
                           r'/'
                           r'(\d{1,2})'
                           r'(\s+([^\s](.*[^\s])?))?\s*$')
        ret = klass()
        n = 0
        for line in f:
            n += 1
            if comment.match(line) or empty.match(line):
                continue
            m = entry.match(line)
            if not m:
                raise ValueError('While loading routing table from file'
                                 ' %s: line %d: invalid syntax: %r'
                                 % (f, n, line))
            route = m.group(4)
            if route is None:
                if requireNames:
                    raise ValueError('%s:%d: Missing required route name: %r'
                                     % (f, n, line))
                else:
                    route = defaultRouteName
            ret.addSubnet(route, m.group(1), int(m.group(2)))
            if route not in ret.routeNames:
                ret.routeNames.append(route)

        return ret
    fromFile = classmethod(fromFile)

    def __init__(self):
        self.avltree = avltree.AVLTree()
        self.routeNames = []

    def getRouteNames(self):
        return self.routeNames

    def _parseSubnet(self, ipv4String, maskBits):
        return (ipv4StringToInt(ipv4String),
                ~((1 << (32 - maskBits)) - 1))

    def addSubnet(self, route, ipv4String, maskBits=32):
        ipv4Int, mask = self._parseSubnet(ipv4String, maskBits)
        if not ipv4Int & mask == ipv4Int:
            raise ValueError('Net %s too specific for mask with %d bits'
                             % (ipv4String, maskBits))
        self.avltree.insert((mask, ipv4Int, route))

    def removeSubnet(self, route, ipv4String, maskBits=32):
        ipv4Int, mask = self._parseSubnet(ipv4String, maskBits)
        self.avltree.delete((mask, ipv4Int, route))

    def __iter__(self):
        return self.avltree.iterreversed()

    def iterHumanReadable(self):
        for mask, net, route in self:
            yield route, ipv4IntToString(net), 32-countTrailingZeroes32(mask)

    def __len__(self):
        return len(self.avltree)

    def route(self, ip):
        """
        Return the preferred route for this IP.

        @param ip: The IP to use for routing decisions.
        @type  ip: An integer or string representing an IPv4 address
        """
        if isinstance(ip, str):
            ip = ipv4StringToInt(ip)

        for netmask, net, route in self:
            if ip & netmask == net:
                return route

        return None

    def route_iter(self, ip):
        """
        Return an iterator yielding routes in order of preference.

        @param ip: The IP to use for routing decisions.
        @type  ip: An integer or string representing an IPv4 address
        """
        if isinstance(ip, str):
            ip = ipv4StringToInt(ip)
        for mask, net, route in self:
            if ip & mask == net:
                yield route
        # Yield the default route
        yield None


def addressGetHost(a):
    """
    Get the host name of an IPv4 address.

    @type a: L{twisted.internet.address.IPv4Address}
    """
    if not isinstance(a, address.IPv4Address) and not isinstance(a,
        address.UNIXAddress):
        raise TypeError("object %r is not an IPv4Address or UNIXAddress" % a)
    if isinstance(a, address.UNIXAddress):
        return 'localhost'

    try:
        host = a.host
    except AttributeError:
        host = a[1]
    return host


def addressGetPort(a):
    """
    Get the port number of an IPv4 address.

    @type a: L{twisted.internet.address.IPv4Address}
    """
    assert(isinstance(a, address.IPv4Address))
    try:
        port = a.port
    except AttributeError:
        port = a[2]
    return port


def tryPort(port=0):
    """Checks if the given port is unused
    @param port: the port number or 0 for a random port
    @type port: integer
    @returns: port number or None if in use
    @rtype: integer or None
    """

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        try:
            s.bind(('', port))
            port = s.getsockname()[1]
        except socket.error, e:
            if e.args[0] != errno.EADDRINUSE:
                raise
            port = None
    finally:
        s.close()

    return port
