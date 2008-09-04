SUBDIRS = glade image

desktopdir = $(datadir)/applications
desktop_in_files = flumotion-admin.desktop.in
desktop_DATA = $(desktop_in_files:.desktop.in=.desktop)

pixmapdir = $(datadir)/pixmaps
pixmap_DATA = image/flumotion.png

xsldir = $(pkgdatadir)
xsl_DATA = upgrade-to-0.2.0.xsl upgrade-to-0.3.2.xsl upgrade-to-0.4.1.xsl \
	upgrade=to-0.5.3.xsl

scriptdir = $(pkgdatadir)
script_DATA = make-dummy-cert

halpolicydir = $(datadir)/hal/fdi/policy/20thirdparty
halpolicy_DATA = 91-flumotion-device-policy.fdi

templatedir = $(pkgdatadir)
template_DATA = cortado-template.html

EXTRA_DIST = \
        $(desktop_in_files) \
	$(pixmap_DATA) \
	$(xsl_DATA) \
	$(script_DATA) \
	$(halpolicy_DATA) \
	$(template_DATA)
