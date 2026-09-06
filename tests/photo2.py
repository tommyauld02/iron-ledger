from playwright.sync_api import sync_playwright
import os, datetime, json
d=os.getcwd().replace("\\","/"); d="/"+d if d[1:2]==":" else d; T=datetime.date.today().isoformat()
G={"cal":{"dir":"-","v":2000},"pro":{"dir":"+","v":150}}
STORE={"days":{T:{"food":[],"lifts":[],"updated":1,"goal":G}},"moves":None,"goal":G,
       "region":"United States","pantry":[],"v":1}
def stub(grams):
    return """window.claude={use:function(n){
     if(n==='sample'){var f=function(){};
      f.json=function(p,o){return new Promise(r=>setTimeout(()=>r(
        {name:'Kirkland protein bar',servingGrams:%s,calories:190,protein:21}),200));};
      f.limits=function(){return Promise.resolve({maxPromptBytes:65536,images:{maxCount:4,maxInputBytes:2e7,mediaTypes:['image/png']}});};
      return Promise.resolve(f);} return Promise.resolve(null);}};""" % grams

with sync_playwright() as pw:
    b=pw.chromium.launch()
    for label, grams, queries in [("panel gives grams (60 g)", "60", ["1 kirkland protein bar","120 g kirkland protein bar","2 kirkland protein bar"]),
                                  ("panel gives no weight",     "0", ["1 kirkland protein bar","2 kirkland protein bar"])]:
        ctx=b.new_context(viewport={"width":393,"height":852}, has_touch=True, is_mobile=True); ctx.add_init_script(stub(grams))
        p=ctx.new_page(); errs=[]
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.goto("file://"+d+"/iron-ledger.html"); p.wait_for_timeout(300)
        p.evaluate("s=>localStorage.setItem('iron-ledger-v1',JSON.stringify(s))", STORE)
        p.reload(); p.wait_for_timeout(800)
        p.click('.tabs button[data-tab="pantry"]'); p.wait_for_timeout(500)
        p.set_input_files("#shotFile","tests/label.png"); p.wait_for_timeout(900)
        print("\n=== %s ===" % label)
        print("  form:", p.evaluate("()=>[panName.value,panServe.value,panUnit.value,panCal.value,panPro.value]"))
        p.click("#savePan"); p.wait_for_timeout(400)
        rec=p.evaluate("()=>JSON.parse(localStorage.getItem('iron-ledger-v1')).pantry[0]")
        print("  saved:", json.dumps({k:rec[k] for k in ['serveQty','serveUnit','serveG','sCal','sPro']}))
        print("  list row:", p.eval_on_selector(".pan-item .sub","e=>e.textContent"))
        p.click('.tabs button[data-tab="macros"]'); p.wait_for_timeout(400)
        for q in queries:
            p.fill("#estText",q); p.click("#runEst"); p.wait_for_timeout(700)
            r=p.eval_on_selector_all(".rev-item","e=>{const amt=x=>{const g=x.querySelector('[data-ig]'),t=x.querySelector('.amt');if(!g) return t.textContent.trim();const pre=t.querySelector('.pre'),u=t.querySelector('.g-unit'),s=t.querySelector('.src-tag');return ((pre?pre.textContent:'')+g.value+' '+(u?u.textContent:'')+' '+(s?s.textContent:'')).trim();};return e.map(x=>x.querySelector('[data-ic]').value+' kcal, '+x.querySelector('[data-ip]').value+' g ('+amt(x)+')');}")
            print("  %-34s %s" % ('"'+q+'"', r[0] if r else "NO RESULT"))
            if r: p.click("#discardEst"); p.wait_for_timeout(250)
        print("  errors:", errs if errs else "none")
        ctx.close()
    b.close()
