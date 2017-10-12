DEST=/usr
L10N=fr
PYDEST=/
PKGNAME=carp

all: build

build: $(PKGNAME).1 $(PKGNAME).conf.5 $(PKGNAME).desktop
	gzip -k $(PKGNAME).1
	gzip -k $(PKGNAME).conf.5
	sed -i "s|CARP_L10N_PATH = \"./locales\"|CARP_L10N_PATH = \"$(DEST)/share/locale\"|" $(PKGNAME)/*.py
	@echo "python setup.py build"
	@python setup.py build &> /dev/null

$(PKGNAME).1: man/$(PKGNAME).1.org
	emacs -Q --batch --eval "(progn (require 'org)(require 'ox-man)(find-file \"man/$(PKGNAME).1.org\")(org-man-export-to-man)(kill-buffer))"
	@mv man/$(PKGNAME).1.man $(PKGNAME).1

$(PKGNAME).conf.5: man/$(PKGNAME).conf.5.org
	emacs -Q --batch --eval "(progn (require 'org)(require 'ox-man)(find-file \"man/$(PKGNAME).conf.5.org\")(org-man-export-to-man)(kill-buffer))"
	@mv man/$(PKGNAME).conf.5.man $(PKGNAME).conf.5

$(PKGNAME).desktop:
	python3 generate_translations.py compile

install: build
	install -d -m755	$(DEST)/bin
	install -d -m755	$(DEST)/share/bash-completion/completions
	install -d -m755	$(DEST)/share/zsh/site-functions
	install -d -m755	$(DEST)/share/man/man1
	install -d -m755	$(DEST)/share/man/man5
	install -d -m755	$(DEST)/share/licenses/$(PKGNAME)
	install -d -m755	$(DEST)/share/applications

	install -D -m755 $(PKGNAME).py			$(DEST)/bin/$(PKGNAME)
	install -D -m644 LICENSE				$(DEST)/share/licenses/$(PKGNAME)/LICENSE
	install -D -m644 $(PKGNAME).desktop		$(DEST)/share/applications/$(PKGNAME).desktop
	install -D -m644 $(PKGNAME).1.gz		$(DEST)/share/man/man1/$(PKGNAME).1.gz
	install -D -m644 $(PKGNAME).conf.5.gz	$(DEST)/share/man/man5/$(PKGNAME).conf.5.gz
	install -D -m644 dist/$(PKGNAME)-completions	$(DEST)/share/bash-completion/completions/$(PKGNAME)
	install -D -m644 dist/_$(PKGNAME)		$(DEST)/share/zsh/site-functions/_$(PKGNAME)

	install -D -m644 carp_icon.svg			$(DEST)/share/icons/hicolor/scalable/apps/carp.svg

	for lang in $(L10N) ; do \
	  install -d -m755 $(DEST)/share/locale/$$lang/LC_MESSAGES ; \
	  install -D -m644 locales/$$lang/LC_MESSAGES/$(PKGNAME).mo $(DEST)/share/locale/$$lang/LC_MESSAGES/$(PKGNAME).mo ; \
	done

	@echo "python setup.py install"
	@python setup.py install --root=$(PYDEST) --skip-build &>/dev/null

uninstall:
	rm $(DEST)/bin/$(PKGNAME)
	rm $(DEST)/share/applications/$(PKGNAME).desktop
	rm $(DEST)/share/licenses/$(PKGNAME)/LICENSE
	rmdir $(DEST)/share/licenses/$(PKGNAME)
	rm $(DEST)/share/man/man1/$(PKGNAME).1.gz
	rm $(DEST)/share/man/man5/$(PKGNAME).conf.5.gz
	rm $(DEST)/share/bash-completion/completions/$(PKGNAME)
	rm $(DEST)/share/zsh/site-functions/_$(PKGNAME)

	rm $(DEST)/share/icons/hicolor/scalable/apps/carp.svg

	for lang in $(L10N) ; do \
	  rm $(DEST)/share/locale/$$lang/LC_MESSAGES/carp.mo ; \
	done

	rm -rf $(PYDEST)usr/lib/python3.6/site-packages/carp*

clean:
	@sed -i "s|CARP_L10N_PATH = \"$(DEST)/share/locale\"|CARP_L10N_PATH = \"./locales\"|" $(PKGNAME)/*.py
	@rm -rf build carp.egg-info
	@rm $(PKGNAME).1.gz
	@rm $(PKGNAME).1
	@rm $(PKGNAME).conf.5.gz
	@rm $(PKGNAME).conf.5
	@rm $(PKGNAME).desktop
