{
  pkgs ? import (fetchTarball {
    url = "https://github.com/NixOS/nixpkgs/archive/8ce73368d1efd4d657e9064d29b144a52046b4e8.tar.gz";
    sha256 = "1prpakwjqvzlprxviv97dginqic2a4s649l3a9kdn6pasqk9xf8p";
  }) { },
}:
pkgs.mkShell {
  packages = with pkgs; [
    python312
    kind
    kubectl
    trivy
    gh
  ];

  LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
    pkgs.stdenv.cc.cc.lib
    pkgs.zlib
  ];
}
