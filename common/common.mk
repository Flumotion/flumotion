# these are toplevel targets
test:
	@make check -C flumotion/test

check-docs:
	@make check -C doc/reference

check-local-registry:
	$(top_builddir)/env bash -c 'export PYTHONPATH=$(FLUMOTION_DIR):$(top_srcdir)$${PYTHONPATH:+:$$PYTHONPATH} && export FLU_PROJECT_PATH=$(top_srcdir)$${FLU_PROJECT_PATH:+:$$FLU_PROJECT_PATH} && $(PYTHON) $(top_srcdir)/common/validate-registry.py'

# this is a target for any directory containing CONFIG in its Makefile.am
check-local-config:
	ret=0; for f in $(CONFIG); do echo "Validating $$f"; $(top_builddir)/env bash -c "export PYTHONPATH=$(FLUMOTION_DIR):$(top_srcdir)${PYTHONPATH:+:$PYTHONPATH} && $(PYTHON) $(top_srcdir)/common/validate-config.py $(srcdir)/$$f" || ret=1; done && exit $$ret

check-local-pep8:
	find $(top_srcdir)/flumotion ! -regex $(top_srcdir)/flumotion/extern/.\* -name \*.py | sort -u | xargs $(PYTHON) $(top_srcdir)/common/pep8.py --repeat
	find $(top_srcdir)/flumotion ! -regex $(top_srcdir)/flumotion/extern/.\* -name \*.py.in | sort -u | xargs $(PYTHON) $(top_srcdir)/common/pep8.py --repeat

# run our hacked-up version of trial with all the reactors that we actually use and build up the final result
coverage:
	@test ! -z "$(COVERAGE_MODULES)" ||				\
	(echo Define COVERAGE_MODULES in your Makefile.am; exit 1)
	rm -f flu-saved-coverage.pickle
	@$(top_builddir)/env bash -c "common/flumotion-trial --reactor default --temp-directory=_trial_coverage --coverage --saved-coverage=flu-saved-coverage.pickle $(COVERAGE_MODULES)"
	@$(top_builddir)/env bash -c "common/flumotion-trial --reactor gtk2    --temp-directory=_trial_coverage --coverage --saved-coverage=flu-saved-coverage.pickle $(COVERAGE_MODULES)"
	make show-coverage

show-coverage:
	@test ! -z "$(COVERAGE_MODULES)" ||				\
	(echo Define COVERAGE_MODULES in your Makefile.am; exit 1)
	@keep="";							\
	for m in $(COVERAGE_MODULES); do				\
		echo adding $$m;					\
		keep="$$keep `ls _trial_coverage/coverage/$$m*`";	\
	done;								\
	$(PYTHON) common/show-coverage.py $$keep

fixme:
	tools/fixme | less -R

# remove any cache written in distcheck	
dist-hook::
	rm -rf cache

release: dist
	make $(PACKAGE)-$(VERSION).tar.bz2.md5
	[ -r $(PACKAGE)-$(VERSION).tar.gz ] && make $(PACKAGE)-$(VERSION).tar.gz.md5

# generate md5 sum files
%.md5: %
	md5sum $< > $@

# generate a sloc count
sloc:
	sloccount flumotion | grep "(SLOC)" | cut -d = -f 2

.PHONY: test


locale-uninstalled-1:
	if test -d po; then \
	cd po; \
	make datadir=../$(top_builddir) itlocaledir=../$(top_builddir)/locale install; \
	fi

# the locale-uninstalled rule can be replaced with the following lines, 
# once we can depend on a newer intltool than 0.34.2
# 	if test -d po; then \
# 	cd po; \
# 	make datadir=../$(top_builddir) itlocaledir=../$(top_builddir)/locale install; \
# 	fi

locale-uninstalled:
	podir=$(top_builddir)/po; \
	localedir=$(top_builddir)/locale; \
        make -C $$podir; \
	for file in $$(ls $$podir/*.gmo); do \
	  lang=`basename $$file .gmo`; \
	  dir=$$localedir/$$lang/LC_MESSAGES; \
	  mkdir -p $$dir; \
          echo "installing $$podir/$$lang.gmo as $$dir/$(GETTEXT_PACKAGE).mo"; \
	  install $$podir/$$lang.gmo $$dir/$(GETTEXT_PACKAGE).mo; \
	done;

locale-uninstalled-clean:
	@-rm -rf _trial_temp
	@-rm -f flu-saved-coverage.pickle
	@-rm -rf $(top_builddir)/locale
