AUTOMAKE_OPTIONS = dist-bzip2 no-dist-gzip 1.8

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

test:
	@make check -C flumotion/test

check-docs:
	@make check -C doc/reference

coverage:
	@trial --coverage coverage -R flumotion.test
	@$(PYTHON) tools/show-coverage.py _trial_temp/coverage/flumotion.*

pychecker:
	pychecker -F misc/pycheckerrc \
		flumotion/common/*.py \
		flumotion/component/*.py \
		flumotion/manager/*.py \
		flumotion/worker/*.py

fixme:
	tools/fixme | less -R

release: dist
	make $(PACKAGE)-$(VERSION).tar.bz2.md5

# generate md5 sum files
%.md5: %
	md5sum $< > $@
