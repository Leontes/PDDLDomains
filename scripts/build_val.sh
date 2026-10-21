#!/usr/bin/env bash
# Descarga y compila VAL (https://github.com/KCL-Planning/VAL), el validador de planes PDDL.
# Deja los ejecutables Validate (valida planes) y Parser (comprueba la sintaxis) en
# tools/bin/. Requisitos: git, cmake y g++.
#
# Uso: scripts/build_val.sh [ref]   (ref: rama, tag o commit; por defecto, 3c7a1f3, el último
#                                    de la rama master, de 2021)
set -euo pipefail

REF="${1:-3c7a1f3}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/tools/VAL"
BUILD="$SRC/build"
BIN="$ROOT/tools/bin"

if [ ! -d "$SRC/.git" ]; then
    git clone https://github.com/KCL-Planning/VAL.git "$SRC"
fi
git -C "$SRC" fetch --quiet origin
git -C "$SRC" checkout --quiet "$REF"

cmake -S "$SRC" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD" --target Validate Parser -j"$(nproc)"

# VAL enlaza con rpath $ORIGIN: libVAL.so tiene que estar junto a los ejecutables.
mkdir -p "$BIN"
cp "$BUILD/bin/Validate" "$BUILD/bin/Parser" "$BUILD/bin/libVAL.so" "$BIN/"
echo "VAL compilado en $BIN (commit $(git -C "$SRC" rev-parse --short HEAD))"
