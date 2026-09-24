from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parent; files=sorted((ROOT/"content/shorts").glob("*.json")); errors=[]
if len(files)!=30: errors.append(f"Expected 30 JSONs, found {len(files)}")
for p in files:
    try: d=json.loads(p.read_text())
    except Exception as e: errors.append(f"{p}: invalid JSON: {e}"); continue
    if not 5<=len(d.get("captions",[]))<=7: errors.append(f"{p}: captions must be 5–7")
    if d.get("duration_seconds")!=10: errors.append(f"{p}: duration must be 10")
    if not d.get("image",{}).get("prompt"): errors.append(f"{p}: missing image prompt")
    if not d.get("music",{}).get("name") or not d.get("music",{}).get("prompt"): errors.append(f"{p}: incomplete music")
if errors: print("\n".join(errors)); sys.exit(1)
print(f"OK — {len(files)} Short JSONs validated.")
