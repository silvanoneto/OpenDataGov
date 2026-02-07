package proxy_test

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/silvanoneto/OpenDataGov/services/gateway/internal/health"
	"github.com/silvanoneto/OpenDataGov/services/gateway/internal/proxy"
)

const (
	contentType         = "Content-Type"
	applicationJSON     = "application/json"
	textEventStream     = "text/event-stream"
	headerUserAgent     = "User-Agent"
	chatCompletionsPath = "/v1/chat/completions"
	testRequestBody     = `{"model":"test","messages":[{"role":"user","content":"hi"}]}`
	errNewHandler       = "NewHandler: %v"
	errExpected200      = "expected 200, got %d"
	errParseResponse    = "failed to parse response: %v"
)

// TestRoundRobinSelectsBackendsInOrder verifies that successive requests
// are forwarded to backends in round-robin order.
func TestRoundRobinSelectsBackendsInOrder(t *testing.T) {
	// Track which backends received requests.
	var received []int

	backend0 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		received = append(received, 0)
		w.Header().Set(contentType, applicationJSON)
		_, _ = w.Write([]byte(`{"id":"0"}`))
	}))
	defer backend0.Close()

	backend1 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		received = append(received, 1)
		w.Header().Set(contentType, applicationJSON)
		_, _ = w.Write([]byte(`{"id":"1"}`))
	}))
	defer backend1.Close()

	backend2 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		received = append(received, 2)
		w.Header().Set(contentType, applicationJSON)
		_, _ = w.Write([]byte(`{"id":"2"}`))
	}))
	defer backend2.Close()

	h, err := proxy.NewHandler([]string{backend0.URL, backend1.URL, backend2.URL})
	if err != nil {
		t.Fatalf(errNewHandler, err)
	}
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	body := testRequestBody

	// Send 6 requests; expect 0,1,2,0,1,2.
	for i := range 6 {
		req := httptest.NewRequest(http.MethodPost, chatCompletionsPath, strings.NewReader(body))
		req.Header.Set(contentType, applicationJSON)
		w := httptest.NewRecorder()
		mux.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			t.Fatalf("request %d: expected 200, got %d", i, w.Code)
		}
	}

	expected := []int{0, 1, 2, 0, 1, 2}
	if len(received) != len(expected) {
		t.Fatalf("expected %d requests, got %d", len(expected), len(received))
	}
	for i, want := range expected {
		if received[i] != want {
			t.Errorf("request %d: expected backend %d, got %d", i, want, received[i])
		}
	}
}

// TestProxyNoBackends verifies that the proxy returns 502 when no
// backends are configured.
func TestProxyNoBackends(t *testing.T) {
	h, err := proxy.NewHandler(nil)
	if err != nil {
		t.Fatalf(errNewHandler, err)
	}
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	body := testRequestBody
	req := httptest.NewRequest(http.MethodPost, chatCompletionsPath, strings.NewReader(body))
	req.Header.Set(contentType, applicationJSON)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusBadGateway {
		t.Fatalf("expected 502, got %d", w.Code)
	}
}

// TestProxyStreaming verifies that the proxy correctly forwards an SSE
// streaming response from the backend.
func TestProxyStreaming(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set(contentType, textEventStream)
		w.Header().Set("Cache-Control", "no-cache")
		w.Header().Set("Connection", "keep-alive")
		flusher, ok := w.(http.Flusher)
		if !ok {
			t.Fatal("expected http.Flusher")
		}

		for _, chunk := range []string{
			"data: {\"choices\":[{\"delta\":{\"content\":\"Hello\"}}]}\n\n",
			"data: {\"choices\":[{\"delta\":{\"content\":\" World\"}}]}\n\n",
			"data: [DONE]\n\n",
		} {
			_, _ = w.Write([]byte(chunk))
			flusher.Flush()
		}
	}))
	defer backend.Close()

	h, err := proxy.NewHandler([]string{backend.URL})
	if err != nil {
		t.Fatalf(errNewHandler, err)
	}
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	body := `{"model":"test","messages":[{"role":"user","content":"hi"}],"stream":true}`
	req := httptest.NewRequest(http.MethodPost, chatCompletionsPath, strings.NewReader(body))
	req.Header.Set(contentType, applicationJSON)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf(errExpected200, w.Code)
	}

	if ct := w.Header().Get(contentType); ct != textEventStream {
		t.Errorf("expected Content-Type text/event-stream, got %s", ct)
	}

	respBody := w.Body.String()
	if !strings.Contains(respBody, "Hello") || !strings.Contains(respBody, "World") {
		t.Errorf("response body missing expected chunks: %s", respBody)
	}
	if !strings.Contains(respBody, "[DONE]") {
		t.Errorf("response body missing [DONE]: %s", respBody)
	}
}

