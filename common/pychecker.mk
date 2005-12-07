# include this snippet for the pychecker stuff
# Makefile.am needs to define
# PYCHECKER_WHITELIST
# and
# PYCHECKER_BLACKLIST

pychecker_setup = `ls $(top_srcdir)/misc/setup.py 2> /dev/null`
pychecker_help = `ls $(top_srcdir)/misc/pycheckerhelp.py 2> /dev/null`
pychecker =					\
	pychecker -Q -F misc/pycheckerrc	\
	$(pychecker_setup)			\
	$(pychecker_help)

# TODO: This looks a little confusing because out 0.10 files are names blah09.py
pychecker_all_files = $(filter-out $(PYCHECKER_BLACKLIST),$(wildcard $(PYCHECKER_WHITELIST)))
pychecker_08_files = $(filter %08.py,$(pychecker_all_files))
pychecker_10_files = $(filter %09.py,$(pychecker_all_files))
pychecker_indep_files = $(filter-out $(pychecker_08_files) $(pychecker_10_files),$(pychecker_all_files))

pychecker_indep = PYTHONPATH=`pwd` $(pychecker)
pychecker_08 = PYTHONPATH=$(PYGST_08_DIR):`pwd` FLU_GST_VERSION=0.8 $(pychecker)
pychecker_10 = PYTHONPATH=$(PYGST_10_DIR):`pwd` FLU_GST_VERSION=0.10 $(pychecker)

pychecker_if_08 = if test $(GST_08_SUPPORTED) = yes; then 
pychecker_if_10 = if test $(GST_10_SUPPORTED) = yes; then 
pychecker_fi = else echo "passing, gstreamer version not supported"; fi

# we redirect stderr so we don't get messages like
# warning: couldn't find real module for class SSL.Error (module name: SSL)
# which can't be turned off in pychecker
pycheckersplit:
	@echo running pychecker on each file ...
	@for file in $(pychecker_all_files)
	do \
		$(pychecker) $$file > /dev/null 2>&1			\
		if test $$? -ne 0; then 				\
			echo "Error on $$file";				\
			$(pychecker) $$file; break			\
		fi							\
	done

pychecker: pychecker08 pychecker10 pycheckerindep
	@true

pycheckerindep: 
	@echo running pychecker, gstreamer-agnostic files ...
	@$(pychecker_indep) $(pychecker_indep_files) 2>/dev/null || make pycheckerverboseindep

pychecker08:
	@echo running pychecker, gstreamer 0.8-specific code ...
	@$(pychecker_if_08) $(pychecker_08) $(pychecker_08_files) 2>/dev/null \
	  || make pycheckerverbose08; $(pychecker_fi)

pychecker10:
	@echo running pychecker, gstreamer 0.10-specific code ...
	@$(pychecker_if_10) $(pychecker_10) $(pychecker_10_files) 2>/dev/null \
	  || make pycheckerverbose10; $(pychecker_fi)

pycheckerverbose: pycheckerverbose08 pycheckerverbose10 pycheckerverboseindep

pycheckerverboseindep:
	@echo "running pychecker, gstreamer-agnostic files (verbose) ..."
	$(pychecker_indep) $(pychecker_indep_files)

pycheckerverbose08:
	@echo "running pychecker, gstreamer 0.8-specific code (verbose) ..."
	$(pychecker_if_08) $(pychecker_08) $(pychecker_08_files); $(pychecker_fi)

pycheckerverbose10:
	@echo "running pychecker, gstreamer 0.10-specific code (verbose) ..."
	$(pychecker_if_10) $(pychecker_10) $(pychecker_10_files); $(pychecker_fi)
