package server

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/emptypb"
	"google.golang.org/protobuf/types/known/timestamppb"

	_ "github.com/lib/pq"
	pb "github.com/silvanoneto/opendatagov/services/federation-service/proto"
)

// FederationServer implements the COSMOS Federation gRPC service
type FederationServer struct {
	pb.UnimplementedFederationServiceServer

	db             *sql.DB
	instanceCache  map[string]*pb.InstanceInfo
	cacheMutex     sync.RWMutex
	localInstance  *pb.InstanceInfo
}

// NewFederationServer creates a new federation server instance
func NewFederationServer() (*FederationServer, error) {
	// Connect to PostgreSQL
	dbURL := getEnv("DATABASE_URL", "postgres://odg:password@postgresql:5432/odg?sslmode=disable")
	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	// Initialize tables
	if err := initializeTables(db); err != nil {
		return nil, fmt.Errorf("failed to initialize tables: %w", err)
	}

	// Get local instance info
	localInstance := &pb.InstanceInfo{
		InstanceId:       getEnv("INSTANCE_ID", "opendatagov-local"),
		InstanceName:     getEnv("INSTANCE_NAME", "OpenDataGov Local"),
		GraphqlEndpoint:  getEnv("GRAPHQL_ENDPOINT", "http://gateway:8080/graphql"),
		GrpcEndpoint:     getEnv("GRPC_ENDPOINT", "federation-service:50060"),
		Region:           getEnv("REGION", "local"),
		Organization:     getEnv("ORGANIZATION", "Default Organization"),
		SharedNamespaces: []string{"gold", "platinum"},
		RegisteredAt:     timestamppb.Now(),
		Status:           pb.InstanceStatus_INSTANCE_STATUS_ACTIVE,
		Metadata:         make(map[string]string),
	}

	server := &FederationServer{
		db:            db,
		instanceCache: make(map[string]*pb.InstanceInfo),
		localInstance: localInstance,
	}

	// Register local instance on startup
	log.Printf("Registering local instance: %s (%s)", localInstance.InstanceId, localInstance.InstanceName)
	if _, err := server.RegisterInstance(context.Background(), localInstance); err != nil {
		log.Printf("Warning: Failed to self-register: %v", err)
	}

	return server, nil
}

// RegisterInstance registers an instance in the federation registry
func (s *FederationServer) RegisterInstance(ctx context.Context, req *pb.InstanceInfo) (*pb.RegistrationResponse, error) {
	log.Printf("Registering instance: %s", req.InstanceId)

	// Validate request
	if req.InstanceId == "" || req.GraphqlEndpoint == "" {
		return nil, status.Errorf(codes.InvalidArgument, "instance_id and graphql_endpoint are required")
	}

	// Store in database
	query := `
		INSERT INTO federation_instances (
			instance_id, instance_name, graphql_endpoint, grpc_endpoint,
			region, organization, shared_namespaces, status, metadata, registered_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		ON CONFLICT (instance_id) DO UPDATE SET
			instance_name = EXCLUDED.instance_name,
			graphql_endpoint = EXCLUDED.graphql_endpoint,
			grpc_endpoint = EXCLUDED.grpc_endpoint,
			region = EXCLUDED.region,
			organization = EXCLUDED.organization,
			shared_namespaces = EXCLUDED.shared_namespaces,
			status = EXCLUDED.status,
			metadata = EXCLUDED.metadata,
			registered_at = EXCLUDED.registered_at
	`

	sharedNsJSON, _ := json.Marshal(req.SharedNamespaces)
	metadataJSON, _ := json.Marshal(req.Metadata)

	_, err := s.db.ExecContext(ctx, query,
		req.InstanceId, req.InstanceName, req.GraphqlEndpoint, req.GrpcEndpoint,
		req.Region, req.Organization, sharedNsJSON, req.Status.String(), metadataJSON, time.Now(),
	)

	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to register instance: %v", err)
	}

	// Update cache
	s.cacheMutex.Lock()
	s.instanceCache[req.InstanceId] = req
	s.cacheMutex.Unlock()

	expiresAt := timestamppb.New(time.Now().Add(24 * time.Hour))

	return &pb.RegistrationResponse{
		Success:   true,
		Message:   fmt.Sprintf("Instance %s registered successfully", req.InstanceId),
		ExpiresAt: expiresAt,
	}, nil
}

