# OpenDataGov — Decisões Arquiteturais

<!--
document_metadata:
  version: "0.1.0"
  status: COMPLETE
  created: 2026-02-07
  authors:
    - role: human_architect
      name: Silvano Neto
    - role: ai_architect
      name: Claude (Opus 4.6)
  source: docs/ARCHITECTURE_DEFINITIONS.md
  total_adrs: 50
  decided: 50
  open: 0
  deferred: 0
-->

## Como usar este documento

Este documento registra as **decisões** tomadas a partir das definições em `ARCHITECTURE_DEFINITIONS.md`. Cada entrada inclui:

- **Decisão** — o que foi decidido
- **Justificativa** — por que essa opção
- **Impacto** — quais outras ADRs são afetadas
- **Data** — quando foi decidido

**Status possíveis:** `DECIDED`, `DEFERRED`, `REVISIT`

______________________________________________________________________

## Seção 1: Identidade e Escopo da Plataforma

### ADR-001: Missão da Plataforma

<!-- metadata:
  id: ADR-001
  status: DECIDED
  decided_value: "(b)+(c) progressivo"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** Opção **(b)+(c) com graduação progressiva** — Plataforma de dados completa com governança AI-assistida progressiva.

**Detalhamento:**

1. **Plataforma completa (b):** Lakehouse (Bronze/Silver/Gold), catálogo de dados, qualidade de dados, lineage, observabilidade, privacidade e segurança — tudo integrado em um sistema coeso.

1. **AI progressiva (c com graduação):** A plataforma opera em **modo degradado sem IA** (funcional, porém manual). Conforme a confiança organizacional aumenta, a IA (B-Swarm) assume progressivamente mais responsabilidades — **sempre no modo "IA recomenda, humano decide"**. O nível de autonomia da IA é configurável por organização/deployment.

1. **Multi-setor modular:** Core único com módulos de compliance plugáveis por setor:

   - **Governo/Setor Público:** LGPD, soberania de dados, auditoria rigorosa
   - **Enterprise privado:** SOX, GDPR, integração com ecossistema existente

**Justificativa:**

- A progressividade reduz risco de adoção: organizações podem começar sem IA e evoluir
- "IA recomenda, humano decide" alinha com EU AI Act Art. 14 (supervisão humana) e NIST AI RMF
- A modularidade multi-setor maximiza o mercado endereçável sem fragmentar o core
- Mantém a proposta de valor diferenciada do B-Swarm sem torná-lo requisito

**Impacto em outras ADRs:**

- ADR-002: Público é ambos (governo + enterprise), modular
- ADR-011: IA recomenda, humano decide (já decidido implicitamente)
- ADR-030: Favorece modelo híbrido (B-Swarm como governance layer sobre MLOps)
- ADR-034: Extensibilidade de experts precisa suportar "sem experts" como estado válido
- ADR-121: Perfil "dev" pode ser sem IA; "medium/large" com IA progressiva

**Data:** 2026-02-07

______________________________________________________________________

### ADR-002: Persona-Alvo e Contexto de Deploy

<!-- metadata:
  id: ADR-002
  status: DECIDED
  decided_value: "single-org, 10-100TB/dia, air-gapped obrigatório, multi-setor"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** Deploy **single-org** (cada organização opera sua instância), com volume de referência de **10-100TB/dia**, e **air-gapped obrigatório** (zero dependência de internet/APIs externas).

**Detalhamento:**

1. **Single-org por instância:** Cada organização implanta e opera sua própria instância do OpenDataGov. Não há multi-tenancy. A comunicação entre instâncias de diferentes organizações se dá via federação COSMOS.

1. **Volume de referência: 10-100TB/dia:** A arquitetura deve ser dimensionada para large enterprise desde o início. Isso implica:

   - Spark/Trino otimizados para escala
   - Multi-AZ para alta disponibilidade
   - GPU infrastructure para inferência de IA local
   - Armazenamento otimizado por temperatura (hot/warm/cold)

1. **Air-gapped obrigatório:** Toda a stack deve funcionar 100% offline:

   - Modelos de IA servidos localmente (vLLM com modelos pré-baixados)
   - Registry de containers local (Harbor ou similar)
   - Sem dependência de cloud APIs (OpenAI, Anthropic, etc.)
   - Todas as dependências empacotáveis para instalação offline

1. **Multi-setor:** Conforme ADR-001, core único com módulos de compliance plugáveis para governo e enterprise privado.

**Justificativa:**

- Single-org alinha com requisitos de soberania de dados (governo) e isolamento (enterprise)
- 10-100TB/dia posiciona o OpenDataGov como solução enterprise-grade, não toy project
- Air-gapped é requisito mandatório para governo/defesa e desejável para enterprise com dados sensíveis
- A federação COSMOS permite cooperação entre instâncias sem comprometer isolamento

**Impacto em outras ADRs:**

- ADR-022: Storage deve ser MinIO (self-hosted) ou abstração S3-compatible, não cloud-native
- ADR-031: vLLM local é mandatório; cloud APIs descartadas como opção primária
- ADR-072: IdP deve ser self-hosted (Keycloak), não cloud-managed
- ADR-080: K8s deve rodar on-prem ou em gov-cloud, não apenas EKS
- ADR-083: Scaling deve funcionar sem Karpenter (cloud-specific)
- ADR-084: Dev local precisa simular air-gap
- ADR-092: COSMOS federation precisa funcionar sem internet pública

**Data:** 2026-02-07

______________________________________________________________________

### ADR-003: Licenciamento e Estratégia Open-Source

<!-- metadata:
  id: ADR-003
  status: DECIDED
  decided_value: "Apache-2.0"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **Apache-2.0** — licença permissiva, padrão CNCF/Apache Foundation.

**Detalhamento:**

O OpenDataGov será licenciado sob Apache-2.0, substituindo o AGPL-3.0 herdado do RADaC. Isso significa:

- Qualquer pessoa/organização pode usar, modificar e distribuir (inclusive comercialmente) sem obrigação de abrir código derivado
- Forks proprietários são permitidos
- Não há proteção contra cloud-washing (AWS/GCP podem oferecer como serviço gerenciado)

**Justificativa:**

- **Adoção enterprise:** Departamentos jurídicos de grandes empresas frequentemente bloqueiam AGPL. Apache-2.0 elimina essa barreira
- **Adoção governo:** Muitos órgãos públicos também preferem licenças permissivas por simplicidade jurídica
- **Padrão da indústria:** CNCF, Apache Foundation e a maioria dos projetos de dados open-source (Spark, Kafka, Trino, Iceberg, Airflow) usam Apache-2.0
- **Alinhamento com ADR-001:** A missão multi-setor (governo + enterprise) exige a licença de menor fricção possível
- **Trade-off consciente:** Perde-se proteção contra cloud-washing, mas ganha-se em adoção e ecossistema

**Impacto em outras ADRs:**

- ADR-004: O RADaC (AGPL-3.0) precisará de relicenciamento ou clean-room se código for reutilizado
- ADR-122: Modelo de sustentabilidade não pode depender de copyleft; consulting/support ou open-core são mais adequados
- ADR-130: Contribuidores não precisam de CLA complexo (Apache-2.0 tem patent grant built-in)

**Data:** 2026-02-07

______________________________________________________________________

### ADR-004: Relação com o RADaC

<!-- metadata:
  id: ADR-004
  status: DECIDED
  decided_value: "clean-room redesign"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **Clean-room redesign** — O RADaC (`.radac/`) serve como especificação e referência intelectual. Todo o código do OpenDataGov é escrito do zero sob Apache-2.0.

**Detalhamento:**

1. **RADaC como especificação:** O diretório `.radac/` permanece no repositório como referência de design (arquitetura, governance model, conceitos). Não é executado nem compilado como parte do OpenDataGov.

1. **Código reescrito:** Toda implementação é nova, usando o RADaC como inspiração para:

   - Conceitos de governança (representações, camadas sociais, votação)
   - Arquitetura lakehouse (Bronze/Silver/Gold)
   - Padrões de observabilidade e privacidade
   - Sem copiar código AGPL-3.0 diretamente

1. **Sem conflito de licença:** O OpenDataGov (Apache-2.0) não deriva de código AGPL-3.0. O RADaC é referência intelectual — conceitos e ideias não são protegidos por copyright, apenas expressão em código.

1. **Evolução independente:** O OpenDataGov pode divergir livremente do RADaC em implementação, linguagem, stack e padrões.

**Justificativa:**

- Elimina qualquer risco de conflito AGPL → Apache-2.0
- Permite redesign sem dívida técnica herdada
- Oportunidade de mudar stack/linguagem se necessário
- `.radac/` como documentação de referência tem valor educacional

**Impacto em outras ADRs:**

- Todas as ADRs técnicas: implementação será nova, não adaptação do código RADaC
- ADR-132: Enums podem ser redesenhados em inglês desde o início
- ADR-140: Fase 0 inclui o clean-room design antes de escrever código

**Data:** 2026-02-07

______________________________________________________________________

## Seção 2: Modelo de Governança

### ADR-010: Topologia de Governança

<!-- metadata:
  id: ADR-010
  status: DECIDED
  decided_value: "híbrida configurável"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **Híbrida configurável** — guardrails centrais + autonomia local como default, com modelo de governança configurável por deployment.

**Detalhamento:**

1. **Default: Híbrida** — A plataforma vem com um modelo de governança híbrido opinionado:

   - **Guardrails centrais:** Políticas globais de compliance, segurança e qualidade definidas por administradores
   - **Autonomia local:** Domínios de dados têm autonomia para decisões dentro dos guardrails (schema evolution, qualidade, acesso)

1. **Configurável:** O modelo de governança é plugável. Deployments podem configurar:

   - **Federada (Data Mesh):** Domínios 100% autônomos com padrões compartilhados
   - **B-Swarm social:** Representações com votação ponderada (preserva a inovação do RADaC como opção)
   - **Centralizada:** Para organizações menores ou com requisitos rígidos de controle

1. **Progressividade (alinhado com ADR-001):**

   - Sem IA → governança manual via workflows de aprovação humana
   - Com IA → IA recomenda ações de governança, humano aprova

**Justificativa:**

