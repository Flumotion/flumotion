AUTOMAKE_OPTIONS = dist-bzip2 no-dist-gzip

ACLOCAL_AMFLAGS = -I m4

SUBDIRS = bin conf data flumotion doc m4

EXTRA_DIST = \
	LICENSE.GPL \
	LICENSE.Flumotion \
	flumotion.spec \
	misc/flu.modules \
	misc/jhbuildrc

clean-local:
	@rm -rf _trial_temp

coverage:
	trial --coverage coverage -R flumotion.test

release: dist
	make $(PACKAGE)-$(VERSION).tar.bz2.md5

# generate md5 sum files
%.md5: %
	md5sum $< > $@
