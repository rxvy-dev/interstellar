# NixOS / nix:   nix-shell --run ./bin/interstellar
{ pkgs ? import <nixpkgs> {} }:
pkgs.mkShell {
  nativeBuildInputs = with pkgs; [ wrapGAppsHook4 gobject-introspection ];
  buildInputs = with pkgs; [
    (python3.withPackages (ps: [ ps.pygobject3 ps.pycairo ]))
    gtk4 vte-gtk4 gtk4-layer-shell gsettings-desktop-schemas jetbrains-mono
  ];
  shellHook = ''
    export INTERSTELLAR_PYTHON=$(command -v python3)
    export XDG_DATA_DIRS=${pkgs.gsettings-desktop-schemas}/share/gsettings-schemas/${pkgs.gsettings-desktop-schemas.name}:${pkgs.gtk4}/share/gsettings-schemas/${pkgs.gtk4.name}:$XDG_DATA_DIRS
    echo "Interstellar dev shell — run: ./bin/interstellar"
  '';
}
