import os
import glob
import argparse
from typing import Optional, Dict, List, Tuple
import xml.etree.ElementTree as ET
from lxml import etree  # solo perché xsd_validator lo usa internamente

from xsd_validator import xsd_ok  # usa la signature fornita dall'utente

EGO_NAME = "ego_vehicle"


# --------- Utility XML ---------
def localname(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def iter_with_parent(root: ET.Element):
    """Itera (node, parent) su tutto l'albero (parent=None per root)."""
    stack = [(root, None)]
    while stack:
        node, parent = stack.pop()
        yield node, parent
        # push figli in ordine d'apparizione
        for ch in list(node)[::-1]:
            stack.append((ch, node))


def findall_local(root: ET.Element, name: str) -> List[ET.Element]:
    """Trova tutti gli elementi con localname == name (ovunque nell'albero)."""
    return [n for n, _ in iter_with_parent(root) if localname(n.tag) == name]


def has_child_local(elem: ET.Element, child_name: str) -> bool:
    return any(localname(ch.tag) == child_name for ch in list(elem))


def get_attr(elem: ET.Element, attr: str, default=None):
    return elem.attrib.get(attr, default)


# --------- Riduzione ---------
def reduce_xosc_tree(root: ET.Element) -> ET.Element:
    """
    Applica le regole di riduzione:
      1. non eliminare ScenarioObject name=ego_vehicle
      2. non eliminare ScenarioObject se contiene Pedestrian
      3. se ci sono altri ScenarioObject.Vehicle, lascia solo il primo
      4. elimina tutti i Private con entityRef != ego_vehicle e != (secondo veicolo salvato)
      5. elimina tutti i ManeuverGroup tranne quello che referenzia il secondo veicolo salvato
      6. se ci sono più Story lascia solo la prima
    """
    # --- 1) Identifica ScenarioObject ed il "secondo veicolo salvato" ---
    scenario_objects = findall_local(root, "ScenarioObject")

    # Mappa nome -> elemento
    name_to_obj: Dict[str, ET.Element] = {}
    for so in scenario_objects:
        nm = get_attr(so, "name")
        if nm:
            name_to_obj[nm] = so

    # Sempre salva ego
    ego_obj = name_to_obj.get(EGO_NAME)

    # Candidati "ScenarioObject con Vehicle" (diversi da ego e che NON contengono Pedestrian)
    vehicle_objs: List[ET.Element] = []
    for so in scenario_objects:
        nm = get_attr(so, "name")
        if nm == EGO_NAME:
            continue
        has_vehicle = has_child_local(so, "Vehicle")
        has_ped = has_child_local(so, "Pedestrian")
        if has_vehicle and not has_ped:
            vehicle_objs.append(so)

    # Secondo veicolo salvato: il primo nell'ordine d'apparizione
    second_vehicle_obj: Optional[ET.Element] = vehicle_objs[0] if vehicle_objs else None
    second_vehicle_name: Optional[str] = get_attr(second_vehicle_obj, "name") if second_vehicle_obj is not None else None

    # --- 2) Potatura ScenarioObject con Vehicle: lascia solo il primo (escluso ego) ---
    # Non eliminare mai: ego, qualsiasi SO con Pedestrian
    # Elimina altri SO con Vehicle (diversi dal "secondo veicolo salvato")
    for so in scenario_objects:
        nm = get_attr(so, "name")
        if so is ego_obj:
            continue  # non eliminare l'ego
        if has_child_local(so, "Pedestrian"):
            continue  # non eliminare se contiene Pedestrian
        if has_child_local(so, "Vehicle"):
            # se non è il "secondo veicolo salvato", rimuovi
            if second_vehicle_obj is not None and so is not second_vehicle_obj:
                # rimuovi SO
                # serve il parent
                for n, parent in iter_with_parent(root):
                    if n is so and parent is not None:
                        parent.remove(n)
                        break
            elif second_vehicle_obj is None:
                # non esiste alcun "secondo veicolo": rimuovi tutti i Vehicle non-ego
                for n, parent in iter_with_parent(root):
                    if n is so and parent is not None:
                        parent.remove(n)
                        break

    # Aggiorna lista scenario_objects dopo potatura
    scenario_objects = findall_local(root, "ScenarioObject")
    name_to_obj = {get_attr(so, "name"): so for so in scenario_objects if get_attr(so, "name")}
    ego_obj = name_to_obj.get(EGO_NAME)
    second_vehicle_obj = name_to_obj.get(second_vehicle_name) if second_vehicle_name else None

    # --- 3) Elimina Private con entityRef non ammessi ---
    allowed_refs = {EGO_NAME}
    if second_vehicle_obj is not None and second_vehicle_name:
        allowed_refs.add(second_vehicle_name)

    for node, parent in list(iter_with_parent(root)):
        if parent is None:
            continue
        if localname(node.tag) == "Private":
            ent = get_attr(node, "entityRef")
            if ent not in allowed_refs:
                parent.remove(node)

    # --- 4) Riduci ManeuverGroup ---
    # Mantieni SOLO quelli che hanno Actors/EntityRef[@entityRef == second_vehicle_name]
    # Se non c'è secondo veicolo, rimuovi tutti i ManeuverGroup
    mgroups = [n for n, _ in iter_with_parent(root) if localname(n.tag) == "ManeuverGroup"]

    def mg_refs_second_vehicle(mg: ET.Element, target_name: str) -> bool:
        # Cerca qualsiasi EntityRef sotto Actors con entityRef == target_name
        for actor in mg.iter():
            if localname(actor.tag) == "EntityRef":
                if get_attr(actor, "entityRef") == target_name:
                    return True
        return False

    for mg in mgroups:
        keep = False
        if second_vehicle_name:
            keep = mg_refs_second_vehicle(mg, second_vehicle_name)
        if not keep:
            # rimuovi mg
            for n, parent in iter_with_parent(root):
                if n is mg and parent is not None:
                    parent.remove(n)
                    break

    # --- 5) Mantieni solo la prima Story ---
    stories = [n for n, _ in iter_with_parent(root) if localname(n.tag) == "Story"]
    if len(stories) > 1:
        first_story = stories[0]
        for st in stories[1:]:
            for n, parent in iter_with_parent(root):
                if n is st and parent is not None:
                    parent.remove(n)
                    break

    return root


def reduce_xosc_string(xosc_text: str) -> str:
    """Parsa, riduce, e restituisce l'XML come stringa (senza dichiarazione)."""
    root = ET.fromstring(xosc_text)
    root = reduce_xosc_tree(root)
    return ET.tostring(root, encoding="unicode")


# --------- I/O & main ---------
def process_file(path: str, xsd_path: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Elabora un singolo .xosc:
      - legge il file
      - riduce
      - valida via xsd_ok
    Ritorna: (is_valid, reduced_xml (se valido), error_msg (se non valido))
    """
    with open(path, "r", encoding="utf-8") as f:
        xosc_text = f.read()

    try:
        reduced = reduce_xosc_string(xosc_text)
    except Exception as e:
        return False, None, f"reduce_error: {e}"

    ok, err = xsd_ok(reduced, xsd_path)
    if ok is True:
        return True, reduced, None
    else:
        # ok può essere False o None; err può contenere il motivo
        return False, None, f"xsd_invalid: {err or 'unknown'}"


def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Riduci file OpenSCENARIO 1.0 secondo regole e valida contro XSD.")
    parser.add_argument("--input_dir", default="./resources/original/original_validated_injected",
                        help="Cartella con .xosc di input")
    parser.add_argument("--output_dir", default="./resources/reduced/reduced_scenarios",
                        help="Cartella dove salvare gli .xosc ridotti e validi")
    parser.add_argument("--xsd_path", default="./xsd/OpenSCENARIO.xsd",
                        help="Percorso al file OpenSCENARIO.xsd")
    args = parser.parse_args()

    ensure_dir(args.output_dir)

    paths = sorted(glob.glob(os.path.join(args.input_dir, "*.xosc")))
    if not paths:
        print(f"⚠️  Nessun .xosc trovato in: {args.input_dir}")
        return

    total = len(paths)
    ok_cnt = 0
    fail_cnt = 0

    print(f"📂 Input:  {args.input_dir}")
    print(f"💾 Output: {args.output_dir}")
    print(f"📘 XSD:    {args.xsd_path}\n")

    for p in paths:
        base = os.path.basename(p)
        out_path = os.path.join(args.output_dir, base)
        valid, reduced, err = process_file(p, args.xsd_path)
        if valid and reduced is not None:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(reduced)
            ok_cnt += 1
            print(f"✅ {base}  -> salvato")
        else:
            fail_cnt += 1
            print(f"❌ {base}  -> {err}")

    print("\n# Riepilogo")
    print(f"- Totali: {total}")
    print(f"- Salvati (validi XSD): {ok_cnt}")
    print(f"- Falliti: {fail_cnt}")


if __name__ == "__main__":
    main()
