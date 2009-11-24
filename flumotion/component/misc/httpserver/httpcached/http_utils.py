# -*- Mode: Python; test-case-name: flumotion.test.test_component_providers -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

import urlparse


DEFAULT_PORTS = {'http': 80,
                 'https': 443}

DEFAULT_SCHEME = 'http'


class Dummy(object):
    pass


class Url(object):
    """
    Represents an HTTP URL.
    Can parse and can be serialized to string.
    """

    @classmethod
    def fromString(cls, url):
        url = url.strip()
        parsed = urlparse.urlparse(url)

        scheme = parsed[0]
        path = parsed[2]

        location = urlparse.urlunparse(('', '')+parsed[2:])

        if path == "":
            path = "/"
            location = "/" + location

        hostname = parsed[1]
        username = None
        password = None
        port = None

        if '@' in hostname:
            username, hostname = hostname.split('@', 1)
            if ':' in username:
                username, password = username.split(':', 1)

        host = hostname

        if ':' in hostname:
            hostname, portstr = hostname.rsplit(':', 1)
            port = int(portstr)
        else:
            port = DEFAULT_PORTS.get(scheme, None)


        obj = Dummy()

        obj.url = url
        obj.scheme = scheme
        obj.netloc = parsed[1]
        obj.host = host
        obj.path = path
        obj.params = parsed[3]
        obj.query = parsed[4]
        obj.fragment = parsed[5]
        obj.location = location
        obj.hostname = hostname
        obj.username = username
        obj.password = password
        obj.port = port

        obj.__class__ = cls

        return obj

    def __init__(self, scheme=None, hostname=None, path="/",
                 params="", query="", fragment="",
                 username=None, password=None, port=None):

        self.path = path
        self.params = params
        self.query = query
        self.fragment = fragment

        if hostname:
            # Absolute URL
            if username:
                if password:
                    netloc = username + ':' + password + '@' + hostname
                else:
                    netloc = username + '@' + hostname
            else:
                netloc = hostname

            if not scheme:
                scheme = DEFAULT_SCHEME

            host = hostname

            defport = DEFAULT_PORTS.get(scheme, None)

            if port:
                if port != defport:
                    netloc = netloc + ':' + str(port)
                    host = host + ':' + str(port)
            else:
                port = defport

            self.scheme = scheme
            self.netloc = netloc
            self.host = host
            self.hostname = hostname
            self.username = username
            self.password = password
            self.port = port

        else:
            # Relative URL
            self.scheme = ""
            self.netloc = ""
            self.host = ""
            self.hostname = ""
            self.username = None
            self.password = None
            self.port = None

        self.location = urlparse.urlunparse(('', '', self.path, self.params,
                                             self.query, self.fragment))

        self.url = urlparse.urlunparse((self.scheme, self.netloc, self.path,
            self.params, self.query, self.fragment))

    def toString(self):
        return self.url

    def __repr__(self):
        return self.url

if __name__ == "__main__":
    import sys

    url = Url.fromString(sys.argv[1])
    for a, v in url.__dict__.items():
        print a, ":", v
