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
    # 用 ensureFolderPath 精确检测多层版本(避免旧单层版本误判为已应用)
    if "ensureFolderPath" not in current:
        # 直接复制完整文件
        shutil.copy2(importers_src, importers_path)
        log.info("  ✅ CSV Groups 自动映射为文件夹(支持多层目录)")
    else:
        log.info("  ⏭️ Groups 多层文件夹映射已启用，跳过")

    # 导出侧: ExportTab 传入 bundle.folders 以重建完整路径
    export_tab = Path(repo) / "src" / "components" / "import-export" / "ExportTab.tsx"
    if export_tab.exists():
        etext = export_tab.read_text(encoding="utf-8")
        if "connectionsToCSV(bundle.connections, bundle.folders)" not in etext:
            etext2 = etext.replace(
                "connectionsToCSV(bundle.connections)",
                "connectionsToCSV(bundle.connections, bundle.folders)",
                1,
            )
            if etext2 != etext:
                export_tab.write_text(etext2, encoding="utf-8")
                log.info("  ✅ 导出 CSV 传入文件夹层级(重建 Groups 路径)")


def patch_remaining_ui_text(repo):
    """批量翻译剩余硬编码英文 UI 文本。

    覆盖导入导出菜单/端口转发提示/同步设置等用户可见文本。
    """
    files_patches = {
        "src/hooks/useImportExportContributions.ts": [
            ('label: "Export"', 'label: "导出"'),
            ('label: "Import…"', 'label: "导入…"'),
            ('label: "Export…"', 'label: "导出…"'),
            ('label: "Export Vault"', 'label: "导出保管库"'),
            ('label: "Import into Vault"', 'label: "导入到保管库"'),
        ],
        "src/hooks/usePfToastBridge.ts": [
            ('label: "View Ports →"', 'label: "查看端口 →"'),
        ],
        "src/stores/syncPrefsStore.ts": [
            ('label: "Hosts"', 'label: "主机"'),
            ('sub: "SSH connections"', 'sub: "SSH 连接"'),
            ('label: "Identities"', 'label: "身份"'),
            ('sub: "Usernames and credentials"', 'sub: "用户名和凭据"'),
            ('label: "SSH Keys"', 'label: "SSH 密钥"'),
            ('sub: "Key pairs stored in keychain"', 'sub: "密钥链中存储的密钥对"'),
            ('label: "Folders"', 'label: "文件夹"'),
            ('sub: "Folder structure for organizing objects"', 'sub: "组织对象的文件夹结构"'),
            ('label: "Port Forwarding"', 'label: "端口转发"'),
            ('sub: "Saved tunnel rules"', 'sub: "已保存的隧道规则"'),
        ],
        "src/services/import-export/handlers/connections.ts": [
            ('label: "Connections"', 'label: "连接"'),
        ],
        "src/services/import-export/handlers/identities.ts": [
            ('label: "Identities"', 'label: "身份"'),
        ],
        "src/services/import-export/handlers/keys.ts": [
            ('label: "SSH Keys"', 'label: "SSH 密钥"'),
        ],
        "src/services/import-export/handlers/portForwarding.ts": [
            ('label: "Port Forwarding"', 'label: "端口转发"'),
        ],
        "src/services/import-export/handlers/snippets.ts": [
            ('label: "Snippets"', 'label: "代码片段"'),
        ],
        "src/components/settings/sections/RolesSection.tsx": [
            ('label: "View secrets"', 'label: "查看密文"'),
            ('description: "See passwords and private keys in plain text"', 'description: "以明文查看密码和私钥"'),
            ('label: "Copy secrets"', 'label: "复制密文"'),
            ('description: "Copy passwords and keys to clipboard"', 'description: "复制密码和密钥到剪贴板"'),
            ('label: "Connect"', 'label: "连接"'),
            ('description: "Launch SSH connections"', 'description: "发起 SSH 连接"'),
            ('label: "Edit connections"', 'label: "编辑连接"'),
            ('description: "Create, modify, and delete connections"', 'description: "创建、修改和删除连接"'),
            ('label: "Edit identities"', 'label: "编辑身份"'),
            ('description: "Create, modify, and delete SSH identities"', 'description: "创建、修改和删除 SSH 身份"'),
            ('label: "Edit keys"', 'label: "编辑密钥"'),
            ('description: "Create, modify, and delete SSH keys"', 'description: "创建、修改和删除 SSH 密钥"'),
            ('label: "Edit snippets"', 'label: "编辑代码片段"'),
            ('description: "Create, modify, and delete command snippets"', 'description: "创建、修改和删除命令代码片段"'),
            ('label: "Edit folders"', 'label: "编辑文件夹"'),
            ('description: "Manage folder structure"', 'description: "管理文件夹结构"'),
            ('label: "View audit log"', 'label: "查看审计日志"'),
            ('description: "Read the activity audit log"', 'description: "读取活动审计日志"'),
            ('label: "Invite members"', 'label: "邀请成员"'),
            ('description: "Invite new members to the vault"', 'description: "邀请新成员加入保管库"'),
            ('label: "Manage members"', 'label: "管理成员"'),
            ('description: "Assign roles and remove members"', 'description: "分配角色和移除成员"'),
            ('label: "Manage roles (legacy)"', 'label: "管理角色（旧版）"'),
            ('description: "Retired permission — kept for compatibility"', 'description: "已废弃权限 — 保留以兼容"'),
            ('label: "Manage roles"', 'label: "管理角色"'),
            ('description: "Create, edit, and delete roles"', 'description: "创建、编辑和删除角色"'),
            ('label: "Manage vault"', 'label: "管理保管库"'),
            ('description: "Rename vault and manage vault settings"', 'description: "重命名保管库和管理保管库设置"'),
            ('label: "Start sessions"', 'label: "发起会话"'),
            ('description: "Start multiplayer terminal sessions"', 'description: "发起多人终端会话"'),
            ('label: "Join sessions"', 'label: "加入会话"'),
            ('description: "Join existing terminal sessions"', 'description: "加入现有终端会话"'),
            ('label: "View sessions"', 'label: "查看会话"'),
            ('description: "See active terminal sessions"', 'description: "查看活动的终端会话"'),
        ],
    }

    translated_count = 0
    for file_rel, replacements in files_patches.items():
        file_path = Path(repo) / file_rel
        if not file_path.exists():
            continue

        content = file_path.read_text(encoding="utf-8")
        original = content

        for old, new in replacements:
            content = content.replace(old, new)

        if content != original:
            file_path.write_text(content, encoding="utf-8")
            translated_count += 1

    if translated_count > 0:
        log.info(f"  ✅ 批量翻译 {translated_count} 个文件的硬编码英文")
    else:
        log.info("  ⏭️ 剩余 UI 文本已翻译，跳过")


