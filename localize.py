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
    
    # 强制迁移旧用户的 locale 存储到 zh-CN（防止 persist 覆盖默认值）
    # 在 persist() 的配置里加 version 和 migrate
    new_src, n4 = re.subn(
        r'\{ name: "voltius-locale" \}',
        '''{ name: "voltius-locale", version: 1, migrate: (persistedState: any, version: number) => {
        if (version === 0 || !persistedState?.locale || persistedState.locale === "en") {
          return { ...persistedState, locale: "zh-CN" as Locale };
        }
        return persistedState;
      } }''',
        new_src,
    )
    if n4 == 0:
        log.warning("  ⚠️ 未找到 persist 配置，旧用户迁移未添加")
    else:
        log.info("  ✅ 添加旧用户 locale 强制迁移到 zh-CN")

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


def patch_csv_format(repo):
    """CSV 导入导出格式增强: 支持 Groups/Label/Password 列。

    新格式: Groups,Label,Tags,Hostname/IP,Protocol,Port,Username,Password
    - Groups: 分组(如 me/Papa), 存为特殊 tag __group:xxx__
    - Label: 主机名称
    - Password: 明文密码(导入导出都支持)
    - Tags: 普通标签(分号分隔)
    
    向后兼容旧格式(name/host/port/username)。
    """
    csv_path = Path(repo) / "src" / "services" / "import-export" / "parsers" / "csv.ts"
    csv_src = Path(__file__).parent / "patches" / "csv.ts"
    
    if not csv_src.exists():
        log.warning("  ⚠️ 未找到 patches/csv.ts 源文件，跳过 CSV 格式增强")
        return
    
    if not csv_path.exists():
        log.warning("  ⚠️ 未找到目标 csv.ts，跳过 CSV 格式增强")
        return
    
    # 检查是否已经是新格式(避免重复覆盖)
    current = csv_path.read_text(encoding="utf-8")
    if "CSV_HEADERS_NEW" in current and "Groups,Label" in current:
        log.info("  ⏭️ CSV 格式已增强，跳过")
        return
    
    # 直接复制完整文件
    shutil.copy2(csv_src, csv_path)
    log.info("  ✅ CSV 格式增强(支持 Groups/Label/Password)")


def patch_csv_groups_to_folders(repo):
    """CSV Groups 自动映射为文件夹: importers.ts 智能 bundle 生成。

    从 __group:xxx__ 特殊 tag 提取分组, 生成 FolderExport,
    连接的 _folder_eid 指向对应文件夹, 导入时自动创建文件夹并关联。
    """
    importers_path = Path(repo) / "src" / "services" / "import-export" / "importers.ts"
    importers_src = Path(__file__).parent / "patches" / "importers.ts"
    
    if not importers_src.exists():
        log.warning("  ⚠️ 未找到 patches/importers.ts，跳过 Groups 文件夹映射")
        return
    
    if not importers_path.exists():
        log.warning("  ⚠️ 未找到目标 importers.ts，跳过")
        return
    
    current = importers_path.read_text(encoding="utf-8")
    if "汉化版: 从 __group:xxx__ 特殊 tag 提取分组" in current:
        log.info("  ⏭️ Groups 文件夹映射已启用，跳过")
        return
    
    # 直接复制完整文件
    shutil.copy2(importers_src, importers_path)
    log.info("  ✅ CSV Groups 自动映射为文件夹")


