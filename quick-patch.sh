#!/bin/bash
# Voltius 中文汉化 - 快速汉化脚本
# 用法: ./quick-patch.sh [仓库路径]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="${1:-$SCRIPT_DIR/voltius}"

echo "🚀 Voltius 中文汉化快速脚本"
echo "目标仓库: $REPO"
echo ""

# 1. 检查/克隆仓库
if [ ! -d "$REPO/.git" ]; then
    echo "📦 克隆 Voltius 仓库..."
    git clone --depth 1 https://github.com/VoltiusApp/voltius.git "$REPO"
fi

# 2. 生成中文语料(仅术语表,不用机翻)
echo "🛠️  生成中文语料..."
python3 "$SCRIPT_DIR/localize.py" --repo "$REPO" --translate

# 3. 应用源码补丁
echo "🔧 应用源码补丁..."
python3 "$SCRIPT_DIR/localize.py" --repo "$REPO" --patch

echo ""
echo "✅ 汉化完成！"
echo ""
echo "📌 后续步骤:"
echo "   1. 手动翻译: 编辑 locales/zh-CN/*.json 文件"
echo "   2. 重新应用: python3 localize.py --patch"
echo "   3. 本地测试: cd $REPO && pnpm install && pnpm tauri dev"
echo "   4. 构建发布: cd $REPO && pnpm tauri build"
echo ""
echo "💡 提示: 使用 python3 localize.py --check 检查翻译完整性"
