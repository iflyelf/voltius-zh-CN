package main

import (
	"database/sql"
	"log"

	_ "modernc.org/sqlite"
)

var db *sql.DB

func initDB(path string) error {
	var err error
	db, err = sql.Open("sqlite3", path+"?_busy_timeout=5000&_journal_mode=WAL")
	if err != nil {
		return err
	}

	// 创建表
	schema := `
	CREATE TABLE IF NOT EXISTS accounts (
		account_id TEXT PRIMARY KEY,
		email TEXT UNIQUE NOT NULL,
		auth_key BLOB NOT NULL,
		public_key BLOB,
		wrapped_user_secrets TEXT,
		display_name TEXT,
		email_verified BOOLEAN DEFAULT 1,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	);

	CREATE TABLE IF NOT EXISTS refresh_tokens (
		token_id TEXT PRIMARY KEY,
		account_id TEXT NOT NULL,
		refresh_token TEXT UNIQUE NOT NULL,
		expires_at TIMESTAMP,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		FOREIGN KEY (account_id) REFERENCES accounts(account_id)
	);

	CREATE TABLE IF NOT EXISTS sync_blobs (
		account_id TEXT NOT NULL,
		device_id TEXT NOT NULL,
		blob BLOB NOT NULL,
		metadata TEXT,
		updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		PRIMARY KEY (account_id, device_id),
		FOREIGN KEY (account_id) REFERENCES accounts(account_id)
	);

	CREATE INDEX IF NOT EXISTS idx_refresh_tokens_account 
	ON refresh_tokens(account_id);
	`

	_, err = db.Exec(schema)
	if err != nil {
		return err
	}

	log.Println("✅ 数据库表创建/验证完成")
	return nil
}
