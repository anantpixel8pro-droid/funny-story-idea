#!/usr/bin/env python3
from pathlib import Path
import argparse,subprocess,sys
ROOT=Path(__file__).resolve().parent
ap=argparse.ArgumentParser(); ap.add_argument("--ids",nargs="*"); ap.add_argument("--generate-missing-music",action="store_true"); a=ap.parse_args()
files=sorted((ROOT/"content/shorts").glob("*.json"))
if a.ids: files=[p for p in files if p.stem in set(a.ids)]
if not files: raise SystemExit("No matching Short JSON files.")
for p in files:
    cmd=[sys.executable,str(ROOT/"render_short.py"),str(p)]
    if a.generate_missing_music: cmd.append("--generate-missing-music")
    subprocess.run(cmd,check=True)
