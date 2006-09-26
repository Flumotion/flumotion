rpm: dist
	rm *.rpm
	for i in RPMS SRPMS SOURCES SPECS BUILD; do mkdir -p rpmbuild/$$i; done
	cp flumotion-*.tar.bz2 rpmbuild/SOURCES
	rpmbuild --define "_topdir `pwd`/rpmbuild" -ba flumotion.spec
	mv rpmbuild/RPMS/*/flumotion*.rpm .
	mv rpmbuild/SRPMS/flumotion*.rpm .
	rm -rf rpmbuild
