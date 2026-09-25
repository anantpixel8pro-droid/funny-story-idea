#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,shlex,subprocess,tempfile,time,urllib.parse,urllib.request
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent
FPS=30

def run(cmd):
    print("+"," ".join(shlex.quote(str(x)) for x in cmd)); subprocess.run([str(x) for x in cmd],check=True)

def font_path():
    for p in [os.getenv("SHORT_FONT"),"/System/Library/Fonts/Supplemental/Arial.ttf",
              "/System/Library/Fonts/Supplemental/Arial Unicode.ttf","/Library/Fonts/Arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf","/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"]:
        if p and Path(p).exists(): return p
    raise FileNotFoundError("Set SHORT_FONT to a valid .ttf font.")

def fit_cover(img,size):
    w,h=size; scale=max(w/img.width,h/img.height); nw,nh=round(img.width*scale),round(img.height*scale)
    img=img.resize((nw,nh),Image.Resampling.LANCZOS); x,y=(nw-w)//2,(nh-h)//2
    return img.crop((x,y,x+w,y+h))

def wrap(draw,text,fnt,max_width):
    out=[]; cur=""
    for word in text.split():
        test=word if not cur else cur+" "+word
        if draw.textbbox((0,0),test,font=fnt)[2]<=max_width: cur=test
        else:
            if cur: out.append(cur)
            cur=word
    if cur: out.append(cur)
    return out or [text]

def draw_caption(frame,text,y,size,stroke,emphasis):
    draw=ImageDraw.Draw(frame); fnt=ImageFont.truetype(font_path(),int(size*(1.10 if emphasis else 1)))
    lines=wrap(draw,text,fnt,frame.width-110); gap=8
    heights=[draw.textbbox((0,0),x,font=fnt,stroke_width=stroke)[3] for x in lines]
    lh=max(heights); total=len(lines)*lh+(len(lines)-1)*gap; yy=y-total/2
    for line in lines:
        box=draw.textbbox((0,0),line,font=fnt,stroke_width=stroke); x=(frame.width-(box[2]-box[0]))/2
        draw.text((x,yy),line,font=fnt,fill="white",stroke_width=stroke,stroke_fill="black"); yy+=lh+gap

def make_frame(img,cfg,c,t):
    W,H=cfg["resolution"]; duration=float(cfg["duration_seconds"])
    z0=float(cfg["render"].get("zoom_start",1)); z1=float(cfg["render"].get("zoom_end",1.08)); zoom=z0+(z1-z0)*(t/duration)
    zw,zh=round(W*zoom),round(H*zoom); big=fit_cover(img,(zw,zh)); x,y=(zw-W)//2,(zh-H)//2
    frame=big.crop((x,y,x+W,y+H)).convert("RGB")
    cy={"upper":H*.28,"center":H*.50,"lower":H*.72}.get(cfg["render"].get("caption_position","center"),H*.50)
    draw_caption(frame,c["text"],cy,int(cfg["render"].get("font_size",62)),int(cfg["render"].get("stroke_width",5)),bool(c.get("emphasis")))
    return frame

def music_path(cfg):
    lib=json.loads((ROOT/"assets/music/music_library.json").read_text()); name=cfg["music"]["name"]
    for track in lib["tracks"]:
        if track["name"]==name:
            p=ROOT/track["file"]; return p if p.exists() else None
    p=ROOT/"assets/music"/f"{name}.wav"; return p if p.exists() else None

