# -*- Mode: Python; test-case-name: flumotion.test.test_common_package -*-
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

import os
import sys
import tempfile

from flumotion.common import common, package
from flumotion.common import testsuite

# for our simulation of failIfRaises
import twisted.python.util
from twisted.trial.unittest import FailTest


class TestPackagePath(testsuite.TestCase):

    def setUp(self):
        # store our old sys.path
        self.syspath = sys.path[:]

        self._assertions = 0

        self.cwd = os.getcwd()
        self.tempdir = tempfile.mkdtemp('', 'trialTestPackagePath.')

        self._createOne()
        self._createTwo()
        self._createTwoBis()

    def tearDown(self):
        # clean up for other tests

        # imported packages are kept both in globals() and in sys.modules,
        # both need to be deleted
        # import code; code.interact(local=locals())
        for s in ['', '.A', '.B']:
            n = "mypackage%s" % s
            if n in globals():
                del globals()[n]
            if n in sys.modules:
                del sys.modules[n]
        sys.path = self.syspath
        os.system("rm -r %s" % self.tempdir)

        # sanity checks
        self.failIf('mypackage' in globals())
        self.failIf('mypackage' in sys.modules.keys())

        self.assertRaises(ImportError, self._import, "mypackage")
        self.assertRaises(ImportError, self._import, "mypackage.A")
        self.assertRaises(ImportError, self._import, "mypackage.B")

    # create the file system layout for our test

    def _createOne(self):
        self.onedir = os.path.join(self.tempdir, "one")
        os.mkdir(self.onedir)
        onepackagedir = os.path.join(self.onedir, "mypackage")
        os.mkdir(onepackagedir)
        open(os.path.join(onepackagedir, "__init__.py"), "w").close()
        handle = open(os.path.join(onepackagedir, "A.py"), "w")
        handle.write('me = "A"\n')
        # pull in registerPackagePath for the test we will do
        handle.write('from flumotion.common.package import getPackager\n')
        handle.close()

    def _createTwo(self):
        self.twodir = os.path.join(self.tempdir, "two")
        os.mkdir(self.twodir)
        twopackagedir = os.path.join(self.twodir, "mypackage")
        os.mkdir(twopackagedir)
        open(os.path.join(twopackagedir, "__init__.py"), "w").close()
        handle = open(os.path.join(twopackagedir, "B.py"), "w")
        handle.write('me = "B"\n')
        handle.close()

    def _createTwoBis(self):
        self.twobisdir = os.path.join(self.tempdir, "twobis")
        os.mkdir(self.twobisdir)
        twobispackagedir = os.path.join(self.twobisdir, "mypackage")
        os.mkdir(twobispackagedir)
        open(os.path.join(twobispackagedir, "__init__.py"), "w").close()
        handle = open(os.path.join(twobispackagedir, "B.py"), "w")
        handle.write('me = "B bis"\n')
        handle.close()


    # a way of making import statements into functions so we can
    # use assertRaises

    def _import(self, which):
        exec("import %s" % which)

    # a way of failing if a method call raises

    def _failIfRaises(self, exception, f, *args, **kwargs):
        self._assertions += 1
        try:
            if twisted.python.util.raises(exception, f, *args, **kwargs):
                raise FailTest(
                    '%s raised' % exception.__name__)
        except FailTest, e:
            raise
        except:
            # import traceback; traceback.print_exc()
            raise FailTest(
                '%s raised instead of %s' % (
                sys.exc_info()[0],
                exception.__name__))

    def testCurrent(self):
        packager = package.getPackager()
        packager.registerPackagePath(self.tempdir, 'tempdir')
        packager.unregister()

    def testTwoStackedProjects(self):
        # we create two stacked projects both with a "mypackage" import space
        # project one:
        #   tempdir/one/mypackage/__init__.py
        #   tempdir/one/mypackage/A.py
        # project two:
        #   tempdir/two/mypackage/__init__.py
        #   tempdir/two/mypackage/B.py

        # each has parts of a common namespace
        # set up stuff so we can import from both
        # this shows we can develop uninstalled against uninstalled

        # first show we cannot import mypackage.A
        self.assertRaises(ImportError, self._import, "mypackage.A")

        # set up so we can import mypackage.A from project one
        sys.path.append(self.onedir)
        self._failIfRaises(ImportError, self._import, "mypackage.A")

        # but still can't from import mypackage.B from project two
        self.assertRaises(ImportError, self._import, "mypackage.B")

        # but we can pull in registerPackagePath from project one to bootstrap,
        # and register the "mypackage" import space from project two
        import mypackage.A
        mypackage.A.getPackager().registerPackagePath(
            os.path.join(self.tempdir, 'two'), "two",
            prefix='mypackage')
        self._failIfRaises(ImportError, self._import, "mypackage.B")

    def testPyRegisterBeforeImportWithoutHooks(self):
        # when registering mypackage paths before having imported anything,
        # __path__ does not get fixed up automatically

        # first show we cannot import mypackage
        self.assertRaises(ImportError, self._import, "mypackage")

        # register both projects
        packager = package.getPackager()
        packager.registerPackagePath(self.onedir, 'one', prefix="mypackage")
        packager.registerPackagePath(self.twodir, 'two', prefix="mypackage")

        self._failIfRaises(ImportError, self._import, "mypackage")

        # "import mypackage" imported mypackage from twodir, because it
        # was added last; also, it only has twodir in its __path__
        import mypackage
        self.failUnless(mypackage.__file__.startswith(self.twodir))
        self.assertEquals(len(mypackage.__path__), 1)
        self.failUnless(mypackage.__path__[0].startswith(self.twodir))

        # this means we can only import mypackage.B now, not mypackage.A
        self._failIfRaises(ImportError, self._import, "mypackage.B")
        self.assertRaises(ImportError, self._import, "mypackage.A")
        packager.unregister()

    def testRegisterBeforeImportWithPackager(self):
        # when registering package paths before having imported anything,
        # and using import hooks, we can fix __path__

        packager = package.Packager()

        # first show we cannot import mypackage
        self.assertRaises(ImportError, self._import, "mypackage")

        # register both projects
        packager.registerPackagePath(self.onedir, "one", "mypackage")
        packager.registerPackagePath(self.twodir, "two", "mypackage")

        import mypackage
        #self._failIfRaises(ImportError, self._import, "mypackage")

        # "import mypackage" imported mypackage from twodir, because it
        # was added last; but now it has twodir, onedir in its __path__
        import mypackage
        self.failUnless(mypackage.__file__.startswith(self.twodir))
        self.assertEquals(len(mypackage.__path__), 2)
        self.failUnless(mypackage.__path__[0].startswith(self.twodir))
        self.failUnless(mypackage.__path__[1].startswith(self.onedir))

        # this means we can import both mypackage.B and mypackage.A
        self._failIfRaises(ImportError, self._import, "mypackage.B")
        self._failIfRaises(ImportError, self._import, "mypackage.A")

        # cleanup and do some imports to verify tearDown clears them
        packager.unregister()
        import mypackage.A
        import mypackage.B

    def testRegisterNewPackagePath(self):
        # register package paths and import, then register a new package
        # path (twobis) and verify B is the new version

        packager = package.Packager()

        # first show we cannot import mypackage
        self.assertRaises(ImportError, self._import, "mypackage")

        # register one and two
        packager.registerPackagePath(self.onedir, "one", "mypackage")
        packager.registerPackagePath(self.twodir, "two", "mypackage")

        self._failIfRaises(ImportError, self._import, "mypackage")
        import mypackage.B
        self.assertEquals(mypackage.B.me, "B")

        # now register the twobis dir for key two, so it replaces the previous
        packager.registerPackagePath(self.twobisdir, "two", "mypackage")

        # package mypackage.B should have been rebuilt
        self.failUnless(mypackage.B.__file__.startswith(self.twobisdir))
        self.assertEquals(mypackage.B.me, "B bis")

        # cleanup and do some imports to verify tearDown clears them
        packager.unregister()
        import mypackage.A
        import mypackage.B

    def testPackagerWithNonePrefix(self):
        # see if import hooks don't mess up non prefix hooks
        packager = package.Packager()
        try:
            from xml.dom.html import HTMLDOMImplementation
        except ImportError:
            return
        HTMLDOMImplementation
        packager.unregister()


