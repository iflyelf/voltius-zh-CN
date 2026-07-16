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

    # 默认语言改为简体中文
    new_src, n3 = re.subn(
        r'locale: "en",',
        'locale: "zh-CN",',
        new_src,
    )
    if n3 == 0:
        log.warning("  ⚠️ 未找到默认 locale 定义，默认语言未修改")
    else:
        log.info("  ✅ 默认语言设为简体中文")

    path.write_text(new_src, encoding="utf-8")
    log.info("  ✅ 已修改 src/stores/localeStore.ts")


def patch_tauri_pubkey(repo):
    """替换 tauri.conf.json 中的 updater pubkey 为汉化版签名公钥。"""
    conf_path = Path(repo) / "src-tauri" / "tauri.conf.json"
    if not conf_path.exists():
        log.warning("  ⚠️ 未找到 tauri.conf.json，跳过 pubkey 替换")
        return
    
    # 汉化版签名公钥 (对应 GitHub Secrets 中的私钥)
    NEW_PUBKEY = "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IDIwNTlGMzdDRDc0QkE5OTAKUldTUXFVdlhmUE5aSUlIbk82T3RYQnVoQm5ITUw2cU8xQVkvZlFUaEFTbUt6NzFwaHNxbTBrclYK"
    
    conf = read_json(conf_path)
    if "plugins" in conf and "updater" in conf["plugins"]:
        old_key = conf["plugins"]["updater"].get("pubkey", "")
        if old_key == NEW_PUBKEY:
            log.info("  ⏭️ pubkey 已是汉化版密钥，跳过")
            return
        conf["plugins"]["updater"]["pubkey"] = NEW_PUBKEY
        write_json(conf_path, conf)
        log.info("  ✅ 已替换 tauri.conf.json 中的 updater pubkey")
    else:
        log.info("  ⏭️ tauri.conf.json 无 updater 配置，跳过")


def patch_unlock_vaults(repo):
    """解除免费版单一保管库限制,允许创建无限制保管库。"""
    path = Path(repo) / "src" / "components" / "layout" / "VaultSidebar.tsx"
    if not path.exists():
        log.warning("  ⚠️ 未找到 VaultSidebar.tsx，跳过保管库解锁")
        return

    src = path.read_text(encoding="utf-8")

    # 已解锁则跳过
    if "解除免费版单一保管库限制" in src:
        log.info("  ⏭️ 保管库限制已解除，跳过")
        return

    # 1. 移除限制检查: if (!isPro && vaults.length >= 1) { ... return; }
    pattern = re.compile(
        r'if \(!isPro && vaults\.length >= 1\) \{\s*'
        r'setShowVaultLimitModal\(true\);\s*'
        r'return;\s*'
        r'\}',
        re.MULTILINE,
    )
    new_src, n = pattern.subn(
        "// 汉化版: 解除免费版单一保管库限制,允许创建无限制保管库", src
    )

    if n == 0:
        log.warning("  ⚠️ 未匹配到保管库限制代码(上游可能已变更),跳过")
        return

    # 2. 移除未使用的 isPro 变量声明
    new_src = re.sub(
        r'^\s*const isPro = useSubscriptionStore\(\(s\) => s\.isPro\);\s*$',
        '',
        new_src,
        flags=re.MULTILINE
    )

    path.write_text(new_src, encoding="utf-8")
    log.info("  ✅ 已解除保管库数量限制 (可创建无限制保管库)")


def patch_force_pro(repo):
    """强制客户端订阅状态为 Pro (配合自建服务器使用)。"""
    path = Path(repo) / "src" / "stores" / "subscriptionStore.ts"
    if not path.exists():
        log.warning("  ⚠️ 未找到 subscriptionStore.ts，跳过 Pro 解锁")
        return

    src = path.read_text(encoding="utf-8")

    if "汉化版: 强制 Pro 订阅" in src:
        log.info("  ⏭️ Pro 状态已解锁，跳过")
        return

    # 将 tier 派生改为强制 "pro",这样 isPro/isTeams/isBusiness 全部为真
    pattern = re.compile(
        r'const tier = \(payload\.tier as Tier\) \?\? "free";'
    )
    new_src, n = pattern.subn(
        'const tier = "pro" as Tier; // 汉化版: 强制 Pro 订阅 (配合自建服务器)',
        src,
    )

    if n == 0:
        log.warning("  ⚠️ 未匹配到 tier 派生代码(上游可能已变更),跳过")
        return

    path.write_text(new_src, encoding="utf-8")
    log.info("  ✅ 已强制客户端订阅状态为 Pro")


