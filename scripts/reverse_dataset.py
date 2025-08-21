import argparse
import json
import os
from pathlib import Path

SYSTEM_PROMPT = (
    "Act as an OpenSCENARIO 1.0 scenario analyst for the CARLA simulator. "
    "I will provide a valid .xosc file. "
    "Your task is to produce ONE natural-language description of the scene for an LLM dataset that will regenerate the scenario. "
    "Requirements: English only; 4–5 sentences; 50–100 words; natural wording (e.g., 'a red traffic light', not XML tag names); "
    "mention vehicles/pedestrians/weather/time of day/speed limits/initial positions/paths/events/triggers if present; "
    "specify temporal/spatial constraints when present; no code, no XML, only plain text description."
)

def parse_args():
    parser = argparse.ArgumentParser(
        description="Reverse user/assistant fields in a JSONL dataset and set a new system prompt."
    )
    parser.add_argument(
        "--input_path",
        default="./resources/reduced/dataset/all.jsonl",
        help="Path to the input JSONL file (default: ./resouces/reduced/dataset/all.jsonl)",
    )
    parser.add_argument(
        "--output_dir",
        default="./resources/reduced/reversed_dataset/all.jsonl",
        help=(
            "Destination directory OR full output file path. "
            "If a directory is provided, the output will be saved as all.jsonl inside it. "
            "(default: ./resouces/reduced/reversed_dataset/all.jsonl)"
        ),
    )
    return parser.parse_args()

def resolve_output_path(output_dir_arg: str) -> Path:
    p = Path(output_dir_arg)
    if p.suffix.lower() == ".jsonl":
        # Treat as a file path
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    else:
        # Treat as a directory
        p.mkdir(parents=True, exist_ok=True)
        return p / "all.jsonl"

def reverse_record(rec: dict) -> dict:
    # Safely fetch fields; default to empty strings if missing
    user = rec.get("user", "")
    assistant = rec.get("assistant", "")
    # Swap user and assistant; set new system
    return {
        "system": SYSTEM_PROMPT,
        "user": assistant,
        "assistant": user,
    }

def main():
    args = parse_args()
    input_path = Path(args.input_path)
    output_path = resolve_output_path(args.output_dir)

    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    total, written = 0, 0
    with input_path.open("r", encoding="utf-8") as fin, \
         output_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                # Skip malformed lines
                continue

            out_rec = reverse_record(rec)
            fout.write(json.dumps(out_rec, ensure_ascii=False) + "\n")
            written += 1

    print(f"Processed {total} records. Wrote {written} records to: {output_path}")

if __name__ == "__main__":
    main()