// DiscoverInstances streams all registered federated instances
func (s *FederationServer) DiscoverInstances(req *pb.DiscoveryRequest, stream pb.FederationService_DiscoverInstancesServer) error {
	log.Printf("Discovering instances (region=%s, org=%s)", req.Region, req.Organization)

	query := `SELECT instance_id, instance_name, graphql_endpoint, grpc_endpoint,
		region, organization, shared_namespaces, status, metadata, registered_at
		FROM federation_instances WHERE status = $1`
	args := []interface{}{pb.InstanceStatus_INSTANCE_STATUS_ACTIVE.String()}

	// Apply filters
	if req.Region != "" {
		query += " AND region = $2"
		args = append(args, req.Region)
	}
	if req.Organization != "" {
		query += " AND organization = $" + fmt.Sprintf("%d", len(args)+1)
		args = append(args, req.Organization)
	}

	rows, err := s.db.QueryContext(stream.Context(), query, args...)
	if err != nil {
		return status.Errorf(codes.Internal, "failed to query instances: %v", err)
	}
	defer rows.Close()

	count := 0
	for rows.Next() {
		var instance pb.InstanceInfo
		var sharedNsJSON, metadataJSON []byte
		var statusStr string
		var registeredAt time.Time

		err := rows.Scan(
			&instance.InstanceId, &instance.InstanceName, &instance.GraphqlEndpoint, &instance.GrpcEndpoint,
			&instance.Region, &instance.Organization, &sharedNsJSON, &statusStr, &metadataJSON, &registeredAt,
		)
		if err != nil {
			log.Printf("Error scanning row: %v", err)
			continue
		}

		json.Unmarshal(sharedNsJSON, &instance.SharedNamespaces)
		json.Unmarshal(metadataJSON, &instance.Metadata)
		instance.Status = parseInstanceStatus(statusStr)
		instance.RegisteredAt = timestamppb.New(registeredAt)

		if err := stream.Send(&instance); err != nil {
			return status.Errorf(codes.Internal, "failed to stream instance: %v", err)
		}
		count++
	}

	log.Printf("Discovered %d instances", count)
	return nil
}

// CreateSharingAgreement creates a data sharing agreement between instances
func (s *FederationServer) CreateSharingAgreement(ctx context.Context, req *pb.SharingAgreement) (*pb.AgreementResponse, error) {
	log.Printf("Creating sharing agreement: %s -> %s", req.SourceInstanceId, req.TargetInstanceId)

	// Validate
	if req.AgreementId == "" || req.SourceInstanceId == "" || req.TargetInstanceId == "" {
		return nil, status.Errorf(codes.InvalidArgument, "agreement_id, source_instance_id, and target_instance_id are required")
	}

	// Store in database
	query := `
		INSERT INTO data_sharing_agreements (
			agreement_id, source_instance_id, target_instance_id, shared_datasets,
			access_level, raci_approvals, compliance_frameworks, encryption_required,
			allowed_ips, valid_from, valid_until, revoked, created_at, created_by
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
	`

	datasetsJSON, _ := json.Marshal(req.SharedDatasets)
	raciJSON, _ := json.Marshal(req.RaciApprovals)
	complianceJSON, _ := json.Marshal(req.ComplianceFrameworks)
	ipsJSON, _ := json.Marshal(req.AllowedIps)

	validFrom := req.ValidFrom.AsTime()
	var validUntil *time.Time
	if req.ValidUntil != nil {
		t := req.ValidUntil.AsTime()
		validUntil = &t
	}

	_, err := s.db.ExecContext(ctx, query,
		req.AgreementId, req.SourceInstanceId, req.TargetInstanceId, datasetsJSON,
		req.AccessLevel.String(), raciJSON, complianceJSON, req.EncryptionRequired,
		ipsJSON, validFrom, validUntil, req.Revoked, time.Now(), req.CreatedBy,
	)

	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to create agreement: %v", err)
	}

	return &pb.AgreementResponse{
		Success:     true,
		AgreementId: req.AgreementId,
		Message:     "Data sharing agreement created successfully",
	}, nil
}

