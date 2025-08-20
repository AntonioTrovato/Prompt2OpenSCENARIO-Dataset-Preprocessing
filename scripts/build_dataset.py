import json, time, glob, argparse
from pathlib import Path
from typing import Optional
from xosc_describer import extract_features_from_xosc, features_to_compact_prompt

# ---- Config ----
MODEL = "gpt-5"  # modello: GPT-5 Thinking
SYSTEM_PROMPT = (
    "Act as an OpenSCENARIO 1.0 scenario analyst for the CARLA simulator. "
    "I will provide a structured summary of a valid .xosc file. "
    "Your task is to produce ONE natural-language description of the scene for an LLM dataset that will regenerate the scenario. "
    "Requirements: English only; 4–5 sentences; 50–100 words; natural wording (e.g., 'a red traffic light', not XML tag names); "
    "mention vehicles/pedestrians/weather/time of day/speed limits/initial positions/paths/events/triggers if present; "
    "specify temporal/spatial constraints when present; no code, no XML, only plain text description."
)
DS_SYSTEM_PROMPT = (
    "Act as an OpenSCENARIO 1.0 generator for ADS testing in CARLA. "
    "I will give you a scene description in English and you must return one valid .xosc file, XML only, encoded in UTF-8, starting with <OpenScenario> and ending with </OpenScenario>. "
    "The file must be schema-compliant, and executable in CARLA without modifications. "
    "The scenario must include: the map (<RoadNetwork>), <Environment> with <TimeOfDay> and <Weather>, exactly one ego vehicle, any other entities with unique names, initial positions using <WorldPosition>, and a valid <Storyboard> with deterministic triggers/events/actions. "
    "Use realistic defaults if details are missing (no randomness), but never omit these features. "
    "No comments or extra text, only the .xosc."
)

# opzionale: metti qui una mappa di default se vuoi includerla nel messaggio
DEFAULT_XODR_NAME: Optional[str] = None

# ---- OpenAI client ----
from openai import OpenAI
client = OpenAI()  # usa OPENAI_API_KEY dall'ambiente

def describe_xosc(xosc_text: str, xodr_name: Optional[str]) -> str:
    feat = extract_features_from_xosc(xosc_text)
    if xodr_name and not feat.get("map"):
        feat["map"] = xodr_name
    compact = features_to_compact_prompt(feat)
    print(f"[INFO] Summary length: {len(compact)} chars")

    user_msg = (
        "Here is a compact, structured summary of a valid OpenSCENARIO 1.0 file (.xosc). "
        "Return ONE description only, as plain text (50–100 words, 4–5 sentences).\n\n"
        + compact
    )

    for attempt in range(6):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            wait = 2 ** attempt
            if attempt == 5:
                raise
            time.sleep(wait)

def main():
    parser = argparse.ArgumentParser(description="Genera descrizioni naturali da file .xosc")
    parser.add_argument("--input_dir", required=True, help="Cartella contenente file .xosc")
    parser.add_argument("--output_dir", required=True, help="Cartella di output (conterrà jsonl)")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_jsonl = output_dir / "all.jsonl"

    # prepara output (append-safe)
    if not output_jsonl.exists():
        output_jsonl.write_text("", encoding="utf-8")

    files = sorted(glob.glob(str(input_dir / "*.xosc")))
    if not files:
        print(f"Nessun .xosc trovato in {input_dir.resolve()}")
        return

    # carica già esistenti per evitare duplicati
    seen_assistants = set()
    if output_jsonl.stat().st_size > 0:
        with output_jsonl.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    seen_assistants.add(obj.get("assistant", ""))
                except:
                    pass

    file_number = 1
    error_files = []
    print(len(files))

    with output_jsonl.open("a", encoding="utf-8") as out:
        for path in files:
            try:
                print("Completamento: " + str((file_number/len(files))*100) + "%.\n")
                xosc_text = Path(path).read_text(encoding="utf-8").strip()
                if xosc_text in seen_assistants:
                    print(f"[SKIP] già presente: {path}")
                    continue

                # prova a inferire un nome mappa dal filename
                xodr_name = DEFAULT_XODR_NAME
                stem = Path(path).stem
                for town in [f"Town{str(i).zfill(2)}" for i in range(1, 15)]:
                    if town.lower() in stem.lower():
                        xodr_name = f"{town}.xodr"
                        break

                print(f"[GEN] {path} (map: {xodr_name or 'n/a'})")

                try:
                    user_text = describe_xosc(xosc_text, xodr_name)
                except Exception as e:
                    print(f"[ERRORE Describe XOSC] {path} → {e}, passo al prossimo file.")
                    error_files.append(Path(path).name)
                    continue

                #time.sleep(25)

                record = {
                    "system": DS_SYSTEM_PROMPT,
                    "user": user_text,
                    "assistant": xosc_text,
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()
                file_number += 1
            except Exception as e:
                print(f"[ERRORE GENERICO] {path} → {e}, passo al prossimo file.")
                error_files.append(Path(path).name)
                continue

    if error_files:
        with open("error_files.txt", "w", encoding="utf-8") as errf:
            errf.write("\n".join(error_files))
        print(f"\n[INFO] Salvati {len(error_files)} errori in error_files.txt")
    else:
        print("\n[INFO] Nessun errore rilevato.")

    print(f"Fatto. Output: {output_jsonl.resolve()}")

if __name__ == "__main__":
    main()
