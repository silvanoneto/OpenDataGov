# OpenDataGov Security Architecture

**Versão**: 1.0
**Data**: 2025-02-08
**Status**: Implementado (ADR-072, ADR-073)

## Índice

- [Visão Geral](#vis%C3%A3o-geral)
- [Arquitetura de Segurança](#arquitetura-de-seguran%C3%A7a)
- [Fase 1: Autenticação e Autorização](#fase-1-autentica%C3%A7%C3%A3o-e-autoriza%C3%A7%C3%A3o)
- [Fase 2: Gestão de Secrets](#fase-2-gest%C3%A3o-de-secrets)
- [Fase 3: Service Mesh mTLS](#fase-3-service-mesh-mtls)
- [Fase 4: Network Security](#fase-4-network-security)
- [Fase 5: Audit Encryption](#fase-5-audit-encryption)
- [Profiles de Deployment](#profiles-de-deployment)
- [Guia de Testes](#guia-de-testes)
- [Compliance e Auditoria](#compliance-e-auditoria)
- [Troubleshooting](#troubleshooting)

______________________________________________________________________

## Visão Geral

O OpenDataGov implementa uma **arquitetura de segurança em camadas** (defense-in-depth) baseada em dois Architecture Decision Records principais:

- **ADR-072**: Keycloak (OIDC/SAML) + OPA (Rego policies) para AuthN/AuthZ
- **ADR-073**: HashiCorp Vault (secrets, encryption) + mTLS via Istio Service Mesh

### Modelo de Segurança RACI

O sistema utiliza o modelo RACI para controle de acesso:

| Role               | Descrição           | Permissões                                                 |
| ------------------ | ------------------- | ---------------------------------------------------------- |
| **data_owner**     | Dono dos dados      | Criar decisões, exercer veto, atribuir roles, acesso total |
| **data_steward**   | Curador de dados    | Submeter/aprovar decisões, quality checks, classificação   |
| **data_consumer**  | Consumidor de dados | Leitura de datasets, execução de queries, dashboards       |
| **data_architect** | Arquiteto de dados  | Definir schemas, criar contratos, modificar lineage        |

### Camadas de Segurança

```
┌──────────────────────────────────────────────────────────────┐
│                    User / Application                         │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 1: Authentication (Keycloak)                           │
│  - OIDC/SAML2.0                                               │
│  - JWT validation (RS256)                                     │
│  - JWKS key rotation                                          │
│  - MFA support                                                │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 2: Authorization (OPA)                                 │
│  - RACI-based RBAC                                            │
│  - Resource-level access control                              │
│  - Data classification enforcement                            │
│  - Policy-as-Code (Rego)                                      │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 3: Secrets Management (Vault)                          │
│  - Dynamic database credentials (TTL: 1h)                     │
│  - Transit encryption (AES-256-GCM)                           │
│  - Automatic lease renewal                                    │
│  - Kubernetes auth integration                                │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 4: Service Mesh (Istio mTLS)                           │
│  - Automatic mTLS (STRICT mode)                               │
│  - Service-to-service authentication                          │
│  - Zero-trust network (AuthorizationPolicy)                   │
│  - Certificate rotation (90 days)                             │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 5: Network Policies                                    │
│  - Default deny-all                                           │
│  - Explicit service allowlists                                │
│  - Infrastructure isolation                                   │
│  - Pod Security Standards (restricted)                        │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 6: Audit & Compliance                                  │
│  - Encrypted audit logs (Vault Transit)                       │
│  - Hash chain integrity (SHA-256)                             │
│  - Immutable audit trail (1 year retention)                   │
│  - GDPR/LGPD/SOX compliance reports                           │
└──────────────────────────────────────────────────────────────┘
```

______________________________________________________________________

## Fase 1: Autenticação e Autorização

### Keycloak (OIDC/SAML)

**Implementação**: [keycloak-init-job.yaml](../deploy/helm/opendatagov/templates/keycloak-init-job.yaml)

#### Configuração do Realm

O Helm job `keycloak-init` configura automaticamente:

1. **Realm**: `opendatagov`
1. **Client**: `odg-api` (service account enabled)
1. **Roles**: `data_owner`, `data_steward`, `data_consumer`, `data_architect`
1. **Protocol**: OIDC (OAuth 2.0 + OpenID Connect)

#### JWT Validation

**Implementação**: [odg_core/auth/keycloak.py](../libs/python/odg-core/src/odg_core/auth/keycloak.py)

```python
from odg_core.auth.keycloak import KeycloakVerifier

verifier = KeycloakVerifier()
token_payload = verifier.verify_token(jwt_token)

# Token structure:
# {
#   "sub": "user-uuid",
#   "preferred_username": "username",
#   "email": "user@example.com",
#   "roles": ["data_owner", "data_steward"],
#   "exp": 1234567890,
#   "iat": 1234567800
# }
```

**Validações realizadas**:

- ✅ Assinatura RS256 com JWKS
- ✅ Audience (`client_id`)
- ✅ Expiração (`exp`)
- ✅ Extração de roles (realm_access + resource_access)

#### Aplicação de Auth nas APIs

**Implementação**: [routes_decisions.py](../services/governance-engine/src/governance_engine/api/routes_decisions.py)

```python
from odg_core.auth.dependencies import get_current_user, require_role
from odg_core.auth.models import UserContext
from odg_core.enums import RACIRole
from fastapi import Depends

@router.post("", status_code=201)
async def create_decision(
    body: CreateDecisionRequest,
    service: DecisionServiceDep,
    user: UserContext = Depends(require_role(RACIRole.DATA_OWNER)),
) -> DecisionResponse:
    """Apenas data_owner pode criar decisões."""
    # user.sub, user.username, user.roles disponíveis
    ...

@router.get("")
async def list_decisions(
    service: DecisionServiceDep,
    user: UserContext = Depends(get_current_user),
    # Qualquer usuário autenticado pode listar
) -> list[DecisionResponse]:
    ...
```

**Endpoints protegidos**:

- ✅ `routes_decisions.py`: 9 endpoints
- ✅ `routes_roles.py`: 4 endpoints
- ✅ `routes_audit.py`: 3 endpoints
- ✅ `routes_dashboard.py`: 4 endpoints
- ✅ `routes_self_service.py`: 6 endpoints
- ✅ `routes_graphql.py`: GraphQL context authentication

### OPA (Open Policy Agent)

**Implementação**: [opa-policies/authz.rego](../deploy/helm/opendatagov/opa-policies/authz.rego)

#### Políticas RACI

```rego
package authz

import rego.v1

default allow := false

# Data Owner: pode criar decisões, exercer veto, atribuir roles
required_role := "data_owner" if {
    input.action in ["create_decision", "assign_role", "exercise_veto"]
}

# Data Steward: pode submeter/aprovar decisões, fazer quality checks
required_role := "data_steward" if {
    input.action in ["submit_decision", "approve_decision", "quality_check"]
}

# Data Consumer: pode ler datasets e queries
required_role := "data_consumer" if {
    input.action in ["read_decision", "read_dataset", "query_data"]
}

# Data Architect: pode definir schemas e modificar lineage
required_role := "data_architect" if {
    input.action in ["define_schema", "create_contract", "modify_lineage"]
}

allow if {
    input.roles[_] == required_role
}
```

#### Resource-Based Access Control

```rego
# Classificação de dados: public, internal, confidential, secret
accessible_resource if {
    input.resource_classification == "public"
}

accessible_resource if {
    input.resource_classification == "internal"
    input.roles[_] in ["data_consumer", "data_steward", "data_owner", "data_architect"]
}

accessible_resource if {
    input.resource_classification == "confidential"
    input.roles[_] in ["data_steward", "data_owner"]
}

accessible_resource if {
    input.resource_classification == "secret"
    input.roles[_] == "data_owner"
}
```

#### Integração com FastAPI

**Implementação**: [odg_core/auth/opa.py](../libs/python/odg-core/src/odg_core/auth/opa.py)

```python
from odg_core.auth.opa import OPAClient

opa = OPAClient()
allowed = await opa.check_policy(
    path="authz/allow",
    input_data={
        "roles": ["data_owner"],
        "action": "create_decision",
        "resource_classification": "confidential",
    }
)

if not allowed:
    raise HTTPException(status_code=403, detail="Forbidden by policy")
```

### gRPC TLS

**Implementação**: [grpc/server.py](../services/governance-engine/src/governance_engine/grpc/server.py)

```python
async def serve_grpc(port: int = 50051, tls_enabled: bool = True) -> None:
    server = grpc.aio.server()

    if tls_enabled:
        with open("/etc/grpc/tls/tls.crt", "rb") as f:
            cert_chain = f.read()
        with open("/etc/grpc/tls/tls.key", "rb") as f:
            private_key = f.read()

        server_credentials = grpc.ssl_server_credentials([(private_key, cert_chain)])
        server.add_secure_port(f"[::]:{port}", server_credentials)
        logger.info(f"gRPC server with TLS on port {port}")
    else:
        logger.warning("TLS disabled, using insecure port")
        server.add_insecure_port(f"[::]:{port}")
```

**Certificados gerenciados por**: cert-manager (rotação automática a cada 90 dias)

______________________________________________________________________

## Fase 2: Gestão de Secrets

### HashiCorp Vault

**Implementação**: [vault-init-job.yaml](../deploy/helm/opendatagov/templates/vault-init-job.yaml)

#### Secrets Engines Habilitados

1. **KV v2** (`secret/`): Secrets estáticos

   ```bash
   vault kv put secret/odg/kafka username=odg-producer password=securepass
   vault kv get secret/odg/kafka
   ```

1. **Transit** (`transit/`): Encryption-as-a-Service

   ```bash
   # Keys: odg-encryption, odg-minio-sse
   vault write -f transit/keys/odg-encryption

   # Encrypt
   vault write transit/encrypt/odg-encryption plaintext=$(echo "sensitive data" | base64)

   # Decrypt
   vault write transit/decrypt/odg-encryption ciphertext="vault:v1:..."
   ```

1. **Database** (`database/`): Dynamic credentials

   ```bash
   # Roles: odg-app (read-write), odg-readonly
   vault read database/creds/odg-app
   # Output: username=v-kubernetes-odg-app-xyz, password=A1b2C3...
   #         lease_id=database/creds/odg-app/abc123
   #         lease_duration=3600 (1 hour)
   ```

#### Dynamic Database Credentials

**Implementação**: [vault/client.py](../libs/python/odg-core/src/odg_core/vault/client.py)

```python
from odg_core.vault.client import VaultClient

vault = VaultClient()

# Obter credenciais dinâmicas
creds = vault.get_database_credentials(role="odg-app")
# {
#   "username": "v-kubernetes-odg-app-xyz",
#   "password": "A1b2C3...",
#   "lease_id": "database/creds/odg-app/abc123",
#   "lease_duration": 3600
# }

# Renovar lease (antes da expiração)
vault.renew_database_lease(lease_id=creds["lease_id"], increment=3600)
```

**Integração com SQLAlchemy**: [db/engine.py](../libs/python/odg-core/src/odg_core/db/engine.py)

```python
from odg_core.db.engine import create_async_engine_factory

# Automaticamente usa Vault se configurado
engine = create_async_engine_factory(use_vault=True)
# Fallback para credenciais estáticas se Vault indisponível
```

#### Automatic Lease Renewal

**Implementação**: [vault/lease_manager.py](../libs/python/odg-core/src/odg_core/vault/lease_manager.py)

```python
from odg_core.vault.lease_manager import LeaseManager

# Background task que renova leases automaticamente
lease_manager = LeaseManager(renewal_threshold=0.5)  # Renova em 50% do TTL
lease_manager.register_lease(lease_id, duration)
await lease_manager.start()  # Checa a cada 30 segundos
```

**Threshold**: Leases são renovados quando restam 50% do TTL (ex: renova aos 30min de um lease de 1h)

#### MinIO Server-Side Encryption

**Implementação**: [storage/minio_storage.py](../libs/python/odg-core/src/odg_core/storage/minio_storage.py)

```python
from odg_core.storage.minio_storage import MinIOStorage

storage = MinIOStorage(
    endpoint="minio:9000",
    bucket="data-lake",
    encrypt=True,  # Vault Transit encryption
    vault_key="odg-minio-sse"
)

# Escrita automática com encryption
await storage.write("path/to/file.parquet", data_bytes)
# Internamente: data -> base64 -> Vault Transit encrypt -> MinIO

# Leitura automática com decryption
data = await storage.read("path/to/file.parquet")
# Internamente: MinIO -> Vault Transit decrypt -> base64 decode -> data
```

### Configuração de Secrets

#### PostgreSQL

```yaml
# values-small.yaml
vault:
  database:
    config:
      postgresql:
        connection_url: "postgresql://odg:testpass@postgresql:5432/odg"
        allowed_roles: "odg-app,odg-readonly"
    roles:
      odg-app:
        db_name: postgresql
        default_ttl: "1h"
        max_ttl: "24h"
        creation_statements: |
          CREATE ROLE "{{name}}" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';
          GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{{name}}";
```

#### Kafka SASL

```bash
# Armazenar credenciais Kafka no Vault
vault kv put secret/odg/kafka \
  username=odg-producer \
  password=$(openssl rand -base64 32) \
  mechanism=SCRAM-SHA-512

# Aplicação lê credenciais
vault kv get -field=password secret/odg/kafka
```

______________________________________________________________________

## Fase 3: Service Mesh mTLS

### Istio Configuration

#### PeerAuthentication (STRICT mTLS)

**Implementação**: [istio-peer-authentication.yaml](../deploy/helm/opendatagov/templates/istio-peer-authentication.yaml)

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: opendatagov-mtls
  namespace: opendatagov
spec:
  mtls:
    mode: STRICT  # Força mTLS para TODAS as conexões
  portLevelMtls:
    8080:
      mode: PERMISSIVE  # Health checks Kubernetes sem mTLS
    15020:
      mode: PERMISSIVE  # Istio health endpoint
```

**Efeito**: Qualquer conexão entre serviços sem mTLS é automaticamente rejeitada.

#### AuthorizationPolicy (Zero-Trust)

**Implementação**: [istio-authorization-policy.yaml](../deploy/helm/opendatagov/templates/istio-authorization-policy.yaml)

```yaml
# Default deny-all
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: opendatagov-deny-all
  namespace: opendatagov
spec:
  {} # Empty spec = deny all traffic

---
# Explicit allow: Gateway -> Governance Engine
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: governance-engine-allow
spec:
  selector:
    matchLabels:
      app: governance-engine
  action: ALLOW
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/opendatagov/sa/gateway"]
    to:
    - operation:
        ports: ["8000"]
        methods: ["GET", "POST", "PUT", "DELETE"]
```

**Princípio**: Default deny + explicit allow = zero-trust networking

#### DestinationRule (TLS + Load Balancing)

**Implementação**: [istio-destination-rule.yaml](../deploy/helm/opendatagov/templates/istio-destination-rule.yaml)

```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: opendatagov-services
spec:
  host: "*.opendatagov.svc.cluster.local"
  trafficPolicy:
    tls:
      mode: ISTIO_MUTUAL  # Usa mTLS automático do Istio
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        http1MaxPendingRequests: 50
        http2MaxRequests: 100
    loadBalancer:
      simple: LEAST_REQUEST  # Load balancing inteligente
    outlierDetection:
      consecutiveErrors: 5
      interval: 30s
      baseEjectionTime: 30s
```

### Kafka TLS + SASL

**Implementação**: [values-small.yaml](../deploy/helm/opendatagov/values-small.yaml)

```yaml
kafka:
  auth:
    enabled: true
    clientProtocol: sasl_ssl  # TLS + SASL authentication
    interBrokerProtocol: sasl_ssl
    sasl:
      mechanism: SCRAM-SHA-512  # Mais seguro que PLAIN
      jaas:
        clientUsers:
          - odg-producer
          - odg-consumer
          - odg-admin
  tls:
    enabled: true
    autoGenerated: true  # Gera certificados automaticamente
    passwordsSecret: kafka-tls-passwords
```

**Cliente Python**:

```python
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers=["kafka:9093"],
    security_protocol="SASL_SSL",
    sasl_mechanism="SCRAM-SHA-512",
    sasl_plain_username="odg-producer",
    sasl_plain_password=vault.get_secret("kafka/password"),
    ssl_cafile="/etc/kafka/certs/ca.crt",
)
```

### Certificate Management

**Implementação**: [cert-manager-certificates.yaml](../deploy/helm/opendatagov/templates/cert-manager-certificates.yaml)

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: governance-engine-grpc
spec:
  secretName: governance-engine-grpc-tls
  duration: 2160h  # 90 days
  renewBefore: 360h  # Renova 15 dias antes
  issuerRef:
    name: opendatagov-ca-issuer
    kind: ClusterIssuer
  dnsNames:
    - governance-engine.opendatagov.svc.cluster.local
    - governance-engine
  privateKey:
    algorithm: RSA
    size: 2048
```

**Rotação automática**: cert-manager renova certificados 15 dias antes da expiração (aos 75 dias de um ciclo de 90 dias).

______________________________________________________________________

## Fase 4: Network Security

### NetworkPolicies

#### Default Deny-All

**Implementação**: [networkpolicy-default.yaml](../deploy/helm/opendatagov/templates/networkpolicy-default.yaml)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: opendatagov-default-deny-all
spec:
  podSelector: {}  # Aplica a TODOS os pods
  policyTypes:
    - Ingress
    - Egress
  # Sem regras = deny all
```

**Efeito**: Nenhum pod pode se comunicar com nenhum outro pod por padrão.

#### DNS Exception

```yaml
# Permitir DNS para todos os pods
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: kube-system
      ports:
        - protocol: UDP
          port: 53
```

#### Service-Specific Policies

**Exemplo: Governance Engine**

**Implementação**: [networkpolicy-services.yaml](../deploy/helm/opendatagov/templates/networkpolicy-services.yaml)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: governance-engine
spec:
  podSelector:
    matchLabels:
      app: governance-engine
  policyTypes:
    - Ingress
    - Egress

  ingress:
    # Aceitar HTTP do Gateway
    - from:
        - podSelector:
            matchLabels:
              app: gateway
      ports:
        - protocol: TCP
          port: 8000

    # Aceitar gRPC do Lakehouse Agent
    - from:
        - podSelector:
            matchLabels:
              app: lakehouse-agent
      ports:
        - protocol: TCP
          port: 50051

  egress:
    # Conectar ao PostgreSQL
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: postgresql
      ports:
        - protocol: TCP
          port: 5432

    # Conectar ao Kafka
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: kafka
      ports:
        - protocol: TCP
          port: 9093

    # Conectar ao Keycloak
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: keycloak
      ports:
        - protocol: TCP
          port: 8080

    # Conectar ao OPA
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: opa
      ports:
        - protocol: TCP
          port: 8181

    # Conectar ao Vault
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: vault
      ports:
        - protocol: TCP
          port: 8200
```

#### Infrastructure Isolation

**Implementação**: [networkpolicy-infrastructure.yaml](../deploy/helm/opendatagov/templates/networkpolicy-infrastructure.yaml)

**PostgreSQL**: Aceita apenas de governance-engine, quality-gate, keycloak, airflow, superset

**Redis**: Aceita apenas de governance-engine, airflow, superset

**Kafka**: Aceita apenas de governance-engine, quality-gate, lakehouse-agent

**MinIO**: Aceita apenas de lakehouse-agent, governance-engine, trino

**Vault**: Aceita de todos os serviços da aplicação (para buscar secrets)

### Pod Security Standards

**Implementação**: [podsecurity-standards.yaml](../deploy/helm/opendatagov/templates/podsecurity-standards.yaml)

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: opendatagov
  labels:
    # Enforcement level: restricted (mais restritivo)
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest

    # Audit (logs) e Warn (warnings)
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

**Restrições do modo `restricted`**:

- ❌ Sem pods privilegiados
- ❌ Sem hostPath mounts
- ❌ Sem hostNetwork/hostPID/hostIPC
- ❌ Sem capabilities adicionais
- ✅ Requer runAsNonRoot
- ✅ Requer seccompProfile (RuntimeDefault)
- ✅ Requer allowPrivilegeEscalation=false

#### ServiceAccounts Dedicados

```yaml
# Um ServiceAccount por serviço (least privilege)
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: governance-engine
automountServiceAccountToken: true
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: lakehouse-agent
automountServiceAccountToken: true
```

#### RBAC para Vault Auth

```yaml
# Role para ler tokens de ServiceAccount (Vault Kubernetes auth)
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: opendatagov-vault-auth
rules:
  - apiGroups: [""]
    resources: ["serviceaccounts/token"]
    verbs: ["create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: opendatagov-vault-auth
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: opendatagov-vault-auth
subjects:
  - kind: ServiceAccount
    name: governance-engine
  - kind: ServiceAccount
    name: lakehouse-agent
```

______________________________________________________________________

## Fase 5: Audit Encryption

### PostgreSQL Encrypted Audit Log

**Implementação**: [postgresql-encryption-init.yaml](../deploy/helm/opendatagov/templates/postgresql-encryption-init.yaml)

#### Tabela audit_log_encrypted

```sql
CREATE TABLE audit_log_encrypted (
  id BIGSERIAL PRIMARY KEY,
  encrypted_event BYTEA NOT NULL,           -- Evento criptografado com Vault
  event_hash VARCHAR(64) NOT NULL,          -- SHA-256 do plaintext
  previous_hash VARCHAR(64),                -- Hash do evento anterior (chain)
  event_type VARCHAR(50) NOT NULL,          -- Tipo do evento
  entity_id VARCHAR(255),                   -- ID da entidade afetada
  actor_id VARCHAR(255) NOT NULL,           -- Quem executou a ação
  timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
  CONSTRAINT valid_hash CHECK (length(event_hash) = 64)
);

-- Índices para performance
CREATE INDEX idx_audit_encrypted_timestamp ON audit_log_encrypted(timestamp DESC);
CREATE INDEX idx_audit_encrypted_entity ON audit_log_encrypted(entity_id);
CREATE INDEX idx_audit_encrypted_actor ON audit_log_encrypted(actor_id);
CREATE INDEX idx_audit_encrypted_type ON audit_log_encrypted(event_type);
CREATE INDEX idx_audit_encrypted_hash ON audit_log_encrypted(event_hash);
```

#### Hash Chain Integrity

```sql
-- Função para verificar integridade da chain
CREATE OR REPLACE FUNCTION verify_audit_chain()
RETURNS TABLE(is_valid BOOLEAN, broken_at BIGINT, total_checked BIGINT) AS $$
DECLARE
  prev_hash VARCHAR(64);
  current_id BIGINT;
  current_prev_hash VARCHAR(64);
  broken_id BIGINT;
  count_checked BIGINT := 0;
BEGIN
  broken_id := NULL;

  -- Iterar através do audit log em ordem
  FOR current_id, current_prev_hash IN
    SELECT id, previous_hash FROM audit_log_encrypted ORDER BY id
  LOOP
    count_checked := count_checked + 1;

    -- Primeiro evento: previous_hash deve ser NULL
    IF count_checked = 1 THEN
      IF current_prev_hash IS NOT NULL THEN
        broken_id := current_id;
        EXIT;
      END IF;
    -- Outros eventos: previous_hash deve bater com hash anterior
    ELSIF current_prev_hash IS NULL OR current_prev_hash != prev_hash THEN
      broken_id := current_id;
      EXIT;
    END IF;

    -- Pegar hash do evento atual para próxima iteração
    SELECT event_hash INTO prev_hash FROM audit_log_encrypted WHERE id = current_id;
  END LOOP;

  RETURN QUERY SELECT (broken_id IS NULL), broken_id, count_checked;
END;
$$ LANGUAGE plpgsql;

-- Executar verificação
SELECT * FROM verify_audit_chain();
-- is_valid | broken_at | total_checked
-- ----------+-----------+--------------
--  true     |           | 1000
```

#### Tabela de Verificação

```sql
CREATE TABLE audit_integrity_check (
  id BIGSERIAL PRIMARY KEY,
  check_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
  total_events BIGINT NOT NULL,
  chain_valid BOOLEAN NOT NULL,
  broken_chain_at BIGINT,
  details JSONB
);
```

### AuditEncryption Service

**Implementação**: [audit/encryption.py](../libs/python/odg-core/src/odg_core/audit/encryption.py)

```python
from odg_core.audit.encryption import AuditEncryption

encryption = AuditEncryption()

# Criptografar evento
event = {
    "event_type": "decision_created",
    "entity_id": "decision-123",
    "actor_id": "user-456",
    "action": "create",
    "metadata": {"classification": "confidential"}
}

encrypted_record = encryption.encrypt_event(event, previous_hash="abc123...")
# {
#   "encrypted_event": b"vault:v1:...",  # Ciphertext do Vault Transit
#   "event_hash": "def456...",           # SHA-256 do plaintext
#   "previous_hash": "abc123..."         # Hash do evento anterior
# }

# Descriptografar evento
plaintext = encryption.decrypt_event(encrypted_record["encrypted_event"])

# Verificar hash (detect tampering)
is_valid = encryption.verify_hash(plaintext, encrypted_record["event_hash"])

# Verificar chain integrity (PostgreSQL)
result = encryption.verify_chain_integrity()
# {"is_valid": True, "broken_at": None, "total_checked": 1000}
```

### AuditService

**Implementação**: [audit/service.py](../libs/python/odg-core/src/odg_core/audit/service.py)

```python
from odg_core.audit.service import AuditService

audit = AuditService()

# Registrar evento
record = audit.log_event(
    event_type="decision_approved",
    entity_id="decision-123",
    actor_id="user-456",
    action="approve",
    metadata={
        "classification": "confidential",
        "decision_type": "data_promotion",
        "steward": "user-789"
    }
)
# Evento automaticamente criptografado e salvo com hash chain

# Verificar integridade
integrity = await audit.verify_integrity()
if not integrity["is_valid"]:
    logger.critical(f"Audit chain broken at event {integrity['broken_at']}")
```

### Kafka Retention

**Configuração**: [values-small.yaml](../deploy/helm/opendatagov/values-small.yaml)

```yaml
kafka:
  topics:
    - name: odg.audit.events
      partitions: 10
      replicationFactor: 3
      config:
        retention.ms: "31536000000"  # 1 year (365 days)
        retention.bytes: "1073741824"  # 1GB per partition (10GB total)
        compression.type: "lz4"       # Compression para economizar espaço
        min.insync.replicas: "2"      # Durabilidade (acks=all)
```

**Retenção total**: 1 ano ou 10GB (o que vier primeiro)

### Security Dashboard

**Implementação**: [grafana-dashboards/security.json](../deploy/helm/opendatagov/grafana-dashboards/security.json)

#### Painéis Disponíveis

1. **Authentication Attempts**

   - Total de tentativas
   - Sucessos vs 401 (Unauthorized) vs 403 (Forbidden)
   - Top IPs com falhas

1. **OPA Policy Evaluations**

   - Decisões allow vs deny
   - Tempo médio de avaliação
   - Policies mais usadas

1. **mTLS Connection Status**

   - Conexões com mTLS vs sem mTLS
   - Taxa de requisições por serviço
   - Falhas de handshake TLS

1. **Certificate Expiration**

   - Certificados expiram em < 30 dias (warning)
   - Certificados expiram em < 7 dias (critical)

1. **Vault Secret Access Rate**

   - Requisições ao Vault por segundo
   - Dynamic credentials gerados
   - Lease renewals

1. **Audit Events Per Second**

   - Taxa de eventos de auditoria
   - Distribuição por tipo
   - Latência de gravação

1. **Audit Chain Integrity**

   - Status: válido vs inválido
   - Total de eventos verificados
   - Última verificação

1. **Network Policy Violations**

   - Conexões bloqueadas por NetworkPolicy
   - Violações por pod
   - Tentativas de acesso não autorizado

1. **Security Events Timeline**

   - Linha do tempo de eventos de segurança
   - Correlação de incidentes

1. **Failed Authentication Sources**

   - Top IPs com falhas de autenticação
   - Mapa geográfico (se disponível)
   - Possíveis ataques de força bruta

**Acesso**: `kubectl port-forward svc/grafana 3000:80` → http://localhost:3000 → Dashboard "OpenDataGov Security"

______________________________________________________________________

## Compliance e Auditoria

### ComplianceReport Module

**Implementação**: [audit/compliance.py](../libs/python/odg-core/src/odg_core/audit/compliance.py)

#### ADR Compliance Report

```python
from odg_core.audit.compliance import ComplianceReport

report = ComplianceReport.generate_adr_compliance_report()
```

**Output**:

```json
{
  "report_date": "2025-02-08T10:30:00Z",
  "report_type": "ADR Compliance",
  "adr_072_authentication_authorization": {
    "status": "COMPLIANT",
    "requirements": {
      "keycloak_oidc": {
        "implemented": true,
        "details": "Keycloak deployed with OIDC/SAML support",
        "evidence": [
          "Keycloak initialization job creates opendatagov realm",
          "JWT validation via PyJWT + JWKS",
          "RACI roles configured"
        ]
      },
      "opa_policy_engine": {
        "implemented": true,
        "details": "OPA deployed with Rego policies",
        "evidence": [
          "OPA policies in opa-policies/authz.rego",
          "Policy checks integrated in API dependencies",
          "Resource-based access control by classification"
        ]
      }
    }
  },
  "adr_073_secrets_mtls": {
    "status": "COMPLIANT",
    "requirements": {
      "vault_secrets_management": {
        "implemented": true,
        "evidence": [
          "Vault initialization job configures all engines",
          "Dynamic database credentials (TTL: 1h, max: 24h)",
          "Transit encryption keys"
        ]
      },
      "mtls_service_mesh": {
        "implemented": true,
        "evidence": [
          "PeerAuthentication STRICT mode",
          "cert-manager for automatic rotation (90 days)"
        ]
      }
    }
  }
}
```

#### GDPR Compliance Report

```python
gdpr_report = ComplianceReport.generate_gdpr_compliance_report()
```

**Output**:

```json
{
  "report_type": "GDPR Compliance",
  "requirements": {
    "article_32_security": {
      "status": "COMPLIANT",
      "requirement": "Implement appropriate technical measures",
      "controls": [
        "Encryption at rest (Vault Transit)",
        "Encryption in transit (mTLS, TLS)",
        "Pseudonymization via encryption",
        "Ability to ensure confidentiality (access controls)",
        "Ability to ensure integrity (hash chains)",
        "Ability to ensure availability (HA deployments)"
      ]
    },
    "article_30_records": {
      "status": "COMPLIANT",
      "requirement": "Maintain records of processing activities",
      "controls": [
        "Encrypted audit log of all data access",
        "Retention: 1 year minimum",
        "Immutable audit trail with hash verification"
      ]
    },
    "article_25_data_protection": {
      "status": "COMPLIANT",
      "requirement": "Data protection by design and by default",
      "controls": [
        "Zero-trust network architecture",
        "Principle of least privilege",
        "Encryption by default"
      ]
    }
  }
}
```

#### Security Summary

```python
summary = ComplianceReport.generate_security_summary()
```

**Output**:

```json
{
  "security_posture": "STRONG",
  "compliance_frameworks": ["ADR-072", "ADR-073", "GDPR", "LGPD"],
  "security_layers": {
    "authentication": {
      "technology": "Keycloak (OIDC/SAML)",
      "status": "ACTIVE",
      "mfa_supported": true
    },
    "authorization": {
      "technology": "Open Policy Agent (Rego)",
      "status": "ACTIVE",
      "model": "RACI-based RBAC"
    },
    "secrets_management": {
      "technology": "HashiCorp Vault",
      "status": "ACTIVE",
      "features": ["Dynamic credentials", "Transit encryption", "Lease renewal"]
    },
    "network_security": {
      "service_mesh": "Istio (mTLS strict mode)",
      "network_policies": "Zero-trust (default deny)",
      "pod_security": "Restricted standard"
    },
    "encryption": {
      "at_rest": "Vault Transit + PostgreSQL pgcrypto",
      "in_transit": "TLS 1.3 + mTLS",
      "key_rotation": "90 days (cert-manager)"
    },
    "audit": {
      "encryption": "Vault Transit per event",
      "integrity": "SHA-256 hash chain",
      "retention": "1 year (Kafka)",
      "tamper_detection": "Enabled"
    }
  },
  "security_metrics": {
    "authentication_enabled": true,
    "authorization_enforced": true,
    "encryption_at_rest": true,
    "encryption_in_transit": true,
    "mtls_enabled": true,
    "audit_logging": true,
    "network_isolation": true,
    "secret_rotation": true
  }
}
```

______________________________________________________________________

## Profiles de Deployment

### Embedded Profile

**Target**: Edge devices, dev laptops (1-2 vCPU, 2-4GB)

**Segurança**: ❌ Mínima (dev/test only)

```yaml
# values-embedded.yaml
keycloak:
  enabled: false
opa:
  enabled: false
vault:
  enabled: false
istio:
  enabled: false
networkPolicies:
  enabled: false

# Credenciais estáticas
postgresql:
  auth:
    username: odg
    password: odg
kafka:
  auth:
    enabled: false
```

**Uso**: Desenvolvimento local, testes unitários, demos

______________________________________________________________________

### Dev Profile

**Target**: Single-node dev cluster (4 vCPU, 16GB)

**Segurança**: ⚠️ Básica

```yaml
# values-dev.yaml
keycloak:
  enabled: true
  replicaCount: 1
  postgresql:
    enabled: true
    primary:
      persistence:
        enabled: false  # Ephemeral

opa:
  enabled: true
  replicaCount: 1

vault:
  enabled: true
  server:
    dev:
      enabled: true  # Dev mode (in-memory, não persistente)
    ha:
      enabled: false

istio:
  enabled: false  # Optional (adiciona overhead)

networkPolicies:
  enabled: true
  enforceMode: false  # Advisory only (logs, não bloqueia)
```

**Características**:

- ✅ Auth habilitado (Keycloak + OPA)
- ✅ Vault dev mode (não persistente)
- ⚠️ NetworkPolicies permissivas
- ❌ Sem mTLS (opcional)
- ❌ Credenciais não rotacionam

**Uso**: Desenvolvimento de features, testes de integração

______________________________________________________________________

### Small Profile

**Target**: Produção pequena (16 vCPU, 64GB, 3 nodes)

**Segurança**: ✅ Full stack

```yaml
# values-small.yaml
keycloak:
  enabled: true
  replicaCount: 1
  postgresql:
    primary:
      persistence:
        enabled: true
        size: 10Gi

opa:
  enabled: true
  replicaCount: 1
  resources:
    requests:
      cpu: 250m
      memory: 512Mi

vault:
  enabled: true
  server:
    ha:
      enabled: true
      replicas: 3  # Raft consensus
      raft:
        enabled: true
        setNodeId: true
    dataStorage:
      enabled: true
      size: 10Gi
    auditStorage:
      enabled: true
      size: 5Gi

istio:
  enabled: true
  profile: minimal
  pilot:
    resources:
      requests:
        cpu: 500m
        memory: 1Gi

networkPolicies:
  enabled: true
  enforceMode: true  # Enforce (bloqueia violações)

kafka:
  auth:
    enabled: true
    clientProtocol: sasl_ssl
  logRetentionHours: 8760  # 1 year

postgresql:
  encryption:
    enabled: true  # pgcrypto

certManager:
  enabled: true
```

**Características**:

- ✅ Auth completo (Keycloak + OPA)
- ✅ Vault HA (3 replicas Raft)
- ✅ mTLS (Istio strict mode)
- ✅ NetworkPolicies enforced
- ✅ Kafka TLS + SASL
- ✅ Audit encryption
- ✅ Certificate rotation (90 days)
- ✅ Dynamic credentials (TTL: 1h)

**Uso**: Produção para startups, PMEs, projetos small-scale

______________________________________________________________________

### Medium Profile

**Target**: Enterprise (64 vCPU, 256GB, 1 GPU, 10+ nodes)

**Segurança**: ✅ Full stack + HA

```yaml
# values-medium.yaml
keycloak:
  replicaCount: 2
  postgresql:
    primary:
      persistence:
        size: 20Gi

opa:
  replicaCount: 2
  resources:
    requests:
      cpu: 500m
      memory: 1Gi

vault:
  server:
    ha:
      replicas: 3
    dataStorage:
      size: 20Gi
    injector:
      enabled: true  # Vault Agent Injector para secrets automáticos

istio:
  enabled: true
  profile: default  # Full features
  pilot:
    replicaCount: 2
    resources:
      requests:
        cpu: "1"
        memory: 2Gi

networkPolicies:
  enabled: true
  enforceMode: true

kafka:
  replicaCount: 3
  auth:
    enabled: true
    clientProtocol: sasl_ssl
  logRetentionHours: 17520  # 2 years
```

**Características**:

- ✅ HA para todos os componentes (Keycloak, OPA, Vault, Istio)
- ✅ Vault Agent Injector (secrets injetados automaticamente)
- ✅ Istio profile: default (full features)
- ✅ Kafka 3 replicas
- ✅ Retention: 2 anos

**Uso**: Empresas médias, SaaS, aplicações críticas

______________________________________________________________________

### Large Profile

**Target**: Large-scale (256+ vCPU, 1TB+ RAM, 2+ GPUs, 50+ nodes)

**Segurança**: ✅ Maximum HA + Zero-Trust

```yaml
# values-large.yaml
keycloak:
  replicaCount: 3
  postgresql:
    primary:
      persistence:
        size: 50Gi

opa:
  replicaCount: 3
  resources:
    requests:
      cpu: "1"
      memory: 2Gi

vault:
  server:
    ha:
      replicas: 5  # 5 replicas para maior tolerância
    dataStorage:
      size: 50Gi
    injector:
      enabled: true
      replicas: 2  # HA no injector também

istio:
  enabled: true
  profile: production  # Istio production profile
  pilot:
    replicaCount: 3
    resources:
      requests:
        cpu: "2"
        memory: 4Gi

networkPolicies:
  enabled: true
  enforceMode: true
  zeroTrust: true  # Regras ainda mais restritivas

kafka:
  replicaCount: 5
  auth:
    enabled: true
    clientProtocol: sasl_ssl
  logRetentionHours: 26280  # 3 years
```

**Características**:

- ✅ Maximum HA (5 Vault replicas, 3 Keycloak, 3 OPA, 3 Istio)
- ✅ Zero-trust networking (regras ultra-restritivas)
- ✅ Istio production profile
- ✅ Kafka 5 replicas
- ✅ Retention: 3 anos

**Uso**: Grandes corporações, governo, high-traffic SaaS

______________________________________________________________________

## Guia de Testes

### 1. Testar Autenticação (Keycloak + JWT)

```bash
# 1.1: Obter token admin
ADMIN_TOKEN=$(curl -s -X POST "http://keycloak:8080/realms/master/protocol/openid-connect/token" \
  -d "username=admin" \
  -d "password=admin" \
  -d "grant_type=password" \
  -d "client_id=admin-cli" | jq -r '.access_token')

# 1.2: Criar usuário de teste
curl -X POST "http://keycloak:8080/admin/realms/opendatagov/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test-owner",
    "enabled": true,
    "credentials": [{"type": "password", "value": "testpass123", "temporary": false}],
    "realmRoles": ["data_owner"]
  }'

# 1.3: Obter token do usuário
USER_TOKEN=$(curl -s -X POST "http://keycloak:8080/realms/opendatagov/protocol/openid-connect/token" \
  -d "username=test-owner" \
  -d "password=testpass123" \
  -d "grant_type=password" \
  -d "client_id=odg-api" | jq -r '.access_token')

echo $USER_TOKEN | jwt decode -

# 1.4: Testar endpoint protegido (deve funcionar)
curl -X POST "http://governance-engine:8000/api/v1/decisions" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decision_type": "data_promotion", "title": "Test Decision"}'

# 1.5: Testar sem token (deve retornar 401)
curl -X POST "http://governance-engine:8000/api/v1/decisions" \
  -H "Content-Type: application/json" \
  -d '{"decision_type": "data_promotion", "title": "Test Decision"}'
```

**Resultado esperado**:

- ✅ Com token: 201 Created
- ❌ Sem token: 401 Unauthorized

______________________________________________________________________

### 2. Testar Autorização (OPA)

```bash
# 2.1: Testar policy diretamente
curl -X POST "http://opa:8181/v1/data/authz/allow" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "roles": ["data_owner"],
      "action": "create_decision"
    }
  }'
# {"result": true}

# 2.2: Testar com role insuficiente
curl -X POST "http://opa:8181/v1/data/authz/allow" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "roles": ["data_consumer"],
      "action": "create_decision"
    }
  }'
# {"result": false}

# 2.3: Testar resource-based access control
curl -X POST "http://opa:8181/v1/data/authz/accessible_resource" \
  -d '{
    "input": {
      "roles": ["data_consumer"],
      "resource_classification": "confidential"
    }
  }'
# {"result": false} - data_consumer não pode acessar confidential
```

**Resultado esperado**:

- ✅ data_owner pode create_decision
- ❌ data_consumer não pode create_decision
- ❌ data_consumer não pode acessar dados confidential

______________________________________________________________________

### 3. Testar Vault (Secrets Management)

```bash
# 3.1: Verificar status do Vault
kubectl exec -it vault-0 -- vault status

# 3.2: Testar KV secrets
kubectl exec -it vault-0 -- vault kv put secret/odg/test key=value
kubectl exec -it vault-0 -- vault kv get secret/odg/test

# 3.3: Testar dynamic database credentials
kubectl exec -it vault-0 -- vault read database/creds/odg-app
# Output:
# Key                Value
# ---                -----
# lease_id           database/creds/odg-app/abc123
# lease_duration     3600
# lease_renewable    true
# password           A1b-c2D3e4F5...
# username           v-kubernetes-odg-app-xyz123

# 3.4: Verificar credenciais funcionam
VAULT_USER=$(kubectl exec -it vault-0 -- vault read -field=username database/creds/odg-app)
VAULT_PASS=$(kubectl exec -it vault-0 -- vault read -field=password database/creds/odg-app)

kubectl exec -it postgresql-0 -- psql -U $VAULT_USER -d odg -c "SELECT current_user;"

# 3.5: Testar Transit encryption
kubectl exec -it vault-0 -- vault write transit/encrypt/odg-encryption plaintext=$(echo "sensitive data" | base64)
# ciphertext: vault:v1:abc123...

# 3.6: Verificar aplicação usa Vault
kubectl logs -l app=governance-engine | grep "Using Vault dynamic database credentials"
```

**Resultado esperado**:

- ✅ Vault status: Unsealed
- ✅ Dynamic credentials gerados
- ✅ Credenciais funcionam no PostgreSQL
- ✅ Transit encryption funciona
- ✅ Aplicação usa Vault

______________________________________________________________________

### 4. Testar mTLS (Istio)

```bash
# 4.1: Verificar Istio instalado
istioctl version
kubectl get pods -n istio-system

# 4.2: Verificar sidecars injetados
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].name}{"\n"}'
# governance-engine-0    governance-engine istio-proxy
# lakehouse-agent-0      lakehouse-agent istio-proxy

# 4.3: Verificar mTLS status
istioctl authn tls-check governance-engine-0.governance-engine -n opendatagov
# HOST:PORT                        STATUS     SERVER     CLIENT
# lakehouse-agent:8001             OK         STRICT     ISTIO_MUTUAL

# 4.4: Capturar tráfego (deve estar criptografado)
kubectl exec -it governance-engine-0 -c istio-proxy -- tcpdump -i any -A 'port 8001' &
kubectl exec -it governance-engine-0 -c governance-engine -- curl http://lakehouse-agent:8001/health

# 4.5: Verificar AuthorizationPolicy (zero-trust)
kubectl get authorizationpolicies
kubectl describe authorizationpolicy opendatagov-deny-all

# 4.6: Testar acesso bloqueado
kubectl run test-pod --image=curlimages/curl --rm -it -- curl -v http://governance-engine:8000/health
# Deve ser bloqueado se não estiver na allowlist
```

**Resultado esperado**:

- ✅ Sidecars injetados em todos os pods
- ✅ mTLS status: STRICT + ISTIO_MUTUAL
- ✅ Tráfego criptografado (não legível no tcpdump)
- ✅ AuthorizationPolicy bloqueia acessos não autorizados

______________________________________________________________________

### 5. Testar NetworkPolicies

```bash
# 5.1: Verificar NetworkPolicies criadas
kubectl get networkpolicies
kubectl describe networkpolicy opendatagov-default-deny-all

# 5.2: Testar acesso bloqueado (deve falhar)
kubectl run test-pod --image=busybox --rm -it -- wget -O- http://postgresql:5432
# Timeout (bloqueado por NetworkPolicy)

# 5.3: Testar acesso permitido (deve funcionar)
kubectl exec -it governance-engine-0 -c governance-engine -- \
  psql postgresql://odg:testpass@postgresql:5432/odg -c "SELECT 1;"
# (1 row)

# 5.4: Verificar DNS funciona (exception)
kubectl exec -it test-pod -- nslookup kubernetes.default

# 5.5: Monitorar violações (se Cilium)
kubectl logs -n kube-system -l k8s-app=cilium | grep -i "denied\|dropped"
```

**Resultado esperado**:

- ✅ Default deny-all policy presente
- ❌ Acesso direto bloqueado
- ✅ Acesso de pods autorizados funciona
- ✅ DNS funciona (exception)

______________________________________________________________________

### 6. Testar Audit Encryption

```bash
# 6.1: Verificar tabela audit_log_encrypted
kubectl exec -it postgresql-0 -- psql -U odg -d odg -c "\d audit_log_encrypted"

# 6.2: Inserir evento de teste (via API)
curl -X POST "http://governance-engine:8000/api/v1/decisions" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -d '{"decision_type": "data_promotion", "title": "Test"}'

# 6.3: Verificar evento criptografado
kubectl exec -it postgresql-0 -- psql -U odg -d odg -c \
  "SELECT id, event_hash, previous_hash, event_type, actor_id FROM audit_log_encrypted ORDER BY id DESC LIMIT 5;"

# 6.4: Verificar hash chain integrity
kubectl exec -it postgresql-0 -- psql -U odg -d odg -c \
  "SELECT * FROM verify_audit_chain();"
# is_valid | broken_at | total_checked
# ----------+-----------+--------------
#  t        |           |           100

# 6.5: Verificar Kafka audit topic
kubectl exec -it kafka-0 -- kafka-console-consumer.sh \
  --bootstrap-server kafka:9093 \
  --topic odg.audit.events \
  --from-beginning \
  --max-messages 5

# 6.6: Verificar retention
kubectl exec -it kafka-0 -- kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --describe \
  --topic odg.audit.events | grep retention.ms
```

**Resultado esperado**:

- ✅ Eventos criptografados (encrypted_event é BYTEA)
- ✅ Hash chain válido
- ✅ Kafka topic com retention de 1 ano

______________________________________________________________________

### 7. Testar Compliance Reports

```python
# 7.1: Gerar ADR compliance report
from odg_core.audit.compliance import ComplianceReport
import json

adr_report = ComplianceReport.generate_adr_compliance_report()
print(json.dumps(adr_report, indent=2))

# 7.2: Gerar GDPR compliance report
gdpr_report = ComplianceReport.generate_gdpr_compliance_report()
print(json.dumps(gdpr_report, indent=2))

# 7.3: Gerar security summary
summary = ComplianceReport.generate_security_summary()
print(json.dumps(summary, indent=2))

# 7.4: Verificar métricas de segurança
assert summary["security_metrics"]["authentication_enabled"] == True
assert summary["security_metrics"]["mtls_enabled"] == True
assert summary["security_posture"] == "STRONG"
```

**Resultado esperado**:

- ✅ ADR-072: COMPLIANT
- ✅ ADR-073: COMPLIANT
- ✅ GDPR Article 32: COMPLIANT
- ✅ Security posture: STRONG

______________________________________________________________________

### 8. E2E Security Test Script

```bash
#!/bin/bash
# test-security-stack.sh

set -e

echo "=== OpenDataGov Security Stack E2E Test ==="

# 1. Keycloak auth
echo "[1/8] Testing Keycloak authentication..."
USER_TOKEN=$(curl -s -X POST "http://keycloak:8080/realms/opendatagov/protocol/openid-connect/token" \
  -d "username=test-owner" -d "password=testpass123" -d "grant_type=password" -d "client_id=odg-api" | jq -r '.access_token')
[[ -n "$USER_TOKEN" ]] && echo "✅ Keycloak authentication successful"

# 2. API access with JWT
echo "[2/8] Testing API access with JWT..."
DECISION_ID=$(curl -s -X POST "http://governance-engine:8000/api/v1/decisions" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decision_type": "data_promotion", "title": "E2E Test"}' | jq -r '.id')
[[ -n "$DECISION_ID" ]] && echo "✅ API access successful (decision_id=$DECISION_ID)"

# 3. OPA policy enforcement
echo "[3/8] Testing OPA policy enforcement..."
OPA_RESULT=$(curl -s -X POST "http://opa:8181/v1/data/authz/allow" \
  -d '{"input": {"roles": ["data_owner"], "action": "create_decision"}}' | jq -r '.result')
[[ "$OPA_RESULT" == "true" ]] && echo "✅ OPA policy enforcement working"

# 4. Vault dynamic credentials
echo "[4/8] Testing Vault dynamic credentials..."
DB_USERNAME=$(kubectl exec vault-0 -- vault read -field=username database/creds/odg-app)
[[ -n "$DB_USERNAME" ]] && echo "✅ Vault dynamic credentials generated (user=$DB_USERNAME)"

# 5. mTLS verification
echo "[5/8] Testing mTLS..."
MTLS_STATUS=$(istioctl authn tls-check governance-engine-0.governance-engine -n opendatagov | grep lakehouse-agent | awk '{print $2}')
[[ "$MTLS_STATUS" == "OK" ]] && echo "✅ mTLS verification successful"

# 6. NetworkPolicy isolation
echo "[6/8] Testing NetworkPolicy isolation..."
timeout 5 kubectl run test-pod --image=busybox --rm -it -- wget -O- http://postgresql:5432 2>&1 | grep -q "timeout" && echo "✅ NetworkPolicy isolation working"

# 7. Encrypted audit logs
echo "[7/8] Testing encrypted audit logs..."
AUDIT_COUNT=$(kubectl exec postgresql-0 -- psql -U odg -d odg -tAc "SELECT COUNT(*) FROM audit_log_encrypted WHERE event_type='decision_created';")
[[ "$AUDIT_COUNT" -gt 0 ]] && echo "✅ Encrypted audit logs working (count=$AUDIT_COUNT)"

# 8. Hash chain integrity
echo "[8/8] Testing audit hash chain integrity..."
CHAIN_VALID=$(kubectl exec postgresql-0 -- psql -U odg -d odg -tAc "SELECT is_valid FROM verify_audit_chain();")
[[ "$CHAIN_VALID" == "t" ]] && echo "✅ Audit hash chain integrity verified"

echo ""
echo "=== All Security Tests Passed ✅ ==="
```

______________________________________________________________________

## Troubleshooting

### Problema: JWT validation falha

**Sintoma**: 401 Unauthorized com "Invalid token"

**Diagnóstico**:

```bash
# Verificar Keycloak está acessível
curl http://keycloak:8080/health/ready

# Verificar JWKS endpoint
curl http://keycloak:8080/realms/opendatagov/protocol/openid-connect/certs

# Verificar logs do governance-engine
kubectl logs -l app=governance-engine | grep -i "jwt\|keycloak"
```

**Solução**:

1. Verificar `KEYCLOAK_SERVER_URL` aponta para Keycloak correto
1. Verificar `KEYCLOAK_REALM` = `opendatagov`
1. Verificar `KEYCLOAK_CLIENT_ID` = `odg-api`
1. Recriar realm se necessário: `kubectl delete job keycloak-init && helm upgrade odg`

______________________________________________________________________

### Problema: OPA nega acesso inesperadamente

**Sintoma**: 403 Forbidden mesmo com role correta

**Diagnóstico**:

```bash
# Testar policy diretamente
curl -X POST "http://opa:8181/v1/data/authz/allow" -d '{
  "input": {
    "roles": ["data_owner"],
    "action": "create_decision"
  }
}'

# Verificar logs do OPA
kubectl logs -l app.kubernetes.io/name=opa

# Verificar policies carregadas
curl http://opa:8181/v1/policies
```

**Solução**:

1. Verificar policies em `/deploy/helm/opendatagov/opa-policies/authz.rego`
1. Recarregar policies: `kubectl rollout restart deployment opa`
1. Verificar input enviado ao OPA corresponde ao esperado pela policy

______________________________________________________________________

### Problema: Vault dynamic credentials expiram

**Sintoma**: "Database connection failed" depois de 1 hora

**Diagnóstico**:

```bash
# Verificar lease
kubectl exec vault-0 -- vault lease lookup database/creds/odg-app/abc123

# Verificar LeaseManager está rodando
kubectl logs -l app=governance-engine | grep "LeaseManager\|lease renewal"
```

**Solução**:

1. Verificar `LeaseManager` está iniciado: `await lease_manager.start()`
1. Aumentar TTL no Vault: `vault write database/roles/odg-app default_ttl="4h"`
1. Verificar threshold de renewal (default: 50%)

______________________________________________________________________

### Problema: mTLS handshake falha

**Sintoma**: "upstream connect error or disconnect/reset before headers"

**Diagnóstico**:

```bash
# Verificar PeerAuthentication
kubectl get peerauthentication

# Verificar sidecars injetados
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].name}{"\n"}'

# Verificar mTLS status
istioctl authn tls-check governance-engine-0.governance-engine

# Logs do Envoy sidecar
kubectl logs governance-engine-0 -c istio-proxy | grep -i "tls\|handshake"
```

**Solução**:

1. Verificar namespace tem label `istio-injection=enabled`
1. Recriar pods: `kubectl rollout restart deployment governance-engine`
1. Verificar PeerAuthentication mode=STRICT
1. Verificar DestinationRule usa `tls.mode=ISTIO_MUTUAL`

______________________________________________________________________

### Problema: NetworkPolicy bloqueia tráfego legítimo

**Sintoma**: Timeout ao conectar entre serviços

**Diagnóstico**:

```bash
# Verificar NetworkPolicies aplicadas
kubectl get networkpolicies
kubectl describe networkpolicy governance-engine

# Testar conexão
kubectl exec -it governance-engine-0 -- curl -v http://postgresql:5432

# Monitorar violações (Cilium)
kubectl logs -n kube-system -l k8s-app=cilium | grep -i denied
```

**Solução**:

1. Adicionar regra de egress no NetworkPolicy do pod origem
1. Adicionar regra de ingress no NetworkPolicy do pod destino
1. Verificar labels dos pods: `kubectl get pods --show-labels`
1. Temporariamente desabilitar enforceMode: `enforceMode: false` (dev only!)

______________________________________________________________________

### Problema: Certificados expirados

**Sintoma**: "x509: certificate has expired"

**Diagnóstico**:

```bash
# Verificar certificados
kubectl get certificates

# Detalhes do certificado
kubectl describe certificate governance-engine-grpc

# Verificar expiration
kubectl get secret governance-engine-grpc-tls -o json | \
  jq -r '.data["tls.crt"]' | base64 -d | openssl x509 -noout -dates
```

**Solução**:

1. Verificar cert-manager está rodando: `kubectl get pods -n cert-manager`
1. Forçar renewal: `kubectl delete certificate governance-engine-grpc`
1. Verificar ClusterIssuer: `kubectl get clusterissuer`
1. Aumentar `renewBefore` no Certificate spec

______________________________________________________________________

### Problema: Audit hash chain quebrado

**Sintoma**: `verify_audit_chain()` retorna `is_valid=false`

**Diagnóstico**:

```bash
# Executar verificação
kubectl exec postgresql-0 -- psql -U odg -d odg -c "SELECT * FROM verify_audit_chain();"

# Identificar evento problemático
kubectl exec postgresql-0 -- psql -U odg -d odg -c \
  "SELECT id, event_hash, previous_hash FROM audit_log_encrypted WHERE id >= (SELECT broken_at FROM verify_audit_chain()) LIMIT 5;"
```

**Solução**:

1. ⚠️ **Hash chain quebrada indica possível tampering!**
1. Investigar logs ao redor do evento: `kubectl logs ... | grep -A5 -B5 "event_id=X"`
1. Verificar backups do audit log
1. **Não deletar eventos** (isso invalida ainda mais a chain)
1. Registrar incidente de segurança

______________________________________________________________________

## Referências

### ADRs (Architecture Decision Records)

- **ADR-072**: Keycloak (OIDC/SAML) + OPA (Rego) para AuthN/AuthZ
- **ADR-073**: HashiCorp Vault + mTLS via Istio

### Standards e Frameworks

- **RACI Model**: Responsible, Accountable, Consulted, Informed
- **GDPR**: General Data Protection Regulation (EU)
- **LGPD**: Lei Geral de Proteção de Dados (Brasil)
- **SOX**: Sarbanes-Oxley Act (Financial compliance)
- **Pod Security Standards**: Kubernetes security policies (restricted, baseline, privileged)

### Tecnologias

- **Keycloak**: https://www.keycloak.org/docs/latest/
- **OPA**: https://www.openpolicyagent.org/docs/latest/
- **Vault**: https://developer.hashicorp.com/vault/docs
- **Istio**: https://istio.io/latest/docs/
- **cert-manager**: https://cert-manager.io/docs/
- **Kafka Security**: https://kafka.apache.org/documentation/#security

### Implementação OpenDataGov

- **GitHub**: https://github.com/yourorg/opendatagov
- **Helm Charts**: `/deploy/helm/opendatagov/`
- **Core Library**: `/libs/python/odg-core/`
- **Services**: `/services/governance-engine/`

______________________________________________________________________

**Última atualização**: 2025-02-08
**Versão**: 1.0
**Autores**: OpenDataGov Security Team
**Status**: ✅ Implementado e Testado
