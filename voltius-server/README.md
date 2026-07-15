# Voltius 自建服务器

Voltius 中文汉化版的自建云同步服务器，Go 语言实现，CGO_ENABLED=0 静态二进制。

## ✨ 特性

- 🔐 **硬编码 Pro 订阅**：所有用户自动获得 Pro 权限
- 🔒 **端到端加密**：服务器只存储加密数据，无法解密用户内容
- 📦 **静态二进制**：CGO_ENABLED=0 编译，无需依赖，直接运行
- 💾 **SQLite 存储**：轻量级，单文件数据库
- 🚀 **SSE 实时推送**：多设备实时同步
- 🌐 **CORS 支持**：客户端直接访问

## 🚀 快速开始

### 1. 编译

```bash
cd voltius-server
chmod +x build.sh
./build.sh
```

生成产物：
- `voltius-server-linux-amd64` - Linux x64
- `voltius-server-linux-arm64` - Linux ARM64
- `voltius-server-darwin-amd64` - macOS Intel
- `voltius-server-darwin-arm64` - macOS M1/M2/M3
- `voltius-server-windows-amd64.exe` - Windows x64

### 2. 运行

```bash
# 使用默认配置
./voltius-server-linux-amd64

# 自定义配置
./voltius-server-linux-amd64 \
  -port 8080 \
  -db /data/voltius.db \
  -jwt-secret "your-random-secret-change-me"
```

### 3. 客户端配置

打开 Voltius 客户端 → 登录界面 → 点击 "▸ Custom server URL"：

```
http://your-server-ip:8080
```

或 HTTPS（推荐）：

```
https://api.yourdomain.com
```

## 📋 API 端点

### 认证
- `POST /v1/auth/register` - 注册
- `GET /v1/auth/challenge?email=xxx` - 获取 account_id
- `POST /v1/auth/login` - 登录
- `POST /v1/auth/refresh` - 刷新 token
- `GET /v1/auth/me` - 当前用户信息
- `PUT /v1/auth/public-key` - 更新公钥

### 同步
- `GET /v1/sync/blob?device_id=xxx` - 下载数据
- `PUT /v1/sync/blob?device_id=xxx` - 上传数据
- `GET /v1/sync/devices` - 设备列表
- `GET /v1/sync/stream?device_id=xxx` - SSE 实时推送

### 订阅
- `GET /v1/billing/subscription` - 订阅状态（硬编码 Pro）

## 🔐 安全说明

### 端到端加密
所有用户数据经过客户端加密后上传：
1. **密钥派生**：Argon2id(password, salt=account_id)
2. **加密算法**：XChaCha20-Poly1305
3. **服务器存储**：只存储密文 (base64 blob)
4. **服务器无法解密**：密钥从不上传服务器

### Auth Key 验证
- 客户端上传 `auth_key = HKDF-SHA256(master_key, info="auth")`
- 服务器存储 `SHA256(auth_key)`
- 登录时恒定时间比较，防御时序攻击

## 🛠️ 生产部署

### 方案 A：Systemd (Linux)

```bash
# 1. 复制二进制到系统路径
sudo cp voltius-server-linux-amd64 /usr/local/bin/voltius-server
sudo chmod +x /usr/local/bin/voltius-server

# 2. 创建服务文件
sudo tee /etc/systemd/system/voltius-server.service << 'EOF'
[Unit]
Description=Voltius Self-Hosted Server
After=network.target

[Service]
Type=simple
User=voltius
WorkingDirectory=/var/lib/voltius
ExecStart=/usr/local/bin/voltius-server -port 8080 -db /var/lib/voltius/voltius.db -jwt-secret YOUR_SECRET
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

### 方案 B：Nginx 反向代理 + HTTPS

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

### 方案 C：Docker

```dockerfile
FROM scratch
COPY voltius-server-linux-amd64 /voltius-server
EXPOSE 8080
CMD ["/voltius-server", "-port", "8080"]
```

```bash
docker build -t voltius-server .
docker run -d -p 8080:8080 -v /data:/data voltius-server \
  -db /data/voltius.db -jwt-secret YOUR_SECRET
```

## 📊 数据库备份

```bash
# SQLite 热备份
sqlite3 /var/lib/voltius/voltius.db ".backup /backup/voltius-$(date +%Y%m%d).db"

# 定时备份 (crontab)
0 2 * * * sqlite3 /var/lib/voltius/voltius.db ".backup /backup/voltius-$(date +\%Y\%m\%d).db"
```

## 🔧 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-port` | `8080` | 服务器端口 |
| `-db` | `./voltius.db` | SQLite 数据库路径 |
| `-jwt-secret` | 自动生成 | JWT 签名密钥（建议手动指定） |

## 📝 许可证

本服务器代码与 Voltius 客户端配套使用，客户端采用 AGPLv3 开源协议。

## 🙏 致谢

- [Voltius](https://github.com/VoltiusApp/voltius) - 原始 SSH 客户端
- [voltius-zh-CN](https://github.com/iflyelf/voltius-zh-CN) - 中文汉化版
