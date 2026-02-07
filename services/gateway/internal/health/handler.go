package health

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"sync"
	"time"
)

const (
	checkInterval     = 30 * time.Second
	clientTimeout     = 5 * time.Second
	healthEndpoint    = "/health"
	errEncodeResponse = "health: failed to encode response: %v"
)

// Handler serves health and readiness endpoints. It runs a background
// goroutine that pings each backend every 30 seconds, and exposes the
// aggregate health through the /ready endpoint.
type Handler struct {
	backends []string

	mu      sync.RWMutex
	healthy map[string]bool // true when the backend last responded 200
}

// NewHandler creates a health handler for the given backend URLs.
func NewHandler(backends []string) *Handler {
	healthy := make(map[string]bool, len(backends))
	for _, b := range backends {
		healthy[b] = false
	}
	return &Handler{
		backends: backends,
		healthy:  healthy,
	}
}

// RegisterRoutes registers the health endpoints on the given mux.
func (h *Handler) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("GET /health", h.handleHealth)
	mux.HandleFunc("GET /ready", h.handleReady)
}

// StartBackgroundChecker launches a goroutine that pings every backend
// every 30 seconds. It stops when the provided context is cancelled.
func (h *Handler) StartBackgroundChecker(ctx context.Context) {
	// Run an initial check immediately so /ready works right away.
	h.checkAll()

	go func() {
		ticker := time.NewTicker(checkInterval)
		defer ticker.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				h.checkAll()
			}
		}
	}()
}

// checkAll pings every backend and updates the healthy map.
func (h *Handler) checkAll() {
	client := &http.Client{Timeout: clientTimeout}

	for _, backend := range h.backends {
		url := backend + healthEndpoint
		resp, err := client.Get(url)
		ok := err == nil && resp.StatusCode == http.StatusOK
		if resp != nil {
			_ = resp.Body.Close()
		}
		if !ok {
			log.Printf("health: backend %s is unhealthy", backend)
		}

		h.mu.Lock()
		h.healthy[backend] = ok
		h.mu.Unlock()
	}
}

// anyHealthy reports whether at least one backend is currently healthy.
func (h *Handler) anyHealthy() bool {
	h.mu.RLock()
	defer h.mu.RUnlock()

	for _, ok := range h.healthy {
		if ok {
			return true
		}
	}
	return false
}

// handleHealth always returns 200 with {"status": "ok"}.
func (h *Handler) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(map[string]string{"status": "ok"}); err != nil {
		log.Printf(errEncodeResponse, err)
	}
}

// handleReady returns 200 with {"status": "ready"} when at least one
// backend is healthy, or 503 with {"status": "not ready"} otherwise.
func (h *Handler) handleReady(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	if len(h.backends) == 0 || !h.anyHealthy() {
		w.WriteHeader(http.StatusServiceUnavailable)
		if err := json.NewEncoder(w).Encode(map[string]string{"status": "not ready"}); err != nil {
			log.Printf(errEncodeResponse, err)
		}
		return
	}

	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(map[string]string{"status": "ready"}); err != nil {
		log.Printf(errEncodeResponse, err)
	}
}