def patch_omni_commands(repo):
    """搜索框(Omni Search)命令汉化: core.commands.ts 硬编码英文 label。

    将 New Host/New SSH Key/Settings 等核心命令 label 翻译为中文。
    """
    path = Path(repo) / "src" / "commands" / "core.commands.ts"
    if not path.exists():
        log.warning("  ⚠️ 未找到 core.commands.ts，跳过搜索框命令汉化")
        return

    src = path.read_text(encoding="utf-8")

    if "新建主机" in src or "新建 SSH 密钥" in src:
        log.info("  ⏭️ 搜索框命令已汉化，跳过")
        return

    # 批量替换核心命令 label
    replacements = [
        ('label: "New Host"', 'label: "新建主机"'),
        ('label: "New SSH Key"', 'label: "新建 SSH 密钥"'),
        ('label: "New Identity"', 'label: "新建身份"'),
        ('label: "Settings"', 'label: "设置"'),
        ('label: "Check for Update"', 'label: "检查更新"'),
        ('label: "What\'s New"', 'label: "更新日志"'),
        ('label: "Port Forwarding"', 'label: "端口转发"'),
        ('label: "Known Hosts"', 'label: "已知主机"'),
        ('label: "Logs"', 'label: "日志"'),
        ('label: "New Snippet"', 'label: "新建代码片段"'),
        ('label: "Team Members"', 'label: "团队成员"'),
        ('label: "Disconnect All"', 'label: "断开所有连接"'),
    ]

    new_src = src
    for old, new in replacements:
        new_src = new_src.replace(old, new)

    if new_src != src:
        path.write_text(new_src, encoding="utf-8")
        log.info("  ✅ 搜索框命令汉化(New Host→新建主机 等)")


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


