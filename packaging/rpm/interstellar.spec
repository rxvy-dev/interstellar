# Fedora / RHEL 9+ (EPEL) / openSUSE:
#   make dist && rpmbuild -ta dist/interstellar-1.0.0.tar.gz      (or: make rpm)
Name:           interstellar
Version:        1.0.0
Release:        1%{?dist}
Summary:        A terminal that's out of this world
License:        MIT
URL:            https://github.com/rxvy-dev/interstellar
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  make
Requires:       python3 >= 3.9
%if 0%{?suse_version}
Requires:       python3-gobject python3-gobject-cairo python3-gobject-Gdk typelib-1_0-Gtk-4_0 typelib-1_0-Vte-3_91
%else
Requires:       python3-gobject python3-cairo gtk4 >= 4.10 vte291-gtk4
Recommends:     jetbrains-mono-fonts
%endif

%description
GTK 4 + VTE terminal with tabs, split panes, an animated starfield, Liquid Glass, 28 themes,
a theme studio, a command palette, quick-select hints, safe paste, session
restore, a drop-down mode and a GUI for every setting.

%prep
%autosetup

%build

%install
make install DESTDIR=%{buildroot} PREFIX=%{_prefix}

%files
%{_bindir}/interstellar
%{_bindir}/istl
%{_datadir}/interstellar/
%{_datadir}/applications/io.github.interstellar.Terminal.desktop
%{_datadir}/metainfo/io.github.interstellar.Terminal.metainfo.xml
%{_datadir}/icons/hicolor/*/*/interstellar*
%{_datadir}/licenses/interstellar/
