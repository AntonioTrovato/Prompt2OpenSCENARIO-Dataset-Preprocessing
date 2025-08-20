import os, glob, argparse
import xml.etree.ElementTree as ET
from collections import Counter

def norm(v):
    if v is None: return "null"
    s = str(v).strip()
    return s if s else "null"

def main():
    parser = argparse.ArgumentParser(description="Analizza .xosc in una cartella e stampa statistiche su entità e meteo.")
    parser.add_argument("--input_dir", default="OpenSCENARIO_valid", help="Cartella contenente file .xosc")
    args = parser.parse_args()

    files = glob.glob(os.path.join(args.input_dir, "*.xosc"))

    entity_ctr = Counter()  # Vehicle/Pedestrian/MiscObject/Unknown
    time_ctr = Counter()    # TimeOfDay values
    weather_ctrs = {
        "cloud_state": Counter(),
        "precip_type": Counter(),
        "precip_intensity": Counter(),
        "fog_visual_range": Counter(),
        "wind_direction": Counter(),
        "wind_speed": Counter(),
    }
    weather_combo = Counter()  # tuple of all weather fields

    ok = bad = 0
    for path in files:
        try:
            root = ET.parse(path).getroot()
            ok += 1
        except Exception as e:
            print(f"⚠️  Salto {path}: {e}")
            bad += 1
            continue

        # === Entities: ScenarioObject.<Type> ===
        for so in root.findall(".//Entities/ScenarioObject"):
            if so.find("./Vehicle") is not None:
                entity_ctr["Vehicle"] += 1
            elif so.find("./Pedestrian") is not None:
                entity_ctr["Pedestrian"] += 1
            elif so.find("./MiscObject") is not None:
                entity_ctr["MiscObject"] += 1
            else:
                entity_ctr["Unknown"] += 1

        # === TimeOfDay & Weather (in Storyboard -> Init -> ... -> Environment) ===
        for env in root.findall(".//EnvironmentAction//Environment"):
            # TimeOfDay
            tod = env.find("./TimeOfDay")
            if tod is not None:
                tod_val = tod.attrib.get("dateTime") or tod.attrib.get("animation")
                time_ctr[norm(tod_val)] += 1

            # Weather
            w = env.find("./Weather")
            if w is not None:
                cs = norm(w.attrib.get("cloudState"))
                p = w.find("./Precipitation")
                pt = norm(p.attrib.get("precipitationType") if p is not None else None)
                pi = norm(p.attrib.get("intensity") if p is not None else None)
                fog = w.find("./Fog")
                fvr = norm(fog.attrib.get("visualRange") if fog is not None else None)
                wind = w.find("./Wind")
                wdir = norm(wind.attrib.get("direction") if wind is not None else None)
                wspd = norm(wind.attrib.get("speed") if wind is not None else None)

                weather_ctrs["cloud_state"][cs] += 1
                weather_ctrs["precip_type"][pt] += 1
                weather_ctrs["precip_intensity"][pi] += 1
                weather_ctrs["fog_visual_range"][fvr] += 1
                weather_ctrs["wind_direction"][wdir] += 1
                weather_ctrs["wind_speed"][wspd] += 1

                weather_combo[(cs, pt, pi, fvr, wdir, wspd)] += 1

    # === Report ===
    print(f"\nAnalizzati {ok} file .xosc (saltati {bad}).\n")

    print("# Entità (ScenarioObject.<Type>)")
    print(f"- Diversità tipi: {len([k for k, v in entity_ctr.items() if v > 0])}")
    for t, c in entity_ctr.most_common():
        print(f"  • {t}: {c}")

    print("\n# Time of Day")
    print(f"- Diversità valori: {len(time_ctr)}")
    for v, c in time_ctr.most_common():
        print(f"  • {v}: {c}")

    print("\n# Meteo per proprietà")
    for k, ctr in weather_ctrs.items():
        print(f"- {k}: {len(ctr)} valori unici")
        for v, c in ctr.most_common():
            print(f"  • {v}: {c}")

    print("\n# Combinazioni meteo complete (cloud_state, precip_type, precip_intensity, fog_visual_range, wind_direction, wind_speed)")
    print(f"- Diversità combinazioni: {len(weather_combo)}")
    for combo, c in weather_combo.most_common(10):
        print(f"  • {combo}: {c}")

if __name__ == "__main__":
    main()
