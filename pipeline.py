import os,sys,json,time,subprocess,hashlib,urllib.parse,urllib.request,shutil,re
import gen, fx
from PIL import Image,ImageDraw,ImageFont
CACHE=os.environ.get('CACHE_DIR','cache'); os.makedirs(CACHE,exist_ok=True)
HERO=os.environ.get('HERO_DIR','hero')   # hero/<proj>_<scene>.mp4 real AI clips (PixVerse/Kling), optional
FONT=next((f for f in ['/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf','/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf','/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf'] if os.path.exists(f)),None)
VOICES=['Orus','Charon','Kore','Puck','Fenrir','Aoede','Zephyr','Leda','Algenib','Enceladus']
SYS='''You are a film director and anime screenwriter writing in Egyptian-friendly Arabic. Output ONLY JSON:
{"title":str,"style":str(English visual style line, 2D anime film, cel shaded, painterly, cinematic),"character":str(English description of main character, repeated for consistency),
"scenes":[{"img":str(English keyframe description),"char":bool,"action":bool(true if fast fight/impact),"drift":1 or -1,
"sfx":[{"t":sec,"k":"boom"|"clash"|"fire"|"drum"}],
"lines":[{"voice":one of Orus,Charon,Kore,Puck,Fenrir,Aoede,Zephyr,Leda,"dir":str(English acting direction, emotional, intense),"text":str(Arabic, 1-2 short sentences)}]}]}
Use 6-8 scenes, dramatic arc, narrator plus character voices with emotion.'''
def h(*a): return hashlib.md5('|'.join(map(str,a)).encode()).hexdigest()[:10]
def jparse(t):
    t=t.strip(); t=re.sub(r'^```(json)?|```$','',t,flags=re.M).strip(); return json.loads(t)
def plan(idea,scenes=None):
    return jparse(gen.text(f'Film idea: {idea}'+(f'\nNumber of scenes: {scenes}' if scenes else ''),SYS,json_mode=True))
def edit_plan(proj,instruction):
    p=f'Current film JSON:\n{json.dumps(proj,ensure_ascii=False)}\n\nUser edit request (Arabic, may be informal): {instruction}\nReturn the FULL updated film JSON, changing only what the request requires. Keep unchanged scenes byte-identical.'
    return jparse(gen.text(p,SYS,json_mode=True))
def poll(p,f,seed):
    u='https://image.pollinations.ai/prompt/'+urllib.parse.quote(p)+f'?width=1280&height=720&nologo=true&seed={seed}'
    for a in range(5):
        try: open(f,'wb').write(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=90).read()); return
        except Exception as e: time.sleep(20*(a+1))
    raise RuntimeError('image generation failed')
def keyframe(sc,pj,i):
    p=f"{pj['style']}. {sc['img']}"+(f". Main character: {pj['character']}" if sc.get('char',True) else '')+'. no text, no watermark'
    f=f'{CACHE}/img_{h(p,i)}.png'
    if os.path.exists(f): return f
    try: gen.image(p,f)
    except Exception: poll(p,f,7+i)
    return f
def cap(text,name,size=40):
    W,H=1280,720; im=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(im); ft=ImageFont.truetype(FONT,size)
    lines=[];cur=''
    for w in text.split():
        x=(cur+' '+w).strip()
        if d.textlength(x,font=ft,direction='rtl')>W-240: lines.append(cur);cur=w
        else: cur=x
    lines.append(cur); yy=H-50-len(lines)*(size+24)
    for l in lines:
        tw=d.textlength(l,font=ft,direction='rtl')
        d.rounded_rectangle([(W-tw)/2-16,yy-2,(W+tw)/2+16,yy+size+14],12,fill=(0,0,0,140))
        d.text(((W-tw)/2,yy+2),l,font=ft,fill=(255,235,180,255),direction='rtl',stroke_width=2,stroke_fill=(0,0,0,255)); yy+=size+24
    f=f'{CACHE}/{name}.png'; im.save(f); return f
