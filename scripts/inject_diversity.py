#!/usr/bin/env python3
import os, glob, random, argparse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# importiamo xsd_ok dal modulo separato
from xsd_validator import xsd_ok

# === Config probabilità ===
SEED = 42  # cambia o rimuovi per non avere riproducibilità

PROB_PED   = 0.20
PROB_TOD   = 1
PROB_CLOUD = 0.20
PROB_SUN   = 0.20
PROB_FOG   = 1

CLOUD_CHOICES = ["free", "cloudy", "skyOff", "overcast", "rainy"]
PRECIP_CHOICES = ["rain", "dry", "snow"]

# === Helpers XML ===
def ln(tag: str) -> str:
    return tag.split('}', 1)[-1] if '}' in tag else tag

def find_children(parent, local):
    return [c for c in list(parent) if ln(c.tag) == local]

def find_first(parent, local):
    for c in list(parent):
        if ln(c.tag) == local:
            return c
    return None

def iter_by_local(root, local):
    for el in root.iter():
        if ln(el.tag) == local:
            yield el

def ensure_output_dir(output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

def random_datetime_post_2018():
    start = datetime(2019, 1, 1, 0, 0, 0)
    end   = datetime(2025, 8, 20, 23, 59, 59)
    delta = end - start
    dt = start + timedelta(seconds=random.randrange(int(delta.total_seconds())))
    return dt.strftime("%Y-%m-%dT%H:%M:%S")

def format_float(v, nd=6):
    return f"{v:.{nd}f}"

def make_pedestrian_scenarioobject(name="ped"):
    so = ET.Element("ScenarioObject", {"name": name})
    ped = ET.SubElement(so, "Pedestrian", {
        "model": "walker.pedestrian.0001",
        "mass": "90.0",
        "name": "walker.pedestrian.0001",
        "pedestrianCategory": "pedestrian"
    })
    ET.SubElement(ped, "ParameterDeclarations")
    bb = ET.SubElement(ped, "BoundingBox")
    ET.SubElement(bb, "Center", {"x": "1.5", "y": "0.0", "z": "0.9"})
    ET.SubElement(bb, "Dimensions", {"width": "2.1", "length": "4.5", "height": "1.8"})
    props = ET.SubElement(ped, "Properties")
    ET.SubElement(props, "Property", {"name": "type", "value": "simulation"})
    return so

def unique_so_name(entities_el):
    existing = {so.attrib.get("name") for so in find_children(entities_el, "ScenarioObject")}
    base = "ped"
    if base not in existing:
        return base
    i = 2
    while f"{base}{i}" in existing:
        i += 1
    return f"{base}{i}"

# === Injection ops ===
def inject_pedestrian(root):
    ents = next(iter_by_local(root, "Entities"), None)
    if ents is None:
        return False
    if random.random() < PROB_PED:
        ents.append(make_pedestrian_scenarioobject(unique_so_name(ents)))
        return True
    return False

def mutate_time_of_day(root):
    changed = 0
    for env in iter_by_local(root, "Environment"):
        tod = find_first(env, "TimeOfDay")
        if tod is not None and random.random() < PROB_TOD:
            tod.set("dateTime", random_datetime_post_2018())
            changed += 1
    return changed

def mutate_weather(root):
    w_changed = {"cloud":0, "precip":0, "sun":0, "fog":0}
    for env in iter_by_local(root, "Environment"):
        w = find_first(env, "Weather")
        if w is None:
            continue

        # cloudState (20%)
        if random.random() < PROB_CLOUD:
            w.set("cloudState", random.choice(CLOUD_CHOICES))
            w_changed["cloud"] += 1

        # Precipitation (sempre almeno uno)
        prec_list = find_children(w, "Precipitation")
        if not prec_list:
            ET.SubElement(w, "Precipitation", {
                "intensity": format_float(random.uniform(0.0, 1.0), 3),
                "precipitationType": random.choice(PRECIP_CHOICES)
            })
            w_changed["precip"] += 1
        else:
            for p in prec_list:
                p.set("precipitationType", random.choice(PRECIP_CHOICES))
                if "intensity" not in p.attrib:
                    p.set("intensity", format_float(random.uniform(0.0, 1.0), 3))
                w_changed["precip"] += 1

        # Sun (20%)
        for sun in find_children(w, "Sun"):
            if random.random() < PROB_SUN:
                sun.set("azimuth",   format_float(random.uniform(-3.14159, 3.14159), 6))
                sun.set("elevation", format_float(random.uniform(-1.57080, 1.57080), 6))
                sun.set("intensity", format_float(random.uniform(0.0, 1.0), 3))
                w_changed["sun"] += 1

        # Fog (20%)
        for fog in find_children(w, "Fog"):
            if random.random() < PROB_FOG:
                fog.set("visualRange", format_float(random.uniform(0.0, 1000.0), 2))
                w_changed["fog"] += 1

    return w_changed

def process_file(path, output_dir, xsd_path):
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        print(f"⚠️  Salto (parse error): {path} — {e}")
        return

    ped_added   = inject_pedestrian(root)
    tod_changed = mutate_time_of_day(root)
    wchg        = mutate_weather(root)

    # Serializza e valida PRIMA di salvare
    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    xml_str   = xml_bytes.decode("utf-8")

    valid, err = xsd_ok(xml_str, xsd_path)
    if valid:
        out_path = os.path.join(output_dir, os.path.basename(path))
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(xml_str)
        print(f"✅ {os.path.basename(path)}  "
              f"[ped:{'1' if ped_added else '0'}, tod:{tod_changed}, "
              f"cloud:{wchg['cloud']}, precip:{wchg['precip']}, sun:{wchg['sun']}, fog:{wchg['fog']}]  → salvato")
    else:
        reason = err or "schema.validate returned False"
        print(f"❌ {os.path.basename(path)} NON salvato (XSD non valido): {reason}")

def main():
    parser = argparse.ArgumentParser(description="Inietta variazioni randomiche in scenari .xosc e valida contro XSD.")
    parser.add_argument("--input_dir", default="OpenSCENARIO_valid", help="Cartella contenente file .xosc di input")
    parser.add_argument("--output_dir", default="OpenSCENARIO_valid_inject", help="Cartella di output per file modificati")
    parser.add_argument("--xsd_path", default="OpenSCENARIO.xsd", help="Percorso al file XSD di OpenSCENARIO")
    args = parser.parse_args()

    if SEED is not None:
        random.seed(SEED)

    ensure_output_dir(args.output_dir)
    files = glob.glob(os.path.join(args.input_dir, "*.xosc"))
    if not files:
        print(f"Nessun .xosc trovato in '{args.input_dir}'")
        return
    for p in files:
        process_file(p, args.output_dir, args.xsd_path)
    print(f"\nFatto. Output in '{args.output_dir}'.\n")

if __name__ == "__main__":
    main()
