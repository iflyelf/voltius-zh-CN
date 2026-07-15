package main

import (
	"context"
	"fmt"
	"net/http"
	"sync"
	"time"
)

type SSEManager struct {
	clients map[string]map[chan string]bool // accountID -> {channel -> true}
	mu      sync.RWMutex
}

var sseManager *SSEManager

func initSSE() {
	sseManager = &SSEManager{
		clients: make(map[string]map[chan string]bool),
	}
}

// 注册 SSE 客户端
func (m *SSEManager) register(accountID string, ch chan string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.clients[accountID] == nil {
		m.clients[accountID] = make(map[chan string]bool)
	}
	m.clients[accountID][ch] = true
}

// 注销 SSE 客户端
func (m *SSEManager) unregister(accountID string, ch chan string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if clients, ok := m.clients[accountID]; ok {
		delete(clients, ch)
		if len(clients) == 0 {
			delete(m.clients, accountID)
		}
	}
	close(ch)
}

// 发送事件
func (m *SSEManager) notify(accountID, sourceDeviceID, event string) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	
	msg := fmt.Sprintf(`{"event":"%s","device_id":"%s","timestamp":"%s"}`, 
		event, sourceDeviceID, time.Now().Format(time.RFC3339))
	
	if clients, ok := m.clients[accountID]; ok {
		for ch := range clients {
			select {
			case ch <- msg:
			case <-time.After(100 * time.Millisecond):
				// 超时则跳过
			}
		}
	}
}

// SSE 端点
func handleSSE(w http.ResponseWriter, r *http.Request) {
	claims := r.Context().Value("claims").(*JWTClaims)
	_ = r.URL.Query().Get("device_id") // 客户端自行过滤自己的事件

	// 设置 SSE headers
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	flusher, ok := w.(http.Flusher)
	if !ok {
		respondError(w, http.StatusInternalServerError, "streaming unsupported")
		return
	}

	ch := make(chan string, 10)
	sseManager.register(claims.AccountID, ch)
	defer sseManager.unregister(claims.AccountID, ch)

	ctx, cancel := context.WithCancel(r.Context())
	defer cancel()

	// 心跳
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case msg := <-ch:
			// 过滤自己的 device_id 事件
			if msg != "" {
				fmt.Fprintf(w, "data: %s\n\n", msg)
				flusher.Flush()
			}
		case <-ticker.C:
			fmt.Fprintf(w, ": ping\n\n")
			flusher.Flush()
		case <-ctx.Done():
			return
		}
	}
}

// 通知其他设备
func notifySSE(accountID, sourceDeviceID, event string) {
	sseManager.notify(accountID, sourceDeviceID, event)
}