def patch_hosts_display(repo):
    """修复主机列表显示: 库根节点显示所有主机(含文件夹内的)。

    上游逻辑: 库根节点只显示未分类主机, 在文件夹里的被隐藏。
    导致"侧边栏有数字, 主区域空白"(主机都在文件夹里时)。
    修复: 库根节点显示全部主机, 更直观。
    """
    path = Path(repo) / "src" / "components" / "hosts" / "HostsPage.tsx"
    if not path.exists():
        log.warning("  ⚠️ 未找到 HostsPage.tsx，跳过主机显示修复")
        return

    src = path.read_text(encoding="utf-8")

    if "库根节点(无 activeFolderId)" in src:
        log.info("  ⏭️ 主机显示已修复，跳过")
        return

    # 把顶层过滤的"只显示未分类"改为"显示全部"
    pattern = re.compile(
        r'if \(activeFolderId\) return c\.folder_id === activeFolderId;\s*'
        r'// Top level:.*?\n\s*'
        r'return scopedFolders\.length === 0 \|\| !c\.folder_id \|\| !scopedFolderIds\.has\(c\.folder_id\);'
    )
    replacement = (
        'if (activeFolderId) return c.folder_id === activeFolderId;\n'
        '        // 库根节点(无 activeFolderId): 显示所有主机(包括文件夹里的),更直观\n'
        '        return true;'
    )
    new_src, n = pattern.subn(replacement, src)

    if n == 0:
        log.warning("  ⚠️ 未匹配到主机过滤逻辑，跳过")
        return

    path.write_text(new_src, encoding="utf-8")
    log.info("  ✅ 主机列表显示修复(库根节点显示所有主机)")


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


def patch_terminal_bold(repo):
    """终端粗体文字更明亮圆润: JetBrains Mono 字体 + 亮色粗体 + 加重字重 + 高对比度。"""
    # 1. 复制 JetBrains Mono 字体文件到 public/fonts/
    fonts_src_dir = Path(__file__).parent / "fonts"
    fonts_dst_dir = Path(repo) / "public" / "fonts"
    if fonts_src_dir.exists():
        for font_file in fonts_src_dir.glob("jetbrains-mono-*.woff2"):
            dst = fonts_dst_dir / font_file.name
            if not dst.exists():
                shutil.copy2(font_file, dst)
                log.info(f"  📦 复制字体: {font_file.name}")
    
    # 2. 注入 @font-face 到 globals.css
    css_path = Path(repo) / "src" / "styles" / "globals.css"
    if css_path.exists():
        css = css_path.read_text(encoding="utf-8")
        # 检测 @font-face 里是否已有 JetBrains Mono(而非 --font-mono 变量里的引用)
        if "font-family: 'JetBrains Mono'" not in css:
            # 在 Inter Variable 的 @font-face 后追加 JetBrains Mono 定义
            pattern = re.compile(
                r"(  @font-face \{\s+font-family: 'Inter Variable';.*?\s+\}\s+)(\})",
                re.DOTALL
            )
            jetbrains_faces = """  @font-face {
    font-family: 'JetBrains Mono';
    font-style: normal;
    font-display: block;
    font-weight: 400;
    src: url('/fonts/jetbrains-mono-latin-400-normal.woff2') format('woff2');
  }
  @font-face {
    font-family: 'JetBrains Mono';
    font-style: normal;
    font-display: block;
    font-weight: 700;
    src: url('/fonts/jetbrains-mono-latin-700-normal.woff2') format('woff2');
  }
}"""
            css, n = pattern.subn(r'\1' + jetbrains_faces, css)
            if n > 0:
                css_path.write_text(css, encoding="utf-8")
                log.info("  ✅ 注入 JetBrains Mono @font-face")
            else:
                log.warning("  ⚠️ globals.css @font-face 匹配失败")
    
    # 3. useTerminal.ts 配置优化
    path = Path(repo) / "src" / "hooks" / "useTerminal.ts"
    if not path.exists():
        log.warning("  ⚠️ 未找到 useTerminal.ts，跳过终端粗体优化")
        return

    src = path.read_text(encoding="utf-8")

    if "drawBoldTextInBrightColors" in src:
        log.info("  ⏭️ 终端粗体配置已优化，跳过")
        return

    # 在 allowProposedApi: true, 后追加粗体/对比度配置
    pattern = re.compile(
        r'(fontFamily: activeTheme\.terminalFontFamily,\n)(\s+)(scrollback,)'
    )
    replacement = (
        r'\1\2fontWeight: "normal",\n'
        r'\2fontWeightBold: "bold",\n'
        r'\2\3'
    )
    src, n1 = pattern.subn(replacement, src)

    pattern2 = re.compile(r'(allowProposedApi: true,\n)(\s+)(\}\);)')
    replacement2 = (
        r'\1\2drawBoldTextInBrightColors: true,\n'
        r'\2minimumContrastRatio: 7,\n'
        r'\2\3'
    )
    src, n2 = pattern2.subn(replacement2, src)

    if n1 == 0 or n2 == 0:
        log.warning("  ⚠️ 终端配置匹配失败 (n1=%d n2=%d)", n1, n2)
        return

    path.write_text(src, encoding="utf-8")
    log.info("  ✅ 终端粗体优化(亮色粗体+加重字重+高对比度)")



