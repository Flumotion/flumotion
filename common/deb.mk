# depends on dpkg-dev

# debversion = $(shell dpkg-parsechangelog -l$(1)|egrep ^Version|cut -d\  -f2)
# @debversion=$(call debversion,pkg/$*/changelog);

deb-%: dist-gzip pkg/%/control pkg/%/changelog
	distdir=$(PACKAGE)-$(VERSION); \
	rm -fr $$distdir && \
	tar xfz $$distdir.tar.gz && \
	mkdir $$distdir/debian && \
	cp pkg/debian-common/* $$distdir/debian && \
	cp pkg/$*/* $$distdir/debian && \
	cd $$distdir && \
	debuild -S -sa

deb-%-inc:
	dist=`echo $*|cut -d\- -f2`; \
	debchange \
	-c pkg/$*/changelog -i \
	--distribution $$dist -D $$dist
