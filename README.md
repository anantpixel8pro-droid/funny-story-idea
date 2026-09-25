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

## Missing music / ACE-Step 1.5 API
Each JSON contains a music object with a reusable library name and generation prompt.

The renderer is **cache-first and automatic**:

1. Look for the requested WAV in `assets/music/`.
2. If it exists, use it immediately — **ACE-Step is not called again**.
3. If it is missing, call the local ACE-Step 1.5 API at `http://localhost:7860`.
4. Poll until generation finishes.
5. Download the generated WAV into `assets/music/<name>.wav`.
6. Render the Short using that saved WAV.

So the normal command is simply:

```bash
python render_short.py content/shorts/001.json
```

### ACE-Step API configuration

Default API URL:

```text
http://localhost:7860
```

Override it if needed:

```bash
export ACESTEP_API_URL="http://localhost:7860"
```

If your ACE-Step server uses an API key:

```bash
export ACESTEP_API_KEY="your-key"
```

Optional timeout/polling settings:

```bash
export ACESTEP_TIMEOUT=600
export ACESTEP_POLL_INTERVAL=2
```

The renderer uses ACE-Step's asynchronous `/release_task` → `/query_result` → `/v1/audio` flow.

The old `ACESTEP_COMMAND` environment variable remains supported as a fallback if the API call fails.

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
