from common import unittest

import flumotion.config

class TestConfig(unittest.TestCase):
    def testGetDatadir(self):
        datadir = flumotion.config.datadir
        print "datadir is " + datadir

    def testGetUidir(self):
        uidir = flumotion.config.uidir
        print "uidir is " + uidir

    def testUninstalled(self):
        assert(flumotion.config.installed == 0)

if __name__ == '__main__':
     unittest.main()
