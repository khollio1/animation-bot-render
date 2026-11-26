# Telegram controller for @Mobde3aflambot. Runs inside GitHub Actions (long-poll), renders in the same job.
import os,sys,json,time,subprocess,threading,queue,urllib.request,urllib.parse,uuid,traceback,glob
import pipeline as P, gen
TOKEN=os.environ['TELEGRAM_TOKEN']; API=f'https://api.telegram.org/bot{TOKEN}/'
STATE_KEY=os.environ.get('STATE_KEY',''); STATE_FILE='state.enc'
ALLOWED={int(x) for x in os.environ.get('ALLOWED_CHATS','844423469').split(',') if x.strip()}
RUN_SECONDS=int(os.environ.get('RUN_SECONDS','19000'))
def api(m,**kw):
    d=urllib.parse.urlencode({k:(json.dumps(v) if isinstance(v,(dict,list)) else v) for k,v in kw.items()}).encode()
    try: return json.load(urllib.request.urlopen(urllib.request.Request(API+m,d),timeout=kw.get('timeout',20)+40))
    except Exception as e: print('api err',m,str(e)[:100],flush=True); return {}
def say(cid,t): return api('sendMessage',chat_id=cid,text=t[:4000])
def upload(cid,path,caption=''):
    b=uuid.uuid4().hex; body=b''
    for k,v in (('chat_id',str(cid)),('caption',caption),('supports_streaming','true')): body+=f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    body+=f'--{b}\r\nContent-Disposition: form-data; name="video"; filename="film.mp4"\r\nContent-Type: video/mp4\r\n\r\n'.encode()+open(path,'rb').read()+f'\r\n--{b}--\r\n'.encode()
    rq=urllib.request.Request(API+'sendVideo',body,{'Content-Type':f'multipart/form-data; boundary={b}'})
    try: return json.load(urllib.request.urlopen(rq,timeout=300))
    except Exception as e: print('upload err',e,flush=True); return {}
# ---- state (encrypted, committed to repo so it survives runner restarts) ----
def enc(src,dst): subprocess.run(['openssl','enc','-aes-256-cbc','-pbkdf2','-salt','-pass','env:STATE_KEY','-in',src,'-out',dst],check=True)
def dec(src,dst): subprocess.run(['openssl','enc','-d','-aes-256-cbc','-pbkdf2','-pass','env:STATE_KEY','-in',src,'-out',dst],check=True)
S={'offset':0,'projects':{}}
def load():
    global S
    if STATE_KEY and os.path.exists(STATE_FILE):
        try: dec(STATE_FILE,'/tmp/s.json'); S=json.load(open('/tmp/s.json')); os.remove('/tmp/s.json')
        except Exception as e: print('state load fail',e)
    os.makedirs(P.HERO,exist_ok=True)
    for f in glob.glob('hero/*.mp4.enc'):
        o=f[:-4]
        if not os.path.exists(o): dec(f,o)
def save():
    if not STATE_KEY: return
    json.dump(S,open('/tmp/s.json','w'),ensure_ascii=False); enc('/tmp/s.json',STATE_FILE); os.remove('/tmp/s.json')
    if os.environ.get('GITHUB_ACTIONS'):
        sh=lambda c: subprocess.run(c,shell=True,capture_output=True)
        sh('git config user.name bot; git config user.email bot@users.noreply.github.com; git add state.enc; git commit -m state -q')
        for _ in range(3):
            if sh('git pull --rebase -q; git push -q').returncode==0: break
            time.sleep(3)
# ---- helpers ----
HELP='''أهلاً! أنا منتج أفلام المبدع 🎬
ابعتلي فكرة فيلم بالكلام العادي (مثلاً: "فيلم أنمي عن محارب شاب بيدافع عن قريته") وأنا هكتب السيناريو وأطلعلك فيديو بصوت وتأثيرات.
بعد كده ابعت أي تعديل بالكلام: "خلي الراوي أهدى" / "غيّر المشهد 3 لمعركة في الغابة" / "ضيف مشهد في الآخر".
أوامر: /script السيناريو · /render إعادة تجميع · /new فكرة جديدة · /hero 2 اطلب لقطة أنيميشن حقيقية للمشهد 2 · /status'''
def script_text(pj):
    o=f"🎬 {pj.get('title','')}\n"
    for i,s in enumerate(pj['scenes']):
        o+=f"\nمشهد {i+1}: {s['img'][:90]}\n"+''.join(f"  - ({l['voice']}) {l['text']}\n" for l in s['lines'])
    return o