def patch_plugins_i18n(repo):
    """汉化 plugins 目录 (docker/proxmox/monitoring/process-manager/gist-sync)。

    这些插件未接入 i18next,全是硬编码英文,通过精确字符串替换汉化。
    """
    try:
        from plugin_translations import PLUGIN_TRANSLATIONS
        from gist_translations import GIST_SYNC_TRANSLATIONS
        from plugin_meta_translations import PLUGIN_META_TRANSLATIONS
    except ImportError as e:
        log.warning("  ⚠️ 无法导入插件翻译表: %s，跳过插件汉化", e)
        return

    # 深度合并: 同一文件的映射合并而非覆盖
    all_translations = {}
    for table in (PLUGIN_TRANSLATIONS, GIST_SYNC_TRANSLATIONS, PLUGIN_META_TRANSLATIONS):
        for rel_path, mapping in table.items():
            all_translations.setdefault(rel_path, {}).update(mapping)

    total_replaced = 0
    total_missed = 0
    for rel_path, mapping in all_translations.items():
        fpath = Path(repo) / rel_path
        if not fpath.exists():
            log.warning("  ⚠️ 插件文件不存在: %s", rel_path)
            continue

        src = fpath.read_text(encoding="utf-8")
        replaced = 0
        for orig, zh in mapping.items():
            if orig in src:
                src = src.replace(orig, zh)
                replaced += 1
            else:
                total_missed += 1
        fpath.write_text(src, encoding="utf-8")
        total_replaced += replaced

    log.info("  ✅ 插件汉化: 替换 %d 条 (未匹配 %d 条)", total_replaced, total_missed)


def patch_add_flexoki_theme(repo):
    """将 Flexoki Light/Dark 主题注入到内置主题列表开头。"""
    try:
        from flexoki_theme import FLEXOKI_LIGHT_THEME, FLEXOKI_DARK_THEME
    except ImportError as e:
        log.warning("  ⚠️ 无法导入 Flexoki 主题定义: %s，跳过", e)
        return

    path = Path(repo) / "src" / "themes" / "presets.ts"
    if not path.exists():
        log.warning("  ⚠️ 未找到 presets.ts，跳过 Flexoki 注入")
        return

    src = path.read_text(encoding="utf-8")
    
    # 检查是否已注入
    if '"flexoki-light"' in src:
        log.info("  ⏭️ Flexoki 主题已存在，跳过")
        return

    # 在 BUILT_IN_THEMES: AppTheme[] = [ 后面注入
    pattern = re.compile(r'(export const BUILT_IN_THEMES: AppTheme\[\] = \[\s*)')
    replacement = r'\1' + FLEXOKI_LIGHT_THEME + FLEXOKI_DARK_THEME
    new_src, n = pattern.subn(replacement, src)
    
    if n == 0:
        log.warning("  ⚠️ 未找到 BUILT_IN_THEMES 数组，跳过")
        return
    
    path.write_text(new_src, encoding="utf-8")
    log.info("  ✅ Flexoki Light/Dark 主题已注入")


def patch_default_theme(repo, theme_id="flexoki-light"):
    """将默认主题设置为指定主题 (默认 flexoki-light)。"""
    path = Path(repo) / "src" / "themes" / "presets.ts"
    if not path.exists():
        log.warning("  ⚠️ 未找到 presets.ts，跳过默认主题设置")
        return

    src = path.read_text(encoding="utf-8")

    pattern = re.compile(r'export const DEFAULT_THEME_ID = "[^"]*";')
    new_src, n = pattern.subn(
        f'export const DEFAULT_THEME_ID = "{theme_id}";', src
    )
    if n == 0:
        log.warning("  ⚠️ 未匹配到 DEFAULT_THEME_ID，跳过")
        return
    path.write_text(new_src, encoding="utf-8")
    log.info("  ✅ 默认主题设为: %s", theme_id)


