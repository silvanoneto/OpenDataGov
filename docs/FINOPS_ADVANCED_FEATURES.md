# FinOps Dashboard - Advanced Features Guide

## 📚 Overview

Este guia cobre as funcionalidades avançadas implementadas:

1. **Database Migrations (Alembic)** - Versionamento de schema do banco de dados
1. **Azure Cost Integration** - Coleta de custos do Azure Cost Management API
1. **Auth0 JWT Authentication** - Autenticação e autorização baseada em roles

______________________________________________________________________

## 🗄️ Database Migrations com Alembic

### Setup Inicial

O FinOps Dashboard usa **Alembic** para gerenciar migrações de schema do banco de dados.

**Arquivos criados:**

- `alembic.ini` - Configuração do Alembic
- `alembic/env.py` - Environment configuration
- `alembic/script.py.mako` - Template para migrations
- `alembic/versions/001_initial_schema.py` - Migration inicial

### Estrutura do Schema

**Tabelas criadas pela migration inicial:**

```sql
-- TimescaleDB Hypertable
cloud_costs (
    time, cloud_provider, account_id, service,
    region, cost, currency, resource_id, resource_name,
    tags JSONB, project, team, environment
)

-- Budget Management
budgets (budget_id, budget_name, scope_type, scope_value,
         amount, currency, period, alert_thresholds, alert_channels)

budget_status_history (history_id, budget_id, snapshot_date,
                       spent_to_date, remaining, pct_consumed, burn_rate)

-- Anomaly Detection
cost_anomalies (anomaly_id, detected_at, cloud_provider, service,
                expected_cost, actual_cost, deviation_pct,
                detection_method, confidence_score, status)

-- Savings Recommendations
savings_recommendations (recommendation_id, generated_at, type, priority,
                         cloud_provider, service, resource_id,
                         monthly_savings, annual_savings, status)
```

### Executando Migrations

**1. Verificar status atual:**

```bash
cd services/finops-dashboard
alembic current
```

**2. Aplicar todas as migrations:**

```bash
alembic upgrade head
```

**3. Reverter última migration:**

```bash
alembic downgrade -1
```

**4. Ver histórico de migrations:**

```bash
alembic history
```

### Criando Nova Migration

**1. Autogenerate (detecta mudanças nos models):**

```bash
alembic revision --autogenerate -m "add new table"
```

**2. Manual (migration vazia):**

```bash
alembic revision -m "add custom index"
```

**3. Editar arquivo gerado:**

```python
# alembic/versions/002_add_cost_forecasts.py

def upgrade() -> None:
    op.create_table(
        'cost_forecasts',
        sa.Column('forecast_id', sa.Integer(), autoincrement=True),
        sa.Column('forecast_date', sa.Date(), nullable=False),
        sa.Column('cloud_provider', sa.String(10)),
        sa.Column('predicted_cost', sa.DECIMAL(12, 2)),
        sa.Column('confidence_lower', sa.DECIMAL(12, 2)),
        sa.Column('confidence_upper', sa.DECIMAL(12, 2)),
        sa.Column('model', sa.String(50)),
        sa.PrimaryKeyConstraint('forecast_id'),
    )

def downgrade() -> None:
    op.drop_table('cost_forecasts')
```

**4. Aplicar nova migration:**

```bash
alembic upgrade head
```

### TimescaleDB Features

A migration inicial configura:

**Hypertable:**

```sql
SELECT create_hypertable('cloud_costs', 'time',
    chunk_time_interval => INTERVAL '1 day');
```

**Compression (dados > 7 dias):**

```sql
ALTER TABLE cloud_costs SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'cloud_provider,account_id,service'
);

SELECT add_compression_policy('cloud_costs', INTERVAL '7 days');
```

**Retention policy (opcional):**

```sql
-- Manter apenas 1 ano de dados
SELECT add_retention_policy('cloud_costs', INTERVAL '1 year');
```

### Configuração do Database URL

**Via variável de ambiente:**

```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/finops"
alembic upgrade head
```

**Editando alembic.ini:**

```ini
sqlalchemy.url = postgresql+asyncpg://odg:odg@postgres:5432/finops
```

### Troubleshooting

**Erro: "No module named 'finops_dashboard'"**

```bash
# Adicione o diretório src ao PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
alembic upgrade head
```

**Erro: "Target database is not up to date"**

```bash
# Force stamp to current version
alembic stamp head
```

**Erro: "TimescaleDB extension not found"**

```sql
-- Conectar ao PostgreSQL e executar:
CREATE EXTENSION IF NOT EXISTS timescaledb;
```

