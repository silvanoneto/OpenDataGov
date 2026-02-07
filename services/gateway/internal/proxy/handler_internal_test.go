package proxy

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// TestProxyDisallowedPath verifies that proxyRequest returns 404 for
// paths not in the allowlist.
func TestProxyDisallowedPath(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"id":"should-not-reach"}`))
	}))
	defer backend.Close()

	h, err := NewHandler([]string{backend.URL})
	if err != nil {
		t.Fatalf("NewHandler: %v", err)
	}

	req := httptest.NewRequest(http.MethodPost, "/v1/models", strings.NewReader(`{}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.proxyRequest(w, req)

	if w.Code != http.StatusNotFound {
		t.Fatalf("expected 404 for disallowed path, got %d", w.Code)
	}
}