def patch_folder_counts(repo):
    """修复文件夹计数: 递归统计所有后代连接(支持多层目录)。

    上游逻辑: 只统计直接子连接, 多层目录父文件夹显示 0。
    修复: 自底向上累加到所有祖先文件夹, 父文件夹显示含所有后代的总数。
    """
    path = Path(repo) / "src" / "components" / "hosts" / "HostsPage.tsx"
    if not path.exists():
        log.warning("  ⚠️ 未找到 HostsPage.tsx，跳过文件夹计数修复")
        return

    src = path.read_text(encoding="utf-8")

    if "含所有后代子文件夹里的连接" in src:
        log.info("  ⏭️ 文件夹计数已递归修复，跳过")
        return

    # 替换 folderCounts 逻辑为递归版本
    old_pattern = re.compile(
        r'// Per-folder item counts\s*\n'
        r'\s*const folderCounts = useMemo\(\(\) => \{\s*\n'
        r'\s*const counts: Record<string, number> = \{\};\s*\n'
        r'\s*for \(const c of connections\) \{\s*\n'
        r'\s*if \(c\.folder_id\) counts\[c\.folder_id\] = \(counts\[c\.folder_id\] \?\? 0\) \+ 1;\s*\n'
        r'\s*\}\s*\n'
        r'\s*return counts;\s*\n'
        r'\s*\}, \[connections\]\);',
        re.MULTILINE
    )
    new_code = '''  // Per-folder item counts (含所有后代子文件夹里的连接,支持多层目录)
  const folderCounts = useMemo(() => {
    // 1. 直接连接数
    const direct: Record<string, number> = {};
    for (const c of connections) {
      if (c.folder_id) direct[c.folder_id] = (direct[c.folder_id] ?? 0) + 1;
    }
    // 2. 自底向上累加到所有祖先文件夹
    const parentOf: Record<string, string | undefined> = {};
    for (const f of folders) parentOf[f.id] = f.parent_folder_id ?? undefined;
    const counts: Record<string, number> = {};
    for (const f of folders) counts[f.id] = 0;
    for (const [fid, n] of Object.entries(direct)) {
      let cur: string | undefined = fid;
      const seen = new Set<string>();
      while (cur && !seen.has(cur)) {
        seen.add(cur);
        counts[cur] = (counts[cur] ?? 0) + n;
        cur = parentOf[cur];
      }
    }
    return counts;
  }, [connections, folders]);'''

    new_src, n = old_pattern.subn(new_code, src)

    if n == 0:
        log.warning("  ⚠️ 未匹配到 folderCounts 逻辑，跳过")
        return

    path.write_text(new_src, encoding="utf-8")
    log.info("  ✅ 文件夹计数递归修复(父文件夹含所有后代连接)")


