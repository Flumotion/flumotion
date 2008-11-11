# add a trial target
# include from flumotion/test/Makefile.am
# set TRIAL_ENV

# FIXME: doing "trial flumotion.test" from this directory causes the
# base package flumotion tests to run always, instead of
# the current package

trial: rm-trial-test-log
	@if test -z "$(TRIAL_ENV)"; then 				\
	    echo "Please set the TRIAL_ENV Makefile variable."; 	\
	    exit 1; fi
	$(TRIAL_ENV) $(top_srcdir)/common/flumotion-trial -r default  \
						flumotion.test 2>&1     \
		| tee trial.test.log;					\
	if ! test $${PIPESTATUS[0]} -eq 0;				\
	then								\
		make rm-trial-test-log;					\
		exit 1;							\
	fi;								\
	$(TRIAL_ENV) $(top_srcdir)/common/flumotion-trial -r gtk2	\
						flumotion.test 2>&1     \
		| tee -a trial.test.log;				\
	if test $${PIPESTATUS[0]} -eq 0;				\
	then 								\
	    rm -fr $(top_builddir)/flumotion/test/_trial_temp;		\
	    if test -e trial.test.log; then				\
		if grep "Could not import" trial.test.log > /dev/null;	\
		then							\
	            exit 1;						\
		fi;							\
	    fi;								\
            make rm-trial-test-log;					\
	else								\
            make rm-trial-test-log;					\
	    exit 1;							\
	fi
	@rm -fr $(top_builddir)/flumotion/test/*.pyc

rm-trial-test-log:
	@if test -e trial.test.log; then rm trial.test.log; fi