// TestProxyQueryStringForwarding verifies that query parameters are
// preserved when proxying requests to the backend.
func TestProxyQueryStringForwarding(t *testing.T) {
	var receivedURL string
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedURL = r.URL.String()
		w.Header().Set(contentType, applicationJSON)
		_, _ = w.Write([]byte(`{"id":"qs"}`))
	}))
	defer backend.Close()

	h, err := proxy.NewHandler([]string{backend.URL})
	if err != nil {
		t.Fatalf(errNewHandler, err)
	}
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	body := testRequestBody
	req := httptest.NewRequest(http.MethodPost, "/v1/chat/completions?stream=true&model=foo", strings.NewReader(body))
	req.Header.Set(contentType, applicationJSON)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf(errExpected200, w.Code)
	}
	if !strings.Contains(receivedURL, "stream=true") || !strings.Contains(receivedURL, "model=foo") {
		t.Errorf("expected query string forwarded, got URL: %s", receivedURL)
	}
}

// TestProxyBackendUnavailable verifies that the proxy returns 502
// when the backend is unreachable.
func TestProxyBackendUnavailable(t *testing.T) {
	// Bind a listener and close it immediately to get an unused port.
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("failed to get free port: %v", err)
	}
	addr := ln.Addr().String()
	_ = ln.Close()

	h, err := proxy.NewHandler([]string{"http://" + addr})
	if err != nil {
		t.Fatalf(errNewHandler, err)
	}
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	body := testRequestBody
	req := httptest.NewRequest(http.MethodPost, chatCompletionsPath, strings.NewReader(body))
	req.Header.Set(contentType, applicationJSON)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusBadGateway {
		t.Fatalf("expected 502, got %d", w.Code)
	}
	if !strings.Contains(w.Body.String(), "backend unavailable") {
		t.Errorf("expected 'backend unavailable' in body, got: %s", w.Body.String())
	}
}

// TestProxyUnparsableBackendURL verifies that NewHandler rejects
// unparsable backend URLs.
func TestProxyUnparsableBackendURL(t *testing.T) {
	_, err := proxy.NewHandler([]string{":%invalid"})
	if err == nil {
		t.Fatal("expected error for unparsable backend URL")
	}
}

// TestProxyInvalidBackendURL verifies that NewHandler rejects
// backend URLs with unsupported schemes or invalid hosts.
func TestProxyInvalidBackendURL(t *testing.T) {
	_, err := proxy.NewHandler([]string{"ftp://example.com"})
	if err == nil {
		t.Fatal("expected error for unsupported scheme")
	}
}

// TestProxyMissingHostBackendURL verifies that NewHandler rejects
// backend URLs that have no host component.
func TestProxyMissingHostBackendURL(t *testing.T) {
	_, err := proxy.NewHandler([]string{"http://"})
	if err == nil {
		t.Fatal("expected error for missing host")
	}
}


// TestProxyCompletionsEndpoint verifies that POST /v1/completions is
// proxied correctly (not just /v1/chat/completions).
func TestProxyCompletionsEndpoint(t *testing.T) {
	var receivedPath string
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedPath = r.URL.Path
		w.Header().Set(contentType, applicationJSON)
		_, _ = w.Write([]byte(`{"id":"comp"}`))
	}))
	defer backend.Close()

	h, err := proxy.NewHandler([]string{backend.URL})
	if err != nil {
		t.Fatalf(errNewHandler, err)
	}
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	body := `{"model":"test","prompt":"Hello"}`
	req := httptest.NewRequest(http.MethodPost, "/v1/completions", strings.NewReader(body))
	req.Header.Set(contentType, applicationJSON)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf(errExpected200, w.Code)
	}
	if receivedPath != "/v1/completions" {
		t.Errorf("expected path /v1/completions, got %s", receivedPath)
	}
}

// TestProxyHeaderForwarding verifies that Authorization, Accept, and
// User-Agent headers are forwarded to the backend.
func TestProxyHeaderForwarding(t *testing.T) {
	var headers http.Header
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		headers = r.Header
		w.Header().Set(contentType, applicationJSON)
		_, _ = w.Write([]byte(`{"id":"hdr"}`))
	}))
	defer backend.Close()

	h, err := proxy.NewHandler([]string{backend.URL})
	if err != nil {
		t.Fatalf(errNewHandler, err)
	}
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	body := testRequestBody
	req := httptest.NewRequest(http.MethodPost, chatCompletionsPath, strings.NewReader(body))
	req.Header.Set(contentType, applicationJSON)
	req.Header.Set("Authorization", "Bearer sk-test-123")
	req.Header.Set("Accept", textEventStream)
	req.Header.Set(headerUserAgent, "test-agent/1.0")
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf(errExpected200, w.Code)
	}
	if headers.Get("Authorization") != "Bearer sk-test-123" {
		t.Errorf("Authorization not forwarded: %s", headers.Get("Authorization"))
	}
	if headers.Get("Accept") != textEventStream {
		t.Errorf("Accept not forwarded: %s", headers.Get("Accept"))
	}
	if headers.Get(headerUserAgent) != "test-agent/1.0" {
		t.Errorf("User-Agent not forwarded: %s", headers.Get(headerUserAgent))
	}
}

