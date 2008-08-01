import os
import sys

VERSION = '0.5.2'


def process_template(input, output=None, vardict={}):
    if output is None and input.endswith('.in'):
        output = input[:-3]
    data = open(input).read()
    for key, value in vardict.items():
        data = data.replace(key, value)
    open(output, 'w').write(data)

scriptdir = os.path.dirname(__file__)
svnroot = os.path.abspath(os.path.join(scriptdir, '..'))

vardict = {
     '@LIBDIR@': os.path.join(svnroot),
     '@VERSION@': VERSION,
     }

process_template(os.path.join(svnroot, 'bin', 'flumotion-admin.in'),
                 os.path.join(svnroot, 'bin', 'flumotion-admin.py'),
                 vardict=vardict)
process_template(os.path.join(svnroot, 'flumotion',
                              'configure', 'uninstalled.py.in'),
                 vardict=vardict)
