#!/bin/bash
# 监控翻译进度

cd /xiaonuo/AI/tools/voltius

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║            Voltius 批量翻译进度监控                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# 检查进程
if ps aux | grep "_full_translate.py" | grep -v grep > /dev/null; then
    echo "✅ 翻译进程运行中"
else
    echo "❌ 翻译进程未运行"
fi

echo ""
echo "=== 📊 实时进度 ==="
if [ -f translations/progress.txt ]; then
    tail -15 translations/progress.txt
else
    echo "暂无进度记录"
fi

echo ""
echo "=== 📈 翻译统计 ==="
python3 << 'EOF'
import json
from pathlib import Path

en_dir = Path("voltius/src/i18n/locales/en")
zh_dir = Path("locales/zh-CN")

total = 0
done = 0

for en_file in sorted(en_dir.glob("*.json")):
    zh_file = zh_dir / en_file.name
    if not zh_file.exists():
        continue
    
    def flatten(d, p=""):
        out = {}
        if isinstance(d, dict):
            for k, v in d.items():
                out.update(flatten(v, f"{p}.{k}" if p else k))
        else:
            out[p] = d
        return out
    
    en_flat = flatten(json.load(open(en_file)))
    zh_flat = flatten(json.load(open(zh_file)))
    
    for k, v in en_flat.items():
        if isinstance(v, str):
            total += 1
            zv = zh_flat.get(k)
            if zv and zv != v:
                done += 1

progress = done / total * 100 if total else 0
bar = "█" * int(progress / 2) + "░" * (50 - int(progress / 2))

print(f"{bar}")
print(f"进度: {done}/{total} ({progress:.1f}%)")
print(f"剩余: {total - done} 条")
EOF

echo ""
echo "=== 🔄 刷新 ==="
echo "运行此脚本查看最新进度: bash _monitor.sh"
echo "查看完整日志: tail -f translations/progress.txt"
echo "结束翻译进程: pkill -f _full_translate.py"
