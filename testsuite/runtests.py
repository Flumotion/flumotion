#!/usr/bin/env python
import glob
import os
import sys
import unittest

SKIP_FILES = ['common', 'runtests', 'webbie']

dir = os.path.join(os.path.split(os.path.abspath(__file__))[0], 'tests')
os.chdir(dir)

def gettestnames():
    files = glob.glob('*.py')
    names = map(lambda x: x[:-3], files)
    for f in SKIP_FILES:
        if f in names:
             names.remove(f)
    return names
        
suite = unittest.TestSuite()
loader = unittest.TestLoader()

try:
    import gst.ltihooks
    gst.ltihooks.uninstall()
except:
    pass

for name in gettestnames():
    suite.addTest(loader.loadTestsFromName(name))
    
testRunner = unittest.TextTestRunner()
result = testRunner.run(suite)
if not result.wasSuccessful():
   sys.exit(1)
