# include this snippet for the pychecker stuff
# Makefile.am needs to define
# PYCHECKER_WHITELIST
# and
# PYCHECKER_BLACKLIST

pychecker_setup = `ls $(top_srcdir)/misc/setup.py 2> /dev/null`
pychecker_help = `ls $(top_srcdir)/misc/pycheckerhelp.py 2> /dev/null`
pychecker =					\
	PYTHONPATH=`pwd`			\
	pychecker -Q -F misc/pycheckerrc	\
	$(pychecker_setup)			\
	$(pychecker_help)

pychecker_all_files = $(filter-out $(PYCHECKER_BLACKLIST),$(wildcard $(PYCHECKER_WHITELIST)))

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

pychecker:
	@echo running pychecker ...
	@$(pychecker) $(pychecker_all_files) 2>/dev/null || make pycheckerverbose

pycheckerverbose:
	@echo running pychecker verbose ...
	$(pychecker) $(pychecker_all_files)
