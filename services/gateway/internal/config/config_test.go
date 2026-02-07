package config_test

import (
	"testing"

	"github.com/silvanoneto/OpenDataGov/services/gateway/internal/config"
)

func TestLoadFromEnvDefaults(t *testing.T) {
	t.Setenv("GATEWAY_PORT", "")
	t.Setenv("VLLM_BACKENDS", "")

	cfg := config.LoadFromEnv()

	if cfg.Port != 8080 {
		t.Errorf("expected default port 8080, got %d", cfg.Port)
	}
	if len(cfg.Backends) != 0 {
		t.Errorf("expected no backends, got %v", cfg.Backends)
	}
}

func TestLoadFromEnvCustomPort(t *testing.T) {
	t.Setenv("GATEWAY_PORT", "9090")

	cfg := config.LoadFromEnv()

	if cfg.Port != 9090 {
		t.Errorf("expected port 9090, got %d", cfg.Port)
	}
}

func TestLoadFromEnvInvalidPort(t *testing.T) {
	t.Setenv("GATEWAY_PORT", "notanumber")

	cfg := config.LoadFromEnv()

	if cfg.Port != 8080 {
		t.Errorf("expected default port 8080 for invalid input, got %d", cfg.Port)
	}
}

func TestLoadFromEnvBackends(t *testing.T) {
	t.Setenv("VLLM_BACKENDS", "http://localhost:8000, http://localhost:8001")

	cfg := config.LoadFromEnv()

	if len(cfg.Backends) != 2 {
		t.Fatalf("expected 2 backends, got %d", len(cfg.Backends))
	}
	if cfg.Backends[0] != "http://localhost:8000" {
		t.Errorf("expected first backend http://localhost:8000, got %s", cfg.Backends[0])
	}
	if cfg.Backends[1] != "http://localhost:8001" {
		t.Errorf("expected second backend http://localhost:8001, got %s", cfg.Backends[1])
	}
}

func TestLoadFromEnvBackendsEmptyEntries(t *testing.T) {
	t.Setenv("VLLM_BACKENDS", "http://a,,http://b,  ,http://c")

	cfg := config.LoadFromEnv()

	if len(cfg.Backends) != 3 {
		t.Fatalf("expected 3 backends (empty entries filtered), got %d: %v", len(cfg.Backends), cfg.Backends)
	}
}
