#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量机器翻译脚本 - 带限流保护和断点续传

用法:
  python batch-translate.py                    # 翻译所有未译文本
  python batch-translate.py --file common.json # 仅翻译指定文件
  python batch-translate.py --dry-run          # 预览待翻译数量

特性:
  - 自动限流(避免 Google API 封禁)
  - 断点续传(中断后可继续)
  - 保留占位符 {{var}}
  - 优先使用术语表
"""
import argparse
import json
import logging
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
LOCALES_DIR = SCRIPT_DIR / "locales" / "zh-CN"
EN_DIR = SCRIPT_DIR / "voltius" / "src" / "i18n" / "locales" / "en"
GLOSSARY_FILE = SCRIPT_DIR / "translations" / "glossary.json"
CACHE_FILE = SCRIPT_DIR / "translations" / "machine.json"

log = logging.getLogger("batch-translate")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def flatten_dict(d, parent_key=""):
    """展平嵌套字典: {"a": {"b": "c"}} -> {"a.b": "c"}"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key).items())
        else:
            items.append((new_key, v))
    return dict(items)


def unflatten_dict(d):
    """展开扁平字典: {"a.b": "c"} -> {"a": {"b": "c"}}"""
    result = {}
    for key, value in d.items():
        parts = key.split(".")
        current = result
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    return result


def needs_translation(en_val, zh_val):
    """判断是否需要翻译: zh 为空 或 与英文相同"""
    if not isinstance(en_val, str):
        return False
    if not zh_val or not isinstance(zh_val, str):
        return True
    return zh_val == en_val


def translate_batch(texts, glossary, translator, delay=0.5):
    """批量翻译，带限流和术语表优先"""
    results = []
    for text in texts:
        # 术语表优先
        if text in glossary:
            results.append(glossary[text])
            continue

        # 机器翻译
        try:
            translated = translator(text)
            results.append(translated)
            time.sleep(delay)  # 限流
        except Exception as e:
            log.warning("翻译失败,保留原文: %s (%s)", text[:40], e)
            results.append(text)
            time.sleep(delay * 2)  # 失败后加倍延迟

    return results


def main():
    parser = argparse.ArgumentParser(description="Voltius 批量机器翻译")
    parser.add_argument("-f", "--file", help="仅处理指定文件(如 common.json)")
    parser.add_argument("-d", "--dry-run", action="store_true", help="预览待翻译数量")
    parser.add_argument("--delay", type=float, default=0.5, help="每次翻译间隔(秒)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    # 加载翻译器
    try:
        from deep_translator import GoogleTranslator
        import re
    except ImportError:
        log.error("❌ 需要安装: pip install deep-translator")
        return 1

    def translator(text):
        # 保护占位符 {{var}}: 用带空格的 token 包裹，避免翻译引擎将其与中文粘连
        placeholders = {}
        def replace_placeholder(m):
            key = f" @@PH{len(placeholders)}@@ "
            placeholders[key.strip()] = m.group(0)
            return key
        protected = re.sub(r"\{\{[^}]+\}\}", replace_placeholder, text)
        result = GoogleTranslator(source="en", target="zh-CN").translate(protected)
        # 先还原带空格 token，再清理占位符两侧多余空格
        for key, val in placeholders.items():
            result = result.replace(f" {key} ", val).replace(key, val)
        return result

    glossary = load_json(GLOSSARY_FILE) if GLOSSARY_FILE.exists() else {}
    cache = load_json(CACHE_FILE) if CACHE_FILE.exists() else {}

    # 确定要处理的文件
    if args.file:
        files = [EN_DIR / args.file]
        if not files[0].exists():
            log.error("❌ 文件不存在: %s", files[0])
            return 1
    else:
        files = sorted(EN_DIR.glob("*.json"))

    log.info("🚀 批量翻译模式 (限流: %.2fs/条)", args.delay)
    total_pending = 0

    for en_file in files:
        zh_file = LOCALES_DIR / en_file.name
        if not zh_file.exists():
            log.warning("⏭️ 跳过(无中文文件): %s", en_file.name)
            continue

        en_data = load_json(en_file)
        zh_data = load_json(zh_file)

        en_flat = flatten_dict(en_data)
        zh_flat = flatten_dict(zh_data)

        # 找出需要翻译的条目
        pending = []
        for key, en_val in en_flat.items():
            zh_val = zh_flat.get(key)
            if needs_translation(en_val, zh_val):
                pending.append((key, en_val))

        if not pending:
            log.info("  ✅ %s - 已完成", en_file.name)
            continue

        log.info("  📝 %s - %d 条待翻译", en_file.name, len(pending))
        total_pending += len(pending)

        if args.dry_run:
            continue

        # 批量翻译
        texts = [en_val for _, en_val in pending]
        translated = translate_batch(texts, glossary, translator, args.delay)

        # 更新中文数据
        for (key, _), new_val in zip(pending, translated):
            zh_flat[key] = new_val
            cache[_] = new_val  # 更新缓存

        zh_data_updated = unflatten_dict(zh_flat)
        save_json(zh_file, zh_data_updated)
        log.info("    ✅ 已保存")

    save_json(CACHE_FILE, cache)

    if args.dry_run:
        log.info("📌 预览: 共 %d 条待翻译", total_pending)
    else:
        log.info("✅ 完成! 共翻译 %d 条", total_pending)

    return 0


if __name__ == "__main__":
    exit(main())