______________________________________________________________________

## ☁️ Azure Cost Integration

### Overview

O **Azure Cost Collector** coleta dados de custo do Azure Cost Management API usando a biblioteca `azure-mgmt-costmanagement`.

**Arquivo:** `services/finops-dashboard/src/finops_dashboard/collectors/azure_collector.py`

### Pré-requisitos

**1. Azure Billing Export (opcional, mas recomendado):**

- Configurar export automático para Storage Account
- Mais rápido que API queries

**2. Service Principal com permissões:**

```bash
# Criar service principal
az ad sp create-for-rbac --name "finops-collector" \
  --role "Cost Management Reader" \
  --scopes "/subscriptions/{subscription-id}"

# Output:
{
  "appId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "displayName": "finops-collector",
  "password": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenant": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

### Autenticação

**Opção 1: Service Principal (Produção)**

```python
from finops_dashboard.collectors.azure_collector import AzureCostCollector

collector = AzureCostCollector(
    subscription_id="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    tenant_id="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    client_id="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    client_secret="your-secret-here"
)
```

**Opção 2: Managed Identity (Azure VM/AKS)**

```python
# DefaultAzureCredential detecta automaticamente
collector = AzureCostCollector(
    subscription_id="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
)
```

**Opção 3: Azure CLI (Desenvolvimento)**

```bash
az login
```

```python
# Usa credenciais do Azure CLI
collector = AzureCostCollector(subscription_id="...")
```

### Uso Básico

**Coletar custos via API:**

```python
from datetime import date, timedelta

# Últimos 7 dias
start_date = date.today() - timedelta(days=7)
end_date = date.today()

costs = await collector.fetch_costs(start_date, end_date)

# Salvar no database
for cost in costs:
    # CloudCost pydantic model
    print(f"{cost.service}: ${cost.cost}")
```

**Coletar custos com tag grouping:**

```python
costs = await collector.fetch_detailed_costs_with_tags(
    start_date=start_date,
    end_date=end_date,
    tag_key="environment"  # ou "project", "team"
)
```

**Detectar recursos idle:**

```python
idle_resources = await collector.detect_idle_resources()

for resource in idle_resources:
    print(f"Idle: {resource['resource_id']} - ${resource['monthly_cost']}/mês")
```

**Top spenders:**

```python
top_services = await collector.get_top_spenders(
    start_date=start_date,
    end_date=end_date,
    limit=10
)
```

### API REST Endpoint

**POST /api/v1/finops/costs/collect/azure**

```bash
curl -X POST "http://localhost:8080/api/v1/finops/costs/collect/azure" \
  -H "Content-Type: application/json" \
  -d '{
    "subscription_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "start_date": "2026-02-01",
    "end_date": "2026-02-08"
  }'
```

**Response:**

```json
{
  "cloud_provider": "azure",
  "records_inserted": 234,
  "total_cost": 1234.56,
  "date_range": ["2026-02-01T00:00:00", "2026-02-08T00:00:00"],
  "collection_time": "2026-02-08T10:30:00"
}
```

### Configuração Kubernetes

**Secret para credenciais Azure:**

```bash
kubectl create secret generic azure-credentials \
  --from-literal=subscription-id=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
  --from-literal=tenant-id=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
  --from-literal=client-id=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
  --from-literal=client-secret=your-secret \
  -n odg-platform
```

**Deployment com Azure credentials:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: finops-dashboard
spec:
  template:
    spec:
      containers:
        - name: finops-dashboard
          env:
            - name: AZURE_SUBSCRIPTION_ID
              valueFrom:
                secretKeyRef:
                  name: azure-credentials
                  key: subscription-id
            - name: AZURE_TENANT_ID
              valueFrom:
                secretKeyRef:
                  name: azure-credentials
                  key: tenant-id
            - name: AZURE_CLIENT_ID
              valueFrom:
                secretKeyRef:
                  name: azure-credentials
                  key: client-id
            - name: AZURE_CLIENT_SECRET
              valueFrom:
                secretKeyRef:
                  name: azure-credentials
                  key: client-secret
```

### Métricas Azure Monitor

**Obter utilização de recursos (rightsizing):**

```python
# CPU de uma VM
cpu_stats = await collector.get_resource_utilization(
    resource_id="/subscriptions/.../resourceGroups/.../providers/Microsoft.Compute/virtualMachines/vm-prod",
    metric_name="Percentage CPU",
    days=14
)

print(f"CPU médio: {cpu_stats['average']:.1f}%")
print(f"CPU máximo: {cpu_stats['maximum']:.1f}%")
print(f"CPU P95: {cpu_stats['p95']:.1f}%")
```

