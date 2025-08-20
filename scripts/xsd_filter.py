#!/usr/bin/env python3
import os
import argparse
import glob
from pathlib import Path
from lxml import etree
from xsd_validator import xsd_ok

def main():
    parser = argparse.ArgumentParser(description="Validate .xosc files against OpenSCENARIO XSD and export only valid ones.")
    parser.add_argument("--input_dir", default="./resources/original/original_scenarios", help="Directory containing .xosc files.")
    parser.add_argument("--xsd_dir", default="xsd/OpenSCENARIO.xsd", help="Path to the OpenSCENARIO XSD file.")
    parser.add_argument("--output_dir", default="./resources/original/original_validated", help="Directory to save validated .xosc files.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    xsd_path = args.xsd_dir  # this is a file path
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        print(f"[ERRORE] input_dir non esiste: {input_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    xosc_paths = sorted(glob.glob(str(input_dir / "*.xosc")))
    if not xosc_paths:
        print(f"[INFO] Nessun .xosc trovato in {input_dir}")
        return

    print(f"[INFO] Trovati {len(xosc_paths)} file .xosc in {input_dir}")
    print(f"[INFO] Userò XSD: {xsd_path}")

    ok_count = 0
    skip_count = 0
    fail_count = 0

    for p in xosc_paths:
        try:
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"[SKIP] Impossibile leggere {p}: {e}")
            skip_count += 1
            continue

        valid, err = xsd_ok(content, xsd_path)
        name = Path(p).name

        if valid is True:
            out_file = output_dir / name
            try:
                with open(out_file, "w", encoding="utf-8", newline="\n") as f:
                    f.write(content)
                print(f"[OK]  {name} -> salvato in {out_file}")
                ok_count += 1
            except Exception as e:
                print(f"[FAIL] Scrittura fallita per {name}: {e}")
                fail_count += 1
        elif valid is None:
            print(f"[ERRORE] XSD non trovato/valido ({xsd_path}). Interrompo.")
            return
        else:
            print(f"[NOPE] {name} non valido XSD. Dettagli: {err}")
            skip_count += 1

    print("\n=== RIEPILOGO ===")
    print(f"Validi e salvati: {ok_count}")
    print(f"Non validi / saltati: {skip_count}")
    print(f"Errori di scrittura: {fail_count}")
    print(f"Output dir: {output_dir.resolve()}")

if __name__ == "__main__":
    main()
