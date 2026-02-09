package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/health"
	"google.golang.org/grpc/health/grpc_health_v1"

	pb "github.com/silvanoneto/opendatagov/services/federation-service/proto"
	"github.com/silvanoneto/opendatagov/services/federation-service/server"
)

const (
	defaultPort    = "50060"
	defaultTLSCert = "/certs/tls.crt"
	defaultTLSKey  = "/certs/tls.key"
	defaultCACert  = "/certs/ca.crt"
)

func main() {
	port := os.Getenv("FEDERATION_PORT")
	if port == "" {
		port = defaultPort
	}

	// Initialize Federation Server
	log.Println("Initializing COSMOS Federation Service...")

	federationServer, err := server.NewFederationServer()
	if err != nil {
		log.Fatalf("Failed to create federation server: %v", err)
	}

	// Setup mTLS credentials
	tlsCredentials, err := loadTLSCredentials()
	if err != nil {
		log.Fatalf("Failed to load TLS credentials: %v", err)
	}

	// Create gRPC server with mTLS
	grpcServer := grpc.NewServer(
		grpc.Creds(tlsCredentials),
		grpc.MaxRecvMsgSize(10*1024*1024), // 10 MB
		grpc.MaxSendMsgSize(10*1024*1024),
	)

	// Register services
	pb.RegisterFederationServiceServer(grpcServer, federationServer)

	// Health check service
	healthServer := health.NewServer()
	grpc_health_v1.RegisterHealthServer(grpcServer, healthServer)
	healthServer.SetServingStatus("", grpc_health_v1.HealthCheckResponse_SERVING)

	// Start listening
	listener, err := net.Listen("tcp", fmt.Sprintf(":%s", port))
	if err != nil {
		log.Fatalf("Failed to listen on port %s: %v", port, err)
	}

	log.Printf("🚀 Federation Service listening on port %s with mTLS enabled", port)

	// Graceful shutdown
	go func() {
		if err := grpcServer.Serve(listener); err != nil {
			log.Fatalf("Failed to serve: %v", err)
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down Federation Service...")
	grpcServer.GracefulStop()
	log.Println("Federation Service stopped")
}

func loadTLSCredentials() (credentials.TransportCredentials, error) {
	certFile := os.Getenv("TLS_CERT_FILE")
	if certFile == "" {
		certFile = defaultTLSCert
	}

	keyFile := os.Getenv("TLS_KEY_FILE")
	if keyFile == "" {
		keyFile = defaultTLSKey
	}

	caCertFile := os.Getenv("CA_CERT_FILE")
	if caCertFile == "" {
		caCertFile = defaultCACert
	}

	// Load server's certificate and private key
	serverCert, err := tls.LoadX509KeyPair(certFile, keyFile)
	if err != nil {
		return nil, fmt.Errorf("failed to load server certificate: %w", err)
	}

	// Load CA certificate for client verification
	caCert, err := os.ReadFile(caCertFile)
	if err != nil {
		return nil, fmt.Errorf("failed to read CA certificate: %w", err)
	}

	certPool := x509.NewCertPool()
	if !certPool.AppendCertsFromPEM(caCert) {
		return nil, fmt.Errorf("failed to add CA certificate to pool")
	}

	// Configure mTLS
	config := &tls.Config{
		Certificates: []tls.Certificate{serverCert},
		ClientAuth:   tls.RequireAndVerifyClientCert,
		ClientCAs:    certPool,
		MinVersion:   tls.VersionTLS13,
	}

	return credentials.NewTLS(config), nil
}
