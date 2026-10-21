# Índice del catálogo

<!-- Generado con `pddldomains index`: no editar a mano. -->

[English version](INDEX.md)

41 colecciones, 737 problemas y 100 planes de referencia.
Los tipos se deducen de lo que usa cada dominio con sus problemas (no de lo que declaran); ver `pddldomains types` y `docs/es/catalogo.md`. Las erratas corregidas están en la ficha (`info.toml`) de cada colección.

## Por tipo

| Tipo | Colecciones | Problemas | Qué es |
|------|------------:|----------:|--------|
| `classical` | 23 | 460 | clásico: sin números (salvo costes), tiempo, PDDL 3 ni PDDL+ |
| `strips` | 15 | 300 | clásico solo con STRIPS (y tipos) |
| `adl` | 8 | 160 | clásico con negación, disyunción, igualdad, cuantificadores o efectos condicionales |
| `costs` | 16 | 320 | costes de acción (:action-costs) sin más números |
| `numeric` | 16 | 237 | fluentes numéricos (PDDL 2.1) |
| `temporal` | 14 | 207 | acciones durativas (PDDL 2.1) |
| `continuous` | 5 | 35 | efectos continuos en acciones durativas |
| `derived` | 1 | 20 | predicados derivados (PDDL 2.2) |
| `til` | 1 | 20 | literales iniciales temporizados (PDDL 2.2) |
| `preferences` | 6 | 118 | preferencias (PDDL 3) |
| `constraints` | 7 | 137 | restricciones de trayectoria (PDDL 3) |
| `pddlplus` | 2 | 18 | procesos y eventos (PDDL+) |

## Por versión de PDDL

Cada colección está en el nivel más alto de lo que usa (ver `pddldomains levels`). Un planificador que llega al nivel N tiene que poder con los niveles 1 a N: `pddldomains dataset --max-level N`.

| Nivel | Versión | Añade | Colecciones | Problemas | Hasta aquí |
|------:|---------|-------|------------:|----------:|-----------:|
| 1 | STRIPS | STRIPS sin tipos | 2 | 40 | 40 |
| 2 | PDDL 1.2 | ADL: tipos, negación, disyunción, igualdad, cuantificadores y efectos condicionales | 4 | 80 | 120 |
| 3 | PDDL 2.1 | fluentes numéricos (y costes de acción) y acciones durativas | 24 | 421 | 541 |
| 4 | PDDL 2.2 | predicados derivados y literales iniciales temporizados | 2 | 40 | 581 |
| 5 | PDDL 3 | preferencias, restricciones de trayectoria y fluentes de objetos | 7 | 138 | 719 |
| 6 | PDDL+ | procesos y eventos | 2 | 18 | 737 |

**1 · STRIPS**: [ipc-1998/gripper-round-1-strips](ipc-1998/gripper-round-1-strips/info.toml), [ipc-2000/blocks-strips-untyped](ipc-2000/blocks-strips-untyped/info.toml)

**2 · PDDL 1.2**: [ipc-2011/tidybot-sequential-satisficing](ipc-2011/tidybot-sequential-satisficing/info.toml), [ipc-2011/visit-all-sequential-satisficing](ipc-2011/visit-all-sequential-satisficing/info.toml), [ipc-2023-classical/rubiks-cube](ipc-2023-classical/rubiks-cube/info.toml), [ipc-2023-classical/slitherlink](ipc-2023-classical/slitherlink/info.toml)

**3 · PDDL 2.1**: [ipc-2002/driverlog-time-simple-automatic](ipc-2002/driverlog-time-simple-automatic/info.toml), [ipc-2002/zenotravel-time-simple-automatic](ipc-2002/zenotravel-time-simple-automatic/info.toml), [ipc-2011/barman-sequential-satisficing](ipc-2011/barman-sequential-satisficing/info.toml), [ipc-2011/elevator-sequential-satisficing](ipc-2011/elevator-sequential-satisficing/info.toml), [ipc-2011/floor-tile-sequential-satisficing](ipc-2011/floor-tile-sequential-satisficing/info.toml), [ipc-2011/no-mystery-sequential-satisficing](ipc-2011/no-mystery-sequential-satisficing/info.toml), [ipc-2011/openstacks-sequential-satisficing](ipc-2011/openstacks-sequential-satisficing/info.toml), [ipc-2011/parc-printer-sequential-satisficing](ipc-2011/parc-printer-sequential-satisficing/info.toml), [ipc-2011/parking-sequential-satisficing](ipc-2011/parking-sequential-satisficing/info.toml), [ipc-2011/peg-solitaire-sequential-satisficing](ipc-2011/peg-solitaire-sequential-satisficing/info.toml), [ipc-2011/scanalyzer-3d-sequential-satisficing](ipc-2011/scanalyzer-3d-sequential-satisficing/info.toml), [ipc-2011/sokoban-sequential-satisficing](ipc-2011/sokoban-sequential-satisficing/info.toml), [ipc-2011/transport-sequential-satisficing](ipc-2011/transport-sequential-satisficing/info.toml), [ipc-2011/woodworking-sequential-satisficing](ipc-2011/woodworking-sequential-satisficing/info.toml), [ipc-2023-classical/folding](ipc-2023-classical/folding/info.toml), [ipc-2023-classical/labyrinth](ipc-2023-classical/labyrinth/info.toml), [ipc-2023-classical/recharging-robots](ipc-2023-classical/recharging-robots/info.toml), [ipc-2023-classical/ricochet-robots](ipc-2023-classical/ricochet-robots/info.toml), [ipc-2023-numeric/counters](ipc-2023-numeric/counters/info.toml), [ipc-2023-numeric/zenotravel](ipc-2023-numeric/zenotravel/info.toml), [propios/greenhouse](propios/greenhouse/info.toml), [smtplan/generator-linear](smtplan/generator-linear/info.toml), [smtplan/generator-nonlinear](smtplan/generator-nonlinear/info.toml), [smtplan/generator-toricelli](smtplan/generator-toricelli/info.toml)

