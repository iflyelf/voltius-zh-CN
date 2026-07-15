#!/bin/bash
# Tauri 签名密钥自动生成和配置脚本
# 
# 功能:
#   1. 生成 Tauri 签名密钥对 (minisign 格式)
#   2. 通过 GitHub API 加密并上传到 Secrets
#   3. 更新 localize.py 中的公钥
#   4. 备份密钥信息
#
# 前置要求:
#   - Node.js (npx)
#   - Python 3 + PyNaCl (pip install pynacl)
#   - GitHub Token (需要 repo 和 workflow 权限)
#   - jq, openssl

set -e

# ============================================================================
# 配置区域
# ============================================================================

GITHUB_USER="iflyelf"
GITHUB_REPO="voltius-zh-CN"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

PROJECT_DIR="/xiaonuo/AI/tools/voltius"
BACKUP_DIR="${HOME}/.voltius-zh-keys-backup-$(date +%Y%m%d-%H%M%S)"

# ============================================================================
# 颜色输出
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() { echo -e "${BLUE}ℹ${NC} $*"; }
success() { echo -e "${GREEN}✅${NC} $*"; }
warn() { echo -e "${YELLOW}⚠️${NC} $*"; }
error() { echo -e "${RED}❌${NC} $*" >&2; }

# ============================================================================
# 前置检查
# ============================================================================

