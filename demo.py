# End-to-end demo without Telegram: idea -> script -> render -> edit -> re-render. Writes demo1.mp4, demo2.mp4, timings.
import os,sys,json,time,pipeline as P
idea=os.environ['DEMO_IDEA']; edit=os.environ.get('DEMO_EDIT',''); os.makedirs('out',exist_ok=True); T={}
t=time.time(); pj=P.plan(idea,int(os.environ.get('DEMO_SCENES','5'))); T['plan_s']=round(time.time()-t); json.dump(pj,open('out/script1.json','w'),ensure_ascii=False,indent=1)
t=time.time(); d=P.render(pj,'demo','out/demo1.mp4'); T['render1_s']=round(time.time()-t); T['dur1']=round(d,1)
if edit:
    t=time.time(); pj2=P.edit_plan(pj,edit); T['edit_plan_s']=round(time.time()-t); json.dump(pj2,open('out/script2.json','w'),ensure_ascii=False,indent=1)
    T['changed_scenes']=[i+1 for i,s in enumerate(pj2['scenes']) if i>=len(pj['scenes']) or s!=pj['scenes'][i]]
    t=time.time(); d=P.render(pj2,'demo','out/demo2.mp4'); T['render2_s']=round(time.time()-t); T['dur2']=round(d,1)
json.dump(T,open('out/timings.json','w')); print(T)
