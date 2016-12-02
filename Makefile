DEST=/usr
PYDEST=/
PKGNAME=carp

all: build

build: $(PKGNAME).1 $(PKGNAME).conf.5
	gzip -k $(PKGNAME).1
	gzip -k $(PKGNAME).conf.5
	@echo "python setup.py build"
	@python setup.py build &>/dev/null

$(PKGNAME).1: README.org
	emacs -Q --batch --eval "(progn (require 'org)(require 'ox-man)(find-file \"README.org\")(org-man-export-to-man)(kill-buffer))"
	@mv README.man $(PKGNAME).1

$(PKGNAME).conf.5: $(PKGNAME).conf.5.org
	emacs -Q --batch --eval "(progn (require 'org)(require 'ox-man)(find-file \"$(PKGNAME).conf.5.org\")(org-man-export-to-man)(kill-buffer))"
	@mv $(PKGNAME).conf.5.man $(PKGNAME).conf.5

install: build
	install -d -m755	$(DEST)/bin
	install -d -m755	$(DEST)/share/bash-completion/completions
	install -d -m755	$(DEST)/share/zsh/site-functions
	install -d -m755	$(DEST)/share/man/man1
	install -d -m755	$(DEST)/share/man/man5
	install -d -m755	$(DEST)/share/licenses/$(PKGNAME)

	install -D -m755 $(PKGNAME).py			$(DEST)/bin/$(PKGNAME)
	install -D -m644 LICENSE				$(DEST)/share/licenses/$(PKGNAME)/LICENSE
	install -D -m644 $(PKGNAME).1.gz		$(DEST)/share/man/man1/$(PKGNAME).1.gz
	install -D -m644 $(PKGNAME).conf.5.gz	$(DEST)/share/man/man5/$(PKGNAME).conf.5.gz
	install -D -m644 $(PKGNAME)-completions	$(DEST)/share/bash-completion/completions/$(PKGNAME)
	install -D -m644 _$(PKGNAME)			$(DEST)/share/zsh/site-functions/_$(PKGNAME)
	@echo "python setup.py install --root=$(PYDEST)"
	@python setup.py install --root=$(PYDEST) &>/dev/null

uninstall:
	rm $(DEST)/bin/$(PKGNAME)
	rm $(DEST)/share/licenses/$(PKGNAME)/LICENSE
	rmdir $(DEST)/share/licenses/$(PKGNAME)
	rm $(DEST)/share/man/man1/$(PKGNAME).1.gz
	rm $(DEST)/share/man/man5/$(PKGNAME).conf.5.gz
	rm $(DEST)/share/bash-completion/completions/$(PKGNAME)
	rm $(DEST)/share/zsh/site-functions/_$(PKGNAME)
	rm -rf $(PYDEST)/usr/lib/python3.5/site-packages/carp*

clean:
	@rm -rf build carp.egg-info
	@rm $(PKGNAME).1.gz
	@rm $(PKGNAME).1
	@rm $(PKGNAME).conf.5.gz
	@rm $(PKGNAME).conf.5