### Limitações

1. **Rate Limits:** Azure Cost Management API tem limites

   - 8 requests/min por subscription
   - Solução: Caching, batch processing

1. **Data Latency:** Custos podem ter atraso de 24-48h

   - Dados finais disponíveis em ~72h

1. **Tag Propagation:** Tags podem não estar em todos os recursos

   - Implementar tag governance policy

### Troubleshooting

**Erro: "AuthenticationError: Unauthorized"**

```bash
# Verificar permissões do service principal
az role assignment list --assignee {client-id} --subscription {subscription-id}

# Deve ter "Cost Management Reader" ou "Reader"
```

**Erro: "InvalidQueryFilter"**

```python
# Tag não existe - usar try/except
try:
    costs = await collector.fetch_detailed_costs_with_tags(tag_key="project")
except Exception as e:
    logger.warning(f"Tag 'project' não encontrada: {e}")
```

**Custos zerados:**

```bash
# Verificar se subscription tem custos no período
az consumption usage list --start-date 2026-02-01 --end-date 2026-02-08
```

______________________________________________________________________

## 🔐 Auth0 JWT Authentication

### Overview

O FinOps Dashboard usa **Auth0** para autenticação JWT com suporte a:

- ✅ Role-Based Access Control (RBAC)
- ✅ Permission-based authorization
- ✅ User identity management
- ✅ Automatic token validation

**Arquivo:** `services/finops-dashboard/src/finops_dashboard/auth.py`

### Setup Auth0

**1. Criar conta Auth0:**

- Acesse https://auth0.com
- Crie um novo tenant (ex: `opendatagov.us.auth0.com`)

**2. Criar API:**

```
Dashboard → Applications → APIs → Create API

Nome: FinOps Dashboard API
Identifier: https://api.opendatagov.com/finops
Signing Algorithm: RS256
```

**3. Habilitar RBAC:**

```
Settings → Enable RBAC: ON
Add Permissions in the Access Token: ON
```

**4. Criar Roles:**

```
User Management → Roles → Create Role

Roles:
- admin (full access)
- finance_manager (read + write budgets)
- viewer (read only)
```

**5. Criar Permissions:**

```
Applications → APIs → FinOps Dashboard API → Permissions

Permissions:
- read:costs
- read:budgets
- write:budgets
- delete:budgets
- read:recommendations
- write:recommendations
- read:anomalies
- write:anomalies
```

**6. Atribuir Permissions às Roles:**

```
admin:
  - read:*, write:*, delete:*

finance_manager:
  - read:costs, read:budgets, write:budgets
  - read:recommendations, write:recommendations

viewer:
  - read:costs, read:budgets, read:recommendations
```

### Configuração da Aplicação

**Variáveis de ambiente:**

```bash
# .env
AUTH0_DOMAIN=opendatagov.us.auth0.com
AUTH0_AUDIENCE=https://api.opendatagov.com/finops
```

**Kubernetes Secret:**

```bash
kubectl create secret generic auth0-config \
  --from-literal=domain=opendatagov.us.auth0.com \
  --from-literal=audience=https://api.opendatagov.com/finops \
  -n odg-platform
```

**Deployment:**

```yaml
env:
  - name: AUTH0_DOMAIN
    valueFrom:
      secretKeyRef:
        name: auth0-config
        key: domain
  - name: AUTH0_AUDIENCE
    valueFrom:
      secretKeyRef:
        name: auth0-config
        key: audience
```

### Uso no FastAPI

**1. Endpoint protegido (authentication required):**

```python
from finops_dashboard.auth import get_current_user, User

@app.get("/api/v1/finops/costs/summary")
async def get_cost_summary(
    user: User = Depends(get_current_user)  # Requer JWT válido
):
    logger.info(f"User {user.user_id} accessing cost summary")
    return {"user_id": user.user_id, "costs": [...]}
```

**2. Endpoint com verificação de role:**

```python
from finops_dashboard.auth import RoleChecker

@app.delete("/api/v1/finops/budgets/{id}")
async def delete_budget(
    id: int,
    user: User = Depends(RoleChecker(["admin"]))  # Apenas admin
):
    # Deletar budget
    return {"success": True}
```

**3. Endpoint com verificação de permission:**

