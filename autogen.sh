#!/bin/sh
set -x
aclocal -I m4 || exit 1
# libtoolize --force
# autoheader
autoconf || exit 1
automake -a || exit 1
echo "./autogen.sh $@" > autoregen.sh
chmod +x autoregen.sh
./configure $@