- Híbrido é o padrão que a indústria converge (Dehghani's "federated computational governance")
- Configurabilidade respeita a diversidade de públicos (ADR-002: governo + enterprise)
- Preserva a inovação do B-Swarm como opção sem forçá-la como default
- Alinha com "IA recomenda, humano decide" (ADR-001)

**Impacto em outras ADRs:**

- ADR-013: Representações B-Swarm são uma opção de config, não o default
- ADR-014: Mecânica de veto é relevante apenas quando modelo B-Swarm está ativo
- ADR-012: Escopo da governança se aplica a qualquer modelo configurado

**Data:** 2026-02-07

______________________________________________________________________

### ADR-011: Atores Humanos vs. IA na Governança

<!-- metadata:
  id: ADR-011
  status: DECIDED
  decided_value: "IA recomenda, humano decide — tudo requer humano"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **IA recomenda, humano decide** para todas as categorias de decisão, incluindo operações de infraestrutura.

**Detalhamento:**

1. **Princípio geral:** A IA analisa, detecta padrões e gera recomendações. Toda ação requer aprovação humana explícita. Sem exceções.

1. **Dados pessoais (LGPD/GDPR):** Humano sempre no loop, **exceto para políticas pré-aprovadas**. Exemplo: se o administrador definiu "anonimizar CPF em toda ingestão Bronze", a IA executa automaticamente. Qualquer exceção ou caso não coberto por política escala para humano.

1. **Operações de infraestrutura:** Mesmo scaling, restart e deploy requerem aprovação humana. A IA pode detectar necessidade de escalar e recomendar, mas o humano executa.

1. **Níveis de autonomia futuros:** A arquitetura deve permitir aumentar autonomia da IA por tipo de decisão no futuro (configurável), mas o default é conservador.

**Justificativa:**

- Máxima compliance regulatória (EU AI Act Art. 14, LGPD, NIST AI RMF)
- Alinhado com contexto governo/defesa (ADR-002)
- Políticas pré-aprovadas permitem eficiência sem sacrificar supervisão
- Progressividade (ADR-001) permite relaxar no futuro conforme confiança cresce

**Impacto:**

- ADR-012: Escopo da governança requer workflow formal para todas as decisões com aprovação humana
- ADR-024: Promoções Silver→Gold e Gold→Platinum requerem aprovação humana obrigatória
- ADR-030: B-Swarm opera como governance layer com humano no loop
- ADR-034: Registro de experts requer aprovação humana para ativação
- ADR-042: IA para active metadata opera em modo "sugere, humano aprova"

**Data:** 2026-02-07

______________________________________________________________________

### ADR-012: Escopo da Governança — O Que é Governado

<!-- metadata:
  id: ADR-012
  status: DECIDED
  decided_value: "tudo — dados, IA e operações de infraestrutura"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **Governança abrangente** — todas as categorias de decisão passam por processo formal de governança.

**Tipos de decisão governados:**

| Tipo de Decisão                            | Governado? | Nível                                    |
| ------------------------------------------ | ---------- | ---------------------------------------- |
| Mudança de schema (breaking change)        | Sim        | Aprovação de Data Owner + Data Architect |
| Concessão/revogação de acesso a dados      | Sim        | Aprovação de Data Owner + Compliance     |
| Promoção de dados (Bronze → Silver → Gold) | Sim        | Aprovação de Data Steward                |
| Deploy de novo modelo de IA                | Sim        | Aprovação de Data Architect + Compliance |
| Alteração de pipeline de dados             | Sim        | Aprovação de Data Steward                |
| Mudança de SLA/limiar de qualidade         | Sim        | Aprovação de Data Owner                  |
| Criação de novo domínio de dados           | Sim        | Aprovação de Data Architect              |
| Exceção temporária de qualidade            | Sim        | Aprovação de Data Owner (com prazo)      |
| Deploy/scaling de infraestrutura           | Sim        | Aprovação de operador autorizado         |
| Configuração de segurança/rede             | Sim        | Aprovação de Data Architect + Segurança  |

**Justificativa:**

- Contexto air-gapped + governo exige controle total (ADR-002)
- "Tudo requer humano" (ADR-011) implica que tudo deve ter workflow formal
- Audit trail completo para compliance (LGPD, EU AI Act)

**Impacto:** ADR-082 (GitOps) deve integrar aprovações de governança no pipeline de deploy.

**Data:** 2026-02-07

______________________________________________________________________

### ADR-013: Modelo de Representações — Substituir por RACI

<!-- metadata:
  id: ADR-013
  status: DECIDED
  decided_value: "substituir 5 representações por modelo RACI/Stewardship"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **Substituir o modelo de 5 representações por RACI/Stewardship** — Data Owner, Data Steward, Data Consumer, Data Architect.

**Detalhamento:**

1. **Papéis RACI padrão DAMA:**

   | Papel              | Responsabilidade                                                                             |
   | ------------------ | -------------------------------------------------------------------------------------------- |
   | **Data Owner**     | Responsável pelo domínio de dados. Aprova acesso, define SLAs, decide promoções Gold         |
   | **Data Steward**   | Cuida da qualidade e compliance no dia a dia. Aprova promoções Bronze→Silver, exceções de DQ |
   | **Data Consumer**  | Consome dados. Solicita acesso, reporta problemas de qualidade                               |
   | **Data Architect** | Define padrões técnicos. Aprova schemas, novos domínios, decisões de infraestrutura          |

1. **Sem votação ponderada:** O modelo RACI usa aprovação/rejeição simples por papel, não votação com pesos.

1. **B-Swarm social como legacy:** O modelo de 5 representações (Política, Econômica, Geográfica, Científica, Militar) não é reimplementado. Os conceitos úteis (multi-perspectiva, deliberação) são absorvidos como capacidade do modelo RACI configurável.

1. **Extensibilidade:** Organizações podem criar papéis adicionais (ex: Compliance Officer, Security Officer) como extensões do modelo base.

**Justificativa:**

- RACI é padrão de mercado reconhecido (DAMA-DMBOK)
- Familiaridade reduz barreira de adoção para governo e enterprise
- As 5 representações (Política, Econômica, Geográfica, Científica, Militar) não mapeiam bem para contexto corporativo/governamental
- Clean-room redesign (ADR-004) é o momento certo para essa mudança

**Impacto:**

- ADR-071: Camadas sociais (PESSOAL, FAMILIA, etc.) precisam ser reavaliadas — não mapeiam para RACI
- ADR-014: Mecânica de veto será por papel RACI, não por representação B-Swarm

**Data:** 2026-02-07

______________________________________________________________________

### ADR-014: Mecânica de Veto e Escalonamento

<!-- metadata:
  id: ADR-014
  status: DECIDED
  decided_value: "configurável com defaults razoáveis"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **Configurável** — mecanismo de veto, percentual de override e escalonamento são configuráveis por deployment, com defaults razoáveis out-of-the-box.

**Defaults:**

| Parâmetro               | Default                                                                                   | Configurável                                                |
| ----------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| **Quem pode vetar**     | Data Owner e Data Architect podem vetar em seus domínios                                  | Sim — qualquer papel pode receber poder de veto             |
| **Override de veto**    | Requer aprovação de papel hierarquicamente superior (ex: CTO para veto de Data Architect) | Sim — % de override ou escalation path                      |
| **Time-bound**          | Veto expira em 24h para decisões normais, 1h para emergenciais                            | Sim — configurável por tipo de decisão                      |
| **Escalonamento**       | Veto não resolvido escala para nível hierárquico acima                                    | Sim — pode escalar para comitê, papel específico, ou COSMOS |
| **Circuit breaker**     | Emergências de segurança permitem bypass com audit trail obrigatório                      | Sim — quem pode acionar e sob quais condições               |
| **Compliance override** | Compliance Officer pode sobrescrever qualquer decisão por razões regulatórias             | Sim — papel e condições configuráveis                       |

**Justificativa:**

- Defaults razoáveis permitem uso imediato sem configuração complexa
- Configurabilidade atende tanto governo (mais rígido) quanto enterprise (mais flexível)
- Time-bound evita deadlocks em produção
- Circuit breaker para emergências é essencial em ambientes de alta disponibilidade
- Compliance override é requisito regulatório (LGPD, EU AI Act)

**Impacto:**

- ADR-010: Veto e escalonamento são parte integrante de qualquer modelo de governança configurado
- ADR-012: Workflows de governança incluem mecanismo de veto e escalonamento
- ADR-082: GitOps deve integrar gates de veto/approval no pipeline de deploy

**Data:** 2026-02-07

______________________________________________________________________

## Seção 3: Arquitetura de Dados

### ADR-020: Padrão Core de Arquitetura de Dados

<!-- metadata:
  id: ADR-020
  status: DECIDED
  decided_value: "Lakehouse + Mesh + Fabric"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **Lakehouse + Mesh + Fabric** — combinação completa dos três padrões dominantes.

**Detalhamento:**

1. **Lakehouse:** Camadas Bronze/Silver/Gold(/Platinum) sobre object storage (MinIO + Iceberg). Engine de query (Trino) e processamento batch (Spark).

1. **Data Mesh:** Domínios de dados com ownership federado. Cada domínio tem Data Owner e Data Steward responsáveis. Alinhado com modelo RACI (ADR-013).

1. **Data Fabric:** Camada de metadados ativos (active metadata) que dispara automações — auto-classificação, auto-tagging, enforcement de políticas. A IA (B-Swarm) pode ser a engine de active metadata quando ativada (ADR-001: progressivo).

**Justificativa:**

- Proposta de valor máxima, "best of all worlds"
- Data Mesh alinha com RACI e governança federada híbrida (ADR-010)
- Data Fabric alinha com AI progressiva (ADR-001): sem IA = metadata passiva; com IA = active metadata
- Complexidade é gerenciada pela progressividade: deploy mínimo começa sem Mesh/Fabric, ativa gradualmente
- Para 10-100TB/dia (ADR-002) a combinação é justificada

**Impacto:** ADR-042 (Active Metadata) é core, não opcional.

**Data:** 2026-02-07

______________________________________________________________________

### ADR-021: Formato de Tabela Padrão

<!-- metadata:
  id: ADR-021
  status: DECIDED
  decided_value: "Iceberg default + UniForm/XTable para interop"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **Apache Iceberg como default** + UniForm/XTable para interoperabilidade com Delta Lake quando necessário.

**Detalhamento:**

- **Iceberg é o formato nativo:** Todas as tabelas são criadas em Iceberg por padrão
- **UniForm/XTable:** Conversão automática para Delta Lake metadata quando necessário (ex: integração com ecossistemas Databricks ou tools que só leem Delta)
- **Sem Delta Lake nativo:** Não há tabelas criadas nativamente em Delta Lake

**Justificativa:**

- Iceberg tem melhor suporte Trino (engine de query primária)
- Schema evolution e partition evolution superiores
- Time travel nativo para auditoria e compliance
- UniForm/XTable cobrem casos de interop sem manter dois formatos

**Impacto:**

- ADR-022: MinIO como storage layer armazena dados em formato Iceberg
- ADR-024: Medallion architecture opera sobre tabelas Iceberg com time travel para auditoria
- ADR-060: Lineage rastreia transformações sobre tabelas Iceberg

**Data:** 2026-02-07

______________________________________________________________________

### ADR-022: Camada de Armazenamento

<!-- metadata:
  id: ADR-022
  status: DECIDED
  decided_value: "MinIO everywhere"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **MinIO everywhere** — S3-compatible e self-hosted em todos os ambientes (dev, staging, produção).

**Detalhamento:**

- **Produção:** MinIO em cluster distribuído (erasure coding, multi-node) sobre discos locais ou SAN
- **Staging:** MinIO single-node ou small cluster
- **Dev local:** MinIO standalone (container único)
- **Sem dependência de cloud storage:** S3 AWS, GCS e Azure Blob não são dependências. Se o deployment for em cloud, MinIO roda sobre EBS/Persistent Disks

**Justificativa:**

- Air-gapped obrigatório (ADR-002) exclui S3/GCS/Azure nativos
- MinIO é S3-compatible: todas as ferramentas do ecossistema (Spark, Trino, Iceberg) funcionam sem adaptação
- Consistência entre ambientes: mesmo storage em dev e prod reduz "works on my machine"
- Sem cloud lock-in
- Performance comprovada para escala enterprise

**Impacto:**

- ADR-023: Datastores de temperatura COLD utilizam MinIO como backend
- ADR-024: Camadas Bronze/Silver/Gold/Platinum residem em MinIO
- ADR-073: Encryption at rest via SSE com keys do Vault sobre MinIO
- ADR-084: Dev local usa MinIO standalone em container

**Data:** 2026-02-07

______________________________________________________________________

### ADR-023: Arquitetura de Temperatura de Dados

<!-- metadata:
  id: ADR-023
  status: DECIDED
  decided_value: "completo por camada — 5 datastores sem duplicação"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **5 datastores organizados por temperatura**, sem duplicação de propósito.

**Stack definida:**

| Temperatura         | Datastore   | Propósito                                                  | Latência |
| ------------------- | ----------- | ---------------------------------------------------------- | -------- |
| **HOT** (\<10ms)    | Redis       | Cache, sessões, rate limiting, pub/sub leve                | \<1ms    |
| **WARM** (10-100ms) | PostgreSQL  | Metadados, catálogo, configuração, governança, audit trail | ~5-20ms  |
| **WARM** (10-100ms) | Qdrant      | Vector DB para RAG, embeddings, busca semântica            | ~10-50ms |
| **WARM** (10-100ms) | TimescaleDB | Time-series para métricas, IoT, data observability         | ~5-30ms  |
| **COLD** (100ms+)   | MinIO       | Object storage, lakehouse (Bronze/Silver/Gold/Platinum)    | ~100ms+  |

**O que NÃO entra no MVP:**

- ScyllaDB, YugabyteDB, FerretDB, DragonflyDB, Memcached, Apache AGE — removidos do escopo
- Se necessários no futuro, podem ser adicionados como extensões

**Justificativa:**

- 5 datastores cobrem todos os workloads sem redundância
- Qdrant é necessário para RAG/IA (ADR-030, ADR-033)
- TimescaleDB é necessário para data observability e métricas de governança
- Escala de 10-100TB/dia (ADR-002) justifica engines especializadas por workload
- Cada datastore opera air-gapped (ADR-002)

**Impacto:**

- ADR-033: Qdrant como vector DB para RAG é um dos 5 datastores definidos
- ADR-061: TimescaleDB alimenta observabilidade com métricas time-series
- ADR-121: Perfis de deployment determinam quais datastores são ativados por tier

**Data:** 2026-02-07

______________________________________________________________________

### ADR-024: Design do Medallion Architecture

<!-- metadata:
  id: ADR-024
  status: DECIDED
  decided_value: "4 camadas (Bronze/Silver/Gold/Platinum) com DQ gates"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **4 camadas** (Bronze/Silver/Gold/Platinum) com quality gates formais e ownership por papel RACI.

**Camadas e regras de transição:**

| Camada       | Owner (RACI)                 | Conteúdo                                                | Quality Gate para próxima                                                                                    |
| ------------ | ---------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Bronze**   | Data Engineer                | Dados raw, ingestão sem transformação                   | DQ score automático > threshold → promoção automática (se política pré-aprovada por Data Steward)            |
| **Silver**   | Data Steward                 | Dados limpos, deduplicados, schema validated            | Requer aprovação humana de Data Owner. Exige: cobertura de testes DQ, documentação no catálogo, SLA definido |
| **Gold**     | Data Owner                   | Dados curados, business-ready, data products            | Requer aprovação humana de Data Owner + Data Architect para Platinum                                         |
| **Platinum** | Data Architect + ML Engineer | Feature store para ML. Dados "blessed" para treinamento | Governança de modelo (ADR-032) controla uso                                                                  |

**Regras de transição detalhadas:**

1. **Bronze → Silver (semi-automático):**

   - Deduplicação obrigatória
   - Schema validation contra data contract (ADR-051)
   - DQ score acima de threshold configurável
   - Se políticas pré-aprovadas pelo Data Steward → promoção automática
   - Exceções escalam para Data Steward

1. **Silver → Gold (humano obrigatório):**

   - Cobertura mínima de testes de qualidade
   - Documentação completa no catálogo
   - SLA definido e registrado
   - Aprovação explícita do Data Owner

1. **Gold → Platinum (humano obrigatório):**

   - Aprovação de Data Architect + ML Engineer
   - Validação de bias e fairness para dados de treinamento
   - Versionamento de dataset para reprodutibilidade

**Justificativa:**

- Bronze→Silver semi-automático equilibra eficiência com controle (ADR-011)
- Silver→Gold e Gold→Platinum mantêm "humano decide" (ADR-011)
- Platinum como camada ML dedicada separa concerns de analytics e ML
- Quality gates formais atendem compliance e auditoria

**Impacto:**

- ADR-050: Great Expectations implementa os quality gates de cada camada
- ADR-051: Data contracts validam schemas na transição entre camadas
- ADR-012: Promoções entre camadas passam por governance workflow formal

**Data:** 2026-02-07

______________________________________________________________________

## Seção 4: Arquitetura AI/ML

### ADR-030: B-Swarm vs. MLOps Padrão vs. Híbrido

<!-- metadata:
  id: ADR-030
  status: DECIDED
  decided_value: "Híbrido — B-Swarm como governance layer sobre MLOps"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **Híbrido** — B-Swarm como camada de governança de IA sobre stack MLOps padrão.

**Detalhamento:**

| Camada            | Ferramenta             | Responsabilidade                                                                                      |
| ----------------- | ---------------------- | ----------------------------------------------------------------------------------------------------- |
| **Governance**    | B-Swarm (quando ativo) | Recomendar deploy de modelos, controle de acesso a modelos, compliance, audit trail de decisões de IA |
| **Lifecycle**     | MLflow                 | Model registry, experiment tracking, model versioning, model cards                                    |
| **Orchestration** | Kubeflow (ou similar)  | Training pipelines, serving, A/B testing                                                              |
| **Inference**     | vLLM + Gateway         | Inferência de LLM local com roteamento inteligente                                                    |

**Sem B-Swarm (modo degradado):** MLflow + Kubeflow operam normalmente. Governança de modelos é feita via approval workflows manuais (RACI: Data Architect aprova deploy).

**Com B-Swarm:** A IA analisa métricas de modelo (drift, performance, fairness) e recomenda ações. Humano aprova via workflow.

**Justificativa:**

- Ferramentas maduras (MLflow, Kubeflow) para lifecycle técnico — não reinventar a roda
- B-Swarm adiciona valor diferenciado na governança, não na operação
- Alinhado com ADR-001 (progressivo) e ADR-011 (IA recomenda, humano decide)
- Cada camada é substituível independentemente

**Impacto:**

- ADR-031: vLLM é o backend de inferência definido para a camada de inferência do híbrido
- ADR-032: MLflow opera como lifecycle layer sob a governance layer B-Swarm
- ADR-034: Experts são geridos pelo B-Swarm governance quando ativo
- ADR-042: Active metadata usa B-Swarm como engine de descoberta quando ativado

**Data:** 2026-02-07

______________________________________________________________________

### ADR-031: Inferência LLM — Backend e Roteamento

<!-- metadata:
  id: ADR-031
  status: DECIDED
  decided_value: "vLLM + Gateway (LiteLLM)"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **vLLM para inferência local** + **Gateway/Router (LiteLLM)** como camada de abstração.

**Detalhamento:**

1. **vLLM:** Backend de inferência primário. Roda localmente em GPU. Modelos pré-baixados e armazenados em MinIO ou filesystem local. PagedAttention para eficiência de memória, continuous batching.

1. **LiteLLM (Gateway):** Camada de abstração sobre vLLM. Permite:

   - Trocar modelos sem mudar código de aplicação
   - Load balancing entre múltiplas instâncias vLLM
   - Fallback entre modelos (se modelo A falha, tenta modelo B)
   - Metering e logging unificado de chamadas
   - API compatível com OpenAI SDK (facilita migração)

1. **Air-gapped:** Tudo local. Zero dependência de APIs externas. Modelos (LLaMA, CodeLlama, etc.) são distribuídos como artefatos junto com o deploy.

1. **GPU obrigatória:** Para inferência de LLM em escala, GPUs são requisito. Perfis de deploy (ADR-121) devem especificar GPU requirements.

**Justificativa:**

- Air-gapped (ADR-002) exclui cloud APIs
- vLLM é o backend de maior performance para inferência local
- LiteLLM como gateway desacopla aplicação do backend: permite trocar vLLM por TGI/Ollama sem refactor
- API OpenAI-compatible facilita adoção por desenvolvedores

**Impacto:**

- ADR-033: Embeddings para RAG são gerados via vLLM com Sentence-Transformers
- ADR-034: Experts utilizam vLLM como backend de inferência via LiteLLM gateway
- ADR-121: Perfis medium/large requerem GPU para inferência local

**Data:** 2026-02-07

______________________________________________________________________

### ADR-032: Model Registry e Experiment Tracking

<!-- metadata:
  id: ADR-032
  status: DECIDED
  decided_value: "MLflow + B-Swarm governance para promoções"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **MLflow** para registry e tracking técnico + **B-Swarm governance** para governar promoções de modelo.

**Detalhamento:**

| Função                        | Ferramenta          | Detalhe                                                                        |
| ----------------------------- | ------------------- | ------------------------------------------------------------------------------ |
| Experiment tracking           | MLflow              | Logs de métricas, parâmetros, artefatos por experimento                        |
| Model registry                | MLflow              | Versionamento, stages (Staging/Production/Archived)                            |
| Model cards                   | MLflow + custom     | Documentação de bias, fairness, limitações, intended use                       |
| Promoção Staging → Production | B-Swarm + RACI      | IA recomenda promoção baseada em métricas; Data Architect + Data Owner aprovam |
| Rollback                      | MLflow + governance | Requer aprovação humana (ADR-011)                                              |

**Sem B-Swarm:** MLflow opera standalone. Promoções via approval manual no workflow RACI.

**Justificativa:**

- MLflow é o padrão open-source para ML lifecycle
- Promoção de modelos para produção é decisão de alto risco → governance obrigatória
- Model cards atendem EU AI Act (transparência, documentação)
- MLflow roda air-gapped sem dependências externas

**Impacto:**

- ADR-030: MLflow é a camada de lifecycle sob a governance layer B-Swarm
- ADR-034: Experts registrados no registry têm modelos versionados no MLflow
- ADR-111: Model cards no MLflow atendem transparência exigida pelo EU AI Act

**Data:** 2026-02-07

______________________________________________________________________

### ADR-033: Vector Database e Arquitetura RAG

<!-- metadata:
  id: ADR-033
  status: DECIDED
  decided_value: "Qdrant standalone"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **Qdrant standalone** como vector DB para RAG e busca semântica.

**Detalhamento:**

1. **Qdrant:** Vector DB dedicado, Rust-native, filtros avançados, suporte a namespaces e multi-tenancy lógica.

1. **Pipeline de indexação RAG:**

   ```text
   Gold/Platinum (MinIO+Iceberg) → Embedding (Sentence-Transformers via vLLM) → Qdrant
   ```

   - Dados curados na camada Gold ou Platinum são candidatos à indexação
   - Governança (ADR-012) controla quais datasets são indexados: Data Owner aprova inclusão no knowledge base
   - Embeddings gerados localmente via Sentence-Transformers (air-gapped)

1. **Persistência:** Qdrant persiste dados em disco. Pode ser reconstruído a partir do lakehouse se necessário (disaster recovery).

1. **Governança do knowledge base:** Inclusão/remoção de documentos no knowledge base passa por approval workflow (Data Owner + Data Steward).

**Justificativa:**

- Já definido no stack de 5 datastores (ADR-023)
- Performance superior a pgvector para >1M vetores
- Filtros avançados permitem RAG contextualizado (por domínio, por classificação de segurança, por camada social)
- Air-gapped: roda localmente, sem dependência externa

**Impacto:**

- ADR-042: Active metadata pode usar RAG/Qdrant para descoberta e sugestão inteligente
- ADR-034: Experts de NLP/RAG consultam knowledge base indexado no Qdrant
- ADR-070: Busca semântica no Qdrant respeita classificação de segurança e privacy controls

**Data:** 2026-02-07

______________________________________________________________________

### ADR-034: Extensibilidade dos Experts

<!-- metadata:
  id: ADR-034
  status: DECIDED
  decided_value: "Registry central + approval flow"
  decided_date: 2026-02-07
  priority: P0
-->

**Decisão:** **Registry central com workflow de aprovação** para registrar novos experts.

**Detalhamento:**

1. **Registry central:** Catálogo de experts disponíveis com metadata (nome, capabilities, versão, autor, status de aprovação).

1. **Approval flow:**

   - Novo expert é submetido ao registry com model card e documentação
   - Data Architect revisa capacidades, segurança e compatibilidade
   - Aprovação humana necessária para ativar expert em produção (ADR-011)
   - Expert pode ser aprovado para ambientes específicos (dev, staging, prod)

1. **Interface de extensão:** `BaseExpert` (ou equivalente no clean-room redesign) define interface abstrata que novos experts implementam. API clara de input/output.

1. **Estado "sem experts":** A plataforma funciona sem nenhum expert ativo (ADR-001: progressivo). O registry pode estar vazio.

1. **Experts built-in:** O OpenDataGov vem com experts de referência (NLP, RAG, Code, Data, Vision, IoT) pré-aprovados, mas desativáveis.

**Justificativa:**

- Registry + approval equilibra extensibilidade com segurança
- Approval flow alinhado com "humano decide" (ADR-011)
- Suporta comunidade (terceiros podem contribuir experts)
- Estado "sem experts" respeita progressividade (ADR-001)
- Em air-gapped, experts são distribuídos como artefatos junto com o deploy

**Impacto:**

- ADR-030: B-Swarm governance gerencia experts registrados no registry
- ADR-111: Cada expert inclui classificação de risco EU AI Act no model card
- ADR-131: AI Expert é um dos 6 pontos de extensão formais da plataforma

**Data:** 2026-02-07

______________________________________________________________________

## Seção 5: Metadados e Catálogo

### ADR-040: Plataforma de Catálogo de Dados

<!-- metadata:
  id: ADR-040
  status: DECIDED
  decided_value: "DataHub"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **DataHub** como plataforma de catálogo de dados.

**Detalhamento:**

- Event-driven architecture (Kafka + Elasticsearch + Graph + RDB)
- Lineage graph nativo
- Comunidade madura e ativa
- Integrações com Spark, Airflow, dbt, Great Expectations

**Justificativa:**

- Catálogo mais maduro do ecossistema open-source
- Lineage graph é diferencial para governança (ADR-060)
- Kafka já está no stack (ADR-091, ADR-112) — sinergia de infraestrutura
- Air-gapped: roda self-hosted sem dependências externas

**Trade-off:** Complexidade operacional alta (múltiplas dependências). Justificada pela escala 10-100TB/dia (ADR-002).

**Impacto:**

- ADR-041: Adapter layer mapeia schema interno do OpenDataGov para DataHub entity model
- ADR-060: DataHub é o backend de visualização de lineage (OpenLineage → DataHub)
- ADR-100: UI primária estende a interface do DataHub com plugins de governança

**Data:** 2026-02-07

______________________________________________________________________

### ADR-041: Modelo e Schema de Metadados

<!-- metadata:
  id: ADR-041
  status: DECIDED
  decided_value: "Adapter layer"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **Adapter layer** — schema interno do OpenDataGov que mapeia para DataHub/OpenLineage.

**Detalhamento:**

- **Schema interno:** O OpenDataGov define seu próprio modelo de metadados que integra governança (RACI, approval workflows), qualidade (DQ scores, data contracts) e privacidade (classificação de dados, jurisdição)
- **Adapters:** Mapeamento bidirecional para DataHub entity model e OpenLineage schema
- **Portabilidade:** Se o catálogo mudar no futuro (DataHub → OpenMetadata), apenas o adapter muda

**Justificativa:**

- Evita lock-in no modelo de um catálogo específico
- Permite integrar conceitos de governança B-Swarm que DataHub não tem nativamente
- OpenLineage adapter permite coleta padronizada de lineage
- Clean-room redesign (ADR-004) é oportunidade de definir schema próprio

**Impacto:**

- ADR-040: DataHub consome metadados via adapter bidirecional
- ADR-042: Active metadata opera sobre o schema interno, não sobre o modelo DataHub
- ADR-060: OpenLineage adapter padroniza coleta de lineage independente do catálogo

**Data:** 2026-02-07

______________________________________________________________________

### ADR-042: Active Metadata e Automação

<!-- metadata:
  id: ADR-042
  status: DECIDED
  decided_value: "Híbrido — regras declarativas + IA para descoberta"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **Híbrido** — regras declarativas para automações previsíveis + IA (B-Swarm) para descoberta e sugestão.

**Detalhamento:**

| Tipo                    | Mecanismo                      | Exemplo                                                               | Aprovação                     |
| ----------------------- | ------------------------------ | --------------------------------------------------------------------- | ----------------------------- |
| **Regras declarativas** | Políticas YAML, GitOps-managed | "Se dataset contém coluna 'cpf', aplicar masking automaticamente"     | Pré-aprovado por Data Steward |
| **IA — descoberta**     | B-Swarm Data Expert            | Auto-classificação de PII, sugestão de tags, detecção de schema drift | IA sugere, humano aprova      |
| **IA — enforcement**    | B-Swarm + regras               | IA detecta violação de política e dispara enforcement automático      | Política pré-aprovada         |

**Sem B-Swarm (modo degradado):** Apenas regras declarativas operam. Sem auto-classificação, sem sugestões inteligentes.

**Justificativa:**

- Data Fabric (ADR-020) requer active metadata como capability core
- Regras declarativas são previsíveis e auditáveis (GitOps)
- IA para descoberta é o diferencial (auto-classificação PII, sugestão de tags)
- "IA sugere, humano aprova" alinhado com ADR-011

**Impacto:**

- ADR-050: DQ engine pode ser acionada por regras declarativas de active metadata
- ADR-070: Auto-classificação de PII via IA alimenta regras de privacy automáticas
- ADR-034: Experts de discovery operam como engines de active metadata quando ativados

**Data:** 2026-02-07

______________________________________________________________________

## Seção 6: Qualidade de Dados

### ADR-050: Engine de Qualidade de Dados

<!-- metadata:
  id: ADR-050
  status: DECIDED
  decided_value: "Great Expectations"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **Great Expectations** como engine de qualidade de dados.

**Detalhamento:**

- Expectations declarativas em YAML/Python
- Integração com Spark, Trino, PostgreSQL (todos no stack)
- Data Docs auto-geradas para documentação de qualidade
- CI/CD-friendly: validação em pipelines de promoção (ADR-024)
- Air-gapped: roda localmente sem dependências externas

**Integração com governança:**

- Quality gates da ADR-024 são implementados como Great Expectations suites
- DQ score é calculado por suite e reportado ao catálogo (DataHub via adapter)
- Violações de qualidade disparam workflows de governança (ADR-012)

**Justificativa:**

- Expectations declarativas são auditáveis e versionáveis em Git (GitOps)
- Integração nativa com Spark e Trino, engines já presentes no stack
- Data Docs auto-geradas reduzem esforço de documentação de qualidade
- Air-gapped: roda localmente sem dependências externas
- Padrão de mercado com comunidade ativa e extensível

**Impacto:**

- ADR-024: Quality gates de promoção entre camadas são implementados como GE suites
- ADR-052: Dimensões de qualidade DAMA são medidas via expectations do GE
- ADR-063: Data observability reutiliza métricas de DQ do Great Expectations

**Data:** 2026-02-07

______________________________________________________________________

### ADR-051: Data Contracts

<!-- metadata:
  id: ADR-051
  status: DECIDED
  decided_value: "DataContract Specification YAML + governança RACI"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **DataContract Specification (YAML)** com versionamento Git e breaking changes governados via RACI.

**Detalhamento:**

1. **Formato:** DataContract Specification (comunidade open-source) em YAML
1. **Versionamento:** Contracts são versionados no Git (GitOps)
1. **Responsabilidade:** Produtor define o contrato, consumidor valida expectativas
1. **Breaking changes:** Mudanças breaking disparam approval workflow:
   - Data Owner aprova
   - Data Architect revisa impacto técnico
   - Consumidores afetados são notificados
1. **Enforcement:** Validação automática em CI/CD e na ingestão Bronze (ADR-024)

**Justificativa:**

- Data contracts são padrão emergente para Data Mesh (ADR-020)
- YAML GitOps-friendly alinha com ArgoCD (ADR-082)
- Governança de breaking changes alinha com ADR-012 (tudo governado)

**Impacto:**

- ADR-024: Quality gates de promoção validam schemas contra data contracts
- ADR-050: Great Expectations valida expectations definidas nos contratos
- ADR-063: Schema drift é detectado via validação de data contracts

**Data:** 2026-02-07

______________________________________________________________________

### ADR-052: Dimensões de Qualidade e Framework de SLA

<!-- metadata:
  id: ADR-052
  status: DECIDED
  decided_value: "6 dimensões DAMA obrigatórias por dataset"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **Todas as 6 dimensões DAMA são obrigatórias** para cada dataset registrado no catálogo.

**Dimensões:**

| Dimensão         | Métrica exemplo                           | Medição                             |
| ---------------- | ----------------------------------------- | ----------------------------------- |
| **Completude**   | % de campos não-nulos                     | Automática via GE                   |
| **Acurácia**     | % de valores válidos contra referência    | Semi-automática (requer referência) |
| **Consistência** | % de registros consistentes cross-dataset | Automática via GE                   |
| **Atualidade**   | Freshness (age of data)                   | Automática via data observability   |
| **Unicidade**    | % de registros únicos (sem duplicatas)    | Automática via GE                   |
| **Validade**     | % de valores dentro de domínio válido     | Automática via GE                   |

**SLAs:**

- SLAs são definidos por dataset pelo Data Owner
- Violação de SLA dispara alerta + workflow de governança
- Cadência de revisão de SLAs: trimestral (alinhado com metodologia de auditoria)

**Justificativa:**

- DAMA-DMBOK define 6 dimensões como padrão reconhecido para qualidade de dados
- Obrigatoriedade garante baseline mínimo de qualidade para todos os datasets
- SLAs por dataset permitem expectativas diferenciadas conforme criticidade
- Revisão trimestral alinha com ciclo de auditoria do roadmap (ADR-140)

**Impacto:**

- ADR-050: Great Expectations implementa medição automática das 6 dimensões
- ADR-063: Data observability monitora SLAs de freshness, volume e qualidade
- ADR-024: Quality gates utilizam DQ scores baseados nas 6 dimensões para promoção

**Data:** 2026-02-07

______________________________________________________________________

## Seção 7: Lineage e Observabilidade

### ADR-060: Padrão de Data Lineage

<!-- metadata:
  id: ADR-060
  status: DECIDED
  decided_value: "OpenLineage → DataHub"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **OpenLineage para coleta** + **DataHub para visualização** de lineage.

**Detalhamento:**

- **Coleta:** OpenLineage SDK instrumenta Airflow, Spark, dbt para emitir eventos de lineage
- **Backend:** Eventos OpenLineage são ingeridos pelo DataHub (ADR-040) para visualização graph
- **End-to-end:** Source → ingestion → Bronze → Silver → Gold → Platinum → dashboard/model

**Justificativa:**

- OpenLineage é padrão aberto com integrações para todo o stack
- DataHub já está no catálogo (ADR-040) — reutiliza infraestrutura
- Lineage end-to-end é requisito de compliance (LGPD, EU AI Act)

**Impacto:**

- ADR-040: DataHub é o backend de visualização do lineage graph
- ADR-063: Data observability utiliza lineage para correlacionar freshness e impacto
- ADR-101: Dashboard de governança exibe lineage integrado com classificação de dados

**Data:** 2026-02-07

______________________________________________________________________

### ADR-061: Arquitetura de Observabilidade

<!-- metadata:
  id: ADR-061
  status: DECIDED
  decided_value: "Convergência via OpenTelemetry"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **OpenTelemetry como collector unificado** com backends especializados.

**Detalhamento:**

| Sinal            | Collector               | Backend                       | Visualização                 |
| ---------------- | ----------------------- | ----------------------------- | ---------------------------- |
| **Métricas**     | OTel Collector          | VictoriaMetrics               | Grafana                      |
| **Traces**       | OTel Collector          | Jaeger                        | Grafana (Tempo) ou Jaeger UI |
| **Logs**         | OTel Collector          | Loki ou Elasticsearch         | Grafana                      |
| **Data metrics** | OTel Collector + custom | VictoriaMetrics + TimescaleDB | Grafana                      |

**Justificativa:**

- OTel é o padrão de facto, vendor-neutral
- Collector unificado simplifica instrumentação
- Backends especializados mantêm performance por tipo de sinal
- Grafana como UI única para todos os sinais

**Impacto:**

- ADR-062: OTel é mandatório para toda instrumentação baseado nesta arquitetura
- ADR-063: Data observability reutiliza backends OTel (VictoriaMetrics, TimescaleDB)
- ADR-120: FinOps dashboards em Grafana seguem mesma stack de visualização

**Data:** 2026-02-07

______________________________________________________________________

### ADR-062: Integração OpenTelemetry

<!-- metadata:
  id: ADR-062
  status: DECIDED
  decided_value: "OTel everywhere"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **OTel mandatório** para toda instrumentação. Todo código novo usa OpenTelemetry SDKs.

**Detalhamento:**

- Traces, métricas e logs via OTel SDKs (Python, Go, etc.)
- OTel Collector como intermediário entre aplicação e backends
- Exporters configuráveis por deployment
- Clean-room redesign (ADR-004) = sem legacy para migrar

**Justificativa:**

- OTel é o padrão de facto para instrumentação (CNCF graduated)
- Clean-room redesign permite adotar OTel desde o início sem migração de legacy
- SDKs disponíveis para Python e Go, as linguagens primárias do stack
- Desacopla instrumentação dos backends (exporters configuráveis)

**Impacto:**

- ADR-061: OTel Collector é o ponto de coleta unificado para métricas, traces e logs
- ADR-063: Data observability emite métricas via OTel SDK
- ADR-120: FinOps pode coletar métricas de custo via OTel custom metrics

**Data:** 2026-02-07

______________________________________________________________________

### ADR-063: Data Observability

<!-- metadata:
  id: ADR-063
  status: DECIDED
  decided_value: "Integrado com DQ engine (Great Expectations) + Grafana"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **Integrado com DQ engine** (Great Expectations) + dashboards Grafana customizados.

**Detalhamento:**

- **Freshness:** Monitorado via timestamp de última atualização (OTel metric)
- **Volume:** Contagem de registros por ingestão (OTel metric)
- **Schema drift:** Detectado via data contract validation (ADR-051)
- **Distribution drift:** Detectado via Great Expectations statistical tests
- **Dashboards:** Grafana dashboards dedicados para data observability

**Justificativa:**

- Reutiliza Great Expectations (ADR-050) e Grafana (ADR-061)
- Menos uma ferramenta para operar
- OTel metrics para freshness/volume integram com stack de observabilidade existente

**Impacto:**

- ADR-050: Great Expectations alimenta métricas de DQ para dashboards de data observability
- ADR-052: SLAs de qualidade são monitorados via data observability dashboards
- ADR-061: Data metrics fluem pelo OTel Collector junto com métricas de infraestrutura

**Data:** 2026-02-07

______________________________________________________________________

## Seção 8: Privacidade e Segurança

### ADR-070: Arquitetura de Privacidade

<!-- metadata:
  id: ADR-070
  status: DECIDED
  decided_value: "DP + RBAC + masking"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **Toolkit pragmático** — Differential Privacy para analytics + RBAC para acesso + Masking para PII.

**Detalhamento:**

| Mecanismo                | Uso                                         | Implementação                                                                          |
| ------------------------ | ------------------------------------------- | -------------------------------------------------------------------------------------- |
| **Differential Privacy** | Queries analytics em dados sensíveis        | OpenDP (ou equivalente no clean-room). Epsilon configurável por classificação de dados |
| **RBAC**                 | Controle de acesso a datasets/domínios      | Keycloak (ADR-072) + OPA policies                                                      |
| **Masking**              | Ocultação de PII em visualizações e exports | Regras declarativas por data contract. Ex: CPF → ***.***.XXX-XX                        |

**Sem IA:** Masking e RBAC operam com regras estáticas.
**Com IA:** B-Swarm pode recomendar regras de masking baseado em auto-classificação de PII (ADR-042).

**Justificativa:**

- Toolkit pragmático cobre os cenários mais comuns de privacidade sem over-engineering
- DP para analytics permite extrair valor de dados sensíveis com garantias matemáticas
- RBAC + OPA (ADR-072) já está no stack — reutiliza infraestrutura de autorização
- Masking declarativo é auditável e versionável (GitOps)
- Modo degradado sem IA garante privacidade mesmo sem B-Swarm

**Impacto:**

- ADR-071: Mecanismos de privacy são aplicados conforme nível de classificação de dados
- ADR-072: OPA policies implementam RBAC e fine-grained access control
- ADR-042: Auto-classificação de PII via IA alimenta regras automáticas de masking

**Data:** 2026-02-07

______________________________________________________________________

### ADR-071: Classificação de Dados — Camadas de Acesso

<!-- metadata:
  id: ADR-071
  status: DECIDED
  decided_value: "Mapear para classificação padrão governo/enterprise"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **Classificação padrão** — Public, Internal, Confidential, Restricted, Top Secret.

**Mapeamento do RADaC:**

| RADaC (original) | OpenDataGov (novo) | Acesso padrão                          |
| ---------------- | ------------------ | -------------------------------------- |
| COSMOS           | Public             | Acesso aberto, dados anonimizados      |
| CLASSE           | Internal           | Acesso a funcionários autenticados     |
| COMUNIDADE       | Confidential       | Acesso por RBAC + need-to-know         |
| FAMILIA          | Restricted         | Acesso com masking + DP                |
| PESSOAL          | Top Secret         | Acesso mínimo, criptografia end-to-end |

**Justificativa:**

- Terminologia reconhecida por governo e enterprise (NIST SP 800-60)
- Mantém 5 níveis (mesma granularidade do RADaC)
- Substitui terminologia sociológica por terminologia de segurança da informação
- Clean-room redesign (ADR-004) permite renomear desde o início

**Impacto:**

- ADR-070: Mecanismos de privacy (DP, masking) são aplicados por nível de classificação
- ADR-072: RBAC no Keycloak mapeia regras de acesso por nível de classificação
- ADR-074: Classificação de dados interage com tags de jurisdição para residência

**Data:** 2026-02-07

______________________________________________________________________

### ADR-072: Autenticação e Autorização

<!-- metadata:
  id: ADR-072
  status: DECIDED
  decided_value: "Keycloak + OPA"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **Keycloak** para AuthN (OIDC/SAML) + **OPA (Open Policy Agent)** para AuthZ (policy-as-code).

**Detalhamento:**

| Camada           | Ferramenta            | Protocolo                                          |
| ---------------- | --------------------- | -------------------------------------------------- |
| **Autenticação** | Keycloak              | OIDC, SAML 2.0                                     |
| **Autorização**  | OPA                   | Rego policies                                      |
| **RBAC**         | Keycloak realms + OPA | Papéis RACI (ADR-013) mapeados para roles Keycloak |
| **Fine-grained** | OPA                   | Row/column level access via policies Rego          |

**Air-gapped:** Keycloak e OPA rodam self-hosted. Sem dependência de cloud IdP.

**Integração com governança:**

- Papéis RACI (Data Owner, Steward, Consumer, Architect) são roles Keycloak
- OPA policies são versionadas em Git (GitOps via ArgoCD)
- Mudanças de política de acesso passam por governance workflow (ADR-012)

**Justificativa:**

- Keycloak é o IdP self-hosted mais maduro (CNCF-adjacent, Red Hat backed)
- OIDC/SAML cobrem integração com qualquer IdP corporativo existente
- OPA (Rego) permite políticas fine-grained (row/column level) como código
- Ambos rodam air-gapped sem dependência de cloud IdP
- Papéis RACI mapeiam diretamente para roles Keycloak

**Impacto:**

- ADR-070: RBAC implementado via Keycloak + OPA controla acesso por classificação
- ADR-013: Papéis RACI são roles Keycloak (Data Owner, Steward, Consumer, Architect)
- ADR-074: OPA policies implementam enforcement de residência e jurisdição de dados

**Data:** 2026-02-07

______________________________________________________________________

### ADR-073: Estratégia de Criptografia

<!-- metadata:
  id: ADR-073
  status: DECIDED
  decided_value: "Vault + mTLS via service mesh"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **HashiCorp Vault** para key management e secrets + **Service mesh (Istio/Linkerd)** para mTLS.

**Detalhamento:**

| Aspecto                   | Solução                                              |
| ------------------------- | ---------------------------------------------------- |
| **Key management**        | Vault (auto-unseal, transit engine)                  |
| **Secret management**     | Vault (dynamic secrets, lease management)            |
| **Encryption at rest**    | MinIO server-side encryption (SSE) com keys do Vault |
| **Encryption in transit** | mTLS entre serviços via service mesh                 |
| **PKI**                   | Vault PKI engine para certificados internos          |

**Air-gapped:** Vault e service mesh rodam self-hosted. Auto-unseal via Shamir ou transit (sem cloud KMS).

**Justificativa:**

- Vault é padrão de mercado para secret e key management (CNCF ecosystem)
- mTLS via service mesh garante zero-trust entre serviços sem configuração manual
- SSE no MinIO com keys do Vault centraliza gestão de criptografia
- PKI engine elimina dependência de CA externa
- Auto-unseal via Shamir funciona air-gapped sem cloud KMS

**Impacto:**

- ADR-022: MinIO usa SSE com keys gerenciadas pelo Vault para encryption at rest
- ADR-072: Keycloak pode usar Vault para armazenar secrets de OIDC/SAML
- ADR-082: GitOps secrets são gerenciados via Vault (sealed secrets ou external secrets)

**Data:** 2026-02-07

______________________________________________________________________

### ADR-074: Soberania e Residência de Dados

<!-- metadata:
  id: ADR-074
  status: DECIDED
  decided_value: "Awareness jurisdicional built-in"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **Awareness jurisdicional built-in** com tags de jurisdição e políticas de residência.

**Detalhamento:**

1. **Tags de jurisdição:** Cada dataset tem metadata de jurisdição (ex: `jurisdiction: BR`, `jurisdiction: EU`)
1. **Políticas de residência:** Configuráveis via OPA (ADR-072). Ex: "dados com jurisdiction=BR não podem ser replicados para instâncias fora do BR"
1. **COSMOS federation:** Federação respeita jurisdição — dados não cruzam fronteiras jurisdicionais sem política explícita
1. **Data localization:** Configurável por deployment — pode ser strict (enforcement ativo) ou advisory (apenas alertas)

**Justificativa:**

- LGPD e GDPR exigem controle sobre residência de dados
- Alinhado com público governo (ADR-002) e soberania de dados
- COSMOS federation (ADR-092) precisa de awareness jurisdicional para operar legalmente

**Impacto:**

- ADR-092: COSMOS federation respeita tags de jurisdição ao sincronizar dados entre instâncias
- ADR-072: OPA policies implementam enforcement de residência de dados
- ADR-071: Classificação de dados interage com jurisdição para definir controles de acesso

**Data:** 2026-02-07

______________________________________________________________________

## Seção 9: Infraestrutura e Deploy

### ADR-080: Distribuição Kubernetes

<!-- metadata:
  id: ADR-080
  status: DECIDED
  decided_value: "Cloud-agnostic focus"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **Cloud-agnostic** — Kind/K3s como referência, clouds como extensão testada.

**Detalhamento:**

| Tier           | Distribuição                      | Nível de suporte                        |
| -------------- | --------------------------------- | --------------------------------------- |
| **Referência** | Kind (dev), K3s (edge/small prod) | Testado em CI, documentado              |
| **Suportado**  | EKS, GKE, AKS                     | Testado periodicamente, documentado     |
| **Compatível** | OpenShift, RKE2, Tanzu            | Compatível mas não testado regularmente |

**Justificativa:**

- Air-gapped (ADR-002) exige funcionar on-prem — não pode depender de cloud-specific features
- K3s é ideal para deployments edge/gov-cloud com recursos limitados
- Kind para dev local alinha com ADR-084

**Impacto:**

- ADR-081: OpenTofu e Helm operam sobre K8s cloud-agnostic
- ADR-082: ArgoCD sincroniza com qualquer distribuição K8s suportada
- ADR-083: Cluster Autoscaler precisa de adaptação para on-prem vs. cloud
- ADR-084: Kind (dev) e K3s (edge) são as distribuições de referência

**Data:** 2026-02-07

______________________________________________________________________

### ADR-081: Estratégia de Infrastructure as Code

<!-- metadata:
  id: ADR-081
  status: DECIDED
  decided_value: "OpenTofu + Helm"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **OpenTofu** (fork open-source do Terraform) para IaC + **Helm** para packaging K8s.

**Detalhamento:**

- **OpenTofu:** IaC para infraestrutura cloud/on-prem. Compatível com providers Terraform existentes. Licença MPL-2.0 (open-source)
- **Helm:** Charts para empacotamento de componentes K8s. Integrado com ArgoCD (ADR-082)

**Justificativa:**

- OpenTofu é Apache-2.0-friendly (vs. Terraform BSL) — alinhado com ADR-003
- Compatível com todo o ecossistema Terraform (providers, modules)
- Helm é padrão de facto para packaging K8s
- CNCF project (Linux Foundation backed)

**Impacto:**

- ADR-082: ArgoCD integra com Helm charts para GitOps
- ADR-080: IaC provisiona infraestrutura K8s cloud-agnostic
- ADR-084: Dev local utiliza Helm charts para teste completo em Kind

**Data:** 2026-02-07

______________________________________________________________________

### ADR-082: GitOps e Modelo de Deploy

<!-- metadata:
  id: ADR-082
  status: DECIDED
  decided_value: "ArgoCD + governança RACI"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **ArgoCD** para GitOps com **integração de governança** para deploys em produção.

**Detalhamento:**

| Ambiente       | Modelo de deploy                                                                                   |
| -------------- | -------------------------------------------------------------------------------------------------- |
| **Dev**        | ArgoCD auto-sync (merge → deploy automático)                                                       |
| **Staging**    | ArgoCD sync manual ou auto-sync com approval gate                                                  |
| **Production** | ArgoCD sync bloqueado até approval via RACI workflow. Data Architect + operador autorizado aprovam |

**Integração com governança (ADR-012):**

- PR para branch de produção dispara workflow de aprovação
- ArgoCD monitora branch mas só sincroniza após approval
- Audit trail de quem aprovou e quando

**Justificativa:**

- ArgoCD é o padrão de facto para GitOps em Kubernetes (CNCF graduated)
- Git como fonte de verdade garante auditabilidade de todo deploy
- Integração com governance RACI garante que deploys em produção passam por aprovação humana
- Ambientes segregados (dev/staging/prod) com políticas de sync diferenciadas
- Air-gapped: ArgoCD roda self-hosted monitorando repo Git local

**Impacto:**

- ADR-012: Governance workflows incluem gates de aprovação no pipeline GitOps
- ADR-014: Mecanismo de veto pode bloquear sync do ArgoCD em produção
- ADR-081: Helm charts são o formato de packaging sincronizado pelo ArgoCD

**Data:** 2026-02-07

______________________________________________________________________

### ADR-083: Estratégia de Scaling

<!-- metadata:
  id: ADR-083
  status: DECIDED
  decided_value: "Cluster Autoscaler + KEDA"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **Cluster Autoscaler** (infra) + **KEDA** (event-driven scaling para workloads).

**Detalhamento:**

| Camada                | Ferramenta         | Trigger                              |
| --------------------- | ------------------ | ------------------------------------ |
| **Cluster (nodes)**   | Cluster Autoscaler | Pods pending + resource requests     |
| **Workloads batch**   | KEDA               | Kafka lag, Airflow queue depth       |
| **Workloads serving** | KEDA + HPA         | Request rate, latência de inferência |

**Justificativa:**

- Cluster Autoscaler é cloud-agnostic (funciona em EKS, GKE, AKS, on-prem com adaptação)
- KEDA permite scaling baseado em métricas de negócio (Kafka lag = pipeline atrasado)
- Ambos operam air-gapped

**Impacto:**

- ADR-080: Scaling opera sobre K8s cloud-agnostic com Cluster Autoscaler
- ADR-091: KEDA escala workloads baseado em Kafka lag e Airflow queue depth
- ADR-121: Perfis de sizing determinam limites de scaling por tier

**Data:** 2026-02-07

______________________________________________________________________

### ADR-084: Experiência de Desenvolvimento Local

<!-- metadata:
  id: ADR-084
  status: DECIDED
  decided_value: "Múltiplos modos — Docker Compose + Kind"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **Múltiplos modos** — Docker Compose (quick start) + Kind (full test).

**Detalhamento:**

| Modo            | Stack                                        | Tempo de setup | Use case                                       |
| --------------- | -------------------------------------------- | -------------- | ---------------------------------------------- |
| **Quick start** | Docker Compose: PostgreSQL + Redis + MinIO   | ~2 min         | Desenvolvimento rápido, sem K8s                |
| **Full test**   | Kind cluster: stack completa com Helm charts | ~10 min        | Teste de Helm, K8s configs, air-gap simulation |

**Justificativa:**

- Docker Compose para onboarding rápido reduz barreira de entrada
- Kind para teste completo garante que Helm charts funcionam
- Ambos simulam air-gap (sem dependência de registry externo)

**Impacto:**

- ADR-080: Kind é a distribuição K8s de referência para dev local
- ADR-022: MinIO standalone roda em Docker Compose para dev rápido
- ADR-121: Perfil "dev" define recursos mínimos para Docker Compose

**Data:** 2026-02-07

______________________________________________________________________

## Seção 12: Compliance e Regulatório

### ADR-110: Mapeamento de Frameworks Regulatórios

<!-- metadata:
  id: ADR-110
  status: DECIDED
  decided_value: "Todos — LGPD, GDPR, EU AI Act, NIST AI RMF, ISO 42001, SOX, DAMA-DMBOK"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **Suporte a todos os frameworks listados** como módulos plugáveis de compliance.

**Detalhamento:**

| Framework           | Escopo                   | Módulo                         |
| ------------------- | ------------------------ | ------------------------------ |
| **LGPD**            | Dados pessoais (Brasil)  | Privacy module (ADR-070)       |
| **GDPR**            | Dados pessoais (EU)      | Privacy module (ADR-070)       |
| **EU AI Act**       | Sistemas de IA por risco | AI governance module (ADR-111) |
| **NIST AI RMF 2.0** | Gestão de risco de IA    | AI governance module           |
| **ISO/IEC 42001**   | AI Management System     | AI governance module           |
| **SOX**             | Controles financeiros    | Audit trail module (ADR-112)   |
| **DAMA-DMBOK**      | Best practices           | Core platform (ADR-113)        |

**Implementação:** Compliance como módulo plugável. Core detecta dados/operações relevantes, módulo aplica controles específicos do framework.

**Justificativa:**

- Cobertura ampla de frameworks é requisito para mercado multi-setor (governo + enterprise)
- Módulos plugáveis permitem ativar apenas frameworks relevantes por deployment
- LGPD e GDPR são mandatórios para qualquer plataforma que processe dados pessoais
- EU AI Act e NIST AI RMF são emergentes e diferenciam o OpenDataGov de soluções tradicionais
- DAMA-DMBOK como best practice framework garante maturidade do core

**Impacto:**

- ADR-070: Privacy module implementa controles LGPD e GDPR
- ADR-111: AI governance module implementa classificação de risco EU AI Act
- ADR-112: Audit trail module atende SOX e requisitos de rastreabilidade

**Data:** 2026-02-07

______________________________________________________________________

### ADR-111: Classificação de Risco de IA (EU AI Act)

<!-- metadata:
  id: ADR-111
  status: DECIDED
  decided_value: "Auto-classificação + controles por nível"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **Auto-classificação** de componentes de IA com controles proporcionais ao nível de risco.

**Detalhamento:**

| Nível EU AI Act | Controles                                                                    | Exemplo no OpenDataGov               |
| --------------- | ---------------------------------------------------------------------------- | ------------------------------------ |
| **Alto**        | Human-in-the-loop obrigatório, logging completo, explicabilidade, model card | Expert que classifica dados pessoais |
| **Limitado**    | Transparência sobre uso de IA, logging                                       | Auto-tagging de metadados            |
| **Mínimo**      | Documentação básica                                                          | Recomendação de schema               |

**Auto-classificação:** Cada expert no registry (ADR-034) inclui sua classificação de risco no model card. Data Architect valida a classificação durante approval flow.

**Justificativa:**

- EU AI Act exige classificação de risco para sistemas de IA (Art. 6-7)
- Controles proporcionais evitam overhead excessivo para componentes de baixo risco
- Model cards com classificação de risco atendem requisito de transparência (Art. 13)
- Auto-classificação no registry (ADR-034) integra com approval flow existente

**Impacto:**

- ADR-034: Registry de experts inclui classificação de risco obrigatória no model card
- ADR-032: MLflow model cards documentam bias, fairness e classificação de risco
- ADR-011: Componentes de alto risco requerem human-in-the-loop obrigatório

**Data:** 2026-02-07

______________________________________________________________________

### ADR-112: Persistência e Integridade do Audit Trail

<!-- metadata:
  id: ADR-112
  status: DECIDED
  decided_value: "Kafka → PostgreSQL"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **Kafka para ingestão imutável** + **PostgreSQL para queries e reports**.

**Detalhamento:**

1. **Kafka (ingestão):** Todos os eventos de audit (decisões, aprovações, vetos, acessos, mudanças) são publicados em tópico Kafka append-only. Retenção longa (configurável, default 1 ano).
1. **PostgreSQL (consulta):** Consumer lê do Kafka e persiste em PostgreSQL com índices para query eficiente. Triggers de imutabilidade (DELETE/UPDATE bloqueados na tabela de audit).
1. **Integridade:** Hash chain SHA-256 mantida no PostgreSQL para verificação de integridade (herança do conceito RADaC).
1. **Verificação:** Endpoint de API para verificar integridade da chain a qualquer momento.

**Justificativa:**

- Kafka append-only garante imutabilidade na ingestão (eventos não podem ser alterados)
- PostgreSQL com triggers de imutabilidade garante integridade na consulta
- Hash chain SHA-256 permite verificação criptográfica de integridade a qualquer momento
- Retenção longa (1 ano default) atende requisitos de compliance (LGPD, SOX, EU AI Act)
- Kafka já está no stack (ADR-091) — reutiliza infraestrutura existente

**Impacto:**

- ADR-091: Kafka é a camada de ingestão do audit trail
- ADR-023: PostgreSQL (WARM) armazena audit trail para consulta eficiente
- ADR-101: Dashboard de governança visualiza timeline de audit trail

**Data:** 2026-02-07

______________________________________________________________________

### ADR-113: Cobertura DAMA-DMBOK

<!-- metadata:
  id: ADR-113
  status: DECIDED
  decided_value: "Todas as 11 knowledge areas"
  decided_date: 2026-02-07
  priority: P1
-->

**Decisão:** **Cobertura das 11 knowledge areas DAMA-DMBOK**, com profundidade variável.

| #   | Knowledge Area             | Cobertura | Componente                                          |
| --- | -------------------------- | --------- | --------------------------------------------------- |
| 1   | Data Governance            | Profunda  | Core: RACI, workflows, veto, audit                  |
| 2   | Data Architecture          | Profunda  | Lakehouse + Mesh + Fabric (ADR-020)                 |
| 3   | Data Modeling & Design     | Moderada  | Data contracts (ADR-051), schema registry           |
| 4   | Data Storage & Operations  | Profunda  | 5 datastores (ADR-023), MinIO (ADR-022)             |
| 5   | Data Security              | Profunda  | DP + RBAC + masking (ADR-070), Vault (ADR-073)      |
| 6   | Data Integration & Interop | Profunda  | Kafka, Airflow, Spark, OpenLineage                  |
| 7   | Document & Content Mgmt    | Básica    | RAG knowledge base (ADR-033)                        |
| 8   | Reference & Master Data    | Moderada  | Catálogo DataHub (ADR-040) com golden records       |
| 9   | Data Warehousing & BI      | Moderada  | Trino + camada Gold                                 |
| 10  | Metadata Management        | Profunda  | DataHub + adapter layer + active metadata           |
| 11  | Data Quality               | Profunda  | Great Expectations (ADR-050), 6 dimensões (ADR-052) |

**Justificativa:**

- DAMA-DMBOK é o framework de referência global para gestão de dados
- Cobertura das 11 knowledge areas posiciona o OpenDataGov como plataforma enterprise-grade
- Profundidade variável permite priorizar áreas core sem negligenciar áreas complementares
- Alinhamento com DAMA facilita adoção por organizações que já seguem o framework

**Impacto:**

- ADR-110: DAMA-DMBOK é um dos frameworks regulatórios mapeados como módulo
- ADR-052: 6 dimensões de qualidade DAMA são implementadas como obrigatórias
- ADR-140: Cobertura DAMA guia priorização de funcionalidades por fase de rollout

**Data:** 2026-02-07

______________________________________________________________________

## Seção 10: API e Integração

### ADR-090: Estilo de API

<!-- metadata:
  id: ADR-090
  status: DECIDED
  decided_value: "REST + GraphQL + gRPC"
  decided_date: 2026-02-07
  priority: P2
-->

**Decisão:** **Três estilos de API**, cada um para seu melhor use case.

| Estilo             | Uso                                                               | Implementação                        |
| ------------------ | ----------------------------------------------------------------- | ------------------------------------ |
| **REST (FastAPI)** | API pública para clientes externos, SDKs, CLI                     | FastAPI com OpenAPI spec auto-gerada |
| **GraphQL**        | Queries flexíveis de metadados, catálogo, lineage                 | Strawberry ou Ariadne sobre FastAPI  |
| **gRPC**           | Comunicação entre serviços internos (alta performance, streaming) | Protocol Buffers, gRPC-Python        |

**Justificativa:**

- REST para simplicidade e universalidade (SDKs, CLI)
- GraphQL evita over-fetching em queries complexas de metadados (catálogo, lineage graph)
- gRPC para performance interna (entre experts, orchestrator, governance engine)

**Impacto:**

- ADR-093: Python SDK e CLI consomem API REST; SDKs internos usam gRPC
- ADR-092: COSMOS federation usa gRPC para sync entre instâncias
- ADR-141: API versioning via path aplica-se à camada REST pública

**Data:** 2026-02-07

______________________________________________________________________

### ADR-091: Arquitetura de Eventos

<!-- metadata:
  id: ADR-091
  status: DECIDED
  decided_value: "Kafka (dados) + NATS (serviços)"
  decided_date: 2026-02-07
  priority: P2
-->

**Decisão:** **Kafka para data streaming** + **NATS para mensagens leves entre serviços**.

| Sistema                   | Uso                                                                                    | Justificativa                         |
| ------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------- |
| **Kafka (Strimzi KRaft)** | Data streaming, CDC, audit trail (ADR-112), OpenLineage events                         | Alta throughput, durabilidade, replay |
| **NATS**                  | Governança (notificações de voto, approval requests), health checks, service discovery | Baixa latência, leve, pub/sub nativo  |

**Air-gapped:** Ambos rodam self-hosted. Kafka via Strimzi operator. NATS como deployment K8s simples.

**Justificativa:**

- Kafka para data streaming oferece durabilidade, replay e alta throughput (10-100TB/dia)
- NATS para mensagens leves oferece baixa latência para governança e notificações
- Separação de responsabilidades evita sobrecarregar Kafka com mensagens transientes
- Strimzi KRaft elimina dependência de ZooKeeper (simplifica operação)
- Ambos operam air-gapped sem dependências externas

**Impacto:**

- ADR-112: Audit trail usa Kafka como camada de ingestão imutável
- ADR-083: KEDA escala workloads baseado em Kafka lag
- ADR-060: OpenLineage events fluem via Kafka para o DataHub

**Data:** 2026-02-07

______________________________________________________________________

### ADR-092: Protocolo de Federação COSMOS

<!-- metadata:
  id: ADR-092
  status: DECIDED
  decided_value: "HTTP/gRPC"
  decided_date: 2026-02-07
  priority: P2
-->

**Decisão:** **HTTP/gRPC** para comunicação entre instâncias federadas COSMOS.

**Detalhamento:**

- **Protocolo:** gRPC para sync de CRDTs, HTTP para API de descoberta e health
- **Discovery:** Configuração estática (lista de peers) ou DNS-based
- **Air-gapped:** Funciona via rede privada (VPN, link dedicado) entre instâncias
- **Jurisdição:** Respeita políticas de soberania de dados (ADR-074) — dados não cruzam fronteiras sem política explícita
- **CRDTs:** GCounter, PNCounter, LWWRegister, ORSet (conceitos do RADaC) reimplementados para sync entre peers

**Justificativa:**

- Simples e firewall-friendly
- gRPC eficiente para sync de estado (CRDTs)
- Funciona air-gapped via rede privada

**Impacto:**

- ADR-074: Federação respeita políticas de soberania de dados e jurisdição
- ADR-091: Kafka e NATS podem ser estendidos para comunicação inter-instância
- ADR-002: COSMOS opera via rede privada em contexto air-gapped

**Data:** 2026-02-07

______________________________________________________________________

### ADR-093: SDK e Client Libraries

<!-- metadata:
  id: ADR-093
  status: DECIDED
  decided_value: "Python SDK + CLI + OpenTofu provider"
  decided_date: 2026-02-07
  priority: P2
-->

**Decisão:** **Três interfaces de cliente**: Python SDK, CLI e OpenTofu provider.

| Interface             | Público                          | Prioridade                 |
| --------------------- | -------------------------------- | -------------------------- |
| **Python SDK**        | Data engineers, ML engineers     | Alta — primeira interface  |
| **CLI**               | DevOps, SREs, automation scripts | Alta — segunda interface   |
| **OpenTofu provider** | Infrastructure teams             | Média — terceira interface |

**Justificativa:**

- Python SDK é natural para o público-alvo (data engineering)
- CLI para automação e integração com pipelines CI/CD
- OpenTofu provider para infra-as-code (alinhado com ADR-081)

**Impacto:**

- ADR-090: SDK e CLI consomem APIs REST e GraphQL definidas
- ADR-081: OpenTofu provider reutiliza IaC patterns definidos
- ADR-102: Self-service portal utiliza SDK internamente para operações programáticas

**Data:** 2026-02-07

______________________________________________________________________

## Seção 11: Experiência do Usuário

### ADR-100: Interface Primária

<!-- metadata:
  id: ADR-100
  status: DECIDED
  decided_value: "Estender UI do DataHub"
  decided_date: 2026-02-07
  priority: P2
-->

**Decisão:** **Estender a UI do DataHub** com plugins e extensões para governança OpenDataGov.

**Detalhamento:**

- **Base:** DataHub UI como portal de catálogo, lineage e busca
- **Extensões:** Plugins customizados para:
  - Dashboard de governança (ADR-101)
  - Workflows de aprovação RACI
  - Visualização de classificação de dados e privacy
  - Self-service portal (ADR-102)
- **Branding:** Customização visual do DataHub para identidade OpenDataGov

**Justificativa:**

- Reutiliza investimento do DataHub (ADR-040) — não duplica UI
- DataHub tem sistema de plugins extensível
- Menor esforço que portal React/Next.js from scratch
- UX unificada: catálogo + governança + qualidade em um só lugar

**Impacto:**

- ADR-101: Dashboard de governança é extensão da UI DataHub
- ADR-102: Portal self-service é extensão da UI DataHub
- ADR-040: DataHub como catálogo é a base da UI primária

**Data:** 2026-02-07

______________________________________________________________________

### ADR-101: Dashboard de Governança

<!-- metadata:
  id: ADR-101
  status: DECIDED
  decided_value: "Completo"
  decided_date: 2026-02-07
  priority: P2
-->

**Decisão:** **Dashboard completo** de governança como extensão do DataHub.

**Views:**

1. **Histórico de decisões:** Todas as decisões de governança com status, aprovadores, timestamps
1. **Padrões de aprovação por papel RACI:** Quem aprova mais, tempo médio de aprovação, gargalos
1. **Privacy budget:** Consumo de epsilon por dataset/domínio (DP — ADR-070)
1. **Lineage integrado com governança:** Lineage graph com overlay de classificação de dados e aprovações
1. **Timeline de audit trail:** Visualização cronológica de todos os eventos de governança

**Justificativa:**

- Visibilidade de governança é requisito para compliance (LGPD, EU AI Act, SOX)
- Dashboard unificado reduz tempo de auditoria e facilita identificação de gargalos
- Privacy budget tracking é requisito para uso responsável de Differential Privacy
- Lineage com overlay de governança conecta decisões ao fluxo de dados

**Impacto:**

- ADR-100: Dashboard é extensão da UI DataHub (mesma plataforma)
- ADR-112: Audit trail alimenta a timeline de eventos de governança
- ADR-070: Privacy budget (epsilon) é monitorado via dashboard

**Data:** 2026-02-07

______________________________________________________________________

### ADR-102: Portal Self-Service de Dados

<!-- metadata:
  id: ADR-102
  status: DECIDED
  decided_value: "Sim, completo"
  decided_date: 2026-02-07
  priority: P2
-->

**Decisão:** **Portal self-service completo** como extensão do DataHub.

**Capabilities:**

1. **Discovery:** Busca de datasets com relevância, filtros por domínio, classificação, qualidade
1. **Access request:** Workflow governado — consumidor solicita, Data Owner aprova (RACI)
1. **Pipeline creation:** Interface visual para criar pipelines simples (ingestão, transformação básica)
1. **Data preview:** Prévia de dados com privacy controls aplicados (masking, DP conforme classificação)

**Meta (da metodologia de auditoria):** Reduzir time-to-pipeline de 4 semanas para 2-5 dias.

**Justificativa:**

- Self-service reduz dependência de equipes centrais e acelera time-to-value
- Access request governado mantém compliance sem burocracia excessiva
- Pipeline creation visual democratiza criação de pipelines para analistas
- Data preview com privacy controls permite exploração segura de dados sensíveis

**Impacto:**

- ADR-100: Portal self-service é extensão da UI DataHub (mesma plataforma)
- ADR-012: Access requests passam por governance workflow RACI
- ADR-070: Data preview aplica masking e DP conforme classificação

**Data:** 2026-02-07

______________________________________________________________________

## Seção 13: Custo e Sustentabilidade

### ADR-120: Estratégia de FinOps

<!-- metadata:
  id: ADR-120
  status: DECIDED
  decided_value: "OpenCost/Kubecost integrado"
  decided_date: 2026-02-07
  priority: P2
-->

**Decisão:** **OpenCost/Kubecost integrado** com dashboards Grafana.

**Detalhamento:**

- OpenCost (CNCF sandbox) para alocação de custo por namespace, label, pod
- Dashboards Grafana para visualização de custo por componente do OpenDataGov
- Alertas de custo anômalo via OTel metrics

**Justificativa:**

- OpenCost é CNCF sandbox project, alinhado com stack cloud-native
- Alocação de custo por namespace/label permite chargeback por domínio de dados
- Grafana dashboards reutilizam stack de visualização existente (ADR-061)
- Alertas de custo anômalo via OTel integram com stack de observabilidade

**Impacto:**

- ADR-061: FinOps dashboards em Grafana seguem mesma stack de observabilidade
- ADR-062: Métricas de custo podem ser emitidas via OTel custom metrics
- ADR-121: Perfis de deployment definem baseline de custo esperado por tier

**Data:** 2026-02-07

______________________________________________________________________

### ADR-121: Perfis de Deployment (Sizing)

<!-- metadata:
  id: ADR-121
  status: DECIDED
  decided_value: "4 perfis — dev/small/medium/large"
  decided_date: 2026-02-07
  priority: P2
-->

**Decisão:** **4 perfis de deployment** com componentes e recursos definidos.

| Perfil     | Componentes                                  | Recursos                  | IA                  | Use Case                               |
| ---------- | -------------------------------------------- | ------------------------- | ------------------- | -------------------------------------- |
| **dev**    | PostgreSQL + Redis + MinIO                   | 4 vCPU, 16GB RAM          | Sem IA              | Desenvolvimento local (Docker Compose) |
| **small**  | + Kafka + Trino + Airflow + DataHub          | 16 vCPU, 64GB RAM         | 1 expert (opcional) | Equipe pequena, \<1TB/dia              |
| **medium** | + Qdrant + TimescaleDB + multi-expert        | 64 vCPU, 256GB RAM, GPU   | Multi-expert ativo  | Enterprise, 1-10TB/dia                 |
| **large**  | Full stack + GPU cluster + multi-AZ + COSMOS | 256+ vCPU, 1TB+ RAM, GPUs | Full B-Swarm        | Large-scale, >10TB/dia                 |

**Justificativa:**

- 4 perfis cobrem desde dev local até large enterprise (10-100TB/dia)
- Componentes incrementais por tier evitam complexidade desnecessária em deployments menores
- IA opcional nos perfis menores respeita progressividade (ADR-001)
- GPU obrigatória apenas a partir de medium alinha custo com necessidade real
- Perfil dev em Docker Compose garante onboarding rápido (ADR-084)

**Impacto:**

- ADR-084: Perfil dev define stack mínima para Docker Compose e Kind
- ADR-031: Perfis medium/large requerem GPU para inferência vLLM
- ADR-023: Perfis small/medium/large determinam quais datastores são ativados

**Data:** 2026-02-07

______________________________________________________________________

### ADR-122: Modelo de Sustentabilidade do Projeto

<!-- metadata:
  id: ADR-122
  status: DECIDED
  decided_value: "Consulting/Support"
  decided_date: 2026-02-07
  priority: P2
-->

**Decisão:** **Consulting/Support** — serviço de implantação e suporte como modelo de sustentabilidade.

**Detalhamento:**

- **Implantação:** Consultoria para deploy, configuração e customização do OpenDataGov
- **Suporte:** SLA de suporte para organizações em produção
- **Treinamento:** Capacitação de equipes em governança de dados e operação da plataforma
- **Alinhamento:** Metodologia de auditoria de 12 semanas do RADaC como framework de engajamento

**Justificativa:**

- Apache-2.0 (ADR-003) permite modelo de consulting sem conflito
- Alinhado com metodologia de auditoria existente
- Receita imediata sem necessidade de features proprietárias
- Pode evoluir para Foundation-backed ou Open Core no futuro

**Impacto:**

- ADR-003: Modelo consulting/support é compatível com Apache-2.0
- ADR-130: BDFL conduz engajamentos de consultoria na fase inicial
- ADR-140: Metodologia de auditoria de 12 semanas é o framework de engajamento do consulting

**Data:** 2026-02-07

______________________________________________________________________

## Seção 14: Comunidade e Open-Source

### ADR-130: Modelo de Contribuição

<!-- metadata:
  id: ADR-130
  status: DECIDED
  decided_value: "BDFL"
  decided_date: 2026-02-07
  priority: P2
-->

**Decisão:** **BDFL (Benevolent Dictator for Life)** como modelo de governança de projeto inicial.

**Detalhamento:**

- Silvano Neto como BDFL na fase inicial
- Decisões técnicas e de roadmap centralizadas
- Contribuições via fork-and-PR com review do BDFL
- Plano de evolução: migrar para meritocracia Apache-style quando comunidade amadurecer

**Justificativa:**

- BDFL garante velocidade de decisão na fase inicial do projeto
- Evita paralisia por comitê quando a comunidade ainda é pequena
- Modelo usado com sucesso por projetos como Python (Guido), Linux (Linus), Rust (início)
- Plano de evolução para meritocracia garante sustentabilidade a longo prazo

**Impacto:**

- ADR-122: BDFL conduz engajamentos de consulting na fase inicial
- ADR-131: Pontos de extensão são definidos e aprovados pelo BDFL
- ADR-140: BDFL define prioridades de roadmap por fase

**Data:** 2026-02-07

______________________________________________________________________

### ADR-131: Arquitetura de Plugins/Extensões

<!-- metadata:
  id: ADR-131
  status: DECIDED
  decided_value: "6 pontos de extensão formais"
  decided_date: 2026-02-07
  priority: P2
-->

**Decisão:** **6 pontos de extensão formais** com interfaces definidas.

| Ponto de Extensão     | Interface                                           | Governado?                      |
| --------------------- | --------------------------------------------------- | ------------------------------- |
| **AI Expert**         | `BaseExpert` (process, capabilities, model card)    | Sim — approval flow (ADR-034)   |
| **DQ Check**          | `BaseCheck` (validate, severity, dimension)         | Não — auto-registro             |
| **Governance Rule**   | `BaseRule` (evaluate, actions, conditions)          | Sim — Data Architect aprova     |
| **Catalog Connector** | `BaseConnector` (extract, transform, load metadata) | Não — auto-registro             |
| **Privacy Mechanism** | `BasePrivacy` (apply, configure, audit)             | Sim — Compliance Officer aprova |
| **Storage Backend**   | `BaseStorage` (read, write, list, S3-compatible)    | Não — auto-registro             |

**Justificativa:**

- 6 pontos de extensão cobrem os principais eixos de customização da plataforma
- Interfaces formais (BaseExpert, BaseCheck, etc.) garantem contratos claros para contribuidores
- Governance por tipo de extensão equilibra segurança (experts, privacy) com facilidade (DQ checks, connectors)
- Auto-registro para extensões de baixo risco reduz burocracia sem comprometer segurança

**Impacto:**

- ADR-034: AI Expert como ponto de extensão reutiliza registry e approval flow de experts
- ADR-050: DQ Check como ponto de extensão permite custom expectations no Great Expectations
- ADR-070: Privacy Mechanism como ponto de extensão permite mecanismos adicionais de privacidade

**Data:** 2026-02-07

______________________________________________________________________

### ADR-132: Internacionalização

<!-- metadata:
  id: ADR-132
  status: DECIDED
  decided_value: "Código EN, docs trilíngue PT/EN/ZH"
  decided_date: 2026-02-07
  priority: P2
-->

**Decisão:** **Código em inglês**, documentação **trilíngue (PT/EN/ZH)**.

**Detalhamento:**

- **Código:** Todos os enums, variáveis, APIs, comentários em inglês. Ex: `POLITICAL` (não `POLITICA`), `PERSONAL` (não `PESSOAL`)
- **Documentação:** Português (primário), Inglês, Chinês — como o RADaC
- **API:** Endpoints e responses em inglês
- **UI:** i18n com PT como default, EN e ZH como alternativas

**Justificativa:**

- Código em inglês é padrão da indústria e facilita contribuições internacionais
- Documentação trilíngue (PT/EN/ZH) maximiza alcance nos mercados-alvo
- Clean-room redesign (ADR-004) permite definir enums/APIs em inglês desde o início
- i18n na UI garante acessibilidade para usuários finais em cada idioma

**Impacto:**

- ADR-004: Clean-room redesign adota nomenclatura em inglês (POLITICAL, PERSONAL, etc.)
- ADR-090: APIs e endpoints são definidos em inglês
- ADR-100: UI do DataHub suporta i18n com PT como default

**Data:** 2026-02-07

______________________________________________________________________

## Seção 15: Evolução e Roadmap

### ADR-140: Modelo de Maturidade e Fases de Rollout

<!-- metadata:
  id: ADR-140
  status: DECIDED
  decided_value: "5 fases"
  decided_date: 2026-02-07
  priority: P2
-->

**Decisão:** **5 fases de evolução** alinhadas com metodologia de auditoria.

| Fase                  | Foco                                          | ADRs  | Alinhamento                    |
| --------------------- | --------------------------------------------- | ----- | ------------------------------ |
| **0 — Definição**     | Este documento. Todas as decisões tomadas     | Todas | Pre-Q1                         |
| **1 — Foundation**    | Core governance + lakehouse mínimo + 1 expert | P0    | Q1 (Diagnosis + Quick Wins)    |
| **2 — Stabilization** | Catálogo + DQ + lineage + observabilidade     | P1    | Q2 (SLAs + Observability)      |
| **3 — Scale**         | Multi-expert + federation + self-service      | P2    | Q3 (Automation + Self-Service) |
| **4 — Optimization**  | FinOps + community plugins + LTS release      | Todas | Q4 (Refinement)                |

**Justificativa:**

- 5 fases permitem entrega incremental de valor sem tentar "boil the ocean"
- Alinhamento com metodologia de auditoria Q1-Q4 facilita planejamento de engajamentos
- Prioridade P0 → P1 → P2 garante que fundações são sólidas antes de features avançadas
- Fase 0 (este documento) garante que todas as decisões são tomadas antes de escrever código

**Impacto:**

- ADR-142: Cadência de releases trimestrais alinha com fases de rollout
- ADR-122: Modelo consulting/support usa fases como framework de engajamento
- ADR-121: Perfis de deployment evoluem conforme fases (dev → small → medium → large)

**Data:** 2026-02-07

______________________________________________________________________

### ADR-141: Compatibilidade Retroativa e Versionamento

<!-- metadata:
  id: ADR-141
  status: DECIDED
  decided_value: "SemVer + API versioning via path"
  decided_date: 2026-02-07
  priority: P2
-->

**Decisão:** **Semantic Versioning** para o projeto + **API versioning via path**.

**Detalhamento:**

- **Projeto:** MAJOR.MINOR.PATCH (SemVer 2.0)
- **APIs:** `/v1/`, `/v2/` no path. N-1 suportado (6 meses de sunset period)
- **Deprecation:** Features deprecadas com warning por 2 releases antes de remoção
- **Data contracts:** Breaking changes seguem governance (ADR-051)

**Justificativa:**

- SemVer é o padrão de versionamento mais reconhecido no ecossistema open-source
- API versioning via path é o padrão mais simples e amplamente suportado
- N-1 com sunset period de 6 meses equilibra estabilidade com evolução
- Deprecation warnings por 2 releases dão tempo para migração

**Impacto:**

- ADR-090: APIs REST/GraphQL/gRPC seguem versionamento via path (/v1/, /v2/)
- ADR-051: Data contracts com breaking changes seguem governance e versionamento
- ADR-093: SDKs e CLI versionam junto com o projeto (SemVer)

**Data:** 2026-02-07

______________________________________________________________________

### ADR-142: Cadência de Atualização Tecnológica

<!-- metadata:
  id: ADR-142
  status: DECIDED
  decided_value: "Security ASAP + quarterly features"
  decided_date: 2026-02-07
  priority: P2
-->

**Decisão:** **Patches de segurança imediatos** + **features trimestrais**.

**Detalhamento:**

- **Security patches:** CVEs críticos (CVSS >= 7) em até 72h. Altos em até 2 semanas
- **Feature releases:** Trimestrais (alinhado com ciclo de auditoria Q1-Q4)
- **Dependency updates:** Trimestrais (junto com feature release)
- **LTS:** Após Fase 4, considerar release LTS anual para enterprise

**Justificativa:**

- Patches de segurança imediatos são requisito para ambientes governo/enterprise
- CVSS >= 7 em até 72h alinha com best practices de resposta a incidentes
- Releases trimestrais alinham com fases de rollout (ADR-140) e ciclo de auditoria
- LTS anual após Fase 4 atende enterprise que precisa de estabilidade a longo prazo

**Impacto:**

- ADR-140: Feature releases trimestrais alinham com fases de rollout Q1-Q4
- ADR-141: Patches de segurança podem ser minor/patch releases dentro do SemVer
- ADR-082: ArgoCD pode sincronizar patches de segurança com auto-sync em staging

**Data:** 2026-02-07

______________________________________________________________________

## Resumo de Todas as Decisões

<!--
progress_summary:
  total_adrs: 50
  decided: 50
  open: 0
  deferred: 0
  p0_decided: 18
  p1_decided: 22
  p2_decided: 10
-->

| ADR | Decisão                                            | Prioridade |
| --- | -------------------------------------------------- | ---------- |
| 001 | Plataforma completa + AI progressiva (b)+(c)       | P0         |
| 002 | Single-org, 10-100TB/dia, air-gapped, multi-setor  | P0         |
| 003 | Apache-2.0                                         | P0         |
| 004 | Clean-room redesign (RADaC como referência)        | P0         |
| 010 | Híbrida configurável                               | P0         |
| 011 | IA recomenda, humano decide (tudo requer humano)   | P0         |
| 012 | Governança abrangente (dados + IA + infra)         | P0         |
| 013 | RACI/Stewardship (substituir 5 representações)     | P0         |
| 014 | Veto configurável com defaults                     | P0         |
| 020 | Lakehouse + Mesh + Fabric                          | P0         |
| 021 | Iceberg + UniForm/XTable                           | P0         |
| 022 | MinIO everywhere                                   | P0         |
| 023 | 5 datastores por temperatura                       | P0         |
| 024 | 4 camadas (Bronze/Silver/Gold/Platinum) + DQ gates | P0         |
| 030 | Híbrido: B-Swarm governance + MLOps                | P0         |
| 031 | vLLM + LiteLLM Gateway                             | P0         |
| 032 | MLflow + B-Swarm governance                        | P0         |
| 033 | Qdrant standalone                                  | P0         |
| 034 | Registry + approval flow                           | P0         |
| 040 | DataHub                                            | P1         |
| 041 | Adapter layer de metadados                         | P1         |
| 042 | Híbrido: regras + IA para active metadata          | P1         |
| 050 | Great Expectations                                 | P1         |
| 051 | DataContract Spec + governança                     | P1         |
| 052 | 6 dimensões DAMA obrigatórias                      | P1         |
| 060 | OpenLineage → DataHub                              | P1         |
| 061 | Convergência via OTel                              | P1         |
| 062 | OTel everywhere                                    | P1         |
| 063 | Integrado com DQ engine + Grafana                  | P1         |
| 070 | DP + RBAC + masking                                | P1         |
| 071 | Classificação padrão (Public → Top Secret)         | P1         |
| 072 | Keycloak + OPA                                     | P1         |
| 073 | Vault + mTLS via service mesh                      | P1         |
| 074 | Awareness jurisdicional built-in                   | P1         |
| 080 | Cloud-agnostic (Kind/K3s referência)               | P1         |
| 081 | OpenTofu + Helm                                    | P1         |
| 082 | ArgoCD + governança                                | P1         |
| 083 | Cluster Autoscaler + KEDA                          | P1         |
| 084 | Múltiplos modos (Compose + Kind)                   | P1         |
| 090 | REST + GraphQL + gRPC                              | P2         |
| 091 | Kafka + NATS                                       | P2         |
| 092 | HTTP/gRPC para COSMOS                              | P2         |
| 093 | Python SDK + CLI + OpenTofu provider               | P2         |
| 100 | Estender UI do DataHub                             | P2         |
| 101 | Dashboard de governança completo                   | P2         |
| 102 | Portal self-service completo                       | P2         |
| 110 | Todos os frameworks regulatórios                   | P1         |
| 111 | Auto-classificação + controles por nível           | P1         |
| 112 | Kafka → PostgreSQL                                 | P1         |
| 113 | Todas as 11 knowledge areas DAMA                   | P1         |
| 120 | OpenCost/Kubecost                                  | P2         |
| 121 | 4 perfis (dev/small/medium/large)                  | P2         |
| 122 | Consulting/Support                                 | P2         |
| 130 | BDFL                                               | P2         |
| 131 | 6 pontos de extensão                               | P2         |
| 132 | Código EN, docs PT/EN/ZH                           | P2         |
| 140 | 5 fases de rollout                                 | P2         |
| 141 | SemVer + API versioning                            | P2         |
| 142 | Security ASAP + quarterly features                 | P2         |
