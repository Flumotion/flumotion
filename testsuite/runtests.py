#!/usr/bin/env python
import glob
import os
import sys
import unittest

# testsuite srcdir
srcdir = os.path.join(os.path.split(os.path.abspath(__file__))[0], 'tests')

def gettestnames(dir):
    files = glob.glob(os.path.join(dir, '*.py'))
    fullnames = map(lambda x: x[:-3], files)
    names = map(lambda x: os.path.split(x)[1], fullnames)
    return names
        
suite = unittest.TestSuite()
loader = unittest.TestLoader()

try:
    import gst.ltihooks
    gst.ltihooks.uninstall()
except:
    pass

names = gettestnames(srcdir)

for name in names:
    print os.getcwd()
    suite.addTest(loader.loadTestsFromName(name))
    
testRunner = unittest.TextTestRunner()
result = testRunner.run(suite)
if not result.wasSuccessful():
   sys.exit(1)
