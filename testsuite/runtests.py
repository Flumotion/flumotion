#!/usr/bin/env python
import glob
import os
import sys
import unittest

SKIP_FILES = ['common', 'runtests', 'webbie']


dir = os.path.join(os.path.split(os.path.abspath(__file__))[0], 'tests')

def gettestnames(dir):
    files = glob.glob(os.path.join(dir, '*.py'))
    fullnames = map(lambda x: x[:-3], files)
    names = map(lambda x: os.path.split(x)[1], fullnames)
    for f in SKIP_FILES:
        if f in names:
             names.remove(f)
    print names
    return names
        
suite = unittest.TestSuite()
loader = unittest.TestLoader()

try:
    import gst.ltihooks
    gst.ltihooks.uninstall()
except:
    pass

names = gettestnames(dir)

# make sure we're in the subdirectory where tests/*.py lives
if os.environ.has_key('TESTSDIR'):
    os.chdir(os.environ['TESTSDIR'])
    sys.path.insert(0, os.environ['TESTSDIR'])
else:
    os.chdir('tests')

for name in names:
    print os.getcwd()
    suite.addTest(loader.loadTestsFromName(name))
    
testRunner = unittest.TextTestRunner()
result = testRunner.run(suite)
if not result.wasSuccessful():
   sys.exit(1)
