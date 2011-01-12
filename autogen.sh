#!/bin/sh
set -x

# Make sure we have common
if test ! -f common/flumotion-trial;
  then
  echo "+ Setting up common submodule"
  git submodule init
fi
git submodule update

# source helper functions
if test ! -f common/flumotion-trial;
  then
  echo There is something wrong with your source tree.
  echo You are missing common/flumotion-trial
  exit 1
fi

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
