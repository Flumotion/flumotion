# -*- Mode: Python; test-case-name: flumotion.test.test_common -*-
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

from flumotion.common.testsuite import TestCase

from flumotion.component.misc.httpserver.httpcached.http_utils import Url

#TODO: Add a test for multiple different query fields (reordering issues)


class TestURL(TestCase):

    def testQuotedSpaces(self):

        def check(_url, _loc, _path, _query, **kwargs):
            obj = Url(**kwargs)
            self.assertEqual(str(obj), _url)
            self.assertEqual(obj.url, _url)
            self.assertEqual(obj.location, _loc)
            self.assertEqual(obj.path, _path)
            self.assertEqual(obj.query, _query)

            obj2 = Url.fromString(_url)
            self.assertEqual(str(obj2), str(obj))
            self.assertEqual(str(obj2), _url)

        check("/", "/", "/", {}, path="/")

        check("/with%20lots/%20of%20/nasty%20spaces.txt",
              "/with%20lots/%20of%20/nasty%20spaces.txt",
              "/with lots/ of /nasty spaces.txt", {},
              path="/with lots/ of /nasty spaces.txt")

        check("/path?que%20ry=val%20u",
              "/path?que%20ry=val%20u",
              "/path", {"que ry": ["val u"]},
              path="/path", query={"que ry": ["val u"]})

    def testRelativeToString(self):

        def check(url, loc, **kwargs):
            obj = Url(**kwargs)
            self.assertEqual(str(obj), url)
            self.assertEqual(obj.url, url)
            self.assertEqual(obj.location, loc)

        check("/", "/")
        check("/", "/", path="/")
        check("/;P", "/;P", params="P")
        check("/?n=v", "/?n=v", query={"n": ["v"]})
        check("/#f", "/#f", fragment="f")
        check("/", "/", username="user")
        check("/", "/", password="test")
        check("/", "/", port=8080)
        check("/sub/dir/file.py;params?query=val#anchor",
              "/sub/dir/file.py;params?query=val#anchor",
              path="/sub/dir/file.py", params="params",
              query={"query": ["val"]}, fragment="anchor")
        check("/;params?query=val#anchor",
              "/;params?query=val#anchor",
              params="params",
              query={"query": ["val"]}, fragment="anchor")
        check("/sub/dir/file.py?query=val#anchor",
              "/sub/dir/file.py?query=val#anchor",
              path="/sub/dir/file.py",
              query={"query": ["val"]}, fragment="anchor")
        check("/sub/dir/file.py;params#anchor",
              "/sub/dir/file.py;params#anchor",
              path="/sub/dir/file.py", params="params",
              query={}, fragment="anchor")
        check("/sub/dir/file.py;params?query=val",
              "/sub/dir/file.py;params?query=val",
              path="/sub/dir/file.py", params="params",
              query={"query": ["val"]})

    def testAbsoluteToString(self):

        def check(url, loc, netloc, host, **kwargs):
            obj = Url(**kwargs)
            self.assertEqual(str(obj), url)
            self.assertEqual(obj.url, url)
            self.assertEqual(obj.netloc, netloc)
            self.assertEqual(obj.host, host)
            self.assertEqual(obj.location, loc)

        check("http://localhost/", "/", "localhost", "localhost",
              hostname="localhost")
        check("http://localhost/", "/", "localhost", "localhost",
              hostname="localhost", path="/")
        check("https://localhost/", "/", "localhost", "localhost",
              scheme='https', hostname="localhost")
        check("http://localhost:8080/", "/", "localhost:8080",
              "localhost:8080", hostname="localhost", port=8080)
        check("http://localhost/", "/", "localhost", "localhost",
              hostname="localhost", port=80)
        check("https://localhost:80/", "/", "localhost:80", "localhost:80",
              scheme="https", hostname="localhost", port=80)
        check("http://user@localhost/", "/", "user@localhost", "localhost",
               hostname="localhost", username='user')
        check("http://localhost/", "/", "localhost", "localhost",
              hostname="localhost", password='test')
        check("http://user:test@localhost/", "/", "user:test@localhost",
              "localhost", hostname="localhost",
              username='user', password='test')
        check("http://user:test@localhost:8080/", "/",
              "user:test@localhost:8080", "localhost:8080",
              hostname="localhost", port=8080,
              username='user', password='test')
        check("http://localhost/sub/dir/file.py;P?Q=#F",
              "/sub/dir/file.py;P?Q=#F", "localhost", "localhost",
              hostname="localhost", path="/sub/dir/file.py",
              query={"Q": [""]}, params="P", fragment="F")

    def testRelativeFromString(self):

        def check(url, **kwargs):
            obj = Url.fromString(url)
            self.assertEqual(obj.url, url)
            for n, v in kwargs.items():
                self.assertEqual(getattr(obj, n), v)

        self.assertEqual(type(Url.fromString("/")), type(Url()))

        check("/",
              scheme="", hostname="", path="/",
              username=None, password=None, port=None,
              params="", query={}, fragment="",
              location="/")
        check("/sub/file;param?query=string#fragment",
              scheme="", hostname="", path="/sub/file",
              username=None, password=None, port=None,
              params="param", query={"query": ["string"]},
              fragment="fragment",
              location="/sub/file;param?query=string#fragment")
        check("/;param?query=s1&query=s2#fragment",
              scheme="", hostname="", path="/",
              username=None, password=None, port=None,
              params="param", query={"query": ["s1", "s2"]},
              fragment="fragment",
              location="/;param?query=s1&query=s2#fragment")
        check("/sub/file?q1=s1#fragment",
              scheme="", hostname="", path="/sub/file",
              username=None, password=None, port=None,
              params="", query={"q1": ["s1"]},
              fragment="fragment",
              location="/sub/file?q1=s1#fragment")
        check("/sub/file;param#fragment",
              scheme="", hostname="", path="/sub/file",
              username=None, password=None, port=None,
              params="param", query={}, fragment="fragment",
              location="/sub/file;param#fragment")
        check("/sub/file;param?query=string",
              scheme="", hostname="", path="/sub/file",
              username=None, password=None, port=None,
              params="param", query={"query": ["string"]},
              fragment="", location="/sub/file;param?query=string")

    def testAbsoluteFromString(self):

        def check(url, netloc, host, **kwargs):
            obj = Url.fromString(url)
            self.assertEqual(obj.url, url)
            self.assertEqual(obj.netloc, netloc)
            self.assertEqual(obj.host, host)
            for n, v in kwargs.items():
                self.assertEqual(getattr(obj, n), v)

        check("http://user:test@localhost:8080"
              "/sub/file;param?query=string#fragment",
              "user:test@localhost:8080", "localhost:8080",
              scheme="http", hostname="localhost", path="/sub/file",
              username="user", password="test", port=8080,
              params="param", query={"query": ["string"]},
              fragment="fragment",
              location="/sub/file;param?query=string#fragment")

        check("https://user:test@localhost:8080"
              "/sub/file;param?q=s1&q=s2&q=s3#fragment",
              "user:test@localhost:8080", "localhost:8080",
              scheme="https", hostname="localhost", path="/sub/file",
              username="user", password="test", port=8080,
              params="param", query={"q": ["s1", "s2", "s3"]},
              fragment="fragment",
              location="/sub/file;param?q=s1&q=s2&q=s3#fragment")

        check("http://user@localhost:8080"
              "/sub/file;param?query=#fragment",
              "user@localhost:8080", "localhost:8080",
              scheme="http", hostname="localhost", path="/sub/file",
              username="user", password=None, port=8080,
              params="param", query={"query": [""]},
              fragment="fragment",
              location="/sub/file;param?query=#fragment")

        check("http://localhost:8080"
              "/sub/file;param?query=string#fragment",
              "localhost:8080", "localhost:8080",
              scheme="http", hostname="localhost", path="/sub/file",
              username=None, password=None, port=8080,
              params="param", query={"query": ["string"]},
              fragment="fragment",
              location="/sub/file;param?query=string#fragment")

        check("http://user:test@localhost"
              "/sub/file;param?query=string#fragment",
              "user:test@localhost", "localhost",
              scheme="http", hostname="localhost", path="/sub/file",
              username="user", password="test", port=80,
              params="param", query={"query": ["string"]},
              fragment="fragment",
              location="/sub/file;param?query=string#fragment")

        check("https://user:test@localhost"
              "/sub/file;param?query=string#fragment",
              "user:test@localhost", "localhost",
              scheme="https", hostname="localhost", path="/sub/file",
              username="user", password="test", port=443,
              params="param", query={"query": ["string"]},
              fragment="fragment",
              location="/sub/file;param?query=string#fragment")

        check("http://user:test@localhost:8080"
              "/;param?query=string#fragment",
              "user:test@localhost:8080", "localhost:8080",
              scheme="http", hostname="localhost", path="/",
              username="user", password="test", port=8080,
              params="param", query={"query": ["string"]},
              fragment="fragment",
              location="/;param?query=string#fragment")

        check("http://user:test@localhost:8080"
              "/sub/file?query=string#fragment",
              "user:test@localhost:8080", "localhost:8080",
              scheme="http", hostname="localhost", path="/sub/file",
              username="user", password="test", port=8080,
              params="", query={"query": ["string"]},
              fragment="fragment",
              location="/sub/file?query=string#fragment")

        check("http://user:test@localhost:8080/sub/file;param#fragment",
              "user:test@localhost:8080", "localhost:8080",
              scheme="http", hostname="localhost", path="/sub/file",
              username="user", password="test", port=8080,
              params="param", query={}, fragment="fragment",
              location="/sub/file;param#fragment")

        check("http://user:test@localhost:8080/sub/file;param?query=string",
              "user:test@localhost:8080", "localhost:8080",
              scheme="http", hostname="localhost", path="/sub/file",
              username="user", password="test", port=8080,
              params="param", query={"query": ["string"]},
              fragment="", location="/sub/file;param?query=string")
