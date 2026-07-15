package main

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"time"
)

// 上传加密 Blob
func handlePutBlob(w http.ResponseWriter, r *http.Request) {
	claims := r.Context().Value("claims").(*JWTClaims)
	deviceID := r.URL.Query().Get("device_id")

	if deviceID == "" {
		respondError(w, http.StatusBadRequest, "missing device_id")
		return
	}

	var req struct {
		Blob     string                 `json:"blob"`     // base64
		Metadata map[string]interface{} `json:"metadata"` // 可选
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request")
		return
	}

	metadata, _ := json.Marshal(req.Metadata)

	_, err := db.Exec(`
		INSERT INTO sync_blobs (account_id, device_id, blob, metadata, updated_at)
		VALUES (?, ?, ?, ?, ?)
		ON CONFLICT(account_id, device_id) 
		DO UPDATE SET blob = excluded.blob, metadata = excluded.metadata, updated_at = excluded.updated_at
	`, claims.AccountID, deviceID, req.Blob, string(metadata), time.Now())

	if err != nil {
		respondError(w, http.StatusInternalServerError, "upload failed")
		return
	}

	// 通知其他设备
	notifySSE(claims.AccountID, deviceID, "blob_updated")

	w.WriteHeader(http.StatusOK)
}

// 下载加密 Blob
func handleGetBlob(w http.ResponseWriter, r *http.Request) {
	claims := r.Context().Value("claims").(*JWTClaims)
	deviceID := r.URL.Query().Get("device_id")

	if deviceID == "" {
		respondError(w, http.StatusBadRequest, "missing device_id")
		return
	}

	var blob, metadata string
	var updatedAt time.Time
	err := db.QueryRow(`
		SELECT blob, COALESCE(metadata, '{}'), updated_at 
		FROM sync_blobs 
		WHERE account_id = ? AND device_id = ?
	`, claims.AccountID, deviceID).Scan(&blob, &metadata, &updatedAt)

	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "blob not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}

	respondJSON(w, map[string]interface{}{
		"blob":       blob,
		"metadata":   json.RawMessage(metadata),
		"updated_at": updatedAt.Format(time.RFC3339),
	})
}

// 获取设备列表
func handleGetDevices(w http.ResponseWriter, r *http.Request) {
	claims := r.Context().Value("claims").(*JWTClaims)

	rows, err := db.Query(`
		SELECT device_id, updated_at FROM sync_blobs WHERE account_id = ?
	`, claims.AccountID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}
	defer rows.Close()

	devices := []map[string]interface{}{}
	for rows.Next() {
		var deviceID string
		var updatedAt time.Time
		rows.Scan(&deviceID, &updatedAt)
		devices = append(devices, map[string]interface{}{
			"device_id":  deviceID,
			"updated_at": updatedAt.Format(time.RFC3339),
		})
	}

	respondJSON(w, map[string]interface{}{"devices": devices})
}
