package config

import (
	"os"
	"strconv"
	"strings"
)

// Config holds the gateway configuration.
type Config struct {
	Port     int
	Backends []string
}

// LoadFromEnv reads configuration from environment variables.
//
// GATEWAY_PORT: the port to listen on (default 8080).
// VLLM_BACKENDS: comma-separated list of vLLM backend URLs
// (e.g. "http://localhost:8000,http://localhost:8001").
func LoadFromEnv() Config {
	port := 8080
	if v := os.Getenv("GATEWAY_PORT"); v != "" {
		if p, err := strconv.Atoi(v); err == nil && p > 0 {
			port = p
		}
	}

	var backends []string
	if v := os.Getenv("VLLM_BACKENDS"); v != "" {
		for _, b := range strings.Split(v, ",") {
			b = strings.TrimSpace(b)
			if b != "" {
				backends = append(backends, b)
			}
		}
	}

	return Config{
		Port:     port,
		Backends: backends,
	}
}
