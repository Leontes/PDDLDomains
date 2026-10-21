# Revisión (`pddldomains lint`)

[English](../en/lint.md) · **Español**

Revisa dominios y problemas y da sus hallazgos como un compilador:

```
dominios/ipc-2006/tpp-preferences-complex/p01.pddl:60: aviso [val-strict-comparison] 5 comparaciones…
```

```bash
pddldomains lint                              # todo el catálogo
pddldomains lint ipc-2011/tidybot-sequential-satisficing ipc-2006/tpp-preferences-complex/p03
pddldomains lint ruta/a/un/directorio         # domain.pddl (o domain-pNN.pddl) y sus problemas
pddldomains lint problema.pddl --domain d.pddl
pddldomains lint --val ...                    # además, la comprobación de sintaxis de VAL
pddldomains lint -v ...                       # incluye los hallazgos 'info'
pddldomains lint --errors-only --format json ...
```

Los códigos (`[undeclared-requirement]`…) son identificadores fijos, en inglés; los mensajes
salen en el idioma de la herramienta (`--lang es` o `PDDLDOMAINS_LANG=es`; ver el
[README](../../README.es.md)). Sale con código 1 si hay algún error. Hay tres niveles:

- **error**: lo que un planificador estricto rechazaría;
- **aviso** (`warning` en el JSON): PDDL válido que suele ser una errata o que alguna herramienta no lleva bien;
- **info** (solo con `-v`): requisitos declarados que no se usan.

`pddldomains generate` y `pddldomains sources fetch` revisan automáticamente lo que generan
o traen. El catálogo no tiene ningún error (lo comprueba `tests/test_lint.py`).

## Las erratas del catálogo

Cada comprobación de esta tabla salió de una errata real, y la revisión las encuentra todas en
los ficheros originales (`tests/test_sources.py`):

| Código | Nivel | Errata de origen |
|--------|-------|------------------|
| `undeclared-requirement` | error | (\*) `total-cost` sin `:action-costs` (floor-tile), `not` sin `:negative-preconditions` (tidybot, pathways), `#t` sin `:continuous-effects` (generator), métrica `total-time` sin `:numeric-fluents` (driverlog y zenotravel temporales), línea `:requirements` comentada (counters, zenotravel numérico) |
| `glued-dash` | error | (‡) `?g -goods` (tpp), `?t -tank` (generator-events) |
| `malformed-variable` | error | (‡) `? g`, `? duration` (generator-toricelli); también parámetros sin `?` |
| `type-without-names` | error | (‡) una línea `- board` sin objetos (woodworking p10) |
| `function-without-parentheses` | error | (‡) `(= d 0)` en lugar de `(= (d) 0)` (car) |
| `repeated-value` | error | (‡) dos valores iniciales para la misma función (pathways) |
| `domain-mismatch` | error | (‡) problemas de `generator` para un dominio `generator2` |
| `repeated-declaration` | error | (‡) el tipo `area` declarado dos veces (storage) |
| `shared-name` | aviso | (‡) el dominio se llama como un tipo (satellite), acciones como predicados (floor-tile), problemas como el dominio (parking), un objeto como su tipo (tidybot) |
| `uninitialized-function` | aviso | (‡) `ptime` sin valor inicial (generator-events): VAL rechaza cualquier plan. Solo cuenta las funciones que el dominio lee, de acciones que pueden aplicarse en ese problema, y que no reciben valor con `assign` |

## Nombres, tipos y estructura

| Código | Nivel | Qué |
|--------|-------|-----|
| `syntax` | error | paréntesis desequilibrados o un fichero que no es `(define ...)` |
| `invalid-section`, `repeated-section` | error | secciones mal formadas o repetidas |
| `unknown-section` | aviso | una sección que no es de PDDL |
| `unknown-requirement` | error | un requisito que no existe (con sugerencia) |
| `undeclared-predicate`, `undeclared-function`, `undeclared-object`, `undeclared-type` | error | nombres sin declarar (con sugerencia del más parecido) |
| `unbound-variable` | error | una variable que no es parámetro ni está cuantificada |
| `arity` | error | un predicado o función con un número de argumentos distinto del declarado |
| `function-as-predicate`, `predicate-as-function` | error | se usa uno donde va el otro |
| `undeclared-preference` | error | `is-violated` de una preferencia que no existe |
| `incompatible-type` | aviso | un objeto de `:init` de un tipo que no encaja con el del predicado |
| `repeated-fact` | aviso | el mismo hecho dos veces en `:init` |
| `missing-goal` | error | un problema sin `:goal` |
| `missing-effect` | aviso | una acción sin `:effect` |
| `invalid-formula`, `invalid-effect`, `invalid-expression`, `invalid-term`, `invalid-fact`, `invalid-value`, `invalid-declaration`, `invalid-field`, `missing-field-value`, `invalid-parameters`, `unnamed-operator`, `invalid-derived`, `invalid-metric`, `invalid-domain`, `invalid-type`, `dash-without-type` | error | construcciones mal formadas |
| `unused-requirement` | info | un requisito declarado que no se usa |

## Lo que VAL no lleva bien

Ver [val.md](val.md). Son avisos: el fichero es correcto, pero VAL falla o da un resultado
equivocado con él.

| Código | Qué pasa con VAL |
|--------|------------------|
| `val-missing-init` | sin sección `:init` (opcional en PDDL) falla con un fallo de segmentación |
| `val-function-named-like-domain` | una función que se llama como el dominio: fallo de segmentación |
| `val-object-fluents` | cualquier dominio con `:object-fluents`: fallo de segmentación |
| `val-empty-constraints` | con `(:constraints (and))` cuenta como violadas todas las preferencias del objetivo |
| `val-hold-after` | evalúa mal `hold-after` |
| `val-strict-comparison` | en las restricciones evalúa `>` como `>=` (y `<` como `<=`): explica los valores distintos de VAL en tpp y pathways |
| `val-parser` | los mensajes de `Parser` de VAL, con `--val` |

## Qué no comprueba

La revisión es estática: no instancia el problema, así que no sabe si tiene solución ni si
una función que solo se inicializa para algunos objetos llega a leerse sin valor. Para eso
están los planes de referencia y `pddldomains validate`.
