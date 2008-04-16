# depends on dpkg-dev

# adebversion = $(shell dpkg-parsechangelog -l$(1)|egrep ^Version|cut -d\  -f2)
# @debversion=$(call debversion,pkg/$*/changelog);

deb-%: dist-gzip pkg/%/rules pkg/%/control pkg/%/changelog
	distdir=$(PACKAGE)-$(VERSION); \
	pkgorig=$(PACKAGE)_$(VERSION).orig.tar.gz; \
	rm -fr $$distdir $$pkgorig $$pkgorig.tmp-nest && \
	tar xfz $$distdir.tar.gz && \
	cp -r pkg/$* $$distdir/debian && \
	ln -s $$distdir.tar.gz $$pkgorig && \
	cd $$distdir && \
	debuild -S && \
	rm -fr $$distdir && \