def _api_json(url,payload=None,headers=None,timeout=3600):
    data=None
    h={"Content-Type":"application/json"}
    if headers: h.update(headers)
    if payload is not None: data=json.dumps(payload).encode("utf-8")
    req=urllib.request.Request(url,data=data,headers=h,method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def _api_download(url,out,timeout=1200):
    req=urllib.request.Request(url,method="GET")
    with urllib.request.urlopen(req,timeout=timeout) as r, open(out,"wb") as f:
        f.write(r.read())

def _acestep_api_url():
    return os.getenv("ACESTEP_API_URL","http://localhost:7860").rstrip("/")

def generate_music_api(cfg,out):
    base=_acestep_api_url(); duration=float(cfg["duration_seconds"])
    payload={
        "prompt":cfg["music"]["prompt"],
        "lyrics":"[inst]",
        "audio_duration":duration,
        "thinking":False,
        "inference_steps":8,
        "batch_size":1,
        "audio_format":"wav",
    }
    token=os.getenv("ACESTEP_API_KEY")
    headers={"Authorization":f"Bearer {token}"} if token else None
    print(f"Generating missing music via ACE-Step API: {base}")
    response=_api_json(f"{base}/release_task",payload,headers)
    data=response.get("data",response)
    task_id=data.get("task_id") if isinstance(data,dict) else None
    if not task_id: raise RuntimeError(f"ACE-Step release_task failed: {response}")
    deadline=time.time()+float(os.getenv("ACESTEP_TIMEOUT","3600"))
    while time.time()<deadline:
        result=_api_json(f"{base}/query_result",{"task_id_list":[task_id]},headers)
        rows=result.get("data",result)
        row=rows[0] if isinstance(rows,list) and rows else rows
        status=row.get("status") if isinstance(row,dict) else 0
        if status==2: raise RuntimeError(f"ACE-Step generation failed: {row}")
        if status==1:
            raw=row.get("result","[]")
            try: items=json.loads(raw) if isinstance(raw,str) else raw
            except json.JSONDecodeError as e: raise RuntimeError(f"Invalid ACE-Step result: {raw}") from e
            if not items: raise RuntimeError(f"ACE-Step returned no audio: {row}")
            item=items[0] if isinstance(items,list) else items
            audio=item.get("file") if isinstance(item,dict) else None
            if not audio: raise RuntimeError(f"ACE-Step result has no audio file: {item}")
            # query_result may return either a complete /v1/audio?path=... URL
            # or the absolute server-side audio path. A raw path must be wrapped
            # with the API's /v1/audio endpoint; concatenating it to the base URL
            # would produce a 404.
            if audio.startswith("http://") or audio.startswith("https://"):
                audio_url=audio
            elif audio.startswith("/v1/audio?"):
                audio_url=base+audio
            elif audio.startswith("/v1/audio"):
                audio_url=base+audio
            else:
                audio_url=f"{base}/v1/audio?path={urllib.parse.quote(audio, safe='')}"
            print("Downloading generated audio:", audio_url)
            _api_download(audio_url,out)
            if out.exists() and out.stat().st_size>0: return
            raise RuntimeError("ACE-Step audio download produced an empty file.")
        time.sleep(float(os.getenv("ACESTEP_POLL_INTERVAL","2")))
    raise TimeoutError(f"ACE-Step generation timed out after {os.getenv('ACESTEP_TIMEOUT','3600')} seconds.")

def generate_music(cfg,out):
    out.parent.mkdir(parents=True,exist_ok=True)
    # Prefer the local ACE-Step API. The CLI remains an optional fallback for older setups.
    try:
        generate_music_api(cfg,out); return
    except Exception as api_error:
        template=os.getenv("ACESTEP_COMMAND")
        if not template:
            raise RuntimeError(f"ACE-Step API generation failed: {api_error}") from api_error
        print(f"ACE-Step API unavailable/failed; falling back to ACESTEP_COMMAND: {api_error}")
        run(["/bin/sh","-lc",template.format(prompt=cfg["music"]["prompt"],output=str(out),duration=cfg["duration_seconds"])])
        if not out.exists(): raise RuntimeError("Music command did not create "+str(out))

def render(cfg,image_path,music,out):
    W,H=cfg["resolution"]; duration=float(cfg["duration_seconds"]); img=Image.open(image_path).convert("RGB"); out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="funny_short_") as td:
        frames=Path(td)/"frames"; frames.mkdir()
        for n in range(round(duration*FPS)):
            t=n/FPS; active=cfg["captions"][-1]
            for c in cfg["captions"]:
                if float(c["start"])<=t<float(c["end"]): active=c; break
            make_frame(img,cfg,active,t).save(frames/f"{n:06d}.jpg",quality=95)
        silent=Path(td)/"silent.mp4"
        run(["ffmpeg","-y","-framerate",str(FPS),"-i",str(frames/"%06d.jpg"),"-c:v","libx264","-preset","veryfast","-crf","18","-pix_fmt","yuv420p","-movflags","+faststart",str(silent)])
        run(["ffmpeg","-y","-stream_loop","-1","-i",str(music),"-i",str(silent),"-t",str(duration),"-map","1:v:0","-map","0:a:0","-c:v","copy","-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",str(out)])

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("json",type=Path); ap.add_argument("--image",type=Path); ap.add_argument("--music",type=Path); ap.add_argument("--output",type=Path); ap.add_argument("--generate-missing-music",action="store_true",help="Deprecated: missing music is generated automatically.")
    a=ap.parse_args(); cfg=json.loads(a.json.read_text()); image=a.image or ROOT/cfg["image"]["filename"]; music=a.music or music_path(cfg)
    if not image.exists(): raise FileNotFoundError(f"Image not found: {image}")
    if music is None:
        music=ROOT/"assets/music"/f"{cfg['music']['name']}.wav"; generate_music(cfg,music)
    out=a.output or ROOT/"output"/f"{cfg['id']}.mp4"; render(cfg,image,music,out); print("READY:",out)

if __name__=="__main__": main()