// GetSharingAgreement retrieves a sharing agreement
func (s *FederationServer) GetSharingAgreement(ctx context.Context, req *pb.GetAgreementRequest) (*pb.SharingAgreement, error) {
	query := `SELECT agreement_id, source_instance_id, target_instance_id, shared_datasets,
		access_level, raci_approvals, compliance_frameworks, encryption_required,
		allowed_ips, valid_from, valid_until, revoked, created_at, created_by
		FROM data_sharing_agreements WHERE agreement_id = $1`

	var agreement pb.SharingAgreement
	var datasetsJSON, raciJSON, complianceJSON, ipsJSON []byte
	var accessLevelStr string
	var validFrom time.Time
	var validUntil sql.NullTime
	var createdAt time.Time

	err := s.db.QueryRowContext(ctx, query, req.AgreementId).Scan(
		&agreement.AgreementId, &agreement.SourceInstanceId, &agreement.TargetInstanceId, &datasetsJSON,
		&accessLevelStr, &raciJSON, &complianceJSON, &agreement.EncryptionRequired,
		&ipsJSON, &validFrom, &validUntil, &agreement.Revoked, &createdAt, &agreement.CreatedBy,
	)

	if err == sql.ErrNoRows {
		return nil, status.Errorf(codes.NotFound, "agreement not found")
	}
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to get agreement: %v", err)
	}

	json.Unmarshal(datasetsJSON, &agreement.SharedDatasets)
	json.Unmarshal(raciJSON, &agreement.RaciApprovals)
	json.Unmarshal(complianceJSON, &agreement.ComplianceFrameworks)
	json.Unmarshal(ipsJSON, &agreement.AllowedIps)
	agreement.AccessLevel = parseAccessLevel(accessLevelStr)
	agreement.ValidFrom = timestamppb.New(validFrom)
	if validUntil.Valid {
		agreement.ValidUntil = timestamppb.New(validUntil.Time)
	}
	agreement.CreatedAt = timestamppb.New(createdAt)

	return &agreement, nil
}

// RevokeSharingAgreement revokes a data sharing agreement
func (s *FederationServer) RevokeSharingAgreement(ctx context.Context, req *pb.RevokeRequest) (*emptypb.Empty, error) {
	log.Printf("Revoking agreement %s (reason: %s)", req.AgreementId, req.Reason)

	query := `UPDATE data_sharing_agreements SET revoked = true WHERE agreement_id = $1`
	result, err := s.db.ExecContext(ctx, query, req.AgreementId)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to revoke agreement: %v", err)
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		return nil, status.Errorf(codes.NotFound, "agreement not found")
	}

	return &emptypb.Empty{}, nil
}

// QueryRemoteDataset queries metadata from a remote dataset
func (s *FederationServer) QueryRemoteDataset(ctx context.Context, req *pb.RemoteDatasetRequest) (*pb.DatasetMetadata, error) {
	log.Printf("Querying remote dataset: %s from instance %s", req.DatasetId, req.InstanceId)

	// TODO: Validate sharing agreement
	// TODO: Connect to remote instance and fetch metadata
	// For now, return placeholder

	return &pb.DatasetMetadata{
		DatasetId:  req.DatasetId,
		Namespace:  "gold",
		TableName:  "customers",
		RowCount:   1000000,
		SizeBytes:  5368709120, // 5 GB
		Owner:      "data_owner@example.com",
		Tags:       []string{"pii", "production"},
		QualityScore: 0.95,
	}, nil
}

