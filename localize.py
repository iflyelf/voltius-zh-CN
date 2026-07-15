# -*- coding: utf-8 -*-
"""
Voltius 中文汉化工具

Voltius (https://github.com/VoltiusApp/voltius) 是基于 Rust/Tauri 的 SSH 客户端。
它使用标准 i18next 国际化框架，所有文案抽取在 src/i18n/locales/en/*.json。

本脚本通过「源码级汉化」实现中文支持:
  1. 生成 src/i18n/locales/zh-CN/*.json 中文语料
  2. patch src/i18n/index.ts        注册 zh-CN 资源
  3. patch src/stores/localeStore.ts 添加中文语言选项
之后重新 `pnpm tauri build` 即可产出全平台(Win/macOS/Linux/Android)汉化版。

与 Termius 汉化(修改 asar 二进制)不同，Voltius 是源码构建路线，更干净可维护。
"""
import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ----------------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
UPSTREAM_URL = "https://github.com/VoltiusApp/voltius.git"
DEFAULT_REPO = SCRIPT_DIR / "voltius"          # 克隆的上游仓库
LOCALES_DIR = SCRIPT_DIR / "locales" / "zh-CN"  # 本项目维护的中文语料
GLOSSARY_FILE = SCRIPT_DIR / "translations" / "glossary.json"
CACHE_FILE = SCRIPT_DIR / "translations" / "machine.json"

TARGET_LOCALE = "zh-CN"
TARGET_LABEL = "简体中文"

log = logging.getLogger("voltius-l10n")


# ----------------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------------
def run(cmd, cwd=None, check=True):
    """执行系统命令"""
    log.debug("运行: %s (cwd=%s)", " ".join(cmd), cwd)
    return subprocess.run(cmd, cwd=cwd, check=check)


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def en_locales_dir(repo):
    return Path(repo) / "src" / "i18n" / "locales" / "en"


def zh_locales_dir(repo):
    return Path(repo) / "src" / "i18n" / "locales" / TARGET_LOCALE


# ----------------------------------------------------------------------------
# 步骤 1: 克隆上游
# ----------------------------------------------------------------------------
def ensure_repo(repo):
    repo = Path(repo)
    if (repo / ".git").exists():
        log.info("🔍 仓库已存在: %s", repo)
        return repo
    log.info("🚀 克隆 Voltius 上游仓库到 %s", repo)
    run(["git", "clone", "--depth", "1", UPSTREAM_URL, str(repo)])
    return repo


# ----------------------------------------------------------------------------
# 步骤 2: 翻译 - 生成中文语料
# ----------------------------------------------------------------------------
def load_glossary():
    """加载术语表(用于机器翻译后的强制替换，保证术语一致)"""
    if GLOSSARY_FILE.exists():
        return read_json(GLOSSARY_FILE)
    return {}


def translate_text(text, glossary, cache, translator=None):
    """翻译单条字符串。

    默认不做真正的机器翻译(避免强依赖网络/API)，而是:
      - 保留占位符 {{var}} 与格式
      - 命中术语表则直接用术语
      - 否则原样保留英文并加入待翻译缓存，供人工处理

    若提供 translator(可调用对象)，则用它做机翻。
    """
    if not isinstance(text, str) or not text.strip():
        return text

    # 术语表精确命中
    if text in glossary:
        return glossary[text]

    # 缓存命中(已人工/机翻过)
    if text in cache and cache[text]:
        return cache[text]

    if translator:
        try:
            translated = translator(text)
            cache[text] = translated
            return translated
        except Exception as e:  # noqa
            log.warning("⚠️ 翻译失败,保留原文: %s (%s)", text[:40], e)

    # 无翻译能力: 记录待翻译，保留原文
    cache.setdefault(text, "")
    return text


def translate_obj(obj, glossary, cache, translator=None):
    """递归翻译 JSON 对象。保留 key，仅翻译 string value。"""
    if isinstance(obj, dict):
        return {k: translate_obj(v, glossary, cache, translator) for k, v in obj.items()}
    if isinstance(obj, list):
        return [translate_obj(v, glossary, cache, translator) for v in obj]
    if isinstance(obj, str):
        return translate_text(obj, glossary, cache, translator)
    return obj


def get_translator(engine):
    """按需返回一个 translator 可调用对象。engine 为空则返回 None。"""
    if not engine:
        return None
    if engine == "google":
        try:
            from deep_translator import GoogleTranslator
        except ImportError:
            log.error("❌ 需要 deep-translator: pip install deep-translator")
            sys.exit(1)

        def _tr(text):
            # 保护 {{var}} 占位符
            placeholders = {}
            def _sub(m):
                key = f"@@{len(placeholders)}@@"
                placeholders[key] = m.group(0)
                return key
            protected = re.sub(r"\{\{[^}]+\}\}", _sub, text)
            result = GoogleTranslator(source="en", target="zh-CN").translate(protected)
            result = result or text
            for key, val in placeholders.items():
                result = result.replace(key, val)
            return result

        return _tr
    log.error("❌ 未知翻译引擎: %s", engine)
    sys.exit(1)