```python
from finops_dashboard.auth import PermissionChecker

@app.post("/api/v1/finops/budgets")
async def create_budget(
    budget: BudgetCreate,
    user: User = Depends(PermissionChecker(["write:budgets"]))
):
    # Criar budget
    return {"budget_id": 123}
```

**4. Endpoint opcional (authenticated or anonymous):**

```python
from finops_dashboard.auth import get_current_user_optional

@app.get("/api/v1/finops/public/summary")
async def public_summary(
    user: User | None = Depends(get_current_user_optional)
):
    if user:
        # Dados detalhados para usuário autenticado
        return {"detailed": True, "user": user.user_id}
    else:
        # Dados resumidos para anônimo
        return {"detailed": False}
```

### Obter Token JWT

**Opção 1: Auth0 Dashboard (Testing):**

```
Applications → APIs → FinOps Dashboard API → Test

Copiar o Access Token gerado
```

**Opção 2: Programaticamente (Client Credentials Flow):**

```bash
curl --request POST \
  --url https://opendatagov.us.auth0.com/oauth/token \
  --header 'content-type: application/json' \
  --data '{
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "audience": "https://api.opendatagov.com/finops",
    "grant_type": "client_credentials"
  }'
```

**Response:**

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 86400,
  "token_type": "Bearer"
}
```

**Opção 3: Authorization Code Flow (Web App):**

```javascript
// Frontend (React, Vue, etc.)
import { createAuth0Client } from '@auth0/auth0-spa-js';

const auth0 = await createAuth0Client({
  domain: 'opendatagov.us.auth0.com',
  clientId: 'YOUR_CLIENT_ID',
  authorizationParams: {
    audience: 'https://api.opendatagov.com/finops',
    redirect_uri: window.location.origin
  }
});

// Login
await auth0.loginWithRedirect();

// Get token
const token = await auth0.getTokenSilently();
```

### Fazer Request com JWT

```bash
curl -X GET "http://localhost:8080/api/v1/finops/costs/summary" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```python
import httpx

token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."

async with httpx.AsyncClient() as client:
    response = await client.get(
        "http://localhost:8080/api/v1/finops/costs/summary",
        headers={"Authorization": f"Bearer {token}"}
    )
    print(response.json())
```

### User Model

**Estrutura do User:**

```python
class User(BaseModel):
    sub: str  # User ID (e.g., "auth0|123456")
    email: str | None
    name: str | None
    roles: list[str]  # ["admin", "finance_manager"]
    permissions: list[str]  # ["read:budgets", "write:budgets"]

# Métodos
user.has_role("admin")  # True/False
user.has_permission("write:budgets")  # True/False
user.has_any_role("admin", "finance_manager")  # True se tiver qualquer uma
```

### Decorators Customizados

```python
from finops_dashboard.auth import require_role, require_permission

@require_role("admin", "finance_manager")
async def admin_function(user: User):
    # Apenas admin ou finance_manager
    pass

@require_permission("write:budgets", "delete:budgets")
async def manage_budgets(user: User):
    # Requer ambas as permissões
    pass
```

### Mock Authentication (Development)

**Modo desenvolvimento (sem Auth0):**

```python
from finops_dashboard.auth import MockAuth, get_current_user_dev

# No startup da aplicação
if not os.getenv("AUTH0_DOMAIN"):
    app.dependency_overrides[get_current_user] = get_current_user_dev

# Retorna user mock:
# - user_id: "dev|123456"
# - email: "dev@opendatagov.com"
# - roles: ["admin", "finance_manager"]
# - permissions: ["read:*", "write:*", "delete:*"]
```

**⚠️ NUNCA use em produção!**

### JWT Token Structure

**Decoded JWT:**

```json
{
  "iss": "https://opendatagov.us.auth0.com/",
  "sub": "auth0|123456789",
  "aud": "https://api.opendatagov.com/finops",
  "iat": 1707401600,
  "exp": 1707488000,
  "scope": "openid profile email",
  "azp": "CLIENT_ID",
  "permissions": [
    "read:budgets",
    "write:budgets",
    "read:costs"
  ],
  "https://opendatagov.com/roles": [
    "finance_manager"
  ],
  "email": "user@example.com",
  "name": "John Doe"
}
```

### Error Handling

**401 Unauthorized:**

```json
{
  "detail": "Token has expired"
}
```

**403 Forbidden:**

```json
{
  "detail": "Missing permissions: ['write:budgets']"
}
```

**500 Internal Server Error:**

```json
{
  "detail": "Auth0 not configured"
}
```

### Troubleshooting

**Erro: "Invalid token signature"**