class TestRecursively(testsuite.TestCase):

    def testListDir(self):
        self.tempdir = tempfile.mkdtemp()

        # empty tree
        a = os.path.join(self.tempdir, 'A')
        common.ensureDir(a, "a description")
        dirs = package._listDirRecursively(self.tempdir)
        self.assertEquals(dirs, [])

        # add a non-python file
        os.system("touch %s" % os.path.join(a, 'test'))
        dirs = package._listDirRecursively(self.tempdir)
        self.assertEquals(dirs, [])

        # add a python file; should now get returned
        os.system("touch %s" % os.path.join(a, 'test.py'))
        dirs = package._listDirRecursively(self.tempdir)
        self.assertEquals(dirs, [a])

        # add another level
        b = os.path.join(self.tempdir, 'B')
        b = os.path.join(self.tempdir, 'B')
        common.ensureDir(b, "a description")
        c = os.path.join(b, 'C')
        common.ensureDir(c, "a description")
        dirs = package._listDirRecursively(self.tempdir)
        self.assertEquals(dirs, [a])

        # add a non-python file
        os.system("touch %s" % os.path.join(c, 'test'))
        dirs = package._listDirRecursively(self.tempdir)
        self.assertEquals(dirs, [a])

        # add a python file; should now get returned
        os.system("touch %s" % os.path.join(c, 'test.py'))
        dirs = package._listDirRecursively(self.tempdir)
        self.assertEquals(dirs.sort(), [a, c].sort())

        # cleanup
        os.system("rm -r %s" % self.tempdir)

    def testListPyfile(self):
        self.tempdir = tempfile.mkdtemp()

        # empty tree
        a = os.path.join(self.tempdir, 'A')
        common.ensureDir(a, "a description")
        dirs = package._listPyFileRecursively(self.tempdir)
        self.assertEquals(dirs, [])

        # add a non-python file
        os.system("touch %s" % os.path.join(a, 'test'))
        dirs = package._listPyFileRecursively(self.tempdir)
        self.assertEquals(dirs, [])

        # add a __init__ file
        os.system("touch %s" % os.path.join(a, '__init__.py'))
        dirs = package._listPyFileRecursively(self.tempdir)
        self.assertEquals(dirs, [])
        os.system("touch %s" % os.path.join(a, '__init__.pyc'))
        dirs = package._listPyFileRecursively(self.tempdir)
        self.assertEquals(dirs, [])

        # add a python file; should now get returned
        test1 = os.path.join(a, 'test.py')
        os.system("touch %s" % test1)
        dirs = package._listPyFileRecursively(self.tempdir)
        self.assertEquals(dirs, [test1])

        # add another level
        b = os.path.join(self.tempdir, 'B')
        common.ensureDir(b, "a description")
        c = os.path.join(b, 'C')
        common.ensureDir(c, "a description")
        dirs = package._listPyFileRecursively(self.tempdir)
        self.assertEquals(dirs, [test1])

        # add a non-python file
        os.system("touch %s" % os.path.join(c, 'test'))
        dirs = package._listPyFileRecursively(self.tempdir)
        self.assertEquals(dirs, [test1])

        # add a python file; should now get returned
        test2 = os.path.join(c, 'test.py')
        os.system("touch %s" % test2)
        dirs = package._listPyFileRecursively(self.tempdir)
        self.assertEquals(dirs.sort(), [test1, test2].sort())
        mods = package.findEndModuleCandidates(self.tempdir,
            prefix='')
        self.assertEquals(mods, ['B.C.test', 'A.test'])

        # add a python file but with .c; should now get returned, but
        # no new module candidate
        test3 = os.path.join(c, 'test.pyc')
        os.system("touch %s" % test3)
        dirs = package._listPyFileRecursively(self.tempdir)
        self.assertEquals(dirs.sort(), [test1, test2, test3].sort())

        mods = package.findEndModuleCandidates(self.tempdir,
            prefix='')
        self.assertEquals(mods, ['B.C.test', 'A.test'])

        # cleanup
        os.system("rm -r %s" % self.tempdir)
