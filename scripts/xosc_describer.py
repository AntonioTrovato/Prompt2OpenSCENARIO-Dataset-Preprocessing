import os, json, glob, argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from pprint import pformat

def extract_features_from_xosc(xosc_text: str) -> dict:
    """
    Estrae feature salienti dall'OpenSCENARIO 1.0 (best-effort, robusta a mancanze).
    Non include speed_limits né notes.
    """
    feat = {
        "map": None,
        "time_of_day": None,
        "weather": {"cloud_state": None, "precipitation": None, "fog": None, "wind": None},
        "entities": [],   # [{"name":..., "type": "ego|vehicle|pedestrian|misc"}]
        "initial_positions": [],  # [{"entity": name, "x":.., "y":.., "z":.., "h":..}]
        "events": []      # descrizioni brevi di azioni/trigger
    }
    try:
        root = ET.fromstring(xosc_text)
    except Exception:
        return feat

    # RoadNetwork / LogicFile
    rn = root.find(".//RoadNetwork/LogicFile")
    if rn is not None:
        feat["map"] = rn.attrib.get("filepath") or rn.attrib.get("file") or None

    # Environment / TimeOfDay / Weather
    tod = root.find(".//Environment/TimeOfDay")
    if tod is not None:
        # Preferisci dateTime; se assente, metti animation (true/false) come fallback
        feat["time_of_day"] = tod.attrib.get("dateTime") or tod.attrib.get("animation") or None

    w = root.find(".//Environment/Weather")
    if w is not None:
        feat["weather"]["cloud_state"] = w.attrib.get("cloudState")

        # <Precipitation intensity="..." precipitationType="rain|snow|..." />
        prec = w.find("./Precipitation")
        if prec is not None:
            ptype = prec.attrib.get("precipitationType")
            pint  = prec.attrib.get("intensity")
            if ptype and pint:
                feat["weather"]["precipitation"] = f"{ptype} (intensity={pint})"
            elif ptype:
                feat["weather"]["precipitation"] = ptype
            elif pint:
                feat["weather"]["precipitation"] = f"intensity={pint}"

        fog = w.find("./Fog")
        if fog is not None:
            feat["weather"]["fog"] = fog.attrib.get("visualRange")

        # Alcuni XOSC hanno <Wind direction="..." speed="..."/>
        wind = w.find("./Wind")
        if wind is not None:
            direction = wind.attrib.get("direction")
            speed = wind.attrib.get("speed")
            if direction and speed:
                feat["weather"]["wind"] = f"dir={direction}, speed={speed}"
            else:
                feat["weather"]["wind"] = direction or speed

    # Entities (ScenarioObject -> Vehicle/Pedestrian/MiscObject)
    for ent in root.findall(".//Entities/ScenarioObject"):
        name = ent.attrib.get("name") or ent.attrib.get("nameRef")
        etype = "vehicle"  # default
        if ent.find("./Pedestrian") is not None:
            etype = "pedestrian"
        elif ent.find("./MiscObject") is not None:
            etype = "misc"
        elif ent.find("./Vehicle") is not None:
            etype = "vehicle"

        if name == "ego_vehicle":
            etype = "ego"

        if name:
            feat["entities"].append({"name": name, "type": etype})

    # Initial positions: SOLO TeleportAction/WorldPosition (non includere AcquirePositionAction)
    for priv in root.findall(".//Init/Actions/Private"):
        name = priv.attrib.get("entityRef")
        wp = priv.find("./PrivateAction/TeleportAction/Position/WorldPosition")
        if wp is not None:
            feat["initial_positions"].append({
                "entity": name,
                "x": wp.attrib.get("x"), "y": wp.attrib.get("y"),
                "z": wp.attrib.get("z"), "h": wp.attrib.get("h")
            })

    # Events & Triggers
    for ev in root.findall(".//Storyboard//Event"):
        ev_name = ev.attrib.get("name")
        # Può esserci più di un <Action> per evento
        actions = ev.findall("./Action")
        start_trig = ev.find("./StartTrigger")
        desc_bits = []
        if ev_name:
            desc_bits.append(ev_name)

        # Estrai condizioni di start: ByValueCondition/SimulationTimeCondition
        if start_trig is not None:
            for cond in start_trig.findall(".//ByValueCondition/SimulationTimeCondition"):
                val = cond.attrib.get("value")
                rule = cond.attrib.get("rule")
                if val:
                    if rule:
                        desc_bits.append(f"when sim_time {rule} {val}s")
                    else:
                        desc_bits.append(f"after {val}s")

        # Tipi di azione (foglia più informativa, es. ActivateControllerAction, SpeedAction, ecc.)
        action_types = []
        for act in actions:
            # cerca la prima foglia significativa dentro <Action>
            stack = list(act)
            leaf_type = None
            while stack:
                node = stack.pop(0)
                children = list(node)
                if not children:
                    # usa il tag della foglia
                    if isinstance(node.tag, str):
                        leaf_type = node.tag
                        break
                else:
                    stack.extend(children)
            if leaf_type is None:
                # fallback: primo figlio diretto di Action (PrivateAction/GlobalAction/..)
                child = next((c for c in list(act) if isinstance(c.tag, str)), None)
                if child is not None:
                    leaf_type = child.tag
            if leaf_type:
                action_types.append(leaf_type)

        if action_types:
            desc_bits.append("actions=" + ",".join(action_types))

        if desc_bits:
            feat["events"].append(" ".join(desc_bits))

    return feat

