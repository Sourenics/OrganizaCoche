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


def test_forced_driver_is_kept():
    # B está marcada "conduce" el dilluns aunque, por equidad, le tocaría a A (ya conduce menos)
    trips = [
        Trip("A", "dilluns", "8:00", "14:00"),
        Trip("B", "dilluns", "8:00", "14:00", fixed_role=Role.DRIVER),
        Trip("A", "dimarts", "8:00", "14:00"),
        Trip("B", "dimarts", "8:00", "14:00", fixed_role=Role.DRIVER),
    ]
    res = solve(trips, _people("A", "B"), capacity=4)
    assert res.plan.roles[("B", "dilluns")] is Role.DRIVER
    assert res.plan.roles[("B", "dimarts")] is Role.DRIVER
    assert res.plan.roles[("A", "dilluns")] is Role.PASSENGER
    assert not res.warnings


def test_paquete_never_drives():
    trips = [
        Trip("A", "dilluns", "8:00", "14:00", fixed_role=Role.PASSENGER),
        Trip("B", "dilluns", "8:00", "14:00"),
        Trip("C", "dilluns", "8:00", "14:00"),
    ]
    res = solve(trips, _people("A", "B", "C"), capacity=4)
    assert res.plan.roles[("A", "dilluns")] is Role.PASSENGER
    assert res.plan.sharing_days("A") == 1  # sigue contando como día compartido
    assert "A" not in {c.driver for c in res.plan.cars}
    # A es paquete todos sus días: aviso
    assert any("A: marcado 'paquete' todos sus días" in w for w in res.warnings)


def test_warning_when_only_paquetes():
    trips = [
        Trip("A", "dilluns", "8:00", "14:00", fixed_role=Role.PASSENGER),
        Trip("B", "dilluns", "8:00", "14:00", fixed_role=Role.PASSENGER),
    ]
    res = solve(trips, _people("A", "B"), capacity=4)
    assert not res.plan.cars
    assert any("faltan conductores" in w for w in res.warnings)
    assert any("nadie puede conducir" in w for w in res.warnings)


def test_alternatives_exclude_paquetes_and_overloaded():
    # Tres personas, un solo día: alguien conduce 1/1 y los demás 0/1.
    # Un paquete nunca es alternativa; quien aún no conduce sí lo es.
    trips = [
        Trip("A", "dilluns", "8:00", "14:00", fixed_role=Role.DRIVER),
        Trip("B", "dilluns", "8:00", "14:00"),
        Trip("C", "dilluns", "8:00", "14:00", fixed_role=Role.PASSENGER),
    ]
    res = solve(trips, _people("A", "B", "C"), capacity=4)
    for car in res.plan.cars:
        assert car.driver == "A"
        assert car.alternatives == ["B"]


def test_bias_compensates_previous_cycles():
    # A y B idénticos: sin saldo se reparten; si A viene "perjudicada" (condujo de más
    # en ciclos anteriores), ahora conduce menos días que B.
    trips = [Trip(p, d, "8:00", "14:00") for p in "AB" for d in ("dilluns", "dimarts", "dimecres", "dijous")]
    base = solve(trips, _people("A", "B"), capacity=4).plan
    assert base.driving_days("A") == base.driving_days("B") == 2
    comp = solve(trips, _people("A", "B"), capacity=4, bias={"A": 2.0}).plan
    assert comp.driving_days("A") < comp.driving_days("B")
    assert comp.driving_days("A") + comp.driving_days("B") == 4  # sigue cubierto cada día


def test_cycle_balance():
    # A conduce 2 de 2 días, B 0 de 2: media 0,5 → a cada uno le toca 1 día/semana.
    # En un ciclo de 10 semanas, A acumula +10 días (perjudicada) y B −10.
    trips = [Trip(p, d, "8:00", "14:00") for p in "AB" for d in ("dilluns", "dimarts")]
    trips = [Trip(t.person, t.day, t.arrival, t.departure, None, Role.DRIVER if t.person == "A" else None) for t in trips]
    plan = solve(trips, _people("A", "B"), capacity=4).plan
    assert plan.fair_days("A") == plan.fair_days("B") == 1.0
    assert plan.cycle_balance("A", 10) == 10.0
    assert plan.cycle_balance("B", 10) == -10.0


def test_csv_marca_column(tmp_path):
    csv_path = tmp_path / "h.csv"
    csv_path.write_text(
        "persona,dia,entrada,salida,salida_flex,marca\n"
        "A,dilluns,8:00,14:00,,conduce\n"
        "B,dilluns,8:00,14:00,,paquete\n"
        "C,dilluns,8:00,14:00,,no_comparte\n"
        "D,dilluns,8:00,14:00,,\n",
        encoding="utf-8",
    )
    trips = {t.person: t for t in load_trips(csv_path)}
    assert trips["A"].fixed_role is Role.DRIVER
    assert trips["B"].fixed_role is Role.PASSENGER
    assert trips["C"].fixed_role is Role.SOLO
    assert trips["D"].fixed_role is None


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
