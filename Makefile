DESTDIR =

prefix = $(DESTDIR)/usr
datarootdir = $(prefix)/share

exec_prefix = $(prefix)
bindir = $(exec_prefix)/bin
libdir = $(exec_prefix)/lib

VERSION = $(shell python setup.py --version)

PY_VERSION = $(shell python -c "import sys;v=sys.version_info;print('{}.{}'.format(v.major, v.minor))")
PY_SITE    = $(libdir)/python$(PY_VERSION)/site-packages

L10N_LANGS   = fr
PO_FILES     = $(L10N_LANGS:%=locales/%/LC_MESSAGES/carp.po)
MO_FILES     = $(PO_FILES:%.po=%.mo)
DEST_MO      = $(L10N_LANGS:%=$(datarootdir)/locales/%/LC_MESSAGES/carp.mo)
TRANSLATABLE = carp/carpcli.py carp/carpgui.py carp/stash_manager.py

.PHONY: clean dist install uninstall lang uplang

man/%.gz: man/%.org
	emacs -Q --batch --eval "(progn (require 'org)(require 'ox-man)(find-file \"$<\")(org-man-export-to-man)(kill-buffer))"
	mv $(<:%.org=%.man) $(<:%.org=%)
	gzip $(@:%.gz=%)

carp.desktop: $(MO_FILES)
	python generate_desktop_file.py

dist: carp.desktop man/carp.1.gz man/carp.conf.5.gz
	python setup.py install --root=$(DESTDIR)/
	install -d -m755	$(datarootdir)/bash-completion/completions
	install -d -m755	$(datarootdir)/zsh/site-functions
	install -d -m755	$(datarootdir)/man/man1
	install -d -m755	$(datarootdir)/man/man5
	install -d -m755	$(datarootdir)/licenses/carp
	install -d -m755	$(datarootdir)/applications

	install -D -m644 LICENSE			$(datarootdir)/licenses/carp/LICENSE
	install -D -m644 carp.desktop		$(datarootdir)/applications/carp.desktop
	install -D -m644 man/carp.1.gz		$(datarootdir)/man/man1/carp.1.gz
	install -D -m644 man/carp.conf.5.gz $(datarootdir)/man/man5/carp.conf.5.gz
	install -D -m644 data/carp-completions $(datarootdir)/bash-completion/completions/carp
	install -D -m644 data/_carp $(datarootdir)/zsh/site-functions/_carp

	install -D -m644 data/carp_icon.svg $(datarootdir)/icons/hicolor/scalable/apps/carp.svg

install: dist
	update-desktop-database $(datarootdir)/applications
	gtk-update-icon-cache $(datarootdir)/icons/hicolor

clean:
	find . -type d -name __pycache__ | xargs rm -rf
	rm -rf build carp.egg-info dist
	rm -f man/carp.1.gz man/carp.conf.5.gz
	rm -f carp.desktop

uninstall:
	rm -rf $(PY_SITE)/carp $(PY_SITE)/carp-*-py$(PY_VERSION).egg-info
	rm -f $(bindir)/carp $(bindir)/carp-icon
	rm -f $(datarootdir)/applications/carp.desktop
	rm -rf $(datarootdir)/licenses/carp
	rm -f $(datarootdir)/man/man1/carp.1.gz
	rm -f $(datarootdir)/man/man5/carp.conf.5.gz
	rm -f $(datarootdir)/bash-completion/completions/carp
	rm -f $(datarootdir)/zsh/site-functions/_carp
	rm -f $(datarootdir)/icons/hicolor/scalable/apps/carp.svg
	gtk-update-icon-cache $(datarootdir)/icons/hicolor

locales/carp.pot:
	mkdir -p locales
	xgettext --language=Python --keyword=_ \
		--copyright-holder="Carp volunteers" \
		--package-name=Carp --package-version=$(VERSION) \
		--from-code=UTF-8 --output=locales/carp.pot $(TRANSLATABLE)
	sed -i -e "s/SOME DESCRIPTIVE TITLE./Carp Translation Effort/" \
		-e "s|Content-Type: text/plain; charset=CHARSET|Content-Type: text/plain; charset=UTF-8|" \
		-e "s|Copyright (C) YEAR|Copyright (C) $(shell date +%Y)|" \
		locales/carp.pot

%.po: locales/carp.pot
	mkdir -p $(@D)
	msginit -l $(@:locales/%/LC_MESSAGES/carp.po=%) \
		--no-translator -i $< -o $@

locales/%/LC_MESSAGES/carp.mo: locales/%/LC_MESSAGES/carp.po
	msgfmt -o $@ $<

$(datarootdir)/locales/%/LC_MESSAGES/carp.mo: locales/%/LC_MESSAGES/carp.mo
	install -D -m644 $< $@

lang: $(PO_FILES)

%.po~:
	msgmerge --lang $(@:locales/%/LC_MESSAGES/carp.po~=%) \
		-o $@ $(@:%~=%) locales/carp.pot
	sed -i -e "s|Copyright (C) [0-9]*|Copyright (C) $(shell date +%Y)|" \
		-e "s|Id-Version: Carp [0-9.]*|Id-Version: Carp $(VERSION)|" \
		$@
	cp $@ $(@:%~=%) && rm $@

uplang: $(PO_FILES:%=%~)
