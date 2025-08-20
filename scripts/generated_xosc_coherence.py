#!/usr/bin/env python3
import os, sys, re, json, argparse, glob
from typing import Dict, Any
from openai import OpenAI

GPT_MODEL = "gpt-5"
GPT_SYS = (
    "You are an impartial grader. Given a natural-language description (user) and an "
    "OpenSCENARIO 1.0 XML (prediction), reply with ONLY one decimal number in [0,1] "
    "representing how well the XML corresponds to the description (0=no match, 1=perfect match). "
    "No words, no symbols, no explanation—just the number."
)

def parse_args():
    ap = argparse.ArgumentParser(description="Score (description, XOSC) coherence with GPT-5.")
    ap.add_argument("--input_dir", default="./resources/reduced/generated/",
                    help="Directory containing a single .jsonl file with records.")
    ap.add_argument("--output_dir", default="./resources/reduced/generated/",
                    help="Directory where coherence.json will be written.")
    return ap.parse_args()

def find_single_jsonl(input_dir: str) -> str:
    files = sorted(glob.glob(os.path.join(input_dir, "*.jsonl")))
    if not files:
        print(f"ERROR: no .jsonl found in {input_dir}", file=sys.stderr)
        sys.exit(1)
    if len(files) > 1:
        print(f"WARNING: multiple .jsonl found in {input_dir}. Using the first: {files[0]}", file=sys.stderr)
    return files[0]

_float_pat = re.compile(r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)")

def extract_score(text: str) -> float:
    """
    Extract the first numeric token and clamp to [0,1].
    The grader is instructed to return only a number, but we sanitize anyway.
    """
    m = _float_pat.search(text.strip())
    if not m:
        raise ValueError(f"Could not parse numeric score from: {text!r}")
    try:
        val = float(m.group(1))
    except Exception as e:
        raise ValueError(f"Failed to convert to float: {m.group(1)!r}") from e
    # Clamp to [0,1]
    if val < 0: val = 0.0
    if val > 1: val = 1.0
    return float(f"{val:.3f}")  # keep it neat (3 decimals)

def build_user_prompt(desc: str, xosc: str) -> str:
    return (
        "USER (description):\n"
        f"{desc.strip()}\n\n"
        "PREDICTION (OpenSCENARIO XML):\n"
        f"{xosc.strip()}\n\n"
        "Reply with a single number only."
    )

def main():
    args = parse_args()

    # Ensure output dir exists
    os.makedirs(args.output_dir, exist_ok=True)
    out_path = os.path.join(args.output_dir, "coherence.json")

    # Load input jsonl
    input_file = find_single_jsonl(args.input_dir)
    records = []
    with open(input_file, "r", encoding="utf-8") as f:
        for ln, line in enumerate(f, start=1):
            line = line.strip()
            if not line: continue
            try:
                rec = json.loads(line)
                records.append(rec)
            except json.JSONDecodeError as e:
                print(f"WARNING: skipping malformed JSON on line {ln}: {e}", file=sys.stderr)

    if not records:
        print("ERROR: no valid records found.", file=sys.stderr)
        sys.exit(1)

    # OpenAI client (expects OPENAI_API_KEY in env)
    try:
        client = OpenAI()
    except Exception as e:
        print("ERROR: failed to initialize OpenAI client. "
              "Make sure OPENAI_API_KEY is set in your environment.", file=sys.stderr)
        raise

    results: Dict[str, Any] = {}
    num_records = len(records)

    for idx, rec in enumerate(records):
        rid = rec.get("id", idx)
        user_desc = rec.get("user", "")
        prediction = rec.get("prediction", "")

        if not user_desc or not prediction:
            print(f"WARNING: record {rid} missing 'user' or 'prediction'; skipping.", file=sys.stderr)
            continue

        prompt = build_user_prompt(user_desc, prediction)
        #print(prompt)

        try:
            resp = client.chat.completions.create(
                model=GPT_MODEL,
                messages=[
                    {"role": "system", "content": GPT_SYS},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=8,   # tiny, we expect just a number
            )
            text = resp.choices[0].message.content.strip()
            score = extract_score(text)
            results[f"record_{rid}"] = score
            print(f"[OK] record_{rid} -> {score}")
        except Exception as e:
            print(f"[ERR] record_{rid} failed: {e}", file=sys.stderr)
            results[f"record_{rid}"] = None  # or omit
        print("Completed at " + str(((idx+1)*num_records)/100) + "%")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(results)} results to: {out_path}")

if __name__ == "__main__":
    main()
