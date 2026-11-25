import json,hmac,hashlib,base64,time,uuid,subprocess
HOST="assistant.lumiiai.cn"; ORG="org_bTLzxtBLmugV8uxx4QTyw"; SUB="usr_ZxLewKrgbRYSm7rWDtQX8"
JS="297b8a491bc1920b918d01de77166556d3f835f473968c6b"
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
now=int(time.time())
h=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")))
p=b64u(json.dumps({"sub":SUB,"org":ORG,"iat":now,"exp":now+2592000,"sid":"sid_"+str(uuid.uuid4()),"lgn":now},separators=(",",":")))
sig=hmac.new(JS.encode(),(h+"."+p).encode(),hashlib.sha256).digest()
COOKIE="lumii_session="+h+"."+p+"."+b64u(sig)
def run(name,args):
    cmd=["curl","-s","--http2","-k","-m","25","-o","/tmp/r.bin","-w","%{http_code}","-H","Cookie: "+COOKIE]+args+["https://"+HOST+"/api/me"]
    p=subprocess.run(cmd,capture_output=True,timeout=40)
    body=open("/tmp/r.bin","rb").read()
    print(name,"->",p.stdout.decode().strip(),len(body),body[:120],flush=True)
    time.sleep(1.2)
run("plain-default-ua",[])
run("ua-curl-default",["-A","curl/8.5.0"])
run("ua-mozilla",["-A","Mozilla/5.0"])
run("ua-chrome",["-A","Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"])
run("explicit-XGET",["-X","GET","-A","curl/8.5.0"])
run("sec-fetch",["-A","Mozilla/5.0","-H","Accept: application/json","-H","Referer: https://assistant.lumiiai.cn/"])
run("again-curl-ua",["-A","curl/8.5.0"])