// TestProxyNonEOFReadError verifies that the proxy handles non-EOF
// read errors from the backend gracefully.
func TestProxyNonEOFReadError(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set(contentType, applicationJSON)
		// Write partial response then close connection abruptly by
		// hijacking the connection.
		hj, ok := w.(http.Hijacker)
		if !ok {
			t.Fatal("expected http.Hijacker")
		}
		// Write headers manually before hijack.
		w.WriteHeader(http.StatusOK)
		conn, buf, err := hj.Hijack()
		if err != nil {
			t.Fatalf("hijack failed: %v", err)
		}
		_, _ = buf.WriteString(`{"partial":`)
		_ = buf.Flush()
		// Close without completing the JSON — causes a read error on the proxy side.
		_ = conn.Close()
	}))
	defer backend.Close()

	h, err := proxy.NewHandler([]string{backend.URL})
	if err != nil {
		t.Fatalf(errNewHandler, err)
	}
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	body := testRequestBody
	req := httptest.NewRequest(http.MethodPost, chatCompletionsPath, strings.NewReader(body))
	req.Header.Set(contentType, applicationJSON)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	// The proxy should still return the partial data it received
	// (the status code was already written as 200 by the backend).
	// We just verify it doesn't panic.
	_ = w.Body.String()
}

// failWriter is an http.ResponseWriter that fails on Write after headers
// are written. It wraps a real ResponseWriter for Header() and WriteHeader().
type failWriter struct {
	http.ResponseWriter
	headerWritten bool
}

func (fw *failWriter) WriteHeader(code int) {
	fw.headerWritten = true
	fw.ResponseWriter.WriteHeader(code)
}

func (fw *failWriter) Write(b []byte) (int, error) {
	if fw.headerWritten {
		return 0, errors.New("simulated write error")
	}
	return fw.ResponseWriter.Write(b)
}

func (fw *failWriter) Flush() {
	// Intentionally empty: satisfies http.Flusher so the proxy enters the streaming path.
}

// TestProxyWriteError verifies that the proxy handles write errors
// to the client gracefully without panicking.
func TestProxyWriteError(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set(contentType, applicationJSON)
		_, _ = w.Write([]byte(`{"id":"write-err","choices":[]}`))
	}))
	defer backend.Close()

	h, err := proxy.NewHandler([]string{backend.URL})
	if err != nil {
		t.Fatalf(errNewHandler, err)
	}
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	body := testRequestBody
	req := httptest.NewRequest(http.MethodPost, chatCompletionsPath, strings.NewReader(body))
	req.Header.Set(contentType, applicationJSON)

	// Use the failWriter so that Write() returns an error after headers.
	recorder := httptest.NewRecorder()
	fw := &failWriter{ResponseWriter: recorder}
	mux.ServeHTTP(fw, req)

	// No assertion needed — the test passes if the proxy doesn't panic.
}

// TestHealthEndpointReturnsOK verifies that GET /health returns 200
// with {"status":"ok"}.
func TestHealthEndpointReturnsOK(t *testing.T) {
	h := health.NewHandler(nil)
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf(errExpected200, w.Code)
	}

	body, _ := io.ReadAll(w.Body)
	var result map[string]string
	if err := json.Unmarshal(body, &result); err != nil {
		t.Fatalf(errParseResponse, err)
	}
	if result["status"] != "ok" {
		t.Errorf("expected status ok, got %s", result["status"])
	}
}

// TestReadyReturns503WhenNoBackends verifies that GET /ready returns
// 503 when no backends are configured.
func TestReadyReturns503WhenNoBackends(t *testing.T) {
	h := health.NewHandler(nil)
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	req := httptest.NewRequest(http.MethodGet, "/ready", nil)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected 503, got %d", w.Code)
	}

	body, _ := io.ReadAll(w.Body)
	var result map[string]string
	if err := json.Unmarshal(body, &result); err != nil {
		t.Fatalf(errParseResponse, err)
	}
	if result["status"] != "not ready" {
		t.Errorf("expected status 'not ready', got %s", result["status"])
	}
}

// TestReadyReturns200WhenBackendHealthy verifies that GET /ready
// returns 200 when at least one backend is reachable.
func TestReadyReturns200WhenBackendHealthy(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()

	h := health.NewHandler([]string{backend.URL})
	mux := http.NewServeMux()
	h.RegisterRoutes(mux)

	// Run the background checker once so the backend is marked healthy.
	ctx, cancel := context.WithCancel(context.Background())
	h.StartBackgroundChecker(ctx)
	cancel()

	req := httptest.NewRequest(http.MethodGet, "/ready", nil)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf(errExpected200, w.Code)
	}

	body, _ := io.ReadAll(w.Body)
	var result map[string]string
	if err := json.Unmarshal(body, &result); err != nil {
		t.Fatalf(errParseResponse, err)
	}
	if result["status"] != "ready" {
		t.Errorf("expected status 'ready', got %s", result["status"])
	}
}
