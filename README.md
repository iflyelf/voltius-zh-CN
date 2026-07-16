# Voltius 简体中文版

[Voltius](https://github.com/VoltiusApp/voltius) 的完整中文汉化版本，包含**客户端汉化 + 自建服务器 + Pro 功能解锁**。

Voltius 是一个基于 Rust/Tauri 的现代化 SSH/SFTP 客户端，是 Termius 的开源替代品（AGPLv3 协议）。

---

## 🚀 快速开始

### 下载安装包

访问 [Releases](https://github.com/iflyelf/voltius-zh-CN/releases) 下载最新版本：

- **Windows**: `Voltius_x.x.x_x64-setup.exe` / `.msi`
- **macOS**: `Voltius_x.x.x_universal.dmg` (支持 Intel + Apple Silicon)
- **Linux**: `Voltius_x.x.x_amd64.AppImage` / `.deb`
- **Android**: `Voltius_x.x.x.apk`

安装后，在 **设置 → Language** 选择 **简体中文**。

### 功能特性

✅ **完整汉化**：95.1% 覆盖率 (2526/2656 条)，基于标准 i18next 框架  
✅ **无限保管库**：免费版解除单一保管库限制  
✅ **自建服务器**：Go 语言实现，支持云同步 + Pro 功能  
✅ **端到端加密**：Argon2id + XChaCha20，服务器无法解密数据  
✅ **跨平台**：Windows/macOS/Linux/Android 全平台支持  
✅ **自动更新**：Tauri 签名，支持应用内自动更新

---

## 📦 自建服务器（可选）

本项目提供 Go 语言实现的自建服务器，实现云同步和 Pro 功能（多设备同步、团队保险库等）。

### 服务器特性

- 🔐 **硬编码 Pro 订阅**：所有用户自动获得 Pro 权限
- 📦 **静态二进制**：CGO_ENABLED=0 编译，6MB 单文件，无需依赖
- 🔒 **端到端加密**：服务器只存储密文，无法解密用户数据
- 🚀 **SSE 实时推送**：多设备实时同步
- 💾 **SQLite 存储**：轻量级，单文件数据库

### 快速部署

#### 1. 编译服务器

```bash
cd voltius-server
chmod +x build.sh
./build.sh
```

**产物**：
- `dist/voltius-server-linux-amd64`
- `dist/voltius-server-linux-arm64`
- `dist/voltius-server-darwin-amd64` (macOS Intel)
- `dist/voltius-server-darwin-arm64` (macOS M1/M2/M3)
- `dist/voltius-server-windows-amd64.exe`

#### 2. 运行服务器

```bash
# 基础运行（自动生成 JWT 密钥）
./dist/voltius-server-linux-amd64

# 自定义配置
./dist/voltius-server-linux-amd64 \
  -port 8080 \
  -db /data/voltius.db \
  -jwt-secret "your-random-secret-CHANGE-ME"
```

**参数说明**：
- `-port`：服务器端口（默认 8080）
- `-db`：SQLite 数据库路径（默认 `./voltius.db`）
- `-jwt-secret`：JWT 签名密钥（留空自动生成，**建议手动指定并保存**）

#### 3. 生产部署（Systemd）

```bash
# 1. 安装二进制
sudo cp dist/voltius-server-linux-amd64 /usr/local/bin/voltius-server
sudo chmod +x /usr/local/bin/voltius-server

# 2. 创建服务
sudo tee /etc/systemd/system/voltius-server.service << 'EOF'
[Unit]
Description=Voltius Self-Hosted Server
After=network.target

[Service]
Type=simple
User=voltius
WorkingDirectory=/var/lib/voltius
ExecStart=/usr/local/bin/voltius-server -port 8080 -db /var/lib/voltius/voltius.db -jwt-secret YOUR_SECRET_HERE
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 3. 创建用户和目录
sudo useradd -r -s /bin/false voltius
sudo mkdir -p /var/lib/voltius
sudo chown voltius:voltius /var/lib/voltius

# 4. 启动服务
sudo systemctl daemon-reload
sudo systemctl enable voltius-server
sudo systemctl start voltius-server
sudo systemctl status voltius-server
```

#### 4. Nginx 反向代理 + HTTPS

```nginx
# /etc/nginx/sites-available/voltius
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # SSE 支持
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/voltius /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 5. 客户端配置

打开 Voltius 客户端 → 登录界面 → 点击 **"▸ Custom server URL"**：

```
http://your-server-ip:8080       # HTTP (测试)
https://api.yourdomain.com       # HTTPS (生产环境推荐)
```

注册/登录后，自动获得 **Pro 权限**和**无限保管库**。

### Docker 部署（可选）

```dockerfile
FROM scratch
COPY voltius-server-linux-amd64 /voltius-server
EXPOSE 8080
CMD ["/voltius-server", "-port", "8080"]
```

```bash
docker build -t voltius-server .
docker run -d \
  -p 8080:8080 \
  -v /data:/data \
  voltius-server \
  -db /data/voltius.db \
  -jwt-secret YOUR_SECRET
```

### 数据库备份

```bash
# SQLite 热备份
sqlite3 /var/lib/voltius/voltius.db ".backup /backup/voltius-$(date +%Y%m%d).db"

# 定时备份 (crontab)
0 2 * * * sqlite3 /var/lib/voltius/voltius.db ".backup /backup/voltius-$(date +\%Y\%m\%d).db"
```

### 服务器 API 端点

**认证**：
- `POST /v1/auth/register` - 注册
- `GET /v1/auth/challenge?email=xxx` - 获取 account_id
- `POST /v1/auth/login` - 登录
- `POST /v1/auth/refresh` - 刷新 token
- `GET /v1/auth/me` - 当前用户信息
- `PUT /v1/auth/public-key` - 更新公钥

**同步**：
- `GET /v1/sync/blob?device_id=xxx` - 下载加密数据
- `PUT /v1/sync/blob?device_id=xxx` - 上传加密数据
- `GET /v1/sync/devices` - 设备列表
- `GET /v1/sync/stream?device_id=xxx` - SSE 实时推送

**订阅**：
- `GET /v1/billing/subscription` - 订阅状态（硬编码 Pro）

### 安全说明

#### 端到端加密
所有用户数据经过客户端加密后上传：

```
用户密码 → Argon2id(128MB, t=3, p=4) → master_key (32字节)
  ├─ HKDF-SHA256(info="auth") → auth_key (上传服务器验证)
  └─ HKDF-SHA256(info="enc")  → enc_key  (本地加密数据)

加密: XChaCha20-Poly1305(enc_key, plaintext) → ciphertext (base64)
```

- **服务器只存储密文**：即使数据库泄露也无法解密
- **密钥从不上传**：master_key 和 enc_key 永远在本地
- **auth_key 验证**：服务器存储 SHA256(auth_key)，恒定时间比较

#### JWT Token 结构

```json
{
  "sub": "account_id",
  "email": "user@example.com",
  "tier": "pro",           // 🔓 硬编码 Pro
  "exp": 1720000000,
  "iss": "voltius-selfhosted"
}
```

---

## 🛠️ 开发相关

### 技术栈

**客户端**：
- Tauri 2.0 + Rust (后端)
- React + TypeScript (前端)
- i18next (国际化框架)

**服务器**：
- Go 1.21+ (CGO_ENABLED=0 静态编译)
- modernc.org/sqlite (纯 Go 的 SQLite)
- golang-jwt/jwt (JWT 签发)

### 目录结构

```
voltius-zh-CN/
├── locales/              # 中文语料文件（23 个 JSON）
│   └── zh-CN/
│       ├── common.json
│       ├── layout.json
│       └── ...
├── localize.py           # 汉化脚本（应用补丁/构建/检查）
├── voltius-server/       # Go 自建服务器
│   ├── main.go
│   ├── jwt.go           # 硬编码 tier="pro"
│   ├── auth.go
│   ├── sync.go
│   └── build.sh         # 跨平台编译
├── .github/workflows/
│   └── build-all-platforms.yml  # CI 构建配置
└── README.md            # 本文档
```

### 本地构建

#### 前置要求

- **Node.js** 24+ (推荐使用 nvm)
- **pnpm** 9+ (`npm install -g pnpm`)
- **Rust** (通过 [rustup](https://rustup.rs/) 安装)
- **Python 3** (用于 localize.py)
- **平台构建工具**：
  - Linux: `build-essential` / `libwebkit2gtk-4.1-dev` / `libssl-dev`
  - macOS: Xcode Command Line Tools
  - Windows: Visual Studio 2022 (C++ 工具)

#### 构建流程

```bash
# 1. 克隆仓库
git clone https://github.com/iflyelf/voltius-zh-CN.git
cd voltius-zh-CN

# 2. 运行汉化脚本（克隆上游 + 应用补丁 + 构建）
python3 localize.py --build

# 3. 产物位置
# Windows: voltius/target/release/bundle/msi/Voltius_*.msi
#          voltius/target/release/bundle/nsis/Voltius_*-setup.exe
# macOS:   voltius/target/release/bundle/dmg/Voltius_*.dmg
# Linux:   voltius/target/release/bundle/appimage/Voltius_*.AppImage
#          voltius/target/release/bundle/deb/voltius_*.deb
```

### GitHub Actions 自动构建

推送代码或创建 tag 会自动触发多平台构建：

```bash
# 触发构建（推送 tag）
git tag zh-v0.9.2-1 -m "Voltius 0.9.2 简体中文版"
git push origin zh-v0.9.2-1

# 手动触发（在 GitHub Actions 页面点击 "Run workflow"）
```

**构建时间**：约 15-25 分钟（并行构建 7 个平台）

### 翻译贡献

#### 编辑语料文件

```bash
# 直接编辑 JSON（推荐）
vim locales/zh-CN/layout.json

# 检查翻译完整性
python3 localize.py --check-translation
```

#### 提交 PR

```bash
git checkout -b improve-translation
git add locales/zh-CN/
git commit -m "improve: 优化术语翻译"
git push origin improve-translation
# 在 GitHub 上创建 Pull Request
```

### 术语表

| 英文 | 中文 | 说明 |
|------|------|------|
| Vault | 保管库 | 不译为"金库/保险库" |
| Connection | 连接 | SSH 连接配置 |
| Host | 主机 | 远程服务器 |
| Key | 密钥 | SSH 密钥对 |
| Snippet | 代码片段 | 命令模板 |
| Port Forwarding | 端口转发 | 隧道功能 |
| Identity | 身份 | SSH 身份认证 |

---

## ❓ 常见问题

### Q: 为什么不能直接打补丁到已安装的 Voltius？

**A**: Termius 是 Electron 应用（可解包 asar），Voltius 是 Tauri（Rust 编译成原生二进制，前端编译进 .exe）。Tauri 的架构决定了必须源码级重新构建。

### Q: 汉化版安装后会覆盖原版数据吗？

**A**: 不会。Voltius 的数据存储在系统 keychain/数据目录，安装包只替换可执行文件，数据完全保留。

### Q: 自建服务器安全吗？

**A**: 数据采用端到端加密（Argon2id + XChaCha20-Poly1305），服务器只存储密文。即使服务器被攻破，攻击者也无法解密数据。**前提是密码强度足够**。

### Q: 为什么 ARM64 Linux 构建有时失败？

**A**: GitHub Actions 的 ARM runner 网络不稳定，Rust 编译时下载 crates 可能超时。CI 已配置强制 IPv4 + 重试机制，失败时会自动重试。

### Q: 官方 Voltius 更新后如何同步？

**A**: 
```bash
python3 localize.py --update-upstream v0.9.3  # 拉取上游 v0.9.3
python3 localize.py --check-translation        # 检查 en 新增的条目
# 手动翻译新增条目
git commit -am "sync: 同步上游 v0.9.3"
git push origin main
```

### Q: 可以商用吗？

**A**: Voltius 客户端采用 AGPLv3 协议，**允许商用但必须开源**。自建服务器代码同样遵循 AGPLv3。如果在企业内部使用且不分发，则无需公开源码。**推荐小团队（<20人）使用，大型企业请购买官方订阅支持开发者**。

---

## 📊 功能对比

| 功能 | 官方免费版 | 官方 Pro ($8/月) | **汉化版 + 自建服务器** |
|------|-----------|-----------------|----------------------|
| 界面语言 | 英语/法语 | 英语/法语 | ✅ **简体中文** |
| 保管库数量 | 1 个 | 无限制 | ✅ **无限制** |
| 云同步 | ❌ | ✅ | ✅ **自建服务器** |
| 多设备同步 | ❌ | ✅ | ✅ **SSE 实时推送** |
| 团队保险库 | ❌ | ❌ | ✅ **支持** |
| 数据掌控 | 官方服务器 | 官方服务器 | ✅ **完全自主** |
| 端到端加密 | ✅ | ✅ | ✅ **同样安全** |
| 费用 | 免费 | $8/月 | ✅ **免费（仅服务器成本）** |

---

## 📝 许可证

- **Voltius 客户端**：[AGPLv3](https://github.com/VoltiusApp/voltius/blob/main/LICENSE)（原项目协议）
- **本汉化项目**：AGPLv3（包含客户端补丁和服务器代码）

**说明**：
- AGPLv3 允许自由使用、修改、分发，但要求衍生作品也必须开源
- 自建服务器用于个人/小团队内部使用时，无需公开源码
- 如果提供网络服务（SaaS），必须向用户提供源码

---

## 🙏 致谢

- [Voltius](https://github.com/VoltiusApp/voltius) - 优秀的开源 SSH 客户端
- [Tauri](https://tauri.app/) - 现代化跨平台框架
- [i18next](https://www.i18next.com/) - 国际化框架
- 所有贡献翻译的开发者

---

## 🔗 相关链接

- **原项目**: https://github.com/VoltiusApp/voltius
- **本项目**: https://github.com/iflyelf/voltius-zh-CN
- **官方网站**: https://voltius.app
- **官方订阅**: https://voltius.app/pricing (支持开发者)
- **问题反馈**: https://github.com/iflyelf/voltius-zh-CN/issues

---

**最后更新**: 2026-07-16  
**Voltius 版本**: v0.9.2  
**翻译覆盖率**: 95.1% (2526/2656)  
**服务器版本**: 1.0.0
