package main

import (
	"crypto/sha256"
	"database/sql"
	"encoding/json"
	"log"
	"net/http"
	"strings"
)

// 注册请求
type RegisterRequest struct {
	AccountID           string `json:"account_id"`
	Email               string `json:"email"`
	AuthKey             string `json:"auth_key"` // hex
	WrappedUserSecrets  string `json:"wrapped_user_secrets"`
	PublicKey           string `json:"public_key"` // hex
}

// 登录请求
type LoginRequest struct {
	AccountID string `json:"account_id"`
	AuthKey   string `json:"auth_key"` // hex
}

// 注册处理
func handleRegister(w http.ResponseWriter, r *http.Request) {
	var req RegisterRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request")
		return
	}

	// 验证必填字段
	if req.AccountID == "" || req.Email == "" || req.AuthKey == "" {
		respondError(w, http.StatusBadRequest, "missing required fields")
		return
	}

	// 存储 auth_key 的 SHA256 hash
	authKeyBytes := hexToBytes(req.AuthKey)
	authKeyHash := sha256.Sum256(authKeyBytes)

	_, err := db.Exec(`
		INSERT INTO accounts (account_id, email, auth_key, public_key, wrapped_user_secrets)
		VALUES (?, ?, ?, ?, ?)
	`, req.AccountID, req.Email, authKeyHash[:], hexToBytes(req.PublicKey), req.WrappedUserSecrets)

	if err != nil {
		if strings.Contains(err.Error(), "UNIQUE") {
			respondError(w, http.StatusConflict, "account already exists")
			return
		}
		log.Printf("注册失败: %v", err)
		respondError(w, http.StatusInternalServerError, "registration failed")
		return
	}

	// 生成 JWT
	jwtToken, err := generateJWT(req.AccountID, req.Email)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "token generation failed")
		return
	}

	refreshToken, _, err := generateRefreshToken(req.AccountID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "refresh token generation failed")
		return
	}

	respondJSON(w, map[string]interface{}{
		"jwt_token":     jwtToken,
		"refresh_token": refreshToken,
		"account_id":    req.AccountID,
		"email":         req.Email,
		"tier":          "pro", // 硬编码
	})
}

// 获取 account_id (challenge)
func handleChallenge(w http.ResponseWriter, r *http.Request) {
	email := r.URL.Query().Get("email")
	if email == "" {
		respondError(w, http.StatusBadRequest, "missing email")
		return
	}

	var accountID string
	err := db.QueryRow("SELECT account_id FROM accounts WHERE email = ?", email).Scan(&accountID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "account not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}

	respondJSON(w, map[string]string{"account_id": accountID})
}
