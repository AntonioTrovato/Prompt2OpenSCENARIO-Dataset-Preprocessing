import os
import json
import argparse

# Importa la funzione fornita
from xsd_validator import xsd_ok


def iter_jsonl(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def main():
    ap = argparse.ArgumentParser(description="Verifica XSD per ogni record (campo 'assistant') in un JSONL.")
    ap.add_argument(
        "--input_path",
        default="./resources/reduced/dataset/all.jsonl",
        help="Percorso del file JSONL di input (default: ./resources/reduced/dataset/all.jsonl)",
    )
    ap.add_argument(
        "--xsd_path",
        default="./xsd/OpenSCENARIO.xsd",
        help="Percorso del file XSD (default: ./xsd/OpenSCENARIO.xsd)",
    )
    args = ap.parse_args()

    if not os.path.isfile(args.input_path):
        raise FileNotFoundError(f"Input non trovato: {args.input_path}")

    print(f"Input: {args.input_path}")
    print(f"XSD:   {args.xsd_path}")

    total = 0
    valid = 0
    invalid = 0
    skipped = 0
    no_xsd = 0

    for i, rec in enumerate(iter_jsonl(args.input_path), start=1):
        total += 1
        assistant = (rec.get("assistant") or "").strip()

        if not assistant:
            skipped += 1
            print(f"[{i}] SKIP (assistant vuoto o assente)")
            continue

        ok, err = xsd_ok(assistant, args.xsd_path)

        if ok is None and err == "no_xsd":
            no_xsd += 1
            print(f"[{i}] NO_XSD (impossibile validare: {err})")
        elif ok is True:
            valid += 1
            print(f"[{i}] OK")
        else:
            invalid += 1
            # err può essere None se schema.validate(xml) ha solo ritornato False senza eccezioni
            msg = err if err else "xsd_validate_false"
            print(f"[{i}] FAIL: {msg}")

    print("\n--- Riepilogo ---")
    print(f"Totale record: {total}")
    print(f"Validi XSD:    {valid}")
    print(f"Non validi:    {invalid}")
    print(f"Saltati:       {skipped} (assistant mancante/vuoto)")
    print(f"No XSD:        {no_xsd}")


if __name__ == "__main__":
    main()