def do_translate(repo, engine=None):
    """基于上游 en 语料生成/更新 zh-CN 语料，写入本项目 locales/zh-CN。"""
    en_dir = en_locales_dir(repo)
    if not en_dir.exists():
        log.error("❌ 找不到英文语料目录: %s (请先克隆仓库)", en_dir)
        sys.exit(1)

    glossary = load_glossary()
    cache = read_json(CACHE_FILE) if CACHE_FILE.exists() else {}
    translator = get_translator(engine)

    en_files = sorted(en_dir.glob("*.json"))
    log.info("🛠️ 开始翻译 %d 个语料文件 (引擎: %s)", len(en_files), engine or "无/仅术语表")

    for en_file in en_files:
        en_data = read_json(en_file)
        out_file = LOCALES_DIR / en_file.name

        # 若已有人工维护的中文，合并: 保留已翻译，补充新增 key
        existing = read_json(out_file) if out_file.exists() else {}
        translated = translate_obj(en_data, glossary, cache, translator)
        merged = deep_merge(translated, existing)  # existing 优先(人工优先)

        write_json(out_file, merged)
        log.info("  ✅ %s", en_file.name)

    write_json(CACHE_FILE, cache)
    pending = sum(1 for v in cache.values() if not v)
    log.info("📝 完成。语料输出: %s", LOCALES_DIR)
    if pending and not translator:
        log.warning("⚠️ 有 %d 条待翻译(未启用机翻引擎)，请人工编辑或使用 --engine google", pending)


def deep_merge(base, override):
    """深合并: override 中已有的非空值覆盖 base(用于保留人工翻译)。"""
    if isinstance(base, dict) and isinstance(override, dict):
        out = dict(base)
        for k, v in override.items():
            if k in out:
                out[k] = deep_merge(out[k], v)
            else:
                out[k] = v
        return out
    # override 为非空字符串则优先
    if isinstance(override, str) and override.strip():
        return override
    return base


# ----------------------------------------------------------------------------
# 步骤 3: 应用源码补丁
# ----------------------------------------------------------------------------
def copy_locales_to_repo(repo):
    """把本项目维护的 zh-CN 语料复制进仓库源码树。"""
    if not LOCALES_DIR.exists():
        log.error("❌ 中文语料不存在: %s (请先运行 --translate)", LOCALES_DIR)
        sys.exit(1)
    dst = zh_locales_dir(repo)
    dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in LOCALES_DIR.glob("*.json"):
        shutil.copy2(f, dst / f.name)
        count += 1
    log.info("📂 已复制 %d 个中文语料到 %s", count, dst)


def patch_i18n_index(repo):
    """修改 src/i18n/index.ts: 注册 zh-CN 资源。"""
    path = Path(repo) / "src" / "i18n" / "index.ts"
    src = path.read_text(encoding="utf-8")

    if 'locales/zh-CN' in src:
        log.info("  ⏭️ index.ts 已包含 zh-CN，跳过")
        return

    # 在 fr 的 assemble(...) 之后插入 zh 的 assemble
    fr_block_re = re.compile(
        r'(const fr = assemble\(\s*import\.meta\.glob\("\./locales/fr/\*\.json",'
        r' \{ eager: true \}\) as Record<\s*string,\s*\{ default: Record<string, unknown> \}\s*>,\s*\);)',
    )
    zh_block = (
        '\n\nconst zhCN = assemble(\n'
        '  import.meta.glob("./locales/zh-CN/*.json", { eager: true }) as Record<\n'
        '    string,\n'
        '    { default: Record<string, unknown> }\n'
        '  >,\n'
        ');'
    )
    new_src, n = fr_block_re.subn(r'\1' + zh_block, src)
    if n == 0:
        log.error("❌ 无法定位 index.ts 中的 fr assemble 块，上游结构可能已变更")
        sys.exit(1)

    # 在 resources 中加入 zhCN
    new_src, n2 = re.subn(
        r'(resources: \{ en: \{ translation: en \}, fr: \{ translation: fr \})( \},)',
        r'\1, "zh-CN": { translation: zhCN }\2',
        new_src,
    )
    if n2 == 0:
        log.error("❌ 无法定位 index.ts 中的 resources 声明")
        sys.exit(1)

    path.write_text(new_src, encoding="utf-8")
    log.info("  ✅ 已修改 src/i18n/index.ts")


