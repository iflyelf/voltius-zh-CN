#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全量翻译脚本 - 后台运行版，带重试/断点续传/进度记录"""
import json
import time
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
LOCALES_DIR = SCRIPT_DIR / "locales" / "zh-CN"
EN_DIR = SCRIPT_DIR / "voltius" / "src" / "i18n" / "locales" / "en"
GLOSSARY_FILE = SCRIPT_DIR / "translations" / "glossary.json"
CACHE_FILE = SCRIPT_DIR / "translations" / "machine.json"
PROGRESS_FILE = SCRIPT_DIR / "translations" / "progress.txt"

DELAY = 0.8
MAX_RETRIES = 4

glossary = json.load(open(GLOSSARY_FILE)) if GLOSSARY_FILE.exists() else {}
cache = json.load(open(CACHE_FILE)) if CACHE_FILE.exists() else {}

from deep_translator import GoogleTranslator


def log(msg):
    with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


def translate_with_retry(text, retries=MAX_RETRIES):
    if text in glossary:
        return glossary[text]
    if text in cache and cache[text]:
        return cache[text]

    placeholders = {}
    def replace_ph(m):
        key = f" @@PH{len(placeholders)}@@ "
        placeholders[key.strip()] = m.group(0)
        return key
    protected = re.sub(r"\{\{[^}]+\}\}", replace_ph, text)

    for attempt in range(retries):
        try:
            result = GoogleTranslator(source="en", target="zh-CN").translate(protected)
            if not result:
                result = text
            for key, val in placeholders.items():
                result = result.replace(f" {key} ", f" {val} ").replace(key, val)
            cache[text] = result
            time.sleep(DELAY)
            return result
        except Exception as e:
            if attempt < retries - 1:
                wait = DELAY * (attempt + 2) * 2
                time.sleep(wait)
            else:
                cache[text] = ""
                return text


def flatten(d, prefix=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    else:
        out[prefix] = d
    return out


def unflatten(d):
    result = {}
    for key, value in d.items():
        parts = key.split(".")
        current = result
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    return result


def main():
    total_translated = 0
    total_pending = 0

    # 先统计
    files = sorted(EN_DIR.glob("*.json"))
    for en_file in files:
        zh_file = LOCALES_DIR / en_file.name
        if not zh_file.exists():
            continue
        en_flat = flatten(json.load(open(en_file)))
        zh_flat = flatten(json.load(open(zh_file)))
        for key, en_val in en_flat.items():
            if isinstance(en_val, str):
                zv = zh_flat.get(key)
                if not zv or zv == en_val:
                    total_pending += 1

    log(f"=== 开始全量翻译，共 {total_pending} 条待翻译 ===")

    for i, en_file in enumerate(files, 1):
        zh_file = LOCALES_DIR / en_file.name
        if not zh_file.exists():
            continue

        en_flat = flatten(json.load(open(en_file)))
        zh_flat = flatten(json.load(open(zh_file)))

        pending = []
        for key, en_val in en_flat.items():
            if not isinstance(en_val, str):
                continue
            zv = zh_flat.get(key)
            if not zv or zv == en_val:
                pending.append((key, en_val))

        if not pending:
            log(f"[{i:2d}/{len(files)}] OK {en_file.name} - 已完成")
            continue

        log(f"[{i:2d}/{len(files)}] {en_file.name} - {len(pending)} 条")

        for idx, (key, text) in enumerate(pending, 1):
            zh_flat[key] = translate_with_retry(text)
            total_translated += 1
            if total_translated % 25 == 0:
                json.dump(cache, open(CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                # 中途保存当前文件
                json.dump(unflatten(zh_flat), open(zh_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                log(f"    进度 {total_translated}/{total_pending} ({total_translated/total_pending*100:.1f}%)")

        json.dump(unflatten(zh_flat), open(zh_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        with open(zh_file, "a") as f:
            f.write("\n")
        log(f"    saved {en_file.name}")

    json.dump(cache, open(CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log(f"=== 完成! 共翻译 {total_translated} 条 ===")


if __name__ == "__main__":
    main()