def do_render(cid,pr,label):
    say(cid,'⏳ بجهز الفيديو (الصور والأصوات والتأثيرات)... ممكن ياخد كام دقيقة')
    out=f'/tmp/film_{cid}.mp4'; t=time.time()
    last=[0]
    def log(m):
        if time.time()-last[0]>60: last[0]=time.time(); say(cid,'⏳ '+m)
    T=P.render(pr['pj'],str(cid),out,log=log)
    upload(cid,out,f"{label} · {int(T)} ثانية · اكتب تعديلك وأنا أعدّل بسرعة (بس المشاهد المتغيرة بتتعاد)"); 
def handle(cid,text):
    text=text.strip(); pr=S['projects'].get(str(cid))
    if text in ('/start','/help'): return say(cid,HELP)
    if text=='/status': return say(cid,'جاهز ✅' if not pr else f"مشروع: {pr['pj'].get('title','')} ({len(pr['pj']['scenes'])} مشاهد)")
    if text=='/new': S['projects'].pop(str(cid),None); save(); return say(cid,'تمام، ابعت فكرة الفيلم الجديد.')
    if text=='/script': return say(cid,script_text(pr['pj']) if pr else 'مفيش مشروع لسه. ابعت فكرة.')
    if text=='/render' and pr: return do_render(cid,pr,'🎞️')
    if text.startswith('/hero'):
        if not pr: return say(cid,'ابعت فكرة الأول.')
        n=''.join(c for c in text if c.isdigit())
        if not n or int(n)<1 or int(n)>len(pr['pj']['scenes']): return say(cid,'اكتب رقم المشهد: /hero 2')
        pr.setdefault('hero_req',[]); 
        if int(n)-1 not in pr['hero_req']: pr['hero_req'].append(int(n)-1)
        save(); return say(cid,f"تمام، سجلت طلب لقطة أنيميشن حقيقية للمشهد {n}. دي بتتعمل في الدفعة اللي بتتجهز يدوي (حدود الباقة المجانية)، وهتتدمج تلقائي لما تجهز.")
    if text.startswith('/idea'): text=text[5:].strip()
    if not pr or text.startswith('فكرة جديدة'):
        text=text.replace('فكرة جديدة','',1).strip() or text
        say(cid,'✍️ بكتب السيناريو...'); pj=P.plan(text); pr={'pj':pj,'idea':text}; S['projects'][str(cid)]=pr; save()
        say(cid,script_text(pj)); return do_render(cid,pr,'🎬 النسخة الأولى')
    say(cid,'✏️ بعدّل...'); old=pr['pj']; new=P.edit_plan(old,text); pr['pj']=new; save()
    ch=[i for i,s in enumerate(new['scenes']) if i>=len(old['scenes']) or s!=old['scenes'][i]]
    say(cid,f"اتعدّل: {'مشاهد '+', '.join(str(i+1) for i in ch) if ch else 'مفيش تغيير في المشاهد'}"+(' (الأسلوب/الشخصية اتغيّرت: هتتعاد كل الصور)' if (new.get('style')!=old.get('style') or new.get('character')!=old.get('character')) else ''))
    return do_render(cid,pr,'🎞️ بعد التعديل')
Q=queue.Queue(); BUSY=[False]
def worker():
    while True:
        cid,text=Q.get(); BUSY[0]=True
        try: handle(cid,text)
        except Exception as e:
            traceback.print_exc(); say(cid,'حصلت مشكلة: '+str(e)[:200]+'\nجرب تبعتها تاني أو اكتب /new')
        BUSY[0]=False
def main():
    load(); threading.Thread(target=worker,daemon=True).start(); t0=time.time()
    print('bot up, offset',S['offset'],flush=True)
    while time.time()-t0<RUN_SECONDS:
        r=api('getUpdates',offset=S['offset'],timeout=25,allowed_updates=['message'])
        for u in r.get('result',[]):
            S['offset']=u['update_id']+1; m=u.get('message') or {}
            t=m.get('text'); cid=(m.get('chat') or {}).get('id')
            if not t or not cid: continue
            if cid not in ALLOWED: say(cid,'البوت ده خاص حالياً.'); continue
            if BUSY[0] or not Q.empty(): say(cid,'📥 استلمت، في الطابور')
            Q.put((cid,t))
        if r.get('result'): save()
    while BUSY[0] or not Q.empty(): time.sleep(5)
    save()
if __name__=='__main__': main()
