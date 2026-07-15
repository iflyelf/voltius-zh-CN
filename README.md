# Voltius 中文汉化工具

为 [Voltius](https://github.com/VoltiusApp/voltius) 提供完整的简体中文语言支持。

Voltius 是一个基于 Rust/Tauri 的现代化 SSH/SFTP 客户端，是 Termius 的开源替代品。本项目通过**源码级汉化**（标准 i18next 国际化框架）为其添加简体中文界面。

---

## 目录

- [重要说明](#重要说明)
- [技术方案](#技术方案)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [使用 GitHub Actions 构建](#使用-github-actions-构建)
- [本地构建](#本地构建)
- [翻译贡献指南](#翻译贡献指南)
- [术语表](#术语表)
- [常见问题](#常见问题)
- [许可证](#许可证)
- [致谢](#致谢)

---

## 重要说明

**Q: 能否像 Termius 那样直接对已安装应用打补丁？**

**A: 不能。** 这是架构差异导致的：

| 对比项 | Termius | Voltius（本项目） |
|--------|---------|-------------------|
| 架构 | Electron（`app.asar` 打包，可解包修改） | Rust/Tauri（前端编译进二进制 `.exe`，无法解包） |
| 汉化方式 | 二进制补丁（正则替换 asar 中的 JS） | 源码修改 → 重新构建 |
| 国际化框架 | 硬编码字符串 | i18next（标准 i18n） |
| 维护成本 | 每版本需重新提取字符串 | 语料文件独立，易于维护 |
| 多平台支持 | 需分别处理 | 单一源码，构建产出全平台 |
| 上游贡献 | 无法回馈上游 | 可向上游提交 PR |

**推荐方式：** 使用本工具构建汉化版安装包，用户下载后覆盖安装即可（数据不会丢失）。安装后在 **Settings → Language** 选择 **简体中文**。

---

## 技术方案

Voltius 已内置完善的 i18n 框架：

- 前端使用 `i18next` + React
- 所有文案已抽取至 `src/i18n/locales/en/*.json`（23 个文件）
- 上游目前支持 `en`（英语）和 `fr`（法语）

汉化需要 3 处改动：

**1. 新增中文语料** `src/i18n/locales/zh-CN/*.json`（23 个文件）

**2. 注册中文资源** `src/i18n/index.ts`

```typescript
const zhCN = assemble(
  import.meta.glob("./locales/zh-CN/*.json", { eager: true }) as Record<...>
);

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    fr: { translation: fr },
    "zh-CN": { translation: zhCN }  // 新增
  },
});
```

**3. 添加语言选项** `src/stores/localeStore.ts`

```typescript
export type Locale = "en" | "fr" | "zh-CN";  // 扩展类型

export const SUPPORTED_LOCALES: { value: Locale; label: string }[] = [
  { value: "en", label: "English" },
  { value: "fr", label: "Français" },
  { value: "zh-CN", label: "简体中文" },  // 新增
];
```

上述改动由 `localize.py --patch` 自动完成。

---

## 目录结构

```
voltius/
├── localize.py              # 核心汉化脚本（克隆/翻译/打补丁/构建）
├── batch-translate.py       # 批量机器翻译（带限流保护）
├── quick-patch.sh           # 一键汉化脚本
├── README.md                # 本文档
├── .github/
│   └── workflows/
│       └── build-all-platforms.yml   # 全平台 CI 构建
│
├── locales/                 # 中文语料库（项目维护）
│   └── zh-CN/
│       ├── _meta.json       # 元信息
│       ├── common.json      # 通用 UI（保存/取消/删除等）
│       ├── settings.json    # 设置页面（最大文件，567 条）
│       ├── layout.json      # 主界面/导航
│       ├── hosts.json       # 主机管理
│       ├── terminal.json    # 终端功能
│       └── ...              # 共 23 个文件
│
├── translations/            # 翻译辅助
│   ├── glossary.json        # 术语表（人工维护）
│   └── machine.json         # 机翻缓存（支持断点续传）
│
└── voltius/                 # 克隆的上游仓库（.gitignore，patch 注入到此）
    └── src/i18n/locales/zh-CN/
```

---

## 快速开始

### 使用场景

| 你是... | 推荐方式 |
|---------|---------|
| **普通用户**（想要中文版 Voltius） | 在 [Releases](../../releases) 下载构建好的安装包，或在 [Issues](../../issues) 发起构建请求 |
| **有 GitHub 账号**（想自动构建） | 参考 [使用 GitHub Actions 构建](#使用-github-actions-构建) |
| **开发者**（想贡献翻译） | 参考 [翻译贡献指南](#翻译贡献指南) |

### 前置要求

**仅翻译/打补丁：**
- Python 3.8+
- Git

**完整构建（仅开发者）：**
- Node.js 24+
- pnpm（`npm i -g pnpm`）
- Rust（stable toolchain）
- Tauri 构建依赖（参考 [Tauri 文档](https://tauri.app/start/prerequisites/)）

### `localize.py` 命令参考

```bash
# 完整流程：克隆仓库 → 生成中文语料 → 应用补丁 → 可选构建
python localize.py --all

# 仅生成中文 JSON（基于机器翻译，需人工校对）
python localize.py --translate

# 仅应用源码补丁（手动维护 zh-CN 语料后）
python localize.py --patch

# 应用补丁后自动构建
python localize.py --patch --build

# 检查翻译完整性
python localize.py --check

# 指定 Voltius 仓库路径
python localize.py --repo /path/to/voltius --patch
```

| 参数 | 简写 | 说明 |
|------|------|------|
| `--all` | `-a` | 完整流程：克隆+翻译+补丁 |
| `--translate` | `-t` | 生成中文 JSON 语料 |
| `--patch` | `-p` | 应用源码补丁 |
| `--build` | `-b` | 自动构建（需与 `--patch` 配合） |
| `--check` | | 检查翻译完整性 |
| `--repo PATH` | `-r` | 指定 Voltius 仓库路径 |
| `--verbose` | `-v` | 详细日志输出 |

### 一键汉化

```bash
./quick-patch.sh          # 克隆 + 翻译 + 打补丁

cd voltius
pnpm install
pnpm tauri dev            # 开发模式测试
pnpm tauri build          # 构建安装包
```

---

## 使用 GitHub Actions 构建

本项目已配置好 `.github/workflows/build-all-platforms.yml`，可自动构建全平台：

- Windows（x64 / ARM64）
- macOS（Intel / Apple Silicon）
- Linux（x64 / ARM64）- deb / rpm / AppImage
- Android（ARM64 APK）

### 触发构建

**方式 1：手动触发（推荐）**

1. 进入你的 GitHub 仓库 → **Actions** 标签
2. 左侧选择 **构建全平台汉化版**
3. 点击 **Run workflow**，输入 Voltius 上游版本（如 `v0.9.2`）
4. 等待约 30-40 分钟（并行构建）

**方式 2：修改翻译后自动触发**

```bash
git add locales/zh-CN/
git commit -m "改进翻译: 完善 common.json"
git push origin main
```

**方式 3：打 tag 发布 Release**

```bash
git tag zh-v0.9.2-1
git push origin zh-v0.9.2-1
```

### 下载产物

- **Artifacts**（构建产物，有效期 90 天）：Actions → 对应 workflow → 底部 Artifacts
- **Releases**（正式发布）：仓库 Releases 页面，直接下载安装包

### 构建时间估算

| 平台 | 耗时 | Actions 分钟数 |
|------|------|---------------|
| Windows x64 / ARM64 | 各 10-15 分钟 | ~15 分钟 |
| macOS Intel / M1 | 各 15-20 分钟 | ~20 分钟 |
| Linux x64 / ARM64 | 各 8-12 分钟 | ~12 分钟 |
| Android | 12-18 分钟 | ~18 分钟 |
| **总计（并行）** | **30-40 分钟** | **~112 分钟** |

> GitHub 免费额度：公开仓库无限，私有仓库每月 2000 分钟。

### 仅构建特定平台

编辑 `.github/workflows/build-all-platforms.yml`，在 `matrix.include` 中注释掉不需要的平台。

### 代码签名（可选）

自己构建的版本没有官方签名，Windows SmartScreen / macOS Gatekeeper 会警告"未识别的应用"。代码开源透明，可安全绕过：

- **Windows**：点击 **更多信息** → **仍要运行**
- **macOS**：右键 → **打开**（仅首次）

如需正式签名：Windows 需购买代码签名证书（.pfx）；macOS 需 Apple Developer 账号（99 USD/年）+ 公证；Android 需替换调试密钥为正式密钥。将证书 Base64 编码后配置到 GitHub Secrets，并在 workflow 中添加签名步骤。

---

## 本地构建

```bash
# 1. 克隆本项目
git clone https://github.com/你的用户名/voltius-zh-CN.git
cd voltius-zh-CN

# 2. 一键汉化（需 Python + Git）
python localize.py --all

# 3. 构建（需 Node.js 24+ / pnpm / Rust / 平台构建工具）
cd voltius
pnpm install
pnpm tauri build

# 4. 产物位置
# Windows: voltius/target/release/bundle/msi/Voltius_0.9.2_x64_zh-CN.msi
#          voltius/target/release/bundle/nsis/Voltius_0.9.2_x64-setup.exe
# 其他平台: voltius/target/release/bundle/
```

### 跨平台构建（Docker）

```bash
docker build -f Dockerfile.cross-compile -t voltius-cross .

# Windows ARM64
docker run --rm -v "$(pwd):/project" voltius-cross \
  bash -c 'pnpm tauri build --target aarch64-pc-windows-msvc --runner cargo-xwin'

# Linux x64
docker run --rm -v "$(pwd):/project" voltius-cross \
  bash -c 'pnpm tauri build --target x86_64-unknown-linux-gnu'
```

### 更新上游

```bash
cd voltius
git remote add upstream https://github.com/VoltiusApp/voltius.git
git fetch upstream
git merge upstream/main

# 检查 en 语料是否有新增，对应更新 locales/zh-CN/
cd .. && python localize.py --translate
```

---

## 翻译贡献指南

### 翻译原则

1. **准确性** — 理解上下文含义，避免直译；技术术语保持专业性；参考[术语表](#术语表)
2. **一致性** — 相同概念使用相同译名；参考 Windows/macOS 系统术语；风格统一
3. **可读性** — 符合中文表达习惯，避免欧化长句，适当使用标点和空格

### 翻译流程

```bash
# 方式 1: 直接编辑 JSON（推荐）
vim locales/zh-CN/common.json
python3 localize.py --check       # 检查完整性
python3 localize.py --patch       # 应用到仓库
cd voltius && pnpm tauri dev       # 本地测试

# 方式 2: 机器翻译辅助（分批处理避免限流）
python3 batch-translate.py --file common.json --delay 0.5
vim locales/zh-CN/common.json      # 人工校对
python3 localize.py --patch
```

### 质量检查清单

- [ ] 保留所有 `{{变量}}`，不要翻译占位符
- [ ] JSON 格式正确（用 `jq . file.json` 验证）
- [ ] 占位符前后空格完整（如 `{{count}} 个主机`，机翻常吞掉空格）
- [ ] 无错别字
- [ ] 专业术语符合术语表

### 上下文相关翻译

某些英文词在不同场景下译法不同，需人工判断：

| 英文 | 场景 | 中文 |
|------|------|------|
| Host | 服务器设备 | 主机 |
| Host | 主机名（域名） | 主机名 |
| Key | SSH 密钥 | 密钥 |
| Key | 键盘按键 | 按键 |
| Terminal | 应用名称 | Terminal（保留） |
| Terminal | 终端界面 | 终端 |

> 提示：参考 `src/i18n/locales/en/` 对应文件查看完整上下文。

### 文件优先级（按使用频率）

| 文件 | 说明 | 重要性 |
|------|------|--------|
| `common.json` | 通用 UI 词汇 | ⭐⭐⭐ |
| `layout.json` | 主界面/导航/菜单 | ⭐⭐⭐ |
| `settings.json` | 设置页面（最大文件，567 条） | ⭐⭐⭐ |
| `hosts.json` | 主机管理 | ⭐⭐ |
| `terminal.json` | 终端功能 | ⭐⭐ |
| `fileTransfer.json` | SFTP 文件传输 | ⭐⭐ |
| `connections.json` | 连接管理 | ⭐⭐ |
| 其他 | 次要功能 | ⭐ |

### 提交 PR

```bash
git checkout -b translate-common
vim locales/zh-CN/common.json
git add locales/zh-CN/common.json
git commit -m "翻译: 完善 common.json 中的通用术语"
git push origin translate-common
# 在 GitHub 上创建 Pull Request
```

PR 标题格式示例：
- `翻译: 完成 common.json`
- `修正: settings.json 中"端口转发"术语不一致`
- `新增: 补充 terminal.json 缺失条目`

---

## 术语表

完整术语表见 [`translations/glossary.json`](translations/glossary.json)。核心术语：

### SSH / 网络

| English | 中文 | 备注 |
|---------|------|------|
| SSH / SFTP | SSH / SFTP | 保留英文 |
| Host | 主机 | 服务器设备 |
| Connection | 连接 | |
| Session | 会话 | |
| Port Forwarding | 端口转发 | |
| Jump Host | 跳板机 | 或"堡垒机" |
| Tunnel | 隧道 | |
| Local / Remote / Dynamic | 本地 / 远程 / 动态 | |
| Keychain | 密钥链 | |
| Vault | 保管库 | |
| Snippet | 代码片段 | |

### UI 通用

| English | 中文 | | English | 中文 |
|---------|------|-|---------|------|
| Settings | 设置 | | Save | 保存 |
| Preferences | 偏好设置 | | Cancel | 取消 |
| General | 通用 | | Delete | 删除 |
| Appearance | 外观 | | Remove | 移除 |
| Theme | 主题 | | Add | 添加 |
| Font | 字体 | | Create | 创建 |
| Language | 语言 | | Edit | 编辑 |
| Account | 账号 | | Rename | 重命名 |
| Profile | 个人资料 | | Connect / Disconnect | 连接 / 断开连接 |

---

## 常见问题

**Q: 安装汉化版会丢失数据吗？**
不会。汉化版可直接覆盖官方版安装，所有主机/密钥/设置都会保留，也无需卸载旧版本。

**Q: 安装后找不到中文选项？**
确认下载的文件名包含 `_zh-CN` 且来自本项目 Releases 页面。然后在 **Settings → Language** 选择"简体中文"。

**Q: 部分界面还是英文？**
翻译可能尚未完整覆盖，欢迎在 Issues 反馈或提交 PR 补充。

**Q: 会被自动更新覆盖回英文版吗？**
如果 Voltius 有内置自动更新，可能会。重新下载对应汉化版安装即可。

**Q: 构建失败怎么办？**
查看失败 job 的日志，常见原因：依赖安装失败（重跑）、Rust 编译错误（检查 patch 逻辑）、上游 API 变更（更新 `localize.py`）。

**Q: 为什么不能 100% 翻译？**
Google Translate API 批量翻译时会触发严重限流；部分专业术语需人工校对；占位符变量需特殊处理。建议小批量处理或使用其他翻译服务。

---

## 许可证

- 本汉化工具：**MIT**
- Voltius 本体：**AGPLv3**（插件为 MIT）

---

## 致谢

- [Voltius](https://github.com/VoltiusApp/voltius) 官方团队 — 优秀的开源 SSH 客户端及标准 i18n 框架
- [ArcSurge/Termius-Pro-zh_CN](https://github.com/ArcSurge/Termius-Pro-zh_CN) — 提供思路参考
- Google Translate / deep-translator — 机器翻译支持
- 所有社区贡献者
