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
    # Prefer a bundled Devanagari-capable condensed display face.
    for p in [
        os.getenv("SHORT_FONT"),
        str(ROOT/"assets/fonts/NotoSansDevanagari[wdth,wght].ttf"),
        "/System/Library/Fonts/Supplemental/Arial Narrow Bold.ttf",
        "/Library/Fonts/Arial Narrow Bold.ttf",
        "/Library/Fonts/Oswald-Bold.ttf",
        "/Library/Fonts/Anton-Regular.ttf",
        "/Library/Fonts/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/Library/Fonts/Arial Black.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    ]:
        if p and Path(p).exists(): return p
    raise FileNotFoundError("Set SHORT_FONT to a display TTF such as Impact, Anton, or Oswald Bold.")
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

def draw_caption(frame, lines, y, size, stroke, intro=None, anchor="center", line_gap=10, intro_gap=10):
    draw=ImageDraw.Draw(frame)
    side_margin=int(frame.width*0.03)
    max_width=frame.width-(side_margin*2)
    selected_font=font_path()
    fnt=ImageFont.truetype(selected_font,int(size))
    if Path(selected_font).resolve() == (ROOT/"assets/fonts/NotoSansDevanagari[wdth,wght].ttf").resolve():
        fnt.set_variation_by_axes([700,76])

    def wrap_line(text):
        words=text.split(); wrapped=[]; cur=""
        for word in words:
            candidate=word if not cur else cur+" "+word
            if draw.textbbox((0,0),candidate,font=fnt,stroke_width=stroke)[2] <= max_width:
                cur=candidate
            else:
                if cur: wrapped.append(cur)
                cur=word
        if cur: wrapped.append(cur)
        return wrapped or [""]

    paragraphs=[]
    if intro: paragraphs.append(("intro",wrap_line(intro)))
    for line in lines: paragraphs.append(("line",wrap_line(line)))
    items=[]
    for kind,wrapped in paragraphs:
        for j,line in enumerate(wrapped): items.append((kind,j,len(wrapped),line))

    bbox=draw.textbbox((0,0),"Ag",font=fnt,stroke_width=stroke)
    line_height=bbox[3]-bbox[1]
    total=sum(line_height for _ in items)
    for kind,j,count,_ in items[:-1]:
        if j==count-1: total += intro_gap if kind=="intro" else line_gap
    yy=y if anchor=="top" else y-total/2

    for idx,(kind,j,count,line) in enumerate(items):
        bbox=draw.textbbox((0,0),line,font=fnt,stroke_width=stroke)
        text_width=bbox[2]-bbox[0]
        xx=(frame.width-text_width)/2 if anchor=="center" else side_margin
        draw.text((xx+2,yy+2),line,font=fnt,fill="black",stroke_width=max(2,stroke-1),stroke_fill="black")
        draw.text((xx,yy),line,font=fnt,fill="white",stroke_width=stroke,stroke_fill="black")
        yy += line_height
        if j < count-1: yy += 4
        elif idx < len(items)-1: yy += intro_gap if kind=="intro" else line_gap


def make_frame(img,cfg,c,t):
    W,H=cfg["resolution"]; duration=float(cfg["duration_seconds"])
    z0=float(cfg["render"].get("zoom_start",1)); z1=float(cfg["render"].get("zoom_end",1.08)); zoom=z0+(z1-z0)*(t/duration)
    zw,zh=round(W*zoom),round(H*zoom); big=fit_cover(img,(zw,zh)); x,y=(zw-W)//2,(zh-H)//2
    frame=big.crop((x,y,x+W,y+H)).convert("RGB")
    position=cfg["render"].get("caption_position","center")
    if position=="center": caption_y=int(H*float(cfg["render"].get("caption_center",0.50))); anchor="center"
    elif position=="upper": caption_y=int(H*float(cfg["render"].get("caption_top",0.07))); anchor="top"
    else: caption_y={"lower":H*.72}.get(position,H*.50); anchor="center"
    if "lines" in c:
        role=str(cfg.get("role","")).lower()
        intro_map={"mom":"Mummy har samay kehti rehti hai...","dad":"Papa har samay kehte rehte hain...","dadi":"Dadi har samay kehti rehti hain...","nani":"Nani har samay kehti rehti hain...","dada":"Dada har samay kehte rehte hain...","nana":"Nana har samay kehte rehte hain...","chachi":"Chachi har samay kehti rehti hain..."}
        intro=intro_map.get(role) if cfg["render"].get("show_intro",True) else None
        draw_caption(frame,c["lines"],caption_y,int(cfg["render"].get("font_size",78)),int(cfg["render"].get("stroke_width",5)),intro,anchor,int(cfg["render"].get("line_gap",10)),int(cfg["render"].get("intro_gap",10)))
    else:
        draw_caption(frame,[c["text"]],caption_y,int(cfg["render"].get("font_size",54)),int(cfg["render"].get("stroke_width",4)),None,anchor,int(cfg["render"].get("line_gap",10)),int(cfg["render"].get("intro_gap",10)))
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
            t=n/FPS
            # Keep every caption as its own single line, visible from the first frame.
            # Do not word-wrap a caption; the source JSON is expected to contain
            # short punchy lines that fit within the frame width.
            active={"lines":[c["text"] for c in cfg["captions"]], "emphasis":False}
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
