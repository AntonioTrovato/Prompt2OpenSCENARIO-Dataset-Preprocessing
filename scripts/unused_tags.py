#!/usr/bin/env python3
import os, glob, argparse
from collections import Counter
from lxml import etree
import xml.etree.ElementTree as ET

XS_NS = {"xs": "http://www.w3.org/2001/XMLSchema"}

def localname(tag: str) -> str:
    """Ritorna il local-name senza namespace."""
    return tag.split("}", 1)[-1] if "}" in tag else tag

def load_valid_tags_from_xsd(xsd_path: str) -> set:
    """Estrae i nomi di TUTTI gli xs:element (sia @name che @ref) dal file XSD."""
    if not os.path.isfile(xsd_path):
        raise FileNotFoundError(f"File XSD non trovato: {xsd_path}")

    tree = etree.parse(xsd_path)
    elems = tree.xpath("//xs:element", namespaces=XS_NS)

    valid = set()
    for e in elems:
        if "name" in e.attrib:
            valid.add(e.attrib["name"])
        if "ref" in e.attrib:
            ref = e.attrib["ref"]
            valid.add(ref.split(":")[-1])
    return valid

def scan_used_tags_in_xosc(input_dir: str):
    """
    Scansiona tutti i .xosc e:
      - raccoglie l'insieme dei tag effettivamente usati (local-name)
      - conta quante volte compare ciascun tag (Counter)
    Ritorna: (used_tags_set, tag_counter)
    """
    used = set()
    counter = Counter()
    paths = glob.glob(os.path.join(input_dir, "*.xosc"))
    for p in paths:
        try:
            root = ET.parse(p).getroot()
        except Exception as e:
            print(f"⚠️  Salto (parse error): {p} — {e}")
            continue
        for el in root.iter():
            name = localname(el.tag)
            used.add(name)
            counter[name] += 1
    return used, counter

def main():
    parser = argparse.ArgumentParser(
        description="Mostra i tag validi in un file OpenSCENARIO.xsd che non compaiono in alcun .xosc dell'input e la frequenza d'uso dei tag usati."
    )
    parser.add_argument("--input_dir", required=True, help="Cartella contenente file .xosc")
    parser.add_argument("--xsd_path", required=True, help="Percorso al file OpenSCENARIO.xsd")
    args = parser.parse_args()

    valid_tags = load_valid_tags_from_xsd(args.xsd_path)
    used_tags, tag_counts = scan_used_tags_in_xosc(args.input_dir)

    missing = sorted(valid_tags - used_tags)

    print(f"# Riepilogo")
    print(f"- Tag validi (da XSD): {len(valid_tags)}")
    print(f"- Tag usati (nei .xosc): {len(used_tags)}")
    print(f"- Tag validi ma MAI usati: {len(missing)}\n")

    print("# Elenco tag validi mai usati")
    if not missing:
        print("(Nessuno 🎉)")
    else:
        for t in missing:
            print(f"• {t}")

    print("\n# Frequenza d'uso dei tag (tutti i .xosc)")
    if not tag_counts:
        print("(Nessun file valido trovato)")
    else:
        # Ordina per conteggio decrescente, poi alfabetico
        for tag, cnt in sorted(tag_counts.items(), key=lambda x: (-x[1], x[0])):
            print(f"{tag}: {cnt}")

if __name__ == "__main__":
    main()