check_prerequisites() {
    info "检查前置依赖..."
    
    local missing=()
    
    command -v npx >/dev/null 2>&1 || missing+=("npx (Node.js)")
    command -v python3 >/dev/null 2>&1 || missing+=("python3")
    command -v jq >/dev/null 2>&1 || missing+=("jq")
    command -v openssl >/dev/null 2>&1 || missing+=("openssl")
    
    if ! python3 -c "import nacl.public" 2>/dev/null; then
        missing+=("PyNaCl (运行: pip install pynacl)")
    fi
    
    if [ ${#missing[@]} -gt 0 ]; then
        error "缺少依赖: ${missing[*]}"
        exit 1
    fi
    
    success "依赖检查通过"
}

check_github_token() {
    if [ -z "$GITHUB_TOKEN" ]; then
        error "未设置 GITHUB_TOKEN 环境变量"
        echo ""
        echo "请先设置 GitHub Personal Access Token:"
        echo "  export GITHUB_TOKEN='ghp_xxxxxxxxxxxxx'"
        echo ""
        echo "Token 需要权限: repo, workflow"
        echo "创建地址: https://github.com/settings/tokens/new"
        exit 1
    fi
    
    info "验证 GitHub Token..."
    local user=$(curl -s -H "Authorization: Bearer ${GITHUB_TOKEN}" \
                      -H "Accept: application/vnd.github+json" \
                      https://api.github.com/user | jq -r '.login')
    
    if [ "$user" = "null" ] || [ -z "$user" ]; then
        error "GitHub Token 无效或已过期"
        exit 1
    fi
    
    success "GitHub 验证通过: $user"
}

# ============================================================================
# 密钥生成
# ============================================================================

generate_keypair() {
    info "生成 Tauri 签名密钥对..."
    
    mkdir -p /tmp/voltius-signing
    cd /tmp/voltius-signing
    
    # 生成强密码
    SIGN_PASSWORD=$(openssl rand -base64 24)
    echo "$SIGN_PASSWORD" > password.txt
    
    # 生成密钥对
    info "调用 @tauri-apps/cli signer generate..."
    npx --yes @tauri-apps/cli@latest signer generate \
        -w voltius_zh.key \
        -p "$SIGN_PASSWORD" \
        --force 2>&1 | tee generate.log
    
    if [ ! -f voltius_zh.key ] || [ ! -f voltius_zh.key.pub ]; then
        error "密钥生成失败"
        cat generate.log
        exit 1
    fi
    
    # 读取公钥和私钥
    PRIVATE_KEY=$(cat voltius_zh.key)
    PUBLIC_KEY=$(cat voltius_zh.key.pub)
    
    success "密钥对生成成功"
    echo ""
    echo "  私钥: /tmp/voltius-signing/voltius_zh.key"
    echo "  公钥: /tmp/voltius-signing/voltius_zh.key.pub"
    echo "  密码: /tmp/voltius-signing/password.txt"
    echo ""
}

# ============================================================================
# 配置 GitHub Secrets
# ============================================================================

upload_github_secrets() {
    info "获取仓库公钥..."
    
    curl -s -H "Authorization: Bearer ${GITHUB_TOKEN}" \
         -H "Accept: application/vnd.github+json" \
         "https://api.github.com/repos/${GITHUB_USER}/${GITHUB_REPO}/actions/secrets/public-key" \
         > /tmp/voltius-signing/repo_pubkey.json
    
    local key_id=$(jq -r '.key_id' /tmp/voltius-signing/repo_pubkey.json)
    if [ "$key_id" = "null" ]; then
        error "无法获取仓库公钥,请检查 Token 权限"
        exit 1
    fi
    
    success "仓库公钥获取成功 (key_id: ${key_id:0:16}...)"
    
    info "通过 GitHub API 上传 Secrets..."
    
    # 使用 Python 加密并上传
    python3 - <<PYEOF
import json, base64, os, urllib.request, sys
from nacl import public, encoding

TOKEN = os.environ["GITHUB_TOKEN"]
REPO = "${GITHUB_USER}/${GITHUB_REPO}"
pk = json.load(open("/tmp/voltius-signing/repo_pubkey.json"))
key_id = pk["key_id"]
box = public.SealedBox(public.PublicKey(pk["key"].encode(), encoding.Base64Encoder()))

def encrypt(value):
    return base64.b64encode(box.encrypt(value.encode())).decode()

def put_secret(name, value):
    payload = json.dumps({
        "encrypted_value": encrypt(value),
        "key_id": key_id,
    }).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/actions/secrets/{name}",
        data=payload, method="PUT",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json"
        })
    try:
        resp = urllib.request.urlopen(req)
        print(f"  ✅ {name}: HTTP {resp.status}")
        return True
    except urllib.error.HTTPError as e:
        print(f"  ❌ {name}: HTTP {e.code} - {e.read().decode()}", file=sys.stderr)
        return False

private_key = open("/tmp/voltius-signing/voltius_zh.key").read().strip()
password = open("/tmp/voltius-signing/password.txt").read().strip()

success = True
success &= put_secret("TAURI_SIGNING_PRIVATE_KEY", private_key)
success &= put_secret("TAURI_SIGNING_PRIVATE_KEY_PASSWORD", password)

sys.exit(0 if success else 1)
PYEOF
    
    if [ $? -eq 0 ]; then
        success "GitHub Secrets 配置成功"
    else
        error "GitHub Secrets 配置失败"
        exit 1
    fi
}

# ============================================================================
# 更新 localize.py
# ============================================================================

update_localize_py() {
    info "更新 localize.py 中的公钥..."
    
    cd "$PROJECT_DIR"
    
    if ! grep -q "patch_tauri_pubkey" localize.py; then
        warn "localize.py 中未找到 patch_tauri_pubkey 函数,跳过更新"
        return
    fi
    
    # 提取新公钥
    NEW_PUBKEY=$(cat /tmp/voltius-signing/voltius_zh.key.pub)
    
    # 备份
    cp localize.py localize.py.bak
    
    # 替换公钥 (从文件读取公钥,避免 shell 插值注入风险)
    python3 - <<'PYEOF'
import re

with open("/tmp/voltius-signing/voltius_zh.key.pub", "r", encoding="utf-8") as f:
    new_key = f.read().strip()

with open("localize.py", "r", encoding="utf-8") as f:
    content = f.read()

# 匹配 NEW_PUBKEY = "..." 并替换 (用函数替换避免反斜杠转义问题)
pattern = r'(NEW_PUBKEY\s*=\s*")[^"]*(")'
new_content = re.sub(pattern, lambda m: m.group(1) + new_key + m.group(2), content)

if new_content == content:
    print("  ⚠️ 未找到 NEW_PUBKEY 定义,请手动更新")
    exit(1)

with open("localize.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("  ✅ localize.py 已更新")
PYEOF
    
    if [ $? -ne 0 ]; then
        warn "自动更新失败,请手动将以下公钥添加到 localize.py 的 patch_tauri_pubkey 函数:"
        echo ""
        echo "  NEW_PUBKEY = \"$NEW_PUBKEY\""
        echo ""
        mv localize.py.bak localize.py
    else
        rm -f localize.py.bak
        success "localize.py 公钥已更新"
    fi
}

# ============================================================================
# 备份密钥
# ============================================================================

backup_keys() {
    info "备份密钥信息到 $BACKUP_DIR ..."
    
    mkdir -p "$BACKUP_DIR"
    
    cp /tmp/voltius-signing/voltius_zh.key "$BACKUP_DIR/"
    cp /tmp/voltius-signing/voltius_zh.key.pub "$BACKUP_DIR/"
    cp /tmp/voltius-signing/password.txt "$BACKUP_DIR/"
    
    # 生成说明文件
    cat > "$BACKUP_DIR/README.txt" <<EOF
Voltius 中文汉化版 Tauri 签名密钥备份
生成时间: $(date '+%Y-%m-%d %H:%M:%S')
GitHub 仓库: ${GITHUB_USER}/${GITHUB_REPO}

文件说明:
  voltius_zh.key       私钥(绝密,丢失将无法签名更新)
  voltius_zh.key.pub   公钥(可公开,用于验证更新包)
  password.txt         私钥密码

⚠️ 重要提醒:
1. 私钥和密码已配置到 GitHub Secrets:
   - TAURI_SIGNING_PRIVATE_KEY
   - TAURI_SIGNING_PRIVATE_KEY_PASSWORD

2. 请将本目录备份到密码管理器或离线加密存储

3. 如果丢失私钥或密码,已发布的应用将无法签名新的更新包,
   用户无法通过自动更新功能升级

GitHub Secrets 验证:
https://github.com/${GITHUB_USER}/${GITHUB_REPO}/settings/secrets/actions

公钥内容:
$(cat voltius_zh.key.pub)
EOF
    
    chmod 600 "$BACKUP_DIR"/*
    
    success "密钥已备份到: $BACKUP_DIR"
}

# ============================================================================
# 验证配置
# ============================================================================

verify_secrets() {
    info "验证 GitHub Secrets 是否配置成功..."
    
    local secrets=$(curl -s -H "Authorization: Bearer ${GITHUB_TOKEN}" \
                         -H "Accept: application/vnd.github+json" \
                         "https://api.github.com/repos/${GITHUB_USER}/${GITHUB_REPO}/actions/secrets" \
                    | jq -r '.secrets[].name')
    
    local found_key=0
    local found_pw=0
    
    while IFS= read -r secret; do
        [ "$secret" = "TAURI_SIGNING_PRIVATE_KEY" ] && found_key=1
        [ "$secret" = "TAURI_SIGNING_PRIVATE_KEY_PASSWORD" ] && found_pw=1
    done <<< "$secrets"
    
    if [ $found_key -eq 1 ] && [ $found_pw -eq 1 ]; then
        success "Secrets 验证通过"
        return 0
    else
        error "Secrets 验证失败"
        [ $found_key -eq 0 ] && echo "  缺失: TAURI_SIGNING_PRIVATE_KEY"
        [ $found_pw -eq 0 ] && echo "  缺失: TAURI_SIGNING_PRIVATE_KEY_PASSWORD"
        return 1
    fi
}

# ============================================================================
# 清理
# ============================================================================

cleanup() {
    info "清理临时文件..."
    # 保留 /tmp/voltius-signing 供用户检查,不自动删除
    success "临时文件位于: /tmp/voltius-signing (请手动删除)"
}

# ============================================================================
# 主流程
# ============================================================================

main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║   Voltius 中文汉化版 - Tauri 签名密钥自动配置脚本            ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    check_prerequisites
    check_github_token
    
    echo ""
    warn "即将生成新的 Tauri 签名密钥对并上传到 GitHub Secrets"
    echo ""
    echo "  仓库: ${GITHUB_USER}/${GITHUB_REPO}"
    echo "  Secrets:"
    echo "    - TAURI_SIGNING_PRIVATE_KEY"
    echo "    - TAURI_SIGNING_PRIVATE_KEY_PASSWORD"
    echo ""
    
    read -p "确认继续? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        warn "已取消"
        exit 0
    fi
    
    echo ""
    
    generate_keypair
    upload_github_secrets
    update_localize_py
    backup_keys
    verify_secrets
    cleanup
    
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                        🎉 配置完成                             ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    success "Tauri 签名密钥已生成并配置到 GitHub Secrets"
    echo ""
    echo "📂 密钥备份位置:"
    echo "   $BACKUP_DIR"
    echo ""
    echo "🔐 GitHub Secrets 已配置:"
    echo "   https://github.com/${GITHUB_USER}/${GITHUB_REPO}/settings/secrets/actions"
    echo ""
    echo "🚀 下一步:"
    echo "   1. 推送改动: git add localize.py && git commit -m 'chore: 更新 Tauri 签名公钥' && git push"
    echo "   2. 触发构建: git push 或手动触发 GitHub Actions"
    echo "   3. 验证签名: 构建产物应包含 .sig 文件"
    echo ""
    warn "⚠️ 请务必将 $BACKUP_DIR 备份到安全位置"
    echo ""
}

# 执行主流程
main "$@"