def patch_ssh_algorithms(repo):
    """SSH 连接健壮性增强,修复 10054 连接重置。

    1) 默认完整算法集(安全优先+旧算法后备),兼容各种服务器
    2) 增强连接重试(3次→6次,退避更长),应对间歇性 RST
       (Windows + russh 对某些服务器偶发连接重置,重试可恢复)
    """
    path = Path(repo) / "src-tauri" / "src" / "ssh" / "client.rs"
    if not path.exists():
        log.warning("  ⚠️ 未找到 client.rs，跳过 SSH 算法适配")
        return

    src = path.read_text(encoding="utf-8")

    if "// 汉化版: 默认完整算法集" in src:
        log.info("  ⏭️ SSH 算法已适配，跳过")
        return

    # 把 config 的 preferred 改为始终用 legacy_preferred()(完整算法集)
    pattern = re.compile(
        r'preferred: if legacy_algorithms \{\s*'
        r'legacy_preferred\(\)\s*'
        r'\} else \{\s*'
        r'Default::default\(\)\s*'
        r'\},'
    )
    replacement = (
        '// 汉化版: 默认完整算法集(安全优先+旧算法后备),自动适配老服务器\n'
        '        preferred: legacy_preferred(),'
    )
    new_src, n = pattern.subn(replacement, src)

    if n == 0:
        log.warning("  ⚠️ 未匹配到 preferred 算法配置，跳过")
        return

    # legacy_algorithms 参数不再使用,加 _ 前缀避免未使用警告(Rust warning as error)
    new_src = new_src.replace(
        "    legacy_algorithms: bool,",
        "    _legacy_algorithms: bool, // 汉化版已默认完整算法集,此参数保留兼容",
        1,
    )

    # 增强连接重试: 3次→6次, 退避 300ms→500ms(应对间歇性 RST/10054)
    new_src = re.sub(
        r'const CONNECT_MAX_ATTEMPTS: u32 = \d+;',
        'const CONNECT_MAX_ATTEMPTS: u32 = 6;',
        new_src,
    )
    new_src = re.sub(
        r'const CONNECT_RETRY_BACKOFF_MS: u64 = \d+;',
        'const CONNECT_RETRY_BACKOFF_MS: u64 = 500;',
        new_src,
    )

    path.write_text(new_src, encoding="utf-8")
    log.info("  ✅ SSH 连接健壮性增强(完整算法集+6次重试,修复 10054)")


def patch_keepalive(repo):
    """放宽 SSH keepalive 容忍度,修复频繁断线 (Connection failed: Disconnected)。

    上游默认 balanced=每3秒探测,连续3次(9秒)无响应即断开,对抖动/代理网络过于激进。
    改为: 默认 tolerant, 且放宽各预设的探测间隔和最大次数。
    """
    path = Path(repo) / "src" / "utils" / "keepalive.ts"
    if not path.exists():
        log.warning("  ⚠️ 未找到 keepalive.ts，跳过")
        return

    src = path.read_text(encoding="utf-8")

    # 1. 默认预设改为 tolerant
    src = re.sub(
        r'export const DEFAULT_KEEPALIVE_PRESET: KeepalivePreset = "balanced";',
        'export const DEFAULT_KEEPALIVE_PRESET: KeepalivePreset = "tolerant";',
        src,
    )

    # 2. 放宽各预设的容忍度(检测时间 = intervalSecs × max)
    #    fast: 2×2=4s → 5×3=15s ; balanced: 3×3=9s → 10×3=30s ; tolerant: 5×4=20s → 15×6=90s
    src = re.sub(
        r'fast: \{ intervalSecs: \d+, max: \d+,',
        'fast: { intervalSecs: 5, max: 3,',
        src,
    )
    src = re.sub(
        r'balanced: \{ intervalSecs: \d+, max: \d+,',
        'balanced: { intervalSecs: 10, max: 3,',
        src,
    )
    src = re.sub(
        r'tolerant: \{ intervalSecs: \d+, max: \d+,',
        'tolerant: { intervalSecs: 15, max: 6,',
        src,
    )

    path.write_text(src, encoding="utf-8")
    log.info("  ✅ SSH keepalive 容忍度放宽(默认 tolerant, 90秒容忍)")

    # 同步 Rust 端 connect 默认值(前端没传时的兜底)
    ssh_cmd = Path(repo) / "src-tauri" / "src" / "commands" / "ssh.rs"
    if ssh_cmd.exists():
        rs = ssh_cmd.read_text(encoding="utf-8")
        rs2 = re.sub(r'keepalive_interval_secs\.unwrap_or\(\d+\)', 'keepalive_interval_secs.unwrap_or(15)', rs)
        rs2 = re.sub(r'keepalive_max\.unwrap_or\(\d+\)', 'keepalive_max.unwrap_or(6)', rs2)
        if rs2 != rs:
            ssh_cmd.write_text(rs2, encoding="utf-8")
            log.info("  ✅ Rust 端 keepalive 默认值同步(15秒×6)")