**4 · PDDL 2.2**: [ipc-2004/psr-middle-derived-predicates-adl](ipc-2004/psr-middle-derived-predicates-adl/info.toml), [ipc-2004/satellite-time-time-windows-strips](ipc-2004/satellite-time-time-windows-strips/info.toml)

**5 · PDDL 3**: [ipc-2006/pathways-preferences-complex](ipc-2006/pathways-preferences-complex/info.toml), [ipc-2006/pipesworld-preferences-complex](ipc-2006/pipesworld-preferences-complex/info.toml), [ipc-2006/storage-preferences-complex](ipc-2006/storage-preferences-complex/info.toml), [ipc-2006/storage-preferences-qualitative](ipc-2006/storage-preferences-qualitative/info.toml), [ipc-2006/tpp-preferences-complex](ipc-2006/tpp-preferences-complex/info.toml), [ipc-2006/trucks-preferences-complex](ipc-2006/trucks-preferences-complex/info.toml), [ipc-2006/trucks-time-constraints](ipc-2006/trucks-time-constraints/info.toml)

**6 · PDDL+**: [smtplan/car-nodrag](smtplan/car-nodrag/info.toml), [smtplan/generator-events](smtplan/generator-events/info.toml)

## ipc-1998

| Colección | Tipos | Nivel | Problemas | Erratas | Descripción |
|-----------|-------|-------|----------:|--------:|-------------|
| [gripper-round-1-strips](ipc-1998/gripper-round-1-strips/info.toml) | `classical` `strips` | 1 (STRIPS) | 20 |  | Un robot con dos pinzas lleva bolas de una habitación a otra. |

## ipc-2000

| Colección | Tipos | Nivel | Problemas | Erratas | Descripción |
|-----------|-------|-------|----------:|--------:|-------------|
| [blocks-strips-untyped](ipc-2000/blocks-strips-untyped/info.toml) | `classical` `strips` | 1 (STRIPS) | 20 |  | El mundo de bloques: apilar bloques con una mano. Versión STRIPS sin tipos. |

## ipc-2002

| Colección | Tipos | Nivel | Problemas | Erratas | Descripción |
|-----------|-------|-------|----------:|--------:|-------------|
| [driverlog-time-simple-automatic](ipc-2002/driverlog-time-simple-automatic/info.toml) | `numeric` `temporal` | 3 (PDDL 2.1) | 17 | 1 | Logística en la que los camiones necesitan un conductor para moverse; acciones durativas de duración fija. |
| [zenotravel-time-simple-automatic](ipc-2002/zenotravel-time-simple-automatic/info.toml) | `numeric` `temporal` | 3 (PDDL 2.1) | 17 | 1 | Transporte de personas en avión entre ciudades; acciones durativas de duración fija. |

## ipc-2004

| Colección | Tipos | Nivel | Problemas | Erratas | Descripción |
|-----------|-------|-------|----------:|--------:|-------------|
| [psr-middle-derived-predicates-adl](ipc-2004/psr-middle-derived-predicates-adl/info.toml) | `classical` `adl` `derived` | 4 (PDDL 2.2) | 20 |  | Restauración del suministro eléctrico (Power Supply Restoration) tras una avería: el estado de la red se deduce con predicados derivados. |
| [satellite-time-time-windows-strips](ipc-2004/satellite-time-time-windows-strips/info.toml) | `numeric` `temporal` `til` | 4 (PDDL 2.2) | 20 | 1 | Satélites que orientan sus instrumentos para tomar imágenes y enviarlas a tierra, solo posible en ventanas de tiempo (literales iniciales temporizados). |

