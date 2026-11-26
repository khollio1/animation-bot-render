# Gemini helpers: TTS (acted, per-line direction) and photoreal images. Key read from file, never printed.
import os,json,base64,urllib.request,urllib.error,time,wave,hashlib,sys
KEY=os.environ.get('GEMINI_API_KEY') or open(os.environ.get('GEMINI_KEY_FILE','/home/sandbox/.vault/gemini-api-key-mr-khalid-bot-66ff72/password')).read().strip()
BASE='https://generativelanguage.googleapis.com/v1beta/models/'
TTS_MODEL=os.environ.get('TTS_MODEL','gemini-3.1-flash-tts-preview')
IMG_MODEL=os.environ.get('IMG_MODEL','gemini-2.5-flash-image')
def post(model,body,tries=4):
    for a in range(tries):
        rq=urllib.request.Request(BASE+model+':generateContent',json.dumps(body).encode(),{'Content-Type':'application/json','x-goog-api-key':KEY})
        try: return json.load(urllib.request.urlopen(rq,timeout=120))
        except urllib.error.HTTPError as e:
            msg=e.read().decode()[:300]
            if e.code in (429,500,503): time.sleep(3*(a+1)); continue
            raise RuntimeError(f'{e.code} {msg}')
    raise RuntimeError('retries exhausted')
TTS_CHAIN=['gemini-3.1-flash-tts-preview','gemini-3.8-flash-tts','gemini-2.5-flash-preview-tts','gemini-3.8-flash-lite-tts']
def tts(text,voice,direction,out):
    body={'contents':[{'parts':[{'text':f'{direction}: {text}'}]}],'generationConfig':{'responseModalities':['AUDIO'],'speechConfig':{'voiceConfig':{'prebuiltVoiceConfig':{'voiceName':voice}}}}}
    err=None
    for rnd in range(3):
        for m in TTS_CHAIN:
            try:
                r=post(m,body,tries=2)
                for p in r['candidates'][0]['content']['parts']:
                    if 'inlineData' in p:
                        pcm=base64.b64decode(p['inlineData']['data'])
                        with wave.open(out,'wb') as w: w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(pcm)
                        return
                err=RuntimeError(f'{m}: no audio ({str(r)[:150]})')
            except Exception as e: err=e
        time.sleep(5)
    raise err
def image(prompt,out):
    body={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'responseModalities':['IMAGE','TEXT'],'imageConfig':{'aspectRatio':'16:9'}}}
    for m in IMG_CHAIN:
        try:
            r=post(m,body,tries=1)
            for p in r['candidates'][0]['content']['parts']:
                if 'inlineData' in p: open(out,'wb').write(base64.b64decode(p['inlineData']['data'])); return
        except Exception as e: pass
    raise RuntimeError('no image in response')

TEXT_CHAIN=['gemini-3.8-flash','gemini-3.7-flash','gemini-3.6-flash','gemini-3.5-flash','gemini-3.1-flash-lite','gemini-2.5-flash']
IMG_CHAIN=['gemini-3.1-flash-image','gemini-3.1-flash-lite-image','gemini-2.5-flash-image','gemini-nano-banana-2.1']
def text(prompt,system=None,json_mode=False):
    body={'contents':[{'parts':[{'text':prompt}]}]}
    if system: body['systemInstruction']={'parts':[{'text':system}]}
    if json_mode: body['generationConfig']={'responseMimeType':'application/json'}
    err=None
    for m in TEXT_CHAIN:
        try: return post(m,body,tries=2)['candidates'][0]['content']['parts'][0]['text']
        except Exception as e: err=e
    raise err
