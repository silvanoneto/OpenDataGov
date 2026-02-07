package health_test

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/silvanoneto/OpenDataGov/services/gateway/internal/health"
)

// errWriter is an http.ResponseWriter whose Write always fails.
type errWriter struct {
	header http.Header
}

func (ew *errWriter) Header() http.Header        { return ew.header }
func (ew *errWriter) WriteHeader(int)             { /* no-op for test stub */ }
func (ew *errWriter) Write([]byte) (int, error)   { return 0, errors.New("write failed") }

const (
	readyPath      = "/ready"
	errExpected503 = "expected 503, got %d"
)

func TestHealthEndpoint(t *testing.T) {
	h := health.NewHandler(nil)
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	body, _ := io.ReadAll(w.Body)
	var result map[string]string
	if err := json.Unmarshal(body, &result); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if result["status"] != "ok" {
		t.Errorf("expected status ok, got %s", result["status"])
	}
}

func TestReadyNoBackends(t *testing.T) {
	h := health.NewHandler(nil)
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	req := httptest.NewRequest(http.MethodGet, readyPath, nil)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusServiceUnavailable {
		t.Fatalf(errExpected503, w.Code)
	}
}

func TestReadyWithHealthyBackend(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()

	h := health.NewHandler([]string{backend.URL})
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	// Run background checker (initial check marks backend healthy)
	ctx, cancel := context.WithCancel(context.Background())
	h.StartBackgroundChecker(ctx)
	cancel() // stop the ticker goroutine

	req := httptest.NewRequest(http.MethodGet, readyPath, nil)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	body, _ := io.ReadAll(w.Body)
	var result map[string]string
	if err := json.Unmarshal(body, &result); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if result["status"] != "ready" {
		t.Errorf("expected 'ready', got %s", result["status"])
	}
}

func TestReadyWithUnhealthyBackend(t *testing.T) {
	// Backend that returns 500
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer backend.Close()

	h := health.NewHandler([]string{backend.URL})
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	ctx, cancel := context.WithCancel(context.Background())
	h.StartBackgroundChecker(ctx)
	cancel()

	req := httptest.NewRequest(http.MethodGet, readyPath, nil)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusServiceUnavailable {
		t.Fatalf(errExpected503, w.Code)
	}
}

func TestHealthEncodeError(t *testing.T) {
	h := health.NewHandler(nil)
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	ew := &errWriter{header: make(http.Header)}
	mux.ServeHTTP(ew, req)
	// Pass: the handler logs the error without panicking.
}

func TestReadyEncodeError(t *testing.T) {
	h := health.NewHandler(nil)
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	req := httptest.NewRequest(http.MethodGet, readyPath, nil)
	ew := &errWriter{header: make(http.Header)}
	mux.ServeHTTP(ew, req)
	// Pass: the handler logs the error without panicking.
}

func TestReadyWithUnreachableBackend(t *testing.T) {
	h := health.NewHandler([]string{"http://127.0.0.1:1"}) // port 1 — unreachable
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	ctx, cancel := context.WithCancel(context.Background())
	h.StartBackgroundChecker(ctx)
	cancel()

	req := httptest.NewRequest(http.MethodGet, readyPath, nil)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusServiceUnavailable {
		t.Fatalf(errExpected503, w.Code)
	}
}
