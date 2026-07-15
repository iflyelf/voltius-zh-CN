#!/bin/bash
set -e

echo "🔨 编译 Voltius 服务器 (CGO_ENABLED=0 静态二进制)"
echo ""

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 配置 Go 代理和环境
export GOPATH=${GOPATH:-$HOME/go}
export GOCACHE=${GOCACHE:-$HOME/.cache/go-build}
export GOPROXY=${GOPROXY:-https://goproxy.cn,https://proxy.golang.org,direct}

# 下载依赖 (带重试)
echo "📦 下载 Go 依赖..."
for i in {1..5}; do
    echo "  尝试 $i/5..."
    if go mod download; then
        echo -e "${GREEN}  ✅ 依赖下载完成${NC}"
        break
    else
        if [ $i -lt 5 ]; then
            echo -e "${YELLOW}  ⚠️ 下载失败，3秒后重试...${NC}"
            sleep 3
        else
            echo "  ❌ 依赖下载失败，请检查网络或手动运行: go mod download"
            exit 1
        fi
    fi
done

echo ""

# 编译信息
VERSION="1.0.0"
BUILD_TIME=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

LDFLAGS="-s -w -X 'main.Version=$VERSION' -X 'main.BuildTime=$BUILD_TIME' -X 'main.GitCommit=$GIT_COMMIT'"

# 创建输出目录
mkdir -p dist

# Linux amd64
echo "🐧 编译 Linux x64..."
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags "$LDFLAGS" -o dist/voltius-server-linux-amd64 .

# Linux arm64
echo "🐧 编译 Linux ARM64..."
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -ldflags "$LDFLAGS" -o dist/voltius-server-linux-arm64 .

# macOS amd64
echo "🍎 编译 macOS Intel..."
CGO_ENABLED=0 GOOS=darwin GOARCH=amd64 go build -ldflags "$LDFLAGS" -o dist/voltius-server-darwin-amd64 .

# macOS arm64
echo "🍎 编译 macOS Apple Silicon..."
CGO_ENABLED=0 GOOS=darwin GOARCH=arm64 go build -ldflags "$LDFLAGS" -o dist/voltius-server-darwin-arm64 .

# Windows amd64
echo "🪟 编译 Windows x64..."
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -ldflags "$LDFLAGS" -o dist/voltius-server-windows-amd64.exe .

echo ""
echo -e "${GREEN}✅ 编译完成!${NC}"
echo ""
echo "📦 产物目录: dist/"
ls -lh dist/
echo ""
echo "🚀 运行示例:"
echo "  ./dist/voltius-server-linux-amd64"
echo "  ./dist/voltius-server-linux-amd64 -port 8080 -jwt-secret your-secret"