def patch_locale_store(repo):
    """修改 src/stores/localeStore.ts: 扩展 Locale 类型 + 语言选项。"""
    path = Path(repo) / "src" / "stores" / "localeStore.ts"
    src = path.read_text(encoding="utf-8")

    if '"zh-CN"' in src:
        log.info("  ⏭️ localeStore.ts 已包含 zh-CN，跳过")
        return

    # 扩展 Locale 类型
    new_src, n1 = re.subn(
        r'export type Locale = "en" \| "fr";',
        'export type Locale = "en" | "fr" | "zh-CN";',
        src,
    )
    # 添加到 SUPPORTED_LOCALES
    new_src, n2 = re.subn(
        r'(\{ value: "fr", label: "Français" \},)',
        r'\1\n  { value: "zh-CN", label: "' + TARGET_LABEL + '" },',
        new_src,
    )
    if n1 == 0 or n2 == 0:
        log.error("❌ 无法定位 localeStore.ts 中的 Locale 类型或 SUPPORTED_LOCALES")
        sys.exit(1)

    path.write_text(new_src, encoding="utf-8")
    log.info("  ✅ 已修改 src/stores/localeStore.ts")


def do_patch(repo):
    log.info("🛠️ 应用源码补丁到 %s", repo)
    copy_locales_to_repo(repo)
    patch_i18n_index(repo)
    patch_locale_store(repo)
    log.info("✅ 补丁应用完成")


# ----------------------------------------------------------------------------
# 步骤 4: 构建
# ----------------------------------------------------------------------------
def do_build(repo):
    log.info("🚀 开始构建(pnpm install + tauri build)")
    if shutil.which("pnpm") is None:
        log.error("❌ 未找到 pnpm，请先安装: npm i -g pnpm")
        sys.exit(1)
    run(["pnpm", "install"], cwd=repo)
    run(["pnpm", "tauri", "build"], cwd=repo)
    log.info("✅ 构建完成，产物位于 %s/target/release/bundle/", repo)


# ----------------------------------------------------------------------------
# 检查翻译完整性
# ----------------------------------------------------------------------------
def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out


def do_check(repo):
    en_dir = en_locales_dir(repo)
    if not en_dir.exists():
        log.error("❌ 找不到英文语料: %s", en_dir)
        sys.exit(1)
    log.info("🔍 检查翻译完整性")
    total_missing = 0
    for en_file in sorted(en_dir.glob("*.json")):
        zh_file = LOCALES_DIR / en_file.name
        en_flat = flatten(read_json(en_file))
        zh_flat = flatten(read_json(zh_file)) if zh_file.exists() else {}
        translated = 0
        for k, v in en_flat.items():
            zv = zh_flat.get(k)
            # 认为已翻译: 存在且(非字符串 或 与英文不同)
            if zv is not None and (not isinstance(v, str) or zv != v):
                translated += 1
        missing = len(en_flat) - translated
        total_missing += missing
        mark = "✅" if missing == 0 else "❌"
        log.info("  %s %-22s %d/%d (缺 %d)", mark, en_file.name, translated, len(en_flat), missing)
    log.info("📌 合计缺失/未译: %d 条", total_missing)


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Voltius 中文汉化工具(源码级 i18n)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-a", "--all", action="store_true", help="完整流程: 克隆+翻译+补丁")
    parser.add_argument("-t", "--translate", action="store_true", help="生成中文语料")
    parser.add_argument("-p", "--patch", action="store_true", help="应用源码补丁")
    parser.add_argument("-b", "--build", action="store_true", help="构建(需配合 --patch/--all)")
    parser.add_argument("-c", "--check", action="store_true", help="检查翻译完整性")
    parser.add_argument("-r", "--repo", default=str(DEFAULT_REPO), help="Voltius 仓库路径")
    parser.add_argument("-e", "--engine", default=None, choices=["google"],
                        help="机器翻译引擎(可选，需 pip install deep-translator)")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    if not any([args.all, args.translate, args.patch, args.check]):
        parser.print_help()
        return

    repo = Path(args.repo)

    if args.all:
        repo = ensure_repo(repo)
        do_translate(repo, args.engine)
        do_patch(repo)
        if args.build:
            do_build(repo)
        return

    if args.translate:
        repo = ensure_repo(repo)
        do_translate(repo, args.engine)

    if args.check:
        do_check(repo)

    if args.patch:
        if not (repo / ".git").exists():
            repo = ensure_repo(repo)
        do_patch(repo)
        if args.build:
            do_build(repo)


if __name__ == "__main__":
    main()