// FederatedLineageQuery executes a lineage query across instances
func (s *FederationServer) FederatedLineageQuery(ctx context.Context, req *pb.LineageRequest) (*pb.LineageGraph, error) {
	log.Printf("Federated lineage query for dataset: %s", req.DatasetId)

	// TODO: Query JanusGraph with remote edges
	// For now, return placeholder

	return &pb.LineageGraph{
		Nodes: []*pb.LineageNode{
			{
				Id:         "dataset_1",
				Label:      "Dataset",
				InstanceId: s.localInstance.InstanceId,
				Properties: map[string]string{"dataset_id": req.DatasetId},
			},
		},
		Edges: []*pb.LineageEdge{},
		NodeCount: 1,
		EdgeCount: 0,
	}, nil
}

// PingInstance performs a health check on a remote instance
func (s *FederationServer) PingInstance(ctx context.Context, req *pb.PingRequest) (*pb.PongResponse, error) {
	start := time.Now()

	// TODO: Actually ping remote instance
	// For now, return self-pong

	latency := time.Since(start).Milliseconds()

	return &pb.PongResponse{
		InstanceId: s.localInstance.InstanceId,
		Timestamp:  timestamppb.Now(),
		LatencyMs:  latency,
		Status:     pb.InstanceStatus_INSTANCE_STATUS_ACTIVE,
	}, nil
}

// Helper functions

func initializeTables(db *sql.DB) error {
	schema := `
		CREATE TABLE IF NOT EXISTS federation_instances (
			instance_id VARCHAR(255) PRIMARY KEY,
			instance_name VARCHAR(255) NOT NULL,
			graphql_endpoint VARCHAR(512) NOT NULL,
			grpc_endpoint VARCHAR(512) NOT NULL,
			region VARCHAR(100),
			organization VARCHAR(255),
			shared_namespaces JSONB,
			status VARCHAR(50),
			metadata JSONB,
			registered_at TIMESTAMP NOT NULL
		);

		CREATE TABLE IF NOT EXISTS data_sharing_agreements (
			agreement_id VARCHAR(255) PRIMARY KEY,
			source_instance_id VARCHAR(255) NOT NULL,
			target_instance_id VARCHAR(255) NOT NULL,
			shared_datasets JSONB NOT NULL,
			access_level VARCHAR(50) NOT NULL,
			raci_approvals JSONB,
			compliance_frameworks JSONB,
			encryption_required BOOLEAN DEFAULT true,
			allowed_ips JSONB,
			valid_from TIMESTAMP NOT NULL,
			valid_until TIMESTAMP,
			revoked BOOLEAN DEFAULT false,
			created_at TIMESTAMP NOT NULL,
			created_by VARCHAR(255)
		);

		CREATE INDEX IF NOT EXISTS idx_federation_instances_region ON federation_instances(region);
		CREATE INDEX IF NOT EXISTS idx_federation_instances_status ON federation_instances(status);
		CREATE INDEX IF NOT EXISTS idx_sharing_agreements_source ON data_sharing_agreements(source_instance_id);
		CREATE INDEX IF NOT EXISTS idx_sharing_agreements_target ON data_sharing_agreements(target_instance_id);
	`

	_, err := db.Exec(schema)
	return err
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func parseInstanceStatus(s string) pb.InstanceStatus {
	switch s {
	case "INSTANCE_STATUS_ACTIVE":
		return pb.InstanceStatus_INSTANCE_STATUS_ACTIVE
	case "INSTANCE_STATUS_MAINTENANCE":
		return pb.InstanceStatus_INSTANCE_STATUS_MAINTENANCE
	case "INSTANCE_STATUS_UNREACHABLE":
		return pb.InstanceStatus_INSTANCE_STATUS_UNREACHABLE
	default:
		return pb.InstanceStatus_INSTANCE_STATUS_UNSPECIFIED
	}
}

func parseAccessLevel(s string) pb.AccessLevel {
	switch s {
	case "ACCESS_LEVEL_METADATA_ONLY":
		return pb.AccessLevel_ACCESS_LEVEL_METADATA_ONLY
	case "ACCESS_LEVEL_READ_ONLY":
		return pb.AccessLevel_ACCESS_LEVEL_READ_ONLY
	case "ACCESS_LEVEL_FULL":
		return pb.AccessLevel_ACCESS_LEVEL_FULL
	default:
		return pb.AccessLevel_ACCESS_LEVEL_UNSPECIFIED
	}
}
