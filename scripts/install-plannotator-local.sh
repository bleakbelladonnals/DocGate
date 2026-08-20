#!/bin/sh
set -eu
version="v0.24.2"
expected="d590a1b786b1299a25d228b30d5b97307a73b4f8f3c4ccade59f40b02f89f15d"
target=".tools/plannotator"
mkdir -p .tools
curl -fL "https://github.com/backnotprop/plannotator/releases/download/${version}/plannotator-darwin-arm64" -o "${target}.download"
actual=$(shasum -a 256 "${target}.download" | awk '{print $1}')
if [ "$actual" != "$expected" ]; then
  rm -f "${target}.download"
  echo "Checksum mismatch: expected ${expected}, got ${actual}" >&2
  exit 1
fi
mv "${target}.download" "$target"
chmod 755 "$target"
"$target" --version

