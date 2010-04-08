#!/bin/sh
set -x

rm -f .version
libtoolize -c --force || exit 1
autopoint --force || exit 1
cp -f common/intltool-Makefile.in.in po/Makefile.in.in
aclocal -I m4 -I common || exit 1
# autoheader || exit 1
autoconf || exit 1
automake -a -c -f || exit 1

echo "./autogen.sh $@" > autoregen.sh
chmod +x autoregen.sh
./configure $@