def features_to_compact_prompt(feat: dict) -> str:
    """
    Converte il dizionario di feature in un testo compatto da dare a GPT.
    """
    lines = []
    if feat.get("map"): lines.append(f"Map: {feat['map']}")
    if feat.get("time_of_day"): lines.append(f"TimeOfDay: {feat['time_of_day']}")
    w = feat.get("weather", {})
    wparts = [f"{k}={v}" for k, v in w.items() if v]
    if wparts: lines.append("Weather: " + ", ".join(wparts))
    if feat["entities"]:
        ents = [f"{e['name']}({e['type']})" for e in feat["entities"][:10]]
        lines.append("Entities: " + ", ".join(ents))
    if feat["initial_positions"]:
        ips = []
        for p in feat["initial_positions"][:6]:
            ips.append(f"{p['entity']}@({p['x']},{p['y']},{p['z']},h={p['h']})")
        lines.append("InitialPositions: " + "; ".join(ips))
    if feat["events"]:
        lines.append("Events: " + " | ".join(feat["events"][:10]))
    body = "\n".join(lines).strip()
    return body or "No features extracted."

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Estrai feature da .xosc e genera descrizioni.")
    parser.add_argument("--input_dir", default="OpenSCENARIO_valid", help="Cartella contenente file .xosc")
    parser.add_argument("--output_dir", default="OpenSCENARIO_valid_descriptions", help="Cartella di output")
    args = parser.parse_args()

    input_folder = Path(args.input_dir)
    output_folder = Path(args.output_dir)
    output_folder.mkdir(parents=True, exist_ok=True)

    xosc_files = glob.glob(str(input_folder / "*.xosc"))

    for filepath in xosc_files:
        with open(filepath, "r", encoding="utf-8") as f:
            xosc_text = f.read()

        # estrai feature
        feat = extract_features_from_xosc(xosc_text)

        # crea prompt compatto
        compact = features_to_compact_prompt(feat)

        # prepara output
        base_name = os.path.splitext(os.path.basename(filepath))[0]

        txt_path = output_folder / (base_name + ".txt")
        with open(txt_path, "w", encoding="utf-8") as out:
            out.write("=== Features (dict) ===\n")
            out.write(pformat(feat, indent=2, width=120))
            out.write("\n\n=== Compact Prompt ===\n")
            out.write(compact)

        # salva json
        json_path = output_folder / (base_name + ".json")
        with open(json_path, "w", encoding="utf-8") as jout:
            json.dump(feat, jout, indent=2, ensure_ascii=False)

        print(f"✅ Salvati: {txt_path}, {json_path}")
