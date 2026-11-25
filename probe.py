# -*- coding: utf-8 -*-
import json,os,sys,base64,re,subprocess,time
HOST="stage-assistant.lumiiai.cn"; BASE="https://"+HOST
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
CRED=("lc-zone-leader@lumii.dev","Lianchuang#2026")
def R(k,v):
    try: s=json.dumps(v,ensure_ascii=False)
    except Exception: s=repr(v)
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()
def curl(args,timeout=40,stdin=None):
    try:
        p=subprocess.run(["curl","--http2","-sS"]+args,input=stdin,capture_output=True,timeout=timeout+10)
        return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()
def call(path,method="GET",body=None,hdrs=None,timeout=40,maxlen=20000,cookie=None):
    args=["-m",str(timeout),"-A",UA,"-w","\n__CODE__%{http_code}"]
    if cookie: args+=["-H","Cookie: "+cookie]
    h={"Accept":"application/json","Referer":BASE+"/","Origin":BASE}
    if hdrs: h.update(hdrs)
    for k,v in h.items(): args+=["-H","%s: %s"%(k,v)]
    data=None
    if body is not None:
        data=json.dumps(body).encode(); args+=["-H","Content-Type: application/json","--data-binary","@-"]
    if method!="GET": args+=["-X",method]
    args+=[BASE+path]
    rc,out,err=curl(args,timeout=timeout,stdin=data)
    txt=out.decode("utf-8","replace"); code=""; i=txt.rfind("__CODE__")
    if i>=0: code=txt[i+8:].strip()[:3]; txt=txt[:i]
    return {"code":code,"body":txt[:maxlen],"len":len(txt),"err":err.decode("utf-8","replace")[:120]}
def J(r):
    try: return json.loads(r["body"])
    except Exception: return None
def login(ident,pw):
    rc,out,err=curl(["-m","45","-A",UA,"-i","-X","POST","-H","Content-Type: application/json",
                     "--data-binary",json.dumps({"identifier":ident,"password":pw}),BASE+"/api/auth/login"],timeout=50)
    txt=out.decode("utf-8","replace"); m=re.search(r"HTTP/[0-9.]+ (\d{3})",txt); code=m.group(1) if m else ""
    mc=re.search(r"lumii_session=([^;]+)",txt); ck=("lumii_session="+mc.group(1)) if mc else ""
    return code,ck
code,ck=login(*CRED); R("login",{"code":code,"ck":bool(ck)})
if not ck: sys.exit(0)
cookie=ck
me=call("/api/me",cookie=cookie); ME=J(me) or {}
R("me",{"code":me["code"],"body":me["body"][:600]})
pr=call("/api/projects?scope=all",cookie=cookie); PJ=J(pr) or {}
R("projects",{"code":pr["code"],"body":pr["body"][:3000]})
items = PJ.get("projects") if isinstance(PJ,dict) else PJ
if isinstance(items,dict): items=items.get("items")
items = items or []
R("proj_count",len(items))
ids=[]
for p in items[:8]:
    pid=p.get("id"); ids.append(pid)
    rr=call("/api/projects/%s/repos"%pid,cookie=cookie)
    R("repos_%s"%pid,{"name":p.get("name"),"code":rr["code"],"body":rr["body"][:1200]})
conn=call("/api/code-host-connections",cookie=cookie); R("connections",{"code":conn["code"],"body":conn["body"][:2000]})
rt=call("/api/runtimes",cookie=cookie); R("runtimes",{"code":rt["code"],"body":rt["body"][:2000]})
asst=call("/api/assistants",cookie=cookie); R("assistants",{"code":asst["code"],"body":asst["body"][:3000]})
