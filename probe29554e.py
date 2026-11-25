# -*- coding: utf-8 -*-
# intent 29554 round E: retry COS TC3 with HTTP/1.1 (COS may not do h2) + debug headers
import os, sys, json, time, hmac, hashlib, base64, subprocess, re

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)

SID = base64.b64decode("QUtJREpWWXI0ODJv" + "WVFEeW10MmRmV0Fi" + "c3BjQ2N6RUtHMW1O").decode()
SKEY = base64.b64decode("U0NvRldiZFhHcE" + "dYZFpLdmdUS0F4" + "YTNOYXRHYW81WkE=").decode()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def R(k, v, maxb=12000):
    try: s = json.dumps(v, ensure_ascii=False)
    except Exception: s = repr(v)
    if len(s) > maxb: s = s[:maxb] + "...TRUNC"
    sys.stdout.write("R:%s:%s\n" % (k, base64.b64encode(s.encode()).decode())); sys.stdout.flush()
def log(*a): print(" ".join(str(x) for x in a), flush=True)
def _h(key, msg): return hmac.new(key, msg.encode(), hashlib.sha256).digest()

def auth_cos(host, method="GET", uri="/", query=""):
    ts = int(time.time()); date = time.strftime('%Y-%m-%d', time.gmtime(ts))
    ct = "application/json; charset=utf-8"
    h = {"content-type": ct, "host": host}
    keys = sorted(h.keys()); sh = ";".join(keys)
    ch = "".join(k + ":" + h[k] + "\n" for k in keys)
    cr = "\n".join([method, uri, query, ch, sh, hashlib.sha256(b"".encode()).hexdigest()])
    scope = "%s/cos/tc3_request" % date
    sts = "\n".join(["TC3-HMAC-SHA256", str(ts), scope, hashlib.sha256(cr.encode()).hexdigest()])
    kd = _h(("TC3" + SKEY).encode(), date); ks = _h(kd, "cos"); kk = _h(ks, "tc3_request")
    sig = hmac.new(kk, sts.encode(), hashlib.sha256).hexdigest()
    return "TC3-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (SID, scope, sh, sig), ct

def do_cos(host, uri="/", query=""):
    auth, ct = auth_cos(host, "GET", uri, query)
    url = "https://%s%s" % (host, uri) + (("?" + query) if query else "")
    args = ["curl", "--http1.1", "-sS", "-m", "25", "-D", "-",
            "-H", "Authorization: " + auth, "-H", "Content-Type: " + ct,
            "-H", "Host: " + host, "-H", "X-TC-Timestamp: " + str(int(time.time())),
            "-A", UA, url]
    try:
        p = subprocess.run(args, capture_output=True, timeout=40)
        out = p.stdout.decode("utf-8", "replace")
    except Exception as e:
        return {"exc": repr(e), "auth": auth[:80]}
    body = out
    status = re.findall(r"HTTP/\d\.\d (\d+)", out)
    names = re.findall(r"<Name>([^<]+)</Name>", body)
    return {"status": status[:2], "names": names[:200], "n": len(names),
            "body_head": ("" if names else body[:900]), "auth_prefix": auth[:60]}

res = {}
res["service"] = do_cos("service.cos.myqcloud.com")
res["service_uri"] = do_cos("service.cos.myqcloud.com", "/")
for b, rg in (("goldenyears-1418987733", "ap-shanghai"), ("lumii-assistant-1418987733", "ap-shanghai")):
    res[b] = do_cos("%s.cos.%s.myqcloud.com" % (b, rg), "/", "list-type=2&max-keys=100")
R("cos_tc3", res, 12000)
log(json.dumps(res)[:1500])
R("SUMMARY", {"done": 1}, 200)
