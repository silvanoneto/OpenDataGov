package middleware

import (
	"net/http"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
)

// Tracing wraps an http.Handler with OpenTelemetry HTTP instrumentation.
func Tracing(next http.Handler) http.Handler {
	return otelhttp.NewHandler(next, "gateway")
}
