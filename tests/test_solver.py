from pathlib import Path

from cotxa.io import load_people, load_trips
from cotxa.models import Person, Role, Trip
from cotxa.solver import solve

ROOT = Path(__file__).resolve().parents[1]


def _people(*names, **overrides):
    return {n: overrides.get(n, Person(n)) for n in names}


def test_driver_drives_both_ways():
    trips = [
        Trip("A", "dilluns", "8:00", "14:00"),
        Trip("B", "dilluns", "8:00", "15:00"),
        Trip("C", "dilluns", "9:00", "15:00"),
    ]
    res = solve(trips, _people("A", "B", "C"), capacity=4)
    plan = res.plan
    # Cada franja tiene un coche y cada coche lo conduce alguien con rol DRIVER ese día
    for car in plan.cars:
        assert plan.roles[(car.driver, car.slot.day)] is Role.DRIVER
    # Todas las franjas cubiertas
    slots = {(c.slot.direction, c.slot.time) for c in plan.cars}
    assert slots == {("entrada", "8:00"), ("entrada", "9:00"), ("salida", "14:00"), ("salida", "15:00")}
    assert not res.warnings


def test_capacity_forces_second_car():
    trips = [Trip(p, "dimarts", "8:00", "14:00") for p in "ABCDE"]
    res = solve(trips, _people(*"ABCDE"), capacity=4)
    morning = [c for c in res.plan.cars if c.slot.direction == "entrada"]
    assert len(morning) == 2
    assert all(len(c.occupants) <= 4 for c in res.plan.cars)


def test_person_without_car_never_drives():
    trips = [Trip("A", "dilluns", "8:00", "14:00"), Trip("B", "dilluns", "8:00", "14:00")]
    people = _people("A", "B", B=Person("B", has_car=False))
    res = solve(trips, people, capacity=4)
    assert res.plan.roles[("B", "dilluns")] is Role.PASSENGER
    assert res.plan.roles[("A", "dilluns")] is Role.DRIVER


def test_zones_do_not_mix():
    trips = [Trip("A", "dilluns", "8:00", "14:00"), Trip("B", "dilluns", "8:00", "14:00")]
    people = _people("A", "B", B=Person("B", zone="poble2"))
    res = solve(trips, people, capacity=4)
    assert len([c for c in res.plan.cars if c.slot.direction == "entrada"]) == 2


def test_flex_departure_joins_later_car():
    trips = [
        Trip("A", "dilluns", "8:00", "13:00", departure_flex="13:55"),
        Trip("B", "dilluns", "8:00", "13:55"),
    ]
    res = solve(trips, _people("A", "B"), capacity=4)
    exits = [c for c in res.plan.cars if c.slot.direction == "salida"]
    assert len(exits) == 1 and exits[0].slot.time == "13:55"


def test_real_data_is_balanced():
    trips = load_trips(ROOT / "data" / "horaris.sample.csv")
    people = load_people(ROOT / "data" / "config.json", trips)
    res = solve(trips, people, capacity=4)
    plan = res.plan
    ratios = [plan.driving_days(p) / plan.sharing_days(p) for p in people if plan.sharing_days(p)]
    assert max(ratios) - min(ratios) <= 0.75  # nadie conduce siempre mientras otro nunca
    assert all(len(c.occupants) <= 4 for c in plan.cars)


def test_inactive_person_is_left_out():
    trips = [Trip("A", "dilluns", "8:00", "14:00"), Trip("B", "dilluns", "8:00", "14:00")]
    people = _people("A", "B", B=Person("B", active=False))
    res = solve(trips, people, capacity=4)
    assert ("B", "dilluns") not in res.plan.roles
    assert all("B" not in c.occupants for c in res.plan.cars)


def test_build_web_embeds_seed(tmp_path, monkeypatch):
    import importlib.util, json
    spec = importlib.util.spec_from_file_location("build_web", ROOT / "scripts" / "build_web.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    seed = mod.seed(ROOT / "data" / "horaris.sample.csv", sample=True)
    assert seed["capacity"] == 4 and seed["sample"] is True
    assert len(seed["people"]) == 15
    assert "__SEED__" not in (ROOT / "docs" / "index.html").read_text(encoding="utf-8")


def test_docs_matches_template():
    """docs/index.html (lo publicado) debe estar regenerado tras cada cambio en la plantilla."""
    import re
    tpl = (ROOT / "web" / "index.template.html").read_text(encoding="utf-8")
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    m = re.search(r"const SEED = (.*);", html)
    assert m, "docs/index.html no contiene los datos incrustados"
    assert html.replace(m.group(1), "__SEED__") == tpl, "ejecuta: python scripts/build_web.py"


def test_no_real_data_in_repo():
    """Los nombres reales no deben aparecer en nada que se publique."""
    assert not (ROOT / "data" / "horaris.csv").exists()
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    assert '"sample": true' in html or '"sample":true' in html
