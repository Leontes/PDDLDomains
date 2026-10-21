#!/usr/bin/env bash
# Descarga y compila los generadores externos de problemas en tools/:
#
# * tools/pddl-generators: https://github.com/AI-Planning/pddl-generators (los de la IPC y la
#   colección de Hoffmann), commit fijo. Solo se compilan los que usa pddldomains.
# * tools/ipc2023/<dominio>: los generadores de los dominios de la IPC 2023 clásica
#   (https://github.com/ipc2023-classical/domain-<dominio>), también con commit fijo.
#
# Requisitos: git, make, g++, gcc, cmake y python3. (El de parking, el único de Perl, está
# portado a Python en src/pddldomains/generators/parking.py y no necesita nada.)
#
# Uso: scripts/build_generators.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/tools"
mkdir -p "$TOOLS"

# Clona (o actualiza) un repositorio en un commit fijo.
checkout() {
    local url="$1" dir="$2" ref="$3"
    if [ ! -d "$dir/.git" ]; then
        git clone --quiet "$url" "$dir"
    fi
    if ! git -C "$dir" cat-file -e "$ref^{commit}" 2>/dev/null; then
        git -C "$dir" fetch --quiet origin
    fi
    git -C "$dir" checkout --quiet "$ref"
}

PDDL_GENERATORS_REF="e6277fb"
checkout https://github.com/AI-Planning/pddl-generators.git "$TOOLS/pddl-generators" "$PDDL_GENERATORS_REF"
# Solo se compilan los de C/C++ que usa pddldomains; barman, elevators, floortile,
# scanalyzer, transport y woodworking son scripts de Python y no necesitan nada.
for generator in blocksworld driverlog gripper nomystery visitall zenotravel; do
    echo "== pddl-generators/$generator"
    make -C "$TOOLS/pddl-generators/$generator" > /dev/null
done

declare -A IPC2023=(
    [folding]=461be00
    [labyrinth]=822a999
    [recharging-robots]=49ecb85
    [ricochet-robots]=ebf3050
    [rubiks-cube]=fecf8e3
    [slitherlink]=65fd96b
)
for domain in "${!IPC2023[@]}"; do
    echo "== ipc2023/$domain"
    checkout "https://github.com/ipc2023-classical/domain-$domain.git" "$TOOLS/ipc2023/$domain" "${IPC2023[$domain]}"
done
echo "Generadores en $TOOLS (pddl-generators $PDDL_GENERATORS_REF)"
