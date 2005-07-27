clean-local:
	@rm -rf _trial_temp

if HAVE_PYCHECKER
check-local: pychecker
endif

test:
	@make check -C flumotion/test

check-docs:
	@make check -C doc/reference

coverage:
	@true || trial --coverage coverage -R flumotion.test
	@test ! -z "$(COVERAGE_MODULES)" ||				\
	(echo Define COVERAGE_MODULES in your Makefile.am; exit 1)
	@keep="";							\
	for m in $(COVERAGE_MODULES); do				\
		echo adding $$m;					\
		keep="$$keep `ls _trial_temp/coverage/$$m*`";		\
	done;								\
	$(PYTHON) common/show-coverage.py $$keep

fixme:
	tools/fixme | less -R

release: dist
	make $(PACKAGE)-$(VERSION).tar.bz2.md5

# generate md5 sum files
%.md5: %
	md5sum $< > $@

# generate a sloc count
sloc:
	sloccount flumotion | grep "(SLOC)" | cut -d = -f 2

.PHONY: test