## ipc-2006

| Colección | Tipos | Nivel | Problemas | Erratas | Descripción |
|-----------|-------|-------|----------:|--------:|-------------|
| [pathways-preferences-complex](ipc-2006/pathways-preferences-complex/info.toml) | `numeric` `temporal` `preferences` `constraints` | 5 (PDDL 3) | 20 | 2 | Rutas bioquímicas: reacciones para sintetizar sustancias; acciones durativas, cantidades numéricas y preferencias. |
| [pipesworld-preferences-complex](ipc-2006/pipesworld-preferences-complex/info.toml) | `numeric` `temporal` `preferences` `constraints` | 5 (PDDL 3) | 18 |  | Transporte de derivados del petróleo por una red de oleoductos; acciones durativas y preferencias. |
| [storage-preferences-complex](ipc-2006/storage-preferences-complex/info.toml) | `temporal` `preferences` `constraints` | 5 (PDDL 3) | 20 | 1 | Storage con acciones durativas, preferencias (en el objetivo, en las condiciones de las acciones y en las restricciones de trayectoria) y restricciones duras. |
| [storage-preferences-qualitative](ipc-2006/storage-preferences-qualitative/info.toml) | `preferences` `constraints` | 5 (PDDL 3) | 20 | 1 | Grúas que mueven cajas entre almacenes y contenedores, con preferencias en el objetivo y restricciones de trayectoria (`sometime`, `at-most-once`), sin tiempo. |
| [tpp-preferences-complex](ipc-2006/tpp-preferences-complex/info.toml) | `numeric` `temporal` `preferences` `constraints` | 5 (PDDL 3) | 20 | 1 | Traveling Purchaser Problem: camiones que compran mercancías en mercados y las llevan a depósitos; acciones durativas, cantidades numéricas y preferencias. |
| [trucks-preferences-complex](ipc-2006/trucks-preferences-complex/info.toml) | `numeric` `temporal` `preferences` `constraints` | 5 (PDDL 3) | 20 |  | Trucks con acciones durativas, preferencias y restricciones de trayectoria. |
| [trucks-time-constraints](ipc-2006/trucks-time-constraints/info.toml) | `numeric` `temporal` `constraints` | 5 (PDDL 3) | 20 |  | Logística con camiones cuyo espacio de carga se organiza por zonas; algunos paquetes tienen plazo de entrega (restricciones `within` sobre acciones durativas). |

## ipc-2011

