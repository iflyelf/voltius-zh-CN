package main

import (
	"encoding/json"
	"net/http"
)

// 获取当前用户信息
func handleGetMe(w http.ResponseWriter, r *http.Request) {
	claims := r.Context().Value("claims").(*JWTClaims)

	var displayName, wrappedSecrets string
	var publicKey []byte
	err := db.QueryRow(`
		SELECT COALESCE(display_name, ''), COALESCE(wrapped_user_secrets, ''), COALESCE(public_key, x'')
		FROM accounts WHERE account_id = ?
	`, claims.AccountID).Scan(&displayName, &wrappedSecrets, &publicKey)

	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}

	respondJSON(w, map[string]interface{}{
		"account_id":           claims.AccountID,
		"email":                claims.Email,
		"tier":                 "pro", // 硬编码
		"display_name":         displayName,
		"wrapped_user_secrets": wrappedSecrets,
		"public_key":           bytesToHex(publicKey),
		"email_verified":       true,
	})
}

// 更新公钥
func handlePutPublicKey(w http.ResponseWriter, r *http.Request) {
	claims := r.Context().Value("claims").(*JWTClaims)

	var req struct {
		PublicKey string `json:"public_key"` // hex
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request")
		return
	}

	_, err := db.Exec(`
		UPDATE accounts SET public_key = ? WHERE account_id = ?
	`, hexToBytes(req.PublicKey), claims.AccountID)

	if err != nil {
		respondError(w, http.StatusInternalServerError, "update failed")
		return
	}

	w.WriteHeader(http.StatusOK)
}

// 获取订阅信息 (硬编码 Pro)
func handleGetSubscription(w http.ResponseWriter, r *http.Request) {
	claims := r.Context().Value("claims").(*JWTClaims)

	respondJSON(w, map[string]interface{}{
		"account_id": claims.AccountID,
		"tier":       "pro",
		"active":     true,
		"expires_at": nil, // 永不过期
	})
}
