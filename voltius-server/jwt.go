package main

import (
	"fmt"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
)

type JWTClaims struct {
	AccountID string `json:"sub"`
	Email     string `json:"email"`
	Tier      string `json:"tier"` // 硬编码 "pro"
	jwt.RegisteredClaims
}

// 生成 JWT token (硬编码 tier="pro")
func generateJWT(accountID, email string) (string, error) {
	claims := JWTClaims{
		AccountID: accountID,
		Email:     email,
		Tier:      "pro", // 🔓 硬编码 Pro 订阅
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(24 * time.Hour)),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
			Issuer:    "voltius-selfhosted",
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString([]byte(*jwtSecret))
}

// 生成 Refresh Token
func generateRefreshToken(accountID string) (string, string, error) {
	tokenID := uuid.New().String()
	refreshToken := uuid.New().String() + uuid.New().String() // 72 字符

	expiresAt := time.Now().Add(30 * 24 * time.Hour) // 30 天

	_, err := db.Exec(`
		INSERT INTO refresh_tokens (token_id, account_id, refresh_token, expires_at)
		VALUES (?, ?, ?, ?)
	`, tokenID, accountID, refreshToken, expiresAt)

	return refreshToken, tokenID, err
}

// 验证 JWT token
func verifyJWT(tokenString string) (*JWTClaims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &JWTClaims{}, func(token *jwt.Token) (interface{}, error) {
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return []byte(*jwtSecret), nil
	})

	if err != nil {
		return nil, err
	}

	if claims, ok := token.Claims.(*JWTClaims); ok && token.Valid {
		return claims, nil
	}

	return nil, fmt.Errorf("invalid token")
}