| Colección | Tipos | Nivel | Problemas | Erratas | Descripción |
|-----------|-------|-------|----------:|--------:|-------------|
| [barman-sequential-satisficing](ipc-2011/barman-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | Un robot barman prepara cócteles con vasos, coctelera y dispensadores. |
| [elevator-sequential-satisficing](ipc-2011/elevator-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | Ascensores rápidos y lentos que llevan pasajeros entre plantas. |
| [floor-tile-sequential-satisficing](ipc-2011/floor-tile-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 | 2 | Robots que pintan las baldosas de un suelo sin pisar las ya pintadas. |
| [no-mystery-sequential-satisficing](ipc-2011/no-mystery-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | Logística con combustible limitado. |
| [openstacks-sequential-satisficing](ipc-2011/openstacks-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | Producción de pedidos minimizando las pilas abiertas a la vez. Un dominio por problema. |
| [parc-printer-sequential-satisficing](ipc-2011/parc-printer-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | Planificación de los trabajos de una impresora modular de PARC. Un dominio por problema. |
| [parking-sequential-satisficing](ipc-2011/parking-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 | 1 | Aparcar coches en fila reorganizándolos en las plazas de una calle. |
| [peg-solitaire-sequential-satisficing](ipc-2011/peg-solitaire-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | El solitario de clavijas (senku). |
| [scanalyzer-3d-sequential-satisficing](ipc-2011/scanalyzer-3d-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | Cintas transportadoras que llevan plantas por un escáner para analizarlas. |
| [sokoban-sequential-satisficing](ipc-2011/sokoban-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | El juego Sokoban: empujar cajas hasta sus destinos. |
| [tidybot-sequential-satisficing](ipc-2011/tidybot-sequential-satisficing/info.toml) | `classical` `adl` | 2 (PDDL 1.2) | 20 | 2 | Robots domésticos que recogen objetos y los dejan en su sitio, con un carrito. |
| [transport-sequential-satisficing](ipc-2011/transport-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | Logística con camiones de capacidad limitada en una red de carreteras. |
| [visit-all-sequential-satisficing](ipc-2011/visit-all-sequential-satisficing/info.toml) | `classical` `strips` | 2 (PDDL 1.2) | 20 |  | Visitar todas las casillas de una cuadrícula. |
| [woodworking-sequential-satisficing](ipc-2011/woodworking-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 | 1 | Una carpintería: cortar, cepillar, lijar y barnizar piezas con distintas máquinas. |

## ipc-2023-classical

| Colección | Tipos | Nivel | Problemas | Erratas | Descripción |
|-----------|-------|-------|----------:|--------:|-------------|
| [folding](ipc-2023-classical/folding/info.toml) | `classical` `adl` `costs` | 3 (PDDL 2.1) | 20 (20 con plan) |  | Plegar una cadena en una cuadrícula, rotándola por sus nodos, hasta que tome una forma dada. |
| [labyrinth](ipc-2023-classical/labyrinth/info.toml) | `classical` `adl` `costs` | 3 (PDDL 2.1) | 20 (20 con plan) |  | Un robot que recorre un laberinto de cartas que se desplazan por filas y columnas, como en el juego de mesa. |
| [recharging-robots](ipc-2023-classical/recharging-robots/info.toml) | `classical` `adl` `costs` | 3 (PDDL 2.1) | 20 (20 con plan) |  | Robots con batería limitada que tienen que vigilar zonas de un grafo y pueden pasarse carga entre ellos. |
| [ricochet-robots](ipc-2023-classical/ricochet-robots/info.toml) | `classical` `adl` `costs` | 3 (PDDL 2.1) | 20 (20 con plan) |  | El juego Ricochet Robots: robots que se deslizan en una dirección hasta chocar con una barrera o con otro robot. |
| [rubiks-cube](ipc-2023-classical/rubiks-cube/info.toml) | `classical` `adl` | 2 (PDDL 1.2) | 20 (20 con plan) |  | El cubo de Rubik, con efectos condicionales. |
| [slitherlink](ipc-2023-classical/slitherlink/info.toml) | `classical` `adl` | 2 (PDDL 1.2) | 20 |  | El pasatiempo Slitherlink: trazar un único circuito cerrado por los bordes de una cuadrícula numerada. |

## ipc-2023-numeric

| Colección | Tipos | Nivel | Problemas | Erratas | Descripción |
|-----------|-------|-------|----------:|--------:|-------------|
| [counters](ipc-2023-numeric/counters/info.toml) | `numeric` | 3 (PDDL 2.1) | 20 | 1 | Contadores que se incrementan y decrementan hasta cumplir unas desigualdades entre ellos. |
| [zenotravel](ipc-2023-numeric/zenotravel/info.toml) | `numeric` | 3 (PDDL 2.1) | 20 | 1 | Aviones que transportan personas entre ciudades y gastan combustible según la velocidad. |

## propios

| Colección | Tipos | Nivel | Problemas | Erratas | Descripción |
|-----------|-------|-------|----------:|--------:|-------------|
| [greenhouse](propios/greenhouse/info.toml) | `numeric` `temporal` `continuous` | 3 (PDDL 2.1) | 2 |  | Invernadero creado a mano para reunir casos límite de PDDL 2.1 temporal que no aparecen en ningún benchmark público encontrado (ni en las IPC ni en los de COLIN/OPTIC o VAL): efectos continuos dentro de `forall` y de `when`, efectos condicionales con condiciones `over all`, `?duration` no fijo en efectos `at start`, una duración cuyo máximo depende de una variable que cambia de forma continua y un efecto condicional sobre una variable continua. |

## smtplan

| Colección | Tipos | Nivel | Problemas | Erratas | Descripción |
|-----------|-------|-------|----------:|--------:|-------------|
| [car-nodrag](smtplan/car-nodrag/info.toml) | `numeric` `pddlplus` | 6 (PDDL+) | 10 | 1 | Un coche que acelera y frena para recorrer una distancia y parar a tiempo: la velocidad y la posición cambian con un proceso, y un evento rompe el motor si se fuerza. |
| [generator-events](smtplan/generator-events/info.toml) | `numeric` `temporal` `continuous` `pddlplus` | 6 (PDDL+) | 8 | 3 | Un generador que tiene que funcionar un tiempo seguido mientras se reposta desde depósitos: una acción durativa, un proceso no lineal y dos eventos. |
| [generator-linear](smtplan/generator-linear/info.toml) | `numeric` `temporal` `continuous` | 3 (PDDL 2.1) | 8 | 1 | El generador con repostaje lineal: PDDL 2.1 con efectos continuos lineales, sin procesos ni eventos. |
| [generator-nonlinear](smtplan/generator-nonlinear/info.toml) | `numeric` `temporal` `continuous` | 3 (PDDL 2.1) | 8 | 2 | El generador con repostaje no lineal: PDDL 2.1 con efectos continuos no lineales. |
| [generator-toricelli](smtplan/generator-toricelli/info.toml) | `numeric` `temporal` `continuous` | 3 (PDDL 2.1) | 9 | 3 | El generador con repostaje según la ley de Torricelli: efectos continuos no lineales y duraciones que dependen del estado. |
