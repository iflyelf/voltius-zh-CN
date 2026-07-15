package main

import (
	"crypto/sha256"
	"crypto/subtle"
	"database/sql"
	"encoding/json"
	"net/http"
)

// 登录处理
func handleLogin(w http.ResponseWriter, r *http.Request) {
	var req LoginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request")
		return
	}

	// 查询存储的 auth_key hash
	var storedHash []byte
	var email string
	err := db.QueryRow(`
		SELECT auth_key, email FROM accounts WHERE account_id = ?
	`, req.AccountID).Scan(&storedHash, &email)

	if err == sql.ErrNoRows {
		respondError(w, http.StatusUnauthorized, "invalid credentials")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}

	// 验证 auth_key (恒定时间比较)
	authKeyBytes := hexToBytes(req.AuthKey)
	computedHash := sha256.Sum256(authKeyBytes)
	
	if subtle.ConstantTimeCompare(storedHash, computedHash[:]) != 1 {
		respondError(w, http.StatusUnauthorized, "invalid credentials")
		return
	}

	// 生成 JWT
	jwtToken, err := generateJWT(req.AccountID, email)
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
		"email":         email,
		"tier":          "pro",
	})
}

// 刷新 Token
func handleRefresh(w http.ResponseWriter, r *http.Request) {
	var req struct {
		RefreshToken string `json:"refresh_token"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request")
		return
	}

	var accountID, email string
	err := db.QueryRow(`
		SELECT a.account_id, a.email 
		FROM refresh_tokens rt
		JOIN accounts a ON rt.account_id = a.account_id
		WHERE rt.refresh_token = ? AND rt.expires_at > datetime('now')
	`, req.RefreshToken).Scan(&accountID, &email)

	if err == sql.ErrNoRows {
		respondError(w, http.StatusUnauthorized, "invalid refresh token")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}

	jwtToken, _ := generateJWT(accountID, email)
	newRefreshToken, _, _ := generateRefreshToken(accountID)

	respondJSON(w, map[string]interface{}{
		"jwt_token":     jwtToken,
		"refresh_token": newRefreshToken,
	})
}
