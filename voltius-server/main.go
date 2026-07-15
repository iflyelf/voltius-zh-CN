package main

import (
	"flag"
	"log"
	"net/http"
	"os"
	"time"
)

var (
	port      = flag.String("port", "8080", "服务器端口")
	dbPath    = flag.String("db", "./voltius.db", "SQLite 数据库路径")
	jwtSecret = flag.String("jwt-secret", "", "JWT 签名密钥 (留空自动生成)")
)

func main() {
	flag.Parse()

	// 初始化 JWT 密钥
	if *jwtSecret == "" {
		*jwtSecret = generateRandomSecret()
		log.Printf("⚠️ 未指定 JWT 密钥，自动生成: %s", *jwtSecret)
		log.Printf("   建议保存此密钥，重启后使用 -jwt-secret 参数指定")
	}

	// 初始化数据库
	if err := initDB(*dbPath); err != nil {
		log.Fatalf("❌ 数据库初始化失败: %v", err)
	}
	log.Printf("✅ 数据库就绪: %s", *dbPath)

	// 初始化 SSE 管理器
	initSSE()

	// 路由
	mux := http.NewServeMux()
	
	// CORS 中间件
	handler := corsMiddleware(mux)
	
	// 认证端点
	mux.HandleFunc("POST /v1/auth/register", handleRegister)
	mux.HandleFunc("GET /v1/auth/challenge", handleChallenge)
	mux.HandleFunc("POST /v1/auth/login", handleLogin)
	mux.HandleFunc("POST /v1/auth/refresh", handleRefresh)
	mux.HandleFunc("GET /v1/auth/me", requireAuth(handleGetMe))
	mux.HandleFunc("PUT /v1/auth/public-key", requireAuth(handlePutPublicKey))
	
	// 同步端点
	mux.HandleFunc("GET /v1/sync/blob", requireAuth(handleGetBlob))
	mux.HandleFunc("PUT /v1/sync/blob", requireAuth(handlePutBlob))
	mux.HandleFunc("GET /v1/sync/devices", requireAuth(handleGetDevices))
	mux.HandleFunc("GET /v1/sync/stream", requireAuth(handleSSE))
	
	// 订阅端点 (返回硬编码 Pro)
	mux.HandleFunc("GET /v1/billing/subscription", requireAuth(handleGetSubscription))

	log.Printf("🚀 Voltius 服务器启动: http://0.0.0.0:%s", *port)
	log.Printf("📖 API 文档: https://github.com/iflyelf/voltius-zh-CN")
	
	srv := &http.Server{
		Addr:         ":" + *port,
		Handler:      handler,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
	}
	
	if err := srv.ListenAndServe(); err != nil {
		log.Fatalf("❌ 服务器启动失败: %v", err)
	}
}

// CORS 中间件
func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		
		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}
		
		next.ServeHTTP(w, r)
	})
}

// 生成随机密钥
func generateRandomSecret() string {
	b := make([]byte, 32)
	if _, err := os.ReadFile("/dev/urandom"); err == nil {
		f, _ := os.Open("/dev/urandom")
		defer f.Close()
		f.Read(b)
	}
	return string(b)
}
