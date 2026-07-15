package main

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"strings"
)

// JWT 认证中间件
func requireAuth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		authHeader := r.Header.Get("Authorization")
		if authHeader == "" {
			respondError(w, http.StatusUnauthorized, "missing authorization header")
			return
		}

		parts := strings.Split(authHeader, " ")
		if len(parts) != 2 || parts[0] != "Bearer" {
			respondError(w, http.StatusUnauthorized, "invalid authorization format")
			return
		}

		claims, err := verifyJWT(parts[1])
		if err != nil {
			respondError(w, http.StatusUnauthorized, "invalid token")
			return
		}

		// 注入到 context
		ctx := context.WithValue(r.Context(), "claims", claims)
		next(w, r.WithContext(ctx))
	}
}

// JSON 响应
func respondJSON(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(data)
}

// 错误响应
func respondError(w http.ResponseWriter, status int, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]string{"error": message})
}

// Hex 转字节
func hexToBytes(s string) []byte {
	b, _ := hex.DecodeString(s)
	return b
}

// 字节转 Hex
func bytesToHex(b []byte) string {
	return hex.EncodeToString(b)
}
