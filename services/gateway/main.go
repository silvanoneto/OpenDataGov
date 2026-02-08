package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/silvanoneto/OpenDataGov/services/gateway/internal/config"
	"github.com/silvanoneto/OpenDataGov/services/gateway/internal/health"
	"github.com/silvanoneto/OpenDataGov/services/gateway/internal/middleware"
	"github.com/silvanoneto/OpenDataGov/services/gateway/internal/proxy"
	"github.com/silvanoneto/OpenDataGov/services/gateway/internal/telemetry"
)

func main() {
	cfg := config.LoadFromEnv()

	log.Printf("gateway: starting on port %d with %d backend(s)", cfg.Port, len(cfg.Backends))
	for i, b := range cfg.Backends {
		log.Printf("gateway: backend[%d] = %s", i, b)
	}

	// Initialize OpenTelemetry.
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	otelProviders, err := telemetry.Init(ctx, "gateway", cfg.OTelEndpoint)
	if err != nil {
		log.Printf("gateway: OTel init failed (continuing without telemetry): %v", err)
	} else {
		log.Printf("gateway: OTel initialized → %s", cfg.OTelEndpoint)
	}

	mux := http.NewServeMux()

	// Register proxy routes.
	proxyHandler, err := proxy.NewHandler(cfg.Backends)
	if err != nil {
		log.Fatalf("gateway: invalid backend configuration: %v", err)
	}
	proxyHandler.RegisterRoutes(mux)

	// Register health/readiness routes.
	healthHandler := health.NewHandler(cfg.Backends)
	healthHandler.RegisterRoutes(mux)

	// Start background health checker.
	healthHandler.StartBackgroundChecker(ctx)

	// Wrap the mux with tracing and logging middleware.
	handler := middleware.Logging(middleware.Tracing(mux))

	server := &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.Port),
		Handler:      handler,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 120 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start the server in a goroutine.
	errCh := make(chan error, 1)
	go func() {
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			errCh <- err
		}
		close(errCh)
	}()

	log.Printf("gateway: listening on %s", server.Addr)

	// Wait for interrupt signal or server error.
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	select {
	case sig := <-sigCh:
		log.Printf("gateway: received signal %s, shutting down", sig)
	case err := <-errCh:
		if err != nil {
			log.Printf("gateway: server error: %v", err)
		}
	}

	// Graceful shutdown with a 15-second deadline.
	cancel()
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer shutdownCancel()

	if err := server.Shutdown(shutdownCtx); err != nil {
		log.Printf("gateway: shutdown error: %v", err)
		os.Exit(1)
	}

	if otelProviders != nil {
		if err := otelProviders.Shutdown(shutdownCtx); err != nil {
			log.Printf("gateway: OTel shutdown error: %v", err)
		}
	}

	log.Println("gateway: stopped")
}