def patch_folder_navigation_persistence(repo):
    """文件夹导航路径持久化: 连接主机后保持在当前文件夹(不返回根目录)。

    上游问题: 连接主机后 HostsPage 卸载重挂载, useFolderNavigation 的 useState
              重置为 [], 导航路径丢失, 用户返回主机页时回到根目录。
    修复: 1) useFolderNavigation 增加模块级缓存(按 persistKey 存储路径)
          2) 各页面传入 persistKey ("hosts"/"keychain"/"snippets"/"port-forwarding")
          3) 组件卸载后路径保留在缓存, 重挂载时恢复
    """
    hook_path = Path(repo) / "src" / "hooks" / "useFolderNavigation.ts"
    if not hook_path.exists():
        log.warning("  ⚠️ 未找到 useFolderNavigation.ts，跳过导航持久化")
        return

    src = hook_path.read_text(encoding="utf-8")
    if "模块级缓存" in src or "folderPathCache" in src:
        log.info("  ⏭️ 文件夹导航持久化已启用，跳过")
        return

    # 分步精确替换(避免多行注释里的特殊字符导致正则失败)
    # 1. import 增加 useEffect + 模块级缓存声明
    anchor1 = 'import { useMemo, useState } from "react";'
    if anchor1 not in src:
        log.warning("  ⚠️ 未找到 import 锚点，跳过导航持久化")
        return
    replace1 = (
        'import { useMemo, useState, useEffect } from "react";\n\n'
        '// 汉化版: 模块级缓存, 保存各页面的文件夹导航路径。\n'
        '// 连接主机后 HostsPage 会卸载重挂载, 用此缓存避免导航路径丢失(回到根目录)。\n'
        'const folderPathCache = new Map<string, { id: string; parent_folder_id?: string | null }[]>();'
    )
    src = src.replace(anchor1, replace1, 1)

    # 2. 函数签名 + useState 初始化改为缓存版本
    anchor2 = (
        'export function useFolderNavigation<T extends FolderNavigable>(allFolders: T[]) {\n'
        '  const [folderPath, setFolderPath] = useState<T[]>([]);'
    )
    if anchor2 not in src:
        log.warning("  ⚠️ 未找到函数签名锚点，跳过导航持久化")
        return
    replace2 = '''export function useFolderNavigation<T extends FolderNavigable>(allFolders: T[], persistKey?: string) {
  const [folderPath, setFolderPathRaw] = useState<T[]>(
    () => (persistKey ? (folderPathCache.get(persistKey) as T[] | undefined) ?? [] : []),
  );

  const setFolderPath: typeof setFolderPathRaw = (value) => {
    setFolderPathRaw((prev) => {
      const next = typeof value === "function" ? (value as (p: T[]) => T[])(prev) : value;
      if (persistKey) folderPathCache.set(persistKey, next);
      return next;
    });
  };

  useEffect(() => {
    if (!persistKey || folderPath.length === 0) return;
    const validIds = new Set(allFolders.map((f) => f.id));
    if (folderPath.some((f) => !validIds.has(f.id))) {
      const trimmed: T[] = [];
      for (const f of folderPath) {
        if (validIds.has(f.id)) trimmed.push(f);
        else break;
      }
      setFolderPath(trimmed);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allFolders]);'''
    src = src.replace(anchor2, replace2, 1)

    hook_path.write_text(src, encoding="utf-8")

    # 更新各页面传入 persistKey
    pages = [
        ("src/components/hosts/HostsPage.tsx", "hosts"),
        ("src/components/keychain/KeychainPage.tsx", "keychain"),
        ("src/components/snippets/SnippetsPage.tsx", "snippets"),
        ("src/components/port_forwarding/PortForwardingPage.tsx", "port-forwarding"),
    ]
    for page_rel, key in pages:
        page_path = Path(repo) / page_rel
        if not page_path.exists():
            continue
        page_src = page_path.read_text(encoding="utf-8")
        old_call = f'useFolderNavigation(scopedFolders)'
        new_call = f'useFolderNavigation(scopedFolders, "{key}")'
        if old_call in page_src:
            page_path.write_text(page_src.replace(old_call, new_call), encoding="utf-8")

    log.info("  ✅ 文件夹导航持久化(连接主机后保持当前文件夹)")


