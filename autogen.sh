#!/bin/sh
set -x

libtoolize --force || exit 1
autopoint --force || exit 1
intltoolize --copy --force --automake || exit 1
aclocal -I m4 -I common || exit 1
# autoheader || exit 1
autoconf || exit 1
automake -a || exit 1

echo "./autogen.sh $@" > autoregen.sh
chmod +x autoregen.sh
./configure $@
