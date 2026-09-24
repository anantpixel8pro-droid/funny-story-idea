#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,shlex,subprocess,tempfile
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

def generate_music(cfg,out):
    template=os.getenv("ACESTEP_COMMAND")
    if not template: raise RuntimeError("Missing music. Add the WAV to assets/music or set ACESTEP_COMMAND.")
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
    ap=argparse.ArgumentParser(); ap.add_argument("json",type=Path); ap.add_argument("--image",type=Path); ap.add_argument("--music",type=Path); ap.add_argument("--output",type=Path); ap.add_argument("--generate-missing-music",action="store_true")
    a=ap.parse_args(); cfg=json.loads(a.json.read_text()); image=a.image or ROOT/cfg["image"]["filename"]; music=a.music or music_path(cfg)
    if not image.exists(): raise FileNotFoundError(f"Image not found: {image}")
    if music is None:
        if not a.generate_missing_music: raise FileNotFoundError(f"Music '{cfg['music']['name']}' not found.")
        music=ROOT/"assets/music"/f"{cfg['music']['name']}.wav"; generate_music(cfg,music)
    out=a.output or ROOT/"output"/f"{cfg['id']}.mp4"; render(cfg,image,music,out); print("READY:",out)

if __name__=="__main__": main()