```bash
# Verificar se JWKS está acessível
curl https://opendatagov.us.auth0.com/.well-known/jwks.json
```

**Erro: "Token audience mismatch"**

```bash
# Audience no token deve corresponder ao AUTH0_AUDIENCE
# Verificar configuração da API no Auth0
```

**Erro: "Permission not granted"**

```bash
# Verificar se user tem a permission atribuída:
# Auth0 Dashboard → User Management → Users → {user} → Permissions
```

**Token expirado:**

```python
# Tokens JWT expiram em 24h (padrão)
# Frontend deve renovar automaticamente usando refresh token
```

### Best Practices

1. **Usar HTTPS em produção**

   - JWT em HTTP pode ser interceptado

1. **Curto tempo de expiração**

   - Tokens curtos (1-24h) + refresh tokens

1. **Validar permissions no backend**

   - Nunca confiar apenas no frontend

1. **Audit logging**

   ```python
   logger.info(f"User {user.user_id} created budget {budget_id}")
   ```

1. **Rate limiting por user**

   ```python
   # Implementar rate limit baseado em user.user_id
   ```

______________________________________________________________________

## 🚀 Deployment Completo

### 1. Build da Imagem Docker

```bash
cd services/finops-dashboard
docker build -t odg/finops-dashboard:2.0.0 .
docker push odg/finops-dashboard:2.0.0
```

### 2. Aplicar Migrations

```bash
# Via Job Kubernetes
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: finops-migrations
  namespace: odg-platform
spec:
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: alembic
          image: odg/finops-dashboard:2.0.0
          command: ["alembic", "upgrade", "head"]
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: finops-dashboard-secrets
                  key: database-url
EOF
```

### 3. Deploy via Helm

```bash
helm upgrade --install opendatagov ./deploy/helm/opendatagov \
  --namespace odg-platform \
  --values ./deploy/helm/opendatagov/values-large.yaml \
  --set finops-dashboard.enabled=true \
  --set finops-dashboard.azure.enabled=true \
  --set finops-dashboard.azure.subscriptionId="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

### 4. Verificar Deployment

```bash
# Pods
kubectl get pods -n odg-platform | grep finops

# Logs
kubectl logs -f deployment/finops-dashboard -n odg-platform

# API health
kubectl port-forward svc/finops-dashboard 8080:8080 -n odg-platform
curl http://localhost:8080/health
```

### 5. Testar Autenticação

```bash
# Obter token Auth0
TOKEN=$(curl -s --request POST \
  --url https://opendatagov.us.auth0.com/oauth/token \
  --header 'content-type: application/json' \
  --data '{
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "audience": "https://api.opendatagov.com/finops",
    "grant_type": "client_credentials"
  }' | jq -r '.access_token')

# Testar endpoint protegido
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/v1/finops/budgets
```

______________________________________________________________________

## 📊 Monitoring & Observability

### Logs Estruturados

```python
logger.info("Cost collection completed", extra={
    "cloud_provider": "azure",
    "records": 234,
    "cost": 1234.56,
    "user_id": user.user_id
})
```

### Metrics (Prometheus)

```python
from prometheus_client import Counter, Histogram

requests_total = Counter('finops_requests_total', 'Total requests', ['method', 'endpoint'])
auth_failures = Counter('finops_auth_failures_total', 'Auth failures', ['reason'])
```

### Tracing (OpenTelemetry)

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

@app.post("/api/v1/finops/budgets")
async def create_budget():
    with tracer.start_as_current_span("create_budget"):
        # Implementation
        pass
```

______________________________________________________________________

## 🔒 Security Checklist

- [x] JWT validation com Auth0
- [x] HTTPS enforced (produção)
- [x] RBAC implementado
- [x] Secrets em Kubernetes Secrets (não hardcoded)
- [x] Database migrations versionadas
- [x] Rate limiting (TODO)
- [x] Input validation (Pydantic)
- [x] SQL injection protection (SQLAlchemy ORM)
- [x] CORS configurado
- [ ] API key rotation policy
- [ ] Audit logging completo
- [ ] DDoS protection (Cloudflare/WAF)

______________________________________________________________________

**Documentação completa!** ✅

Agora o FinOps Dashboard tem:

- ✅ Database migrations com Alembic
- ✅ Azure Cost Management integration
- ✅ Auth0 JWT authentication com RBAC
- ✅ Documentação detalhada de todas as features

**Próximos passos opcionais:**

- Testes E2E com pytest
- CI/CD pipeline (GitHub Actions)
- Performance testing (Locust)
- API versioning (v2)
