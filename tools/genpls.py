#!/usr/bin/env python

"""Generate a playlist for use with our playlist-producer.

As the input you should pass a colon-separated list of comma-separated
info-bits of playlist entries. So, something like:

$ ./genpls.py file01.ogg,10:/full/path/to/file02.ogg,25,0,10:file03.ogg,37,5

will generate a playlist with the file01.ogg scheduled 10 seconds
ahead from the moment the script was run, then file02.ogg 15 seconds
after the start of file01.ogg with the duration of 10 seconds and then
12 seconds after the start of file02.ogg will start file03.ogg with an
offset 5 seconds into the file.

File paths starting with '.' and '~' will be expanded and converted to
full absolute paths, otherwise they will be used literally.
"""

import time


def genentry(fname, ts, offset=None, duration=None):
    buf = []
    buf.append('  <entry filename="%s" time="%s"' %
               (fname, time.strftime('%FT%T.00Z', time.gmtime(ts))))
    if offset:
        buf.append(' offset="%d"' % int(offset))
    if duration:
        buf.append(' duration="%r"' % duration)

    buf.append(' />')
    return ''.join(buf)


def genpls(entries):
    buf = ['<playlist>']
    for e in entries:
        buf.append(genentry(*e))
    buf.append('</playlist>')
    return '\n'.join(buf)


def main():
    import sys
    import os.path

    inspec = ' '.join(sys.argv[1:])
    plsl = inspec.split(':')
    if len(plsl) == 1 and plsl[0] == '':
        usage = ('%s filename,schedule_offset[,item_offset[,duration][:...]\n'
                 '\tschedule_offset: offset in secods from the current time\n'
                 '\t":" delimits several playlist entries\n'
                 '\t(see the script for more details and an example)')
        print >> sys.stderr, 'No input\nUsage: %s' % (usage % sys.argv[0])
        sys.exit(1)
    pls = []
    now = time.time()
    for e in plsl:
        te, entry = e.strip().split(','), ()
        path = te[0].strip()
        if path[0] in ('.', '~'):
            path = os.path.abspath(os.path.expanduser(path))
        entry += (path, )               # filename
        entry += (float(te[1]) + now, ) # time
        if len(te) > 2:                # offset
            entry += (float(te[2]), )
        if len(te) > 3:                # duration
            entry += (float(te[3]), )
        pls.append(entry)
    return genpls(pls)


if __name__ == '__main__':
    out = main()
    print out
