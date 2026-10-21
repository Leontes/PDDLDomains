"""Datasets: definiciones, filtros y exportación."""

import json
from pathlib import Path

import pytest

from pddldomains.catalog import Catalog
from pddldomains.datasets import (
    DATASETS_DIR,
    DatasetError,
    build_dataset,
    export,
    load_definition,
    select,
    to_csv,
    to_json,
    to_lines,
)


@pytest.mark.parametrize("path", sorted(DATASETS_DIR.glob("*.toml")), ids=lambda p: p.stem)
def test_definitions_build(path: Path, catalog: Catalog) -> None:
    dataset = build_dataset(load_definition(path), catalog, name=path.stem)
    assert len(dataset) > 0


#: Una definición con grupos explícitos.
GROUPS = {
    "group": [
        {
            "name": "strips/gripper",
            "collection": "ipc-1998/gripper-round-1-strips",
            "problems": ["p01", "p02"],
        },
        {"name": "pddlplus/car", "collection": "smtplan/car-nodrag", "problems": ["p01", "p02"]},
        {
            "name": "adl/rubiks-cube",
            "collection": "ipc-2023-classical/rubiks-cube",
            "problems": ["p01"],
        },
    ]
}


def test_explicit_groups(catalog: Catalog) -> None:
    groups = build_dataset(GROUPS, catalog).groups()
    assert list(groups) == ["strips/gripper", "pddlplus/car", "adl/rubiks-cube"]
    assert [e.task.name for e in groups["pddlplus/car"]] == ["p01", "p02"]


def test_select_filters(catalog: Catalog) -> None:
    temporal = select(catalog, types=["temporal"], exclude_types=["pddlplus"])
    assert temporal.entries
    assert all("temporal" in e.analysis.tags for e in temporal.entries)
    assert all("pddlplus" not in e.analysis.tags for e in temporal.entries)
    small = select(catalog, collections=["ipc-2011/*"], per_collection=2, order="smallest")
    assert len(small) == 28
    assert all(len(entries) == 2 for entries in small.groups().values())
    assert select(catalog, max_kb=1, types=["classical"]).entries
    assert all(e.analysis.size <= 1024 for e in select(catalog, max_kb=1).entries)
    with_plan = select(catalog, with_plan=True)
    assert with_plan.entries and all(e.task.plan for e in with_plan.entries)


def test_level_filters(catalog: Catalog) -> None:
    every = {e.task.id: e.analysis.level for e in select(catalog).entries}
    up_to_3 = {e.task.id for e in select(catalog, max_level="PDDL 2.1").entries}
    assert up_to_3 == {task for task, level in every.items() if level <= 3}
    only_4 = {e.task.id for e in select(catalog, levels=[4]).entries}
    assert only_4 == {task for task, level in every.items() if level == 4}
    from_5 = {e.task.id for e in select(catalog, min_level=5).entries}
    assert from_5 == {task for task, level in every.items() if level >= 5}
    grouped = select(catalog, per_collection=1, group="level{level}/{id}")
    assert all(e.group.startswith(f"level{e.analysis.level}/") for e in grouped.entries)
    with pytest.raises(DatasetError, match="unknown level"):
        select(catalog, max_level="PDDL 9")


def test_random_order_is_reproducible(catalog: Catalog) -> None:
    first = select(catalog, per_collection=3, order="random", seed=5)
    second = select(catalog, per_collection=3, order="random", seed=5)
    other = select(catalog, per_collection=3, order="random", seed=6)
    names = [e.task.id for e in first.entries]
    assert names == [e.task.id for e in second.entries]
    assert names != [e.task.id for e in other.entries]


def test_bad_definitions(tmp_path: Path) -> None:
    path = tmp_path / "x.toml"
    path.write_text("[[select]]\norderr = 'first'\n")
    with pytest.raises(DatasetError, match="unknown keys"):
        load_definition(path)
    path.write_text("description = 'nada'\n")
    with pytest.raises(DatasetError):
        load_definition(path)


def test_outputs(catalog: Catalog) -> None:
    dataset = select(catalog, collections=["ipc-1998/*"], problems=["p01", "p02"])
    lines = to_lines(dataset, relative_to=catalog.root).splitlines()
    assert lines == [
        "ipc-1998/gripper-round-1-strips/domain.pddl ipc-1998/gripper-round-1-strips/p01.pddl",
        "ipc-1998/gripper-round-1-strips/domain.pddl ipc-1998/gripper-round-1-strips/p02.pddl",
    ]
    assert json.loads(to_json(dataset))["tasks"][0]["tags"] == ["classical", "strips"]
    assert to_csv(dataset).splitlines()[0].startswith("group,collection,problem")


def test_export(catalog: Catalog, tmp_path: Path) -> None:
    dataset = build_dataset(GROUPS, catalog)
    written = export(dataset, tmp_path / "x")
    assert written == 9  # 3 dominios, 5 problemas y el plan de rubiks-cube p01
    car = tmp_path / "x" / "pddlplus" / "car"
    assert sorted(p.name for p in car.iterdir()) == ["domain.pddl", "p01.pddl", "p02.pddl"]
    assert (tmp_path / "x" / "adl" / "rubiks-cube" / "p01.plan").exists()
    manifest = json.loads((tmp_path / "x" / "dataset.json").read_text())
    assert len(manifest["tasks"]) == 5
    with pytest.raises(DatasetError, match="is not empty"):
        export(dataset, tmp_path / "x")
    linked = export(dataset, tmp_path / "links", link=True)
    assert linked == written
    assert (tmp_path / "links" / "pddlplus" / "car" / "p01.pddl").is_symlink()