def patch_builtin_themes_font(repo, default_size=16):
    """将所有内置主题的字体大小改为指定值 (默认 16)，并允许编辑。"""
    # 1. 修改 presets.ts 字体大小
    path = Path(repo) / "src" / "themes" / "presets.ts"
    if not path.exists():
        log.warning("  ⚠️ 未找到 presets.ts，跳过字体修改")
        return

    src = path.read_text(encoding="utf-8")
    # 替换所有 uiFontSize 和 terminalFontSize
    src = re.sub(r'uiFontSize: \d+', f'uiFontSize: {default_size}', src)
    src = re.sub(r'terminalFontSize: \d+', f'terminalFontSize: {default_size}', src)
    path.write_text(src, encoding="utf-8")
    log.info("  ✅ 内置主题字体大小改为: %d", default_size)

    # 2. 允许编辑内置主题（在 185 行条件后增加内置主题的编辑按钮）
    appearance_path = Path(repo) / "src" / "components" / "settings" / "sections" / "AppearanceSection.tsx"
    if not appearance_path.exists():
        log.warning("  ⚠️ 未找到 AppearanceSection.tsx，跳过编辑权限修改")
        return

    src = appearance_path.read_text(encoding="utf-8")
    # 在 185-213 行的 {!theme.builtIn && (...)} 后面添加一个内置主题专用的编辑按钮块
    pattern = re.compile(
        r'(\{!theme\.builtIn && \(\s*<div className="absolute bottom-2 right-2 flex gap-1">.*?</div>\s*\)\})',
        re.DOTALL
    )
    replacement = r'''\1
                {theme.builtIn && (
                  <div className="absolute bottom-2 right-2 flex gap-1">
                    <button
                      onClick={(e) => { e.stopPropagation(); openThemeCreator(theme.id); }}
                      className="p-1 rounded-sm opacity-0 group-hover:opacity-50 hover:opacity-100! transition-opacity text-(--t-text-muted)"
                      title={t("settings.appearance.editTheme")}
                      onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "var(--t-text-primary)"; }}
                      onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "var(--t-text-muted)"; }}
                    >
                      <Icon icon="lucide:pencil" width={11} />
                    </button>
                  </div>
                )}'''
    new_src, n = pattern.subn(replacement, src)
    if n > 0:
        appearance_path.write_text(new_src, encoding="utf-8")
        log.info("  ✅ 内置主题现在可编辑")
    else:
        log.warning("  ⚠️ 未找到编辑按钮逻辑，跳过")

    # 3. 编辑内置主题时创建副本（避免 builtIn 冲突）
    creator_path = Path(repo) / "src" / "components" / "theme-creator" / "ThemeCreator.tsx"
    if not creator_path.exists():
        log.warning("  ⚠️ 未找到 ThemeCreator.tsx，跳过副本逻辑")
        return

    src = creator_path.read_text(encoding="utf-8")
    # 找到 524-531 行的逻辑：加载 existing 主题
    # 如果是内置主题(builtIn:true)，生成新 id 并设 builtIn:false
    pattern = re.compile(
        r'(if \(existing\) \{\s*const d = JSON\.parse\(JSON\.stringify\(existing\)\);)',
        re.DOTALL
    )
    replacement = r'''\1
        // 汉化版: 编辑内置主题时创建副本
        if (existing.builtIn) {
          d.id = `custom-${Date.now()}`;
          d.name = `${existing.name} (副本)`;
          d.builtIn = false;
        }'''
    new_src, n = pattern.subn(replacement, src)
    if n > 0:
        creator_path.write_text(new_src, encoding="utf-8")
        log.info("  ✅ 编辑内置主题时自动创建副本")
    else:
        log.warning("  ⚠️ 未找到主题加载逻辑，跳过")


def patch_default_settings(repo):
    """修改默认设置：关闭滚动小地图。"""
    path = Path(repo) / "src" / "stores" / "toggleSettingsStore.ts"
    if not path.exists():
        log.warning("  ⚠️ 未找到 toggleSettingsStore.ts，跳过")
        return

    src = path.read_text(encoding="utf-8")

    # 关闭滚动小地图默认值
    pattern = re.compile(
        r'("scroll-minimap": \{[^}]*default: )true',
        re.DOTALL
    )
    new_src, n = pattern.subn(r'\1false', src)
    
    if n == 0:
        log.warning("  ⚠️ 未找到 scroll-minimap 默认值，跳过")
        return
    
    path.write_text(new_src, encoding="utf-8")
    log.info("  ✅ 滚动小地图默认关闭")


def do_patch(repo):
    log.info("🛠️ 应用源码补丁到 %s", repo)
    copy_locales_to_repo(repo)
    patch_i18n_index(repo)
    patch_locale_store(repo)
    patch_tauri_pubkey(repo)
    patch_unlock_vaults(repo)
    patch_force_pro(repo)
    patch_plugins_i18n(repo)
    patch_add_flexoki_theme(repo)  # 先注入 Flexoki 主题
    patch_default_theme(repo)      # 再设默认为 flexoki-light
    patch_builtin_themes_font(repo)  # 最后统一改字体（包括新注入的）
    patch_default_settings(repo)   # 默认设置：关闭滚动小地图
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
