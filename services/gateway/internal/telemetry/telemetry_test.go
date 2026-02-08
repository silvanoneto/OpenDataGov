package telemetry

import (
	"context"
	"testing"
	"time"
)

func TestInit(t *testing.T) {
	ctx := context.Background()

	// Use a non-routable endpoint so it doesn't actually connect
	providers, err := Init(ctx, "gateway-test", "localhost:4317")
	if err != nil {
		t.Fatalf("Init returned error: %v", err)
	}

	if providers == nil {
		t.Fatal("Init returned nil providers")
	}

	if providers.Tracer == nil {
		t.Error("TracerProvider is nil")
	}

	if providers.Meter == nil {
		t.Error("MeterProvider is nil")
	}

	// Shutdown with a short timeout — the OTLP exporter will fail to flush
	// because no collector is running, which is expected in unit tests.
	shutdownCtx, cancel := context.WithTimeout(ctx, 1*time.Second)
	defer cancel()
	_ = providers.Shutdown(shutdownCtx)
}

func TestShutdownNilProviders(t *testing.T) {
	p := &Providers{}
	// Should not panic with nil providers
	if err := p.Shutdown(context.Background()); err != nil {
		t.Errorf("Shutdown returned error: %v", err)
	}
}
