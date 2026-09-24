# Funny Story Idea — Auto Short Renderer

Local pipeline for 9:16, 10-second Indian-parenting comedy Shorts.

Input: one JSON + one image + one WAV.
Output: one ready MP4. No CapCut required.

## Install
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
FFmpeg must be installed and available as `ffmpeg`.

## Render
Put `001.jpg` in `assets/images/` and the matching WAV in `assets/music/`.

```bash
python render_short.py content/shorts/001.json
```

Output: `output/001.mp4`.

## Missing music / ACE-Step
Each JSON contains a music object with a reusable library name and generation prompt. The renderer first looks for the named WAV. If missing, use `--generate-missing-music` with an `ACESTEP_COMMAND` environment variable.

Example:
```bash
export ACESTEP_COMMAND='python /path/to/your/acestep_entry.py --prompt "{prompt}" --output "{output}" --duration {duration}'
python render_short.py content/shorts/001.json --generate-missing-music
```

ACE-Step local installs expose different CLI/API entry points, so the renderer intentionally does not hard-code one installation.

## Batch
```bash
python render_batch.py
python render_batch.py --ids 001 002 003
python render_batch.py --generate-missing-music
```

## Validate
```bash
python validate_content.py
```

The 30 starter JSONs vary family member (Mom, Dad, Dadi, Nani, Dada, Nana, Chachi), emotional flavor, setup and punchline. Image prompts are Nano-ready and request fictional photorealistic family scenes with no text/watermark.
