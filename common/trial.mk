# add a trial target
# include from flumotion/test/Makefile.am

trial: rm-trial-test-log
	srcdir=`cd $(top_srcdir); pwd`;
	@PYTHONPATH=$(srcdir):$(PYTHONPATH)				\
		trial flumotion.test 2>&1		 		\
		| tee trial.test.log;					\
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
