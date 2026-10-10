PREFIX ?= /usr/local
DESTDIR ?=
VERSION := 1.0.0
APP := io.github.interstellar.Terminal

PYTHON ?= $(shell for p in /usr/bin/python3 python3 /usr/bin/python3.1[0-9]; do $$p -c 'import gi' 2>/dev/null && { echo $$p; break; }; done)

all:
	@echo "Nothing to compile (pure Python). Try: make install [PREFIX=/usr] [DESTDIR=...] | make check | make test | make deb | make rpm | make dist"

install:
	install -d $(DESTDIR)$(PREFIX)/bin $(DESTDIR)$(PREFIX)/share/interstellar
	install -m755 bin/interstellar $(DESTDIR)$(PREFIX)/bin/interstellar
	ln -sf interstellar $(DESTDIR)$(PREFIX)/bin/istl
	cp -r interstellar data $(DESTDIR)$(PREFIX)/share/interstellar/
	find $(DESTDIR)$(PREFIX)/share/interstellar -name __pycache__ -prune -exec rm -rf {} +
	rm -rf $(DESTDIR)$(PREFIX)/share/interstellar/data/*.desktop $(DESTDIR)$(PREFIX)/share/interstellar/data/*.metainfo.xml
	install -d $(DESTDIR)$(PREFIX)/share/icons $(DESTDIR)$(PREFIX)/share/applications $(DESTDIR)$(PREFIX)/share/metainfo
	cp -r data/icons/hicolor $(DESTDIR)$(PREFIX)/share/icons/
	install -m644 data/$(APP).desktop $(DESTDIR)$(PREFIX)/share/applications/
	install -m644 data/$(APP).metainfo.xml $(DESTDIR)$(PREFIX)/share/metainfo/
	install -Dm644 LICENSE $(DESTDIR)$(PREFIX)/share/licenses/interstellar/LICENSE
	-gtk-update-icon-cache -q -t $(DESTDIR)$(PREFIX)/share/icons/hicolor 2>/dev/null
	-update-desktop-database -q $(DESTDIR)$(PREFIX)/share/applications 2>/dev/null

uninstall:
	rm -rf $(DESTDIR)$(PREFIX)/share/interstellar $(DESTDIR)$(PREFIX)/bin/interstellar $(DESTDIR)$(PREFIX)/bin/istl \
	  $(DESTDIR)$(PREFIX)/share/applications/$(APP).desktop $(DESTDIR)$(PREFIX)/share/metainfo/$(APP).metainfo.xml \
	  $(DESTDIR)$(PREFIX)/share/licenses/interstellar
	find $(DESTDIR)$(PREFIX)/share/icons -name 'interstellar.*' -delete

dist:
	mkdir -p dist
	tar czf dist/interstellar-$(VERSION).tar.gz --transform 's,^\.,interstellar-$(VERSION),' \
	  --exclude=./dist --exclude=./.github --exclude=__pycache__ --exclude='*.pyc' --exclude=./.git .
	@echo dist/interstellar-$(VERSION).tar.gz

deb:
	sh packaging/build-deb.sh

rpm: dist
	rpmbuild -ta dist/interstellar-$(VERSION).tar.gz --define "_rpmdir $(CURDIR)/dist" --define "_srcrpmdir $(CURDIR)/dist"

check:
	PYTHONPATH=. $(PYTHON) -c 'import sys; from interstellar.doctor import main; sys.exit(main())'

test:
	PYTHONPATH=. $(PYTHON) -m unittest discover -s tests -v

run:
	./bin/interstellar --no-restore

.PHONY: all install uninstall dist deb rpm check test run
