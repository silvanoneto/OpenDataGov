package proxy

import (
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"path"
	"sync/atomic"
	"time"
)

// Handler proxies OpenAI-compatible requests to vLLM backends using
// round-robin load balancing. It supports streaming (SSE) responses
// for chat completions.
type Handler struct {
	backends []*url.URL
	counter  atomic.Uint64
}

// NewHandler creates a proxy handler with the given backend URLs.
// It validates and parses all URLs upfront, returning an error if any
// backend URL is malformed or uses an unsupported scheme.
func NewHandler(backends []string) (*Handler, error) {
	parsed := make([]*url.URL, 0, len(backends))
	for _, raw := range backends {
		u, err := url.Parse(raw)
		if err != nil {
			return nil, fmt.Errorf("invalid backend URL %q: %w", raw, err)
		}
		if u.Scheme != "http" && u.Scheme != "https" {
			return nil, fmt.Errorf("unsupported scheme in backend URL %q: %s", raw, u.Scheme)
		}
		if u.Host == "" {
			return nil, fmt.Errorf("missing host in backend URL %q", raw)
		}
		parsed = append(parsed, u)
	}
	return &Handler{
		backends: parsed,
	}, nil
}

// RegisterRoutes registers the proxy routes on the given mux.
func (h *Handler) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("POST /v1/chat/completions", h.proxyRequest)
	mux.HandleFunc("POST /v1/completions", h.proxyRequest)
}

// selectBackend returns the next backend URL using round-robin selection.
// It returns nil if no backends are configured.
func (h *Handler) selectBackend() *url.URL {
	n := len(h.backends)
	if n == 0 {
		return nil
	}
	idx := h.counter.Add(1) - 1
	return h.backends[idx%uint64(n)]
}

// allowedPaths is the set of upstream paths the proxy is willing to forward.
var allowedPaths = map[string]bool{
	"/v1/chat/completions": true,
	"/v1/completions":      true,
}

// proxyRequest forwards the incoming request to a selected vLLM backend
// and streams the response back to the client. It preserves headers so
// that Server-Sent Events (SSE) streaming works correctly.
func (h *Handler) proxyRequest(w http.ResponseWriter, r *http.Request) {
	backend := h.selectBackend()
	if backend == nil {
		http.Error(w, `{"error":"no backends configured"}`, http.StatusBadGateway)
		return
	}

	cleanPath := path.Clean(r.URL.Path)
	if !allowedPaths[cleanPath] {
		http.Error(w, `{"error":"not found"}`, http.StatusNotFound)
		return
	}

	// Build the upstream URL from the pre-validated backend, overriding
	// only the path and query with sanitised values.
	upstream := url.URL{
		Scheme:   backend.Scheme,
		Host:     backend.Host,
		Path:     cleanPath,
		RawQuery: r.URL.Query().Encode(),
	}

	// NewRequestWithContext cannot fail here: the URL is assembled from
	// pre-validated scheme/host and an allow-listed path.
	upstreamReq, _ := http.NewRequestWithContext(r.Context(), r.Method, upstream.String(), r.Body)
	copyRequestHeaders(r, upstreamReq)

	// Perform the upstream request. The timeout covers the header wait;
	// streaming bodies are bounded by the request context.
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(upstreamReq)
	if err != nil {
		log.Printf("proxy: upstream request failed: %v", err)
		http.Error(w, `{"error":"backend unavailable"}`, http.StatusBadGateway)
		return
	}
	defer func() { _ = resp.Body.Close() }()

	copyResponseHeaders(resp, w)
	w.WriteHeader(resp.StatusCode)
	streamBody(resp.Body, w)
}

// copyRequestHeaders copies relevant headers from the original request
// to the upstream request.
func copyRequestHeaders(src, dst *http.Request) {
	for _, key := range []string{"Content-Type", "Authorization", "Accept", "User-Agent"} {
		if v := src.Header.Get(key); v != "" {
			dst.Header.Set(key, v)
		}
	}
}

// copyResponseHeaders copies all response headers from the upstream
// response to the client writer. This preserves Content-Type
// (e.g. text/event-stream for SSE) so streaming works transparently.
func copyResponseHeaders(resp *http.Response, w http.ResponseWriter) {
	for key, values := range resp.Header {
		for _, v := range values {
			w.Header().Add(key, v)
		}
	}
}

// streamBody streams the response body to the client, flushing after
// each chunk for SSE support.
func streamBody(src io.Reader, w http.ResponseWriter) {
	flusher, canFlush := w.(http.Flusher)
	buf := make([]byte, 4096)
	for {
		n, readErr := src.Read(buf)
		if n > 0 {
			if _, writeErr := w.Write(buf[:n]); writeErr != nil {
				log.Printf("proxy: failed to write response: %v", writeErr)
				return
			}
			if canFlush {
				flusher.Flush()
			}
		}
		if readErr != nil {
			if readErr != io.EOF {
				log.Printf("proxy: error reading upstream response: %v", readErr)
			}
			break
		}
	}
}