def patch_terminal_scroll_after_fit(repo):
    """终端 resize/全屏后自动滚动到底部(光标可见)。

    上游问题: fitAddon.fit() 后终端扩大, 但滚动位置不变, 导致光标/内容停留在下方,
              顶部出现空白(全屏/最大化/窗口resize/字体变化时)。
    修复: 所有 fit 调用后增加 terminal.scrollToBottom(), 保持光标和最新内容可见。
    """
    path = Path(repo) / "src" / "hooks" / "useTerminal.ts"
    if not path.exists():
        log.warning("  ⚠️ 未找到 useTerminal.ts，跳过终端滚动修复")
        return

    src = path.read_text(encoding="utf-8")

    if "scrollToBottom(); // 汉化版" in src:
        log.info("  ⏭️ 终端 fit 后滚动已启用，跳过")
        return

    replacements = [
        # 1. refitSession
        (
            '  try { entry.fitAddon.fit(); } catch { /* container not laid out yet */ }',
            '  try {\n'
            '    entry.fitAddon.fit();\n'
            '    entry.terminal.scrollToBottom(); // 汉化版: 全屏/resize后滚动到底部,光标可见\n'
            '  } catch { /* container not laid out yet */ }'
        ),
        # 2. 第一个 mount 路径: window resize handler
        (
            '        const handleWindowResize = () => fitAddon.fit();',
            '        const handleWindowResize = () => {\n'
            '          fitAddon.fit();\n'
            '          terminal.scrollToBottom(); // 汉化版: 窗口resize后滚动到底部\n'
            '        };'
        ),
        # 3. 第一个 mount 路径: ResizeObserver
        (
            '          fitTimer = setTimeout(() => { fitTimer = null; fitAddon.fit(); }, 50);',
            '          fitTimer = setTimeout(() => {\n'
            '            fitTimer = null;\n'
            '            fitAddon.fit();\n'
            '            terminal.scrollToBottom(); // 汉化版: resize后滚动到底部\n'
            '          }, 50);'
        ),
        # 4. 第二个 mount 路径: window resize handler (term 变量)
        (
            '      const handleWindowResize = () => fitAddon.fit();\n'
            '      window.addEventListener("resize", handleWindowResize);',
            '      const handleWindowResize = () => {\n'
            '        fitAddon.fit();\n'
            '        term.scrollToBottom(); // 汉化版: 窗口resize后滚动到底部\n'
            '      };\n'
            '      window.addEventListener("resize", handleWindowResize);'
        ),
        # 5. 第二个 mount 路径: ResizeObserver (term 变量)
        (
            '        fitTimer = setTimeout(() => { fitTimer = null; fitAddon.fit(); }, 50);\n'
            '      });\n'
            '      resizeObserver.observe(container);',
            '        fitTimer = setTimeout(() => {\n'
            '          fitTimer = null;\n'
            '          fitAddon.fit();\n'
            '          term.scrollToBottom(); // 汉化版: resize后滚动到底部\n'
            '        }, 50);\n'
            '      });\n'
            '      resizeObserver.observe(container);'
        ),
        # 6. fit callback (maximize/manual fit)
        (
            '    fitAddon.fit();\n'
            '    // Force-send current dimensions',
            '    fitAddon.fit();\n'
            '    term.scrollToBottom(); // 汉化版: fit后滚动到底部\n'
            '    // Force-send current dimensions'
        ),
        # 7. theme change (font size change)
        (
            '      if (term.options.fontSize !== theme.terminalFontSize) {\n'
            '        term.options.fontSize = theme.terminalFontSize;\n'
            '        fitAddon.fit();\n'
            '      }\n'
            '    });\n'
            '  }, [sessionId]);',
            '      if (term.options.fontSize !== theme.terminalFontSize) {\n'
            '        term.options.fontSize = theme.terminalFontSize;\n'
            '        fitAddon.fit();\n'
            '        term.scrollToBottom(); // 汉化版: 字体大小变化后滚动到底部\n'
            '      }\n'
            '    });\n'
            '  }, [sessionId]);'
        ),
        # 8. theme preview (font size change)
        (
            '      if (term.options.fontSize !== theme.terminalFontSize) {\n'
            '        term.options.fontSize = theme.terminalFontSize;\n'
            '        fitAddon.fit();\n'
            '      }\n'
            '    };\n'
            '    window.addEventListener("theme-preview", handler);',
            '      if (term.options.fontSize !== theme.terminalFontSize) {\n'
            '        term.options.fontSize = theme.terminalFontSize;\n'
            '        fitAddon.fit();\n'
            '        term.scrollToBottom(); // 汉化版: 字体大小变化后滚动到底部\n'
            '      }\n'
            '    };\n'
            '    window.addEventListener("theme-preview", handler);'
        ),
    ]

    count = 0
    for old, new in replacements:
        if old in src:
            src = src.replace(old, new, 1)
            count += 1

    if count > 0:
        path.write_text(src, encoding="utf-8")
        log.info(f"  ✅ 终端 fit 后自动滚动({count}/8 处修复)")
    else:
        log.info("  ⏭️ 未匹配到 fit 调用点，跳过")


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
    patch_omni_commands(repo)      # 搜索框命令汉化(New Host→新建主机 等)
    patch_remaining_ui_text(repo)  # 批量翻译剩余硬编码英文(导入导出菜单/同步设置等)
    patch_hosts_display(repo)      # 修复主机列表显示(库根节点显示所有主机)
    patch_folder_counts(repo)      # 修复文件夹计数(递归统计后代连接,多层目录)
    patch_folder_navigation_persistence(repo) # 文件夹导航持久化(连接后保持当前文件夹)
    patch_default_settings(repo)   # 默认设置：关闭滚动小地图
    patch_updater(repo)            # 自动更新默认关闭 + 更新源指向自己仓库
    patch_ssh_algorithms(repo)     # SSH 算法自动适配(修复 10054 连接重置)
    patch_keepalive(repo)          # 放宽 SSH keepalive,修复频繁断线
    patch_terminal_bold(repo)      # 终端粗体优化(亮色+加重+高对比度)
    patch_terminal_scroll_after_fit(repo) # 终端 resize/全屏后自动滚动到底部
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
