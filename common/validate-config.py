# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

import warnings

from flumotion.manager import manager, config
from flumotion.common import registry, setup


def _promoteDeprecationWarnings():
    warnings.filterwarnings('error', category=DeprecationWarning,
                            module='.*flumotion.*')


def _validateManagerPlugs(conf):
    for socket, plugs in conf.plugs.items():
        for args in plugs:
            defs = registry.getRegistry().getPlug(args['type'])
            e = defs.getEntry()
            e.getModuleName()


def validate(fname, onlyManager=False, printOnly=False):
    if not printOnly:
        _promoteDeprecationWarnings()

    conf = config.ManagerConfigParser(fname)
    conf.parseBouncerAndPlugs()
    _validateManagerPlugs(conf)

    if onlyManager:
        return

    conf = config.PlanetConfigParser(fname)
    conf.parse()


def main(argv):
    import optparse

    usage = '%prog [options] CONFIG_FILENAME'
    parser = optparse.OptionParser(usage=usage)

    parser.add_option('-m', '--manager-only',
                      action='store_true', dest='managerOnly', default=False,
                      help=("only validate manager-specific parts - flow and"
                            " atmosphere configurations will not be checked"))

    parser.add_option('-p', '--print-only',
                      action='store_true', dest='printOnly', default=False,
                      help=("only print warnings - don't actually raise"
                            " DeprecationWarning instances"))

    options, args = parser.parse_args(argv)
    if not len(args):
        parser.error('No filename given.')

    setup.setup()
    setup.setupPackagePath()

    validate(args[0], options.managerOnly, options.printOnly)


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