def dur(f): return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f]))
def ff(*a): subprocess.run(['ffmpeg','-y','-loglevel','error',*a],check=True)
def scene_seg(i,sc,pj,pid,log=print):
    tts=[]
    for j,ln in enumerate(sc['lines']):
        f=f'{CACHE}/tts_{h(ln["text"],ln["voice"],ln["dir"])}.wav'
        if not os.path.exists(f): gen.tts(ln['text'],ln['voice'],ln['dir'],f)
        tts.append(f)
    gap=f'{CACHE}/gap.wav'
    if not os.path.exists(gap): ff('-f','lavfi','-i','anullsrc=r=24000:cl=mono','-t','0.35',gap)
    lst=f'{CACHE}/v_{h(*tts)}.txt'; open(lst,'w').write(''.join(f"file '{os.path.abspath(p)}'\nfile '{os.path.abspath(gap)}'\n" for p in tts))
    va=lst.replace('.txt','.wav'); ff('-f','concat','-safe','0','-i',lst,'-c','copy',va)
    d=dur(va)+0.5
    hero=f'{HERO}/{pid}_{i}.mp4'
    key=f'{h(json.dumps(sc,sort_keys=True,ensure_ascii=False),pj["style"],pj["character"],os.path.exists(hero))}'
    seg=f'{CACHE}/seg_{key}.mp4'
    if os.path.exists(seg): return seg,d
    if os.path.exists(hero): src=hero; hv=dur(hero)
    else:
        img=keyframe(sc,pj,i); src=f'{CACHE}/fx_{h(img,sc.get("action"),sc.get("drift",1),d)}.mp4'
        if not os.path.exists(src): fx.fx_clip(img,src,d,action=bool(sc.get('action')),seed=i+1,drift=sc.get('drift',1))
        hv=dur(src)
    if hv<d:
        pp=f'{CACHE}/pp_{key}.mp4'; ff('-i',src,'-filter_complex','[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0[v]','-map','[v]',pp); src=pp
        if dur(pp)<d: pp2=f'{CACHE}/pp2_{key}.mp4'; ff('-stream_loop','3','-i',pp,'-t',str(d),pp2); src=pp2
    caps=[cap(ln['text'],f'cap_{h(ln["text"])}') for ln in sc['lines']]
    t0=0.3; inp=['-i',src,'-i',va]; fc='[0:v]scale=1280:720:flags=lanczos,fps=25[b0];'; last='b0'
    for j,p in enumerate(tts):
        dd=dur(p); inp+=['-i',caps[j]]; fc+=f"[{last}][{2+j}:v]overlay=enable='between(t,{t0:.2f},{t0+dd:.2f})'[o{j}];"; last=f'o{j}'; t0+=dd+0.35
    fc+=f"[{last}]fade=t=in:d=0.3,fade=t=out:st={d-0.3:.2f}:d=0.3[v];[1:a]adelay=300|300,apad,atrim=0:{d:.2f},aresample=44100[a]"
    ff(*inp,'-filter_complex',fc,'-map','[v]','-map','[a]','-t',f'{d:.2f}','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-ar','44100','-ac','2',seg)
    return seg,d
SFX={'boom':"sine=f=50:d=0.9,afade=t=out:st=0.05:d=0.85,volume=2.5",'clash':"anoisesrc=d=0.6:c=white:a=0.7,highpass=f=2500,afade=t=out:st=0.02:d=0.55",
     'fire':"anoisesrc=d=4:c=brown:a=0.5,highpass=f=300,lowpass=f=3000,tremolo=f=9:d=0.5,volume=0.5",'drum':"sine=f=70:d=0.5,afade=t=out:st=0.02:d=0.45,volume=2"}
def render(pj,pid,out,only=None,log=print):
    segs=[];ev=[];off=0
    for i,sc in enumerate(pj['scenes']):
        log(f'مشهد {i+1}/{len(pj["scenes"])}')
        s,d=scene_seg(i,sc,pj,pid,log); segs.append(s); ev.append((off,sc.get('sfx',[]))); off+=d
    lst=f'{CACHE}/list_{pid}.txt'; open(lst,'w').write(''.join(f"file '{os.path.abspath(p)}'\n" for p in segs))
    allv=f'{CACHE}/all_{pid}.mp4'; ff('-f','concat','-safe','0','-i',lst,'-c','copy',allv); T=off
    inp=['-i',allv,'-f','lavfi','-i',f'anoisesrc=d={T}:c=pink:a=0.4','-f','lavfi','-i',f'sine=f=82:d={T}','-f','lavfi','-i',f'sine=f=123:d={T}']
    fc=f"[1:a]lowpass=f=600,tremolo=f=0.25:d=0.7,volume=0.35[w];[2:a][3:a]amix=inputs=2,volume=0.06,afade=t=in:d=2,afade=t=out:st={max(T-2,0)}:d=2[m];"
    mix=['[0:a]','[w]','[m]']; k=4
    for o,evs in ev:
        for e in evs:
            if e.get('k') not in SFX: continue
            at=int((o+float(e['t']))*1000); s0,*fl=SFX[e['k']].split(',',1)
            inp+=['-f','lavfi','-i',s0]; fc+=f"[{k}:a]{fl[0]+',' if fl else ''}volume=0.9,adelay={at}|{at}[e{k}];"; mix.append(f'[e{k}]'); k+=1
    fc+=''.join(mix)+f"amix=inputs={len(mix)}:duration=first:normalize=0[a]"
    ff(*inp,'-filter_complex',fc,'-map','0:v','-map','[a]','-c:v','copy','-c:a','aac',out)
    return T
if __name__=='__main__':
    idea=sys.argv[1]; out=sys.argv[2]; pj=json.load(open(out+'.json')) if os.path.exists(out+'.json') else plan(idea,int(sys.argv[3]) if len(sys.argv)>3 else None); json.dump(pj,open(out+'.json','w'),ensure_ascii=False,indent=1)
    t=time.time(); T=render(pj,'cli',out); print('dur',round(T,1),'wall',round(time.time()-t,1))
