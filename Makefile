DEST=/usr
PKGNAME=carp

all: build install

build:
	gzip -k $(PKGNAME).1

install:
	install -d -m755	$(DEST)/bin
	install -d -m755	$(DEST)/share/bash-completion/completions
	install -d -m755	$(DEST)/share/zsh/site-functions
	install -d -m755	$(DEST)/share/man/man1
	install -d -m755	$(DEST)/share/licenses/$(PKGNAME)

	install -D -m755 $(PKGNAME)				$(DEST)/bin/$(PKGNAME)
	install -D -m644 LICENSE				$(DEST)/share/licenses/$(PKGNAME)/LICENSE
	install -D -m644 $(PKGNAME).1.gz		$(DEST)/share/man/man1/$(PKGNAME).1.gz
	install -D -m644 $(PKGNAME)-completions	$(DEST)/share/bash-completion/completions/$(PKGNAME)
	install -D -m644 _$(PKGNAME)			$(DEST)/share/zsh/site-functions/_$(PKGNAME)

uninstall:
	rm $(DEST)/bin/$(PKGNAME)
	rm $(DEST)/share/licenses/$(PKGNAME)/LICENSE
	rmdir $(DEST)/share/licenses/$(PKGNAME)
	rm $(DEST)/share/man/man1/$(PKGNAME).1.gz
	rm $(DEST)/share/bash-completion/completions/$(PKGNAME)
	rm $(DEST)/share/zsh/site-functions/_$(PKGNAME)

clean:
	rm $(PKGNAME).1.gz
