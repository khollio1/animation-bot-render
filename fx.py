# Free local "anime FX" engine: camera move + speed lines, zoom punch, shake, slash arc, impact frames, embers on a keyframe.
import random, math, subprocess, os, tempfile
from PIL import Image, ImageDraw, ImageFilter, ImageChops
W,H,FPS=1280,720,24
def speed(alpha,seed):
    r=random.Random(seed); im=Image.new('L',(W,H),0); d=ImageDraw.Draw(im); cx,cy=W*0.5,H*0.5
    for _ in range(90):
        a=r.uniform(0,6.283); r0=r.uniform(220,420); r1=r0+r.uniform(250,600); w=r.uniform(0.01,0.03)
        d.polygon([(cx+r0*math.cos(a),cy+r0*math.sin(a)),(cx+r1*math.cos(a-w),cy+r1*math.sin(a-w)),(cx+r1*math.cos(a+w),cy+r1*math.sin(a+w))],fill=int(255*alpha))
    return im
def fx_clip(img_path,out,dur,action=False,seed=1,drift=1):
    """dur seconds. action=True adds impact beat at ~55% of the clip. drift: 1 push-in, -1 pull-out."""
    src=Image.open(img_path).convert('RGB').resize((int(W*1.35),int(H*1.35)),Image.LANCZOS)
    N=max(int(dur*FPS),12); imp=int(N*0.55); rnd=random.Random(seed)
    d0=tempfile.mkdtemp()
    px=rnd.uniform(-30,30)
    for i in range(N):
        t=i/N; z=(1.0+0.14*t) if drift>0 else (1.14-0.14*t)
        if action and imp<=i<imp+4: z+=0.12*(1-(i-imp)/4)
        cw,chh=int(src.width/ (z*1.0)*0.9),int(src.height/(z*1.0)*0.9)
        cx,cy=src.width//2+int(px*t*3),src.height//2
        sh=(rnd.randint(-14,14),rnd.randint(-14,14)) if action and imp<=i<imp+10 else (0,0)
        box=(cx-cw//2+sh[0],cy-chh//2+sh[1],cx+cw//2+sh[0],cy+chh//2+sh[1])
        fr=src.crop(box).resize((W,H),Image.BILINEAR)
        if action:
            if imp-4<=i<imp+4:
                fr=fr.filter(ImageFilter.GaussianBlur(2)); fr=ImageChops.lighter(fr,fr.transform(fr.size,Image.AFFINE,(1,0,-25,0,1,6)))
            if imp-6<=i<imp+16:
                fr=Image.composite(Image.new('RGB',(W,H),(255,255,255)),fr,speed(0.8,seed*100+i//2))
            if imp<=i<imp+2: fr=ImageChops.invert(fr)
            elif imp+2<=i<imp+4: fr=Image.blend(fr,Image.new('RGB',(W,H),(255,255,255)),0.6)
            if imp-2<=i<imp+6:
                k=(i-(imp-2))/7; sl=Image.new('RGB',(W,H),(0,0,0)); dd=ImageDraw.Draw(sl)
                dd.arc((150,-150,1150,850),200,200+130*k,fill=(255,255,255),width=int(30*(1-k)+6))
                fr=ImageChops.screen(fr,sl.filter(ImageFilter.GaussianBlur(3)))
        r=random.Random(seed*1000+i); dd=ImageDraw.Draw(fr)
        for j in range(18):
            x=(r.random()*W+i*6*(j%3+1))%W; y=(r.random()*H-i*5*(j%2+1))%H; dd.ellipse((x,y,x+3,y+3),fill=(255,200,120))
        fr.save(f'{d0}/{i:04d}.jpg',quality=90)
    subprocess.run(['ffmpeg','-y','-loglevel','error','-framerate',str(FPS),'-i',f'{d0}/%04d.jpg','-c:v','libx264','-pix_fmt','yuv420p',out],check=True)
    subprocess.run(['rm','-rf',d0])
