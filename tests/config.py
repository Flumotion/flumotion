from common import unittest

import flumotion.config

class TestConfig(unittest.TestCase):
    def testVariables(self):
        assert hasattr(flumotion.config, 'datadir')
        assert isinstance(flumotion.config.datadir, str)
        assert hasattr(flumotion.config, 'uidir')
        assert isinstance(flumotion.config.uidir, str)

    def testUninstalled(self):
        assert flumotion.config.installed == 0

if __name__ == '__main__':
     unittest.main()