def patch_updater(repo, github_repo="iflyelf/voltius-zh-CN"):
    """1) 自动更新默认关闭 2) 更新源指向自己的 GitHub 仓库 Release。"""
    # 1. Rust 端: updater_auto_enabled 默认改为 false
    sync_path = Path(repo) / "src-tauri" / "src" / "commands" / "sync.rs"
    if sync_path.exists():
        src = sync_path.read_text(encoding="utf-8")
        # 把该函数里的两个 true 默认值改为 false
        pattern = re.compile(
            r'(pub fn updater_auto_enabled\(\) -> bool \{.*?\.unwrap_or\()true(\).*?Err\(_\) => )true',
            re.DOTALL
        )
        new_src, n = pattern.subn(r'\1false\2false', src)
        if n > 0:
            sync_path.write_text(new_src, encoding="utf-8")
            log.info("  ✅ 自动更新默认关闭")
        else:
            log.warning("  ⚠️ 未匹配到 updater_auto_enabled 默认值")
    else:
        log.warning("  ⚠️ 未找到 sync.rs")

    # 2. 前端 store 默认值也改为 false
    pref_path = Path(repo) / "src" / "stores" / "updaterPrefStore.ts"
    if pref_path.exists():
        src = pref_path.read_text(encoding="utf-8")
        new_src, n = re.subn(r'autoUpdate: true,', 'autoUpdate: false,', src)
        if n > 0:
            pref_path.write_text(new_src, encoding="utf-8")
            log.info("  ✅ 前端 autoUpdate 默认关闭")

    # 3. tauri.conf.json: updater endpoint 指向自己的 GitHub Release
    conf_path = Path(repo) / "src-tauri" / "tauri.conf.json"
    if conf_path.exists():
        conf = read_json(conf_path)
        if "plugins" in conf and "updater" in conf["plugins"]:
            # GitHub Release 的 latest.json 更新源
            conf["plugins"]["updater"]["endpoints"] = [
                f"https://github.com/{github_repo}/releases/latest/download/latest.json"
            ]
            write_json(conf_path, conf)
            log.info("  ✅ 更新源指向 %s", github_repo)


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
    patch_csv_format(repo)         # CSV 格式增强(Groups/Label/Password)
    patch_csv_groups_to_folders(repo) # CSV Groups 自动映射为文件夹
    patch_hosts_display(repo)      # 修复主机列表显示(库根节点显示所有主机)
    patch_default_settings(repo)   # 默认设置：关闭滚动小地图
    patch_updater(repo)            # 自动更新默认关闭 + 更新源指向自己仓库
    patch_ssh_algorithms(repo)     # SSH 算法自动适配(修复 10054 连接重置)
    patch_keepalive(repo)          # 放宽 SSH keepalive,修复频繁断线
    patch_terminal_bold(repo)      # 终端粗体优化(亮色+加重+高对比度)
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
