#!/usr/bin/env python
import glob
import os
import sys
import unittest

SKIP_FILES = ['common', 'runtests', 'webbie']

dir = os.path.split(os.path.abspath(__file__))[0]
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

for name in gettestnames():
    try:
        suite.addTest(loader.loadTestsFromName(name))
    except TypeError:
        print "give it up"
    
testRunner = unittest.TextTestRunner()
testRunner.run(suite)
