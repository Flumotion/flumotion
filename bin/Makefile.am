bin_SCRIPTS = \
	flumotion-manager \
	flumotion-admin \
	flumotion-worker \
	flumotion-tester

sbin_SCRIPTS = flumotion

noinst_SCRIPTS = runtest

CLEANFILES = $(bin_SCRIPTS) $(sbin_SCRIPTS)

all: $(bin_SCRIPTS) $(sbin_SCRIPTS) $(noinst_SCRIPTS)
	@chmod +x $(bin_SCRIPTS) $(sbin_SCRIPTS) $(noinst_SCRIPTS)
