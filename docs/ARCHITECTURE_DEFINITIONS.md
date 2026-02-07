# OpenDataGov — Definições Arquiteturais

<!--
document_metadata:
  version: "0.1.0"
  status: DRAFT
  created: 2025-02-07
  authors:
    - role: human_architect
      name: Silvano Neto
    - role: ai_architect
      name: Claude (Opus 4.6)
  source_template: RADaC (.radac/)
  total_adrs: 50
  decided: 0
  open: 50
  deferred: 0
-->

## Como usar este documento

Cada decisão segue o formato **ADR (Architecture Decision Record)** com estrutura consistente:

- **Metadata HTML comment** — parseável por IA para rastreamento automático de progresso
- **Contexto** — por que essa decisão importa
- **Pergunta** — a definição específica necessária
- **Alternativas** — tabela com prós, contras e fit
- **Baseline RADaC** — o que o template `.radac/` faz hoje
- **Recomendação** — sugestão padrão (quando aplicável)
- **Dependências** — outras ADRs que influenciam esta

**Status possíveis:** `OPEN` (pendente), `DECIDED` (decidido), `DEFERRED` (adiado)

**Prioridades:** `P0` (decidir primeiro), `P1` (decidir antes de implementar), `P2` (pode evoluir)

______________________________________________________________________

## Glossário

| Sigla | Significado                                    |
| ----- | ---------------------------------------------- |
| ADR   | Architecture Decision Record                   |
| CDC   | Change Data Capture                            |
| CRDT  | Conflict-free Replicated Data Type             |
| DP    | Differential Privacy (Privacidade Diferencial) |
| DQ    | Data Quality                                   |
| IaC   | Infrastructure as Code                         |
| LGPD  | Lei Geral de Proteção de Dados                 |
| OTel  | OpenTelemetry                                  |
| RBAC  | Role-Based Access Control                      |
| SLA   | Service Level Agreement                        |

______________________________________________________________________

## Seção 1: Identidade e Escopo da Plataforma `P0`

### ADR-001: Missão da Plataforma

<!-- metadata:
  id: ADR-001
  domain: identity
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "Plataforma completa para auditoria e gestão de dados críticos, combinando metodologia estruturada, infraestrutura lakehouse moderna e inteligência artificial distribuída"
  references: ["DAMA-DMBOK", "Data Mesh self-serve platform"]
-->

**Contexto:** O nome "OpenDataGov" sugere dados abertos + governança. Porém o RADaC inclui swarm de IA, lakehouse e metodologia de auditoria. O escopo precisa ser explícito para guiar todas as decisões seguintes — é o "north star" do projeto.

**Pergunta:** O que é o OpenDataGov?

**Alternativas:**

| Opção                                                                                                                    | Prós                                                                  | Contras                                                                             | Fit                                        |
| ------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------ |
| **(a) Plataforma de governança com assistência de IA** — foco em catálogo, qualidade, lineage, compliance; IA é auxiliar | Escopo claro, competitivo com DataHub/OpenMetadata, adoção facilitada | Subutiliza o B-Swarm, não diferencia                                                | Alto se o foco for adoção                  |
| **(b) Plataforma de dados completa com governança embarcada** — lakehouse + governança + IA, tudo integrado              | Proposta de valor única, reduz integração, valor imediato             | Complexidade alta, competição com Databricks/Snowflake OSS, escopo gigante          | Alto se houver equipe/funding              |
| **(c) Plataforma AI-first com auto-governança** — IA governa decisões sobre dados e sobre si mesma                       | Inovação real, diferenciação máxima, alinhado com tendências 2025+    | Risco regulatório (EU AI Act exige supervisão humana), complexidade sem precedentes | Médio — inovador mas arriscado             |
| **(d) Framework/metodologia + implementações de referência** — especificação + templates opinionados                     | Baixo custo de manutenção, escalável como comunidade, educacional     | Não é produto, difícil monetizar, requer documentação excepcional                   | Alto se o objetivo for influência/educação |

**Baseline RADaC:** O README descreve o RADaC como opção (b)+(c) — "plataforma completa para auditar e gerenciar dados críticos, combinando metodologia, infraestrutura lakehouse e IA distribuída".

**Recomendação:** Nenhuma — esta é a decisão mais importante e precisa de input humano.

**Dependências:** Todas as outras ADRs dependem desta.

______________________________________________________________________

### ADR-002: Persona-Alvo e Contexto de Deploy

<!-- metadata:
  id: ADR-002
  domain: identity
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "Data engineers com a metodologia de auditoria sugerindo cenários de consultoria enterprise"
  references: ["DCAM v3 maturity levels"]
-->

**Contexto:** A arquitetura varia drasticamente dependendo de quem vai usar e onde vai rodar. Uma startup com 5 pessoas tem necessidades completamente diferentes de um órgão governamental com 500 engenheiros de dados.

**Pergunta:** Quem é o usuário primário e qual o contexto de deployment?

**Alternativas:**

| Opção                                                          | Prós                                                                 | Contras                                           | Fit                          |
| -------------------------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------- | ---------------------------- |
| **(a) Startups/PMEs (single-tenant, \<10TB)**                  | Deploy simples, baixo custo, feedback rápido                         | Mercado sensível a preço, features simples bastam | Médio                        |
| **(b) Enterprise (multi-tenant, >100TB)**                      | Alto valor por cliente, features complexas justificadas              | Ciclo de venda longo, compliance pesada           | Alto para B-Swarm            |
| **(c) Governo/Setor Público**                                  | Alinhado com "OpenDataGov", regulamentação forte favorece governança | Burocracia, licitações, requisitos de soberania   | Alto pelo nome               |
| **(d) Multi-persona (modular, cada camada serve um segmento)** | Maior mercado endereçável, flexibilidade                             | Mais complexo de desenvolver e manter             | Alto se ADR-001 = (b) ou (d) |

**Sub-perguntas:**

1. O deploy é single-org ou multi-org (SaaS)?
1. Qual o volume de dados esperado como referência? (1TB/dia, 10TB/dia, 100TB/dia)
1. Requer operação air-gapped (sem internet)?

**Baseline RADaC:** Terraform para AWS EKS, custo estimado de ~$9.000/mês para 10TB/dia. Foco implícito em enterprise.

**Dependências:** ADR-001

______________________________________________________________________

### ADR-003: Licenciamento e Estratégia Open-Source

<!-- metadata:
  id: ADR-003
  domain: identity
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "AGPL 3.0"
  references: ["AGPL-3.0", "Apache-2.0", "BSL 1.1", "SSPL"]
-->

**Contexto:** A licença define o ecossistema. AGPL-3.0 (licença atual do RADaC) tem implicações de copyleft forte — qualquer serviço que use o código precisa liberar o código-fonte. Isso limita adoção enterprise mas protege contra "cloud-washing" (AWS/GCP oferecerem como serviço gerenciado sem contribuir).

**Pergunta:** Qual licença deve reger o OpenDataGov?

**Alternativas:**

| Opção                                             | Prós                                                                                      | Contras                                                                               | Fit                      |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------ |
| **AGPL-3.0** (copyleft forte)                     | Protege contra cloud-washing, garante código aberto                                       | Enterprise evita AGPL, limita adoção corporativa                                      | Se prioridade é proteção |
| **Apache-2.0** (permissiva)                       | Máxima adoção, padrão CNCF/Apache Foundation, enterprise-friendly                         | Permite forks proprietários sem retorno, sem proteção contra cloud-washing            | Se prioridade é adoção   |
| **BSL 1.1** (source-available → open após N anos) | Modelo Sentry/CockroachDB/Hashicorp, protege negócio, eventualmente open                  | Polêmica na comunidade, não é "true open-source" pela OSI                             | Se há plano comercial    |
| **Dual License** (AGPL + comercial)               | Comunidade usa AGPL, enterprise compra licença comercial. Modelo MongoDB/Elastic pré-SSPL | Complexidade jurídica, precisa de entidade legal, contribuidores precisam assinar CLA | Se quer ambos            |

**Baseline RADaC:** AGPL 3.0 (arquivo `.radac/LICENSE`).

**Dependências:** ADR-001, ADR-002

______________________________________________________________________

### ADR-004: Relação com o RADaC

<!-- metadata:
  id: ADR-004
  domain: identity
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "RADaC é o template fonte dentro de .radac/"
  references: []
-->

**Contexto:** O OpenDataGov nasce do RADaC. A relação precisa ser definida para gerenciar evolução, branding e contribuições.

**Pergunta:** Qual a relação estrutural entre OpenDataGov e RADaC?

**Alternativas:**

| Opção                                                                     | Prós                                                            | Contras                                                    | Fit                     |
| ------------------------------------------------------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------- | ----------------------- |
| **Hard fork** — diverge completamente, RADaC vira histórico               | Liberdade total de redesign, sem dívida técnica herdada         | Perde contribuições upstream, duplica esforço              | Se redesign profundo    |
| **Upstream/downstream** — RADaC como core, OpenDataGov estende            | Contribuições fluem nos dois sentidos, comunidade compartilhada | Acoplamento, conflitos de merge, dois projetos para manter | Se RADaC continua ativo |
| **Monorepo** — RADaC vira um package/módulo dentro do OpenDataGov         | Tudo junto, facilita refatoração, versão única                  | Repo grande, onboarding complexo                           | Se equipe é pequena     |
| **Clean-room redesign** — usa RADaC como especificação, reescreve do zero | Código limpo, sem dívida técnica, pode mudar linguagem/stack    | Maior esforço inicial, perde código testado                | Se quer mudar stack     |

**Baseline RADaC:** Atualmente `.radac/` é um diretório dentro do repo OpenDataGov.

**Dependências:** ADR-001

______________________________________________________________________

## Seção 2: Modelo de Governança `P0`

### ADR-010: Topologia de Governança

<!-- metadata:
  id: ADR-010
  domain: governance
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "Modelo de 5 representações com votação ponderada por tipo de decisão"
  references: ["Data Mesh - Zhamak Dehghani", "DAMA-DMBOK Cap.3", "Data Fabric - Gartner"]
-->

**Contexto:** Como a governança é organizada afeta todas as outras decisões. A indústria converge para modelos híbridos. O B-Swarm do RADaC implementa algo original — governança por representação democrática com votação ponderada.

**Pergunta:** Qual topologia de governança o OpenDataGov deve implementar?

**Alternativas:**

| Opção                                                                                                              | Prós                                                  | Contras                                               | Fit                   |
| ------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------- | ----------------------------------------------------- | --------------------- |
| **Centralizada** — um time de governança controla tudo                                                             | Simples, consistente, fácil de auditar                | Gargalo, não escala, resistência organizacional       | Baixo                 |
| **Federada (Data Mesh)** — domínios de dados autônomos com padrões compartilhados                                  | Escala, ownership claro, padrão de mercado            | Complexo de coordenar, risco de fragmentação          | Médio-alto            |
| **Híbrida** — guardrails centrais + autonomia local (federated computational governance)                           | Melhor dos dois mundos, flexível                      | Mais difícil de definir fronteiras                    | Alto                  |
| **B-Swarm social** — 5 representações (Política, Econômica, Geográfica, Científica, Militar) com votação ponderada | Inovador, permite nuance, multi-stakeholder by design | Sem precedente na indústria, complexo, pode confundir | Alto se ADR-001 = (c) |
| **Configurável** — oferece todos os modelos acima como opções de configuração                                      | Máxima flexibilidade                                  | Complexidade de implementação e teste                 | Médio                 |

**Baseline RADaC:** B-Swarm implementa o modelo social com 5 representações e 4 tipos de decisão (EMERGENCIAL/CRITICA/NORMAL/ESTRUTURAL) com pesos dinâmicos. Arquivo: `.radac/b-swarm/src/governance/representation.py`.

**Sub-perguntas:**

1. O modelo de 5 representações é uma proposta teórica/filosófica ou deve ser a implementação padrão?
1. Se for configurável, qual deve ser o default?

**Dependências:** ADR-001, ADR-002

______________________________________________________________________

### ADR-011: Atores Humanos vs. IA na Governança

<!-- metadata:
  id: ADR-011
  domain: governance
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "Representações são abstratas — votes vêm de entidades 'representation', não explicitamente humanos ou agentes IA"
  references: ["EU AI Act Art. 14 (human oversight)", "NIST AI RMF 2.0"]
-->

**Contexto:** O sistema de votação do B-Swarm é abstrato — qualquer entidade pode votar como "representação". Mas o EU AI Act (Art. 14) exige supervisão humana significativa para sistemas de IA de alto risco. O NIST AI RMF 2.0 também enfatiza "human-in-the-loop".

**Pergunta:** Como atores humanos e agentes de IA interagem no processo de governança?

**Alternativas:**

| Opção                                                                                                                         | Prós                                                          | Contras                                       | Fit                  |
| ----------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- | --------------------------------------------- | -------------------- |
| **Humanos decidem, IA recomenda** — IA analisa e sugere, humano vota                                                          | Compliance regulatória, confiável                             | Lento, não escala, subutiliza IA              | Alto para compliance |
| **IA decide, humano supervisiona** — IA vota automaticamente, humano pode vetar/overridar                                     | Rápido, escala, AI-first                                      | Risco regulatório para decisões de alto risco | Médio                |
| **Modelo misto por tipo de decisão** — EMERGENCIAL/CRITICA permitem decisão autônoma da IA; NORMAL/ESTRUTURAL requerem humano | Pragmático, respeita urgência e risco                         | Complexo de definir fronteiras                | Alto                 |
| **Delegação explícita** — humano define políticas; IA executa dentro das políticas; exceções escalam para humano              | Melhor equilíbrio, alinhado com NIST AI RMF "govern" function | Requer definição cuidadosa de policies        | Alto                 |

**Baseline RADaC:** O código em `representation.py` e `voting.py` trata representações como strings abstratas. O orchestrator (`main.py`) casta votos por nome de representação sem distinguir se a origem é humana ou IA.

**Sub-perguntas:**

1. Para decisões sobre dados pessoais (LGPD/GDPR), o humano deve estar SEMPRE no loop?
1. Para decisões operacionais (escalonamento de recursos), a IA pode decidir sozinha?
1. Existe um "nível de autonomia" configurável por tipo de decisão?

**Dependências:** ADR-010

______________________________________________________________________

### ADR-012: Escopo da Governança — O Que é Governado

<!-- metadata:
  id: ADR-012
  domain: governance
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "Atualmente governa roteamento de experts e 'decisões' abstratas — não cobre governança de pipelines de dados"
  references: ["DAMA-DMBOK 11 knowledge areas", "Data Contracts"]
-->

**Contexto:** O B-Swarm governa decisões de IA. Mas uma plataforma de governança de dados precisa governar muito mais: mudanças de schema, políticas de acesso, limiares de qualidade, promoções de pipeline, deployments de modelos.

**Pergunta:** Quais tipos de decisão passam pelo processo formal de governança (votação)?

**Alternativas (multi-select possível):**

| Tipo de Decisão                            | Via Votação? | Justificativa                        |
| ------------------------------------------ | ------------ | ------------------------------------ |
| Mudança de schema (breaking change)        | ?            | Pode quebrar consumidores downstream |
| Concessão/revogação de acesso a dados      | ?            | Impacto em privacidade/segurança     |
| Promoção de dados (Bronze → Silver → Gold) | ?            | Afeta confiabilidade para analistas  |
| Deploy de novo modelo de IA                | ?            | Risco de viés, regulatório           |
| Alteração de pipeline de dados             | ?            | Impacto operacional                  |
| Mudança de SLA/limiar de qualidade         | ?            | Afeta contratos com consumidores     |
| Criação de novo domínio de dados           | ?            | Impacto organizacional               |
| Exceção temporária de qualidade            | ?            | Trade-off entre velocidade e rigor   |

**Sub-pergunta:** Decisões automatizáveis vs. decisões que requerem deliberação — onde fica a linha?

**Baseline RADaC:** Governa roteamento de experts e decisões abstratas. Não tem integração com pipeline de dados (Airflow, Spark, Trino).

**Dependências:** ADR-010, ADR-011

______________________________________________________________________

### ADR-013: Modelo de 5 Representações — Manter, Adaptar ou Substituir

<!-- metadata:
  id: ADR-013
  domain: governance
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "5 representações hardcoded: POLITICA, ECONOMICA, GEOGRAFICA, CIENTIFICA, MILITAR"
  references: ["RACI matrix", "Data Stewardship models"]
-->

**Contexto:** As 5 representações (Política, Econômica, Geográfica, Científica, Militar) são filosoficamente interessantes mas podem não mapear bem para governança de dados empresarial. "Militar" pode ser desconfortável em contextos corporativos. Os domínios de veto são: `governance_and_rights`, `resources_and_distribution`, `territory_and_sovereignty`, `technical_questions`, `security_and_defense`.

**Pergunta:** O modelo de 5 representações deve ser mantido como está, adaptado, tornado configurável ou substituído?

**Alternativas:**

| Opção                                                                                                 | Mapeamento                                              | Prós                                    | Contras                                             |
| ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | --------------------------------------- | --------------------------------------------------- |
| **Manter as 5 como estão**                                                                            | POLITICA, ECONOMICA, GEOGRAFICA, CIENTIFICA, MILITAR    | Original, filosófico, multi-perspectiva | Terminologia pode confundir em contexto empresarial |
| **Adaptar para terminologia enterprise**                                                              | Compliance, Financeiro, Regional, Engenharia, Segurança | Familiar, adoção facilitada             | Perde a originalidade e profundidade filosófica     |
| **Configurável** — N representações definidas pelo usuário com pesos e domínios de veto customizáveis | Qualquer                                                | Máxima flexibilidade                    | Complexo de configurar, risco de misconfiguration   |
| **Substituir por RACI/Stewardship** — Data Owner, Data Steward, Data Consumer, Data Architect         | Padrão DAMA                                             | Padrão de mercado, simples              | Perde votação ponderada, menos democrático          |

**Baseline RADaC:** Enum hardcoded em `representation.py`:

```python
class Representation(str, Enum):
    POLITICA = "politica"
    ECONOMICA = "economica"
    GEOGRAFICA = "geografica"
    CIENTIFICA = "cientifica"
    MILITAR = "militar"
```

**Sub-perguntas:**

1. O modelo deve ser fixo (opinionated) ou configurável?
1. Se configurável, qual é o número mínimo e máximo de representações?
1. Os pesos de votação por tipo de decisão devem ser mantidos?

**Dependências:** ADR-010

______________________________________________________________________

### ADR-014: Mecânica de Veto e Escalonamento

<!-- metadata:
  id: ADR-014
  domain: governance
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "Veto por domínio, override com 80% supermaioria, escalonamento para COSMOS"
  references: ["EU AI Act Art. 14", "NIST AI RMF GOVERN function"]
-->

**Contexto:** O sistema de veto é poderoso: cada representação pode vetar decisões em seu domínio, mas o veto pode ser sobrescrito por 80% de supermaioria das representações não-vetantes. Se não resolvido, escala para COSMOS (federação). Porém: em produção, COSMOS pode não ter peers externos; vetos sem time-bound podem bloquear decisões críticas.

**Pergunta:** A mecânica de veto e escalonamento precisa de ajustes?

**Sub-perguntas:**

1. **Time-bound:** O veto deve ter prazo de expiração? (Ex: veto em decisão EMERGENCIAL expira em 1h se não houver override)
1. **Circuit breaker:** Deve haver um mecanismo de emergência que permite bypass total em situações de crise? (Ex: incidente de segurança em produção)
1. **Compliance override:** Um papel de "Compliance Officer" deve poder sobrescrever qualquer decisão por razões regulatórias (LGPD, EU AI Act)?
1. **Escalonamento quando COSMOS não tem peers:** O que acontece quando o nível COSMOS não tem federação configurada?

**Baseline RADaC:** Validação por domínio via `can_veto()`, override com 80% supermaioria em `calculate_result()`, escalation para COSMOS em `DecisionStatus.ESCALATED`. Tudo em `representation.py`.

**Dependências:** ADR-010, ADR-013

______________________________________________________________________

## Seção 3: Arquitetura de Dados `P0`

### ADR-020: Padrão Core de Arquitetura de Dados

<!-- metadata:
  id: ADR-020
  domain: data_architecture
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "Lakehouse puro com camadas Bronze/Silver/Gold"
  references: ["Data Lakehouse - Databricks", "Data Mesh - Zhamak Dehghani", "Data Fabric - Gartner"]
-->

**Contexto:** Três padrões dominam 2025-2026. O mais forte combina todos. O RADaC implementa Lakehouse puro (Bronze/Silver/Gold no S3 + Iceberg). Data Mesh adiciona ownership por domínios. Data Fabric adiciona automação via metadados ativos (active metadata).

**Pergunta:** Qual padrão de arquitetura de dados o OpenDataGov deve implementar?

**Alternativas:**

| Opção                                                                      | Prós                                              | Contras                                           | Fit                   |
| -------------------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------- | --------------------- |
| **Lakehouse puro** (Bronze/Silver/Gold)                                    | Simples, bem entendido, infra do RADaC já suporta | Sem ownership federado, sem automação inteligente | Médio                 |
| **Lakehouse + Mesh** — adiciona domínios de dados com ownership federado   | Ownership claro, escala organizacionalmente       | Requer mudança cultural, mais complexo            | Alto                  |
| **Lakehouse + Fabric** — adiciona camada de metadados ativos com automação | Automação, auto-classificação, self-service       | Complexo de implementar automação real            | Alto                  |
| **Lakehouse + Mesh + Fabric** — combinação completa                        | Proposta de valor máxima, "best of all worlds"    | Complexidade máxima, risco de over-engineering    | Alto se ADR-001 = (b) |

**Baseline RADaC:** Lakehouse com 3 buckets S3 (raw/staging/curated) mapeados para Bronze/Silver/Gold. Trino como engine de query, Spark para batch, Iceberg como table format. Arquitetura em `.radac/docs/ARCHITECTURE.en.md`.

**Referências:**

- Lakehouse: Armbrust et al., "Lakehouse: A New Generation of Open Platforms" (CIDR 2021)
- Data Mesh: Dehghani, "Data Mesh" (O'Reilly, 2022) — 4 princípios: domain ownership, data as a product, self-serve platform, federated computational governance
- Data Fabric: Gartner — automation layer driven by active metadata

**Dependências:** ADR-001

______________________________________________________________________

### ADR-021: Formato de Tabela Padrão

<!-- metadata:
  id: ADR-021
  domain: data_architecture
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "Iceberg (default) com Delta Lake para CDC intensivo"
  references: ["Apache Iceberg", "Delta Lake 4.0", "Apache Hudi", "UniForm/XTable"]
-->

**Contexto:** Open table formats são a base do lakehouse moderno. A interoperabilidade entre formatos está melhorando com UniForm (Delta → Iceberg) e XTable (multi-format).

**Pergunta:** O OpenDataGov deve padronizar em um formato ou suportar múltiplos?

**Alternativas:**

| Opção                                             | Prós                                                                               | Contras                                     | Fit                       |
| ------------------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------- | ------------------------- |
| **Apache Iceberg only**                           | Melhor suporte Trino, schema evolution robusto, partition evolution, time travel   | Ecossistema Spark/Databricks favorece Delta | Alto (alinhado com RADaC) |
| **Delta Lake only**                               | Dominant em Spark/Databricks, Liquid Clustering (Delta 4.0), melhores CDC patterns | Suporte Trino inferior, vendor-leaning      | Médio                     |
| **Multi-format (Iceberg + Delta)**                | Flexibilidade, UniForm bridge interop                                              | Dois padrões para manter, confusão          | Médio                     |
| **Iceberg default + UniForm/XTable para interop** | Best of both, conversão automática                                                 | Complexidade adicional, interop pode falhar | Alto                      |

**Baseline RADaC:** "Iceberg: Default for new datasets (better Trino support); Delta Lake: For specific cases (intensive CDC, Databricks integration)". Documentado em `.radac/docs/ARCHITECTURE.en.md`.

**Dependências:** ADR-020

______________________________________________________________________

### ADR-022: Camada de Armazenamento

<!-- metadata:
  id: ADR-022
  domain: data_architecture
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "S3 nativo (AWS) com MinIO para testes locais"
  references: ["S3 API", "MinIO", "GCS", "Azure Blob"]
-->

**Contexto:** Object storage é a fundação, mas a camada de abstração importa para portabilidade multi-cloud.

**Pergunta:** Como abstrair armazenamento para portabilidade?

**Alternativas:**

| Opção                                                                     | Prós                                                  | Contras                                         | Fit                 |
| ------------------------------------------------------------------------- | ----------------------------------------------------- | ----------------------------------------------- | ------------------- |
| **S3 nativo (AWS)**                                                       | Performance máxima, integração nativa, menor latência | Lock-in AWS                                     | Médio               |
| **MinIO everywhere** — mesmo em produção                                  | S3-compatível, auto-hospedado, sem cloud lock-in      | Overhead operacional, sem SLA de cloud provider | Alto se self-hosted |
| **Abstração via Iceberg catalogs** — Iceberg REST catalog abstrai storage | Transparente, muda storage sem mudar queries          | Depende de suporte do catalog                   | Alto                |
| **Multi-cloud com abstração** — interface unificada sobre S3/GCS/Blob     | Máxima portabilidade                                  | Performance pode variar, complexidade           | Médio               |

**Baseline RADaC:** S3 em produção (Terraform module `.radac/terraform/modules/s3/`), MinIO para local testing (`.radac/local-testing/manifests/minio.yaml`). Claims "95% portable" entre clouds.

**Dependências:** ADR-020

______________________________________________________________________

### ADR-023: Arquitetura de Temperatura de Dados

<!-- metadata:
  id: ADR-023
  domain: data_architecture
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "Diagrama mermaid lista 11 datastores; deploy real tem apenas PostgreSQL, Redis e MinIO"
  references: ["Hot/Warm/Cold storage patterns"]
-->

**Contexto:** O diagrama `swarm_architecture.mermaid` define 3 camadas de temperatura com 11 tecnologias: **HOT** (\<10ms): Redis, Memcached, DragonflyDB; **WARM** (10-100ms): PostgreSQL, YugabyteDB, FerretDB, ScyllaDB, Qdrant, Apache AGE, TimescaleDB; **COLD** (100ms-1s): MinIO. Porém o deploy real (Helm/K8s) só inclui PostgreSQL, Redis e MinIO. Há uma lacuna significativa entre visão e implementação.

**Pergunta:** Quantos datastores o OpenDataGov deve realmente implantar?

**Alternativas:**

| Opção                   | Datastores                                                                          | Prós                                                  | Contras                                                            |
| ----------------------- | ----------------------------------------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------ |
| **Mínimo viável**       | PostgreSQL + Redis + MinIO (3)                                                      | Simples, barato, suficiente para começar              | Sem vector DB, sem time-series, sem graph                          |
| **Pragmático**          | PostgreSQL + Redis + MinIO + Qdrant + TimescaleDB (5)                               | Cobre vector search (IA) e time-series (IoT/métricas) | Mais operacional                                                   |
| **Completo por camada** | HOT: Redis; WARM: PostgreSQL + Qdrant + TimescaleDB; COLD: MinIO (5 sem duplicação) | Cada tipo de workload tem engine otimizada            | 5 bancos para operar                                               |
| **Visão completa (11)** | Todos do diagrama                                                                   | Máximo desempenho teórico                             | Irreal para maioria dos contextos, custo operacional insustentável |

**Sub-perguntas:**

1. O vector DB (Qdrant) é necessário desde o início ou pode ser adicionado quando o RAG for ativado?
1. TimescaleDB é necessário ou extensões de time-series do PostgreSQL bastam?
1. Algum cenário real justifica ScyllaDB, YugabyteDB ou FerretDB no MVP?

**Baseline RADaC:** `.radac/swarm_architecture.mermaid` mostra 11; `.radac/helm-charts/` e `.radac/local-testing/` implantam 3.

**Dependências:** ADR-020, ADR-030

______________________________________________________________________

### ADR-024: Design do Medallion Architecture

<!-- metadata:
  id: ADR-024
  domain: data_architecture
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "3 buckets S3: raw (Bronze), staging (Silver), curated (Gold)"
  references: ["Medallion Architecture - Databricks", "Data Quality Gates"]
-->

**Contexto:** O padrão Bronze/Silver/Gold é standard, mas os contratos entre camadas precisam ser definidos: o que qualifica uma promoção? Quem aprova? Que quality gates existem?

**Pergunta:** Como definir as transições entre camadas e os quality gates?

**Sub-perguntas:**

1. **Regras de transição Bronze → Silver:**

   - Deduplicação obrigatória?
   - Schema validation contra data contract?
   - Quem aprova promoção? (automático por DQ score? governança via votação?)

1. **Regras de transição Silver → Gold:**

   - Exige cobertura mínima de testes de qualidade?
   - Exige documentação no catálogo?
   - Exige SLA definido?

1. **Ownership por camada:**

   - Data Engineers ownam Bronze?
   - Analytics Engineers ownam Silver?
   - Data Product Owners ownam Gold?

1. **Camada adicional (Platinum/Diamond):**

   - Deve existir uma camada de feature store para ML?
   - Dados "blessed" para treinamento de modelos?

**Baseline RADaC:** 3 buckets S3 (`raw-data`, `staging-data`, `curated-data`). Sem quality gates formais, sem ownership definido, sem data contracts entre camadas.

**Dependências:** ADR-020, ADR-050, ADR-051

______________________________________________________________________

## Seção 4: Arquitetura AI/ML `P0`

### ADR-030: B-Swarm vs. MLOps Padrão vs. Híbrido

<!-- metadata:
  id: ADR-030
  domain: ai_ml
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "Full B-Swarm com 6 experts (NLP, RAG, Code, Vision, Data, IoT)"
  references: ["MLflow 3", "Kubeflow", "MLOps in 2026"]
-->

**Contexto:** O B-Swarm é uma arquitetura original com 6 experts especializados, governança social e federação. O padrão da indústria é MLOps com registros de modelos, tracking de experimentos e serving. Estas não são mutuamente exclusivas.

**Pergunta:** Qual arquitetura de IA/ML o OpenDataGov deve adotar?

**Alternativas:**

| Opção                                                                                                                                                              | Prós                                                 | Contras                                               | Fit                   |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------- | ----------------------------------------------------- | --------------------- |
| **B-Swarm puro** — 6 experts com governança social                                                                                                                 | Diferenciação, multi-expert, governança integrada    | Sem model registry, sem experiment tracking, complexo | Alto se ADR-001 = (c) |
| **MLOps padrão** — MLflow + Kubeflow + serving framework                                                                                                           | Padrão de mercado, tooling maduro, comunidade grande | Sem governança sofisticada, "commodity"               | Médio                 |
| **Híbrido: B-Swarm como camada de governança sobre MLOps** — B-Swarm gerencia decisões de deploy, acesso e compliance; MLflow/Kubeflow gerenciam lifecycle técnico | Best of both: governança + operações                 | Dois sistemas para integrar                           | Alto                  |
| **Modular** — cada componente é plugável (registry, serving, governance)                                                                                           | Máxima flexibilidade, sem lock-in em ferramentas     | Complexidade de integração                            | Médio                 |

**Baseline RADaC:** 6 experts em `.radac/b-swarm/src/experts/`: NLP (vLLM + LLaMA 3.2), RAG (Sentence-Transformers → Qdrant), Code (vLLM + CodeLlama), Vision (TorchVision), Data (Trino + Spark), IoT (TimescaleDB).

**Dependências:** ADR-001, ADR-010

______________________________________________________________________

### ADR-031: Inferência LLM — Backend e Roteamento

<!-- metadata:
  id: ADR-031
  domain: ai_ml
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "vLLM para NLP e Code experts"
  references: ["vLLM", "TGI", "Ollama", "LiteLLM", "llama.cpp"]
-->

**Contexto:** O cenário de inferência de LLMs muda rapidamente. vLLM é a escolha do RADaC, mas alternativas existem para diferentes trade-offs de performance, custo e simplicidade.

**Pergunta:** Como padronizar inferência de LLM?

**Alternativas:**

| Opção                                                                                                                     | Prós                                                              | Contras                                                              | Fit                       |
| ------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | -------------------------------------------------------------------- | ------------------------- |
| **vLLM direto**                                                                                                           | Alta performance, PagedAttention, continuous batching             | Precisa de GPU, sem abstração de provider                            | Alto para self-hosted GPU |
| **Gateway/Router (LiteLLM)** — camada de abstração sobre múltiplos backends                                               | Troca de backend transparente, pode usar cloud APIs como fallback | Overhead de proxy, mais um serviço                                   | Alto para flexibilidade   |
| **Multi-backend nativo** — cada expert escolhe seu backend                                                                | Otimização por workload                                           | Complexidade operacional, N deployments diferentes                   | Médio                     |
| **Cloud API first + self-hosted fallback** — usa APIs comerciais (OpenAI, Anthropic, etc.) com vLLM como fallback on-prem | Custo variável, sem GPU necessária inicialmente                   | Latência variável, dependência de terceiros, dados saem do perímetro | Médio                     |

**Sub-perguntas:**

1. O OpenDataGov deve funcionar 100% air-gapped (sem dependência de APIs externas)?
1. GPUs são disponíveis no ambiente de deploy-alvo?
1. Deve haver um model router inteligente que escolhe o backend mais eficiente?

**Baseline RADaC:** vLLM referenciado para NLP (`meta-llama/Llama-3.2-8B-Instruct`) e Code (`codellama`).

**Dependências:** ADR-030

______________________________________________________________________

### ADR-032: Model Registry e Experiment Tracking

<!-- metadata:
  id: ADR-032
  domain: ai_ml
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "Inexistente — nomes de modelos hardcoded em Helm values"
  references: ["MLflow 3", "Weights & Biases", "Model Cards - Google"]
-->

**Contexto:** O RADaC não tem gestão de lifecycle de modelos. Em produção, isso significa: sem versionamento, sem rastreamento de experimentos, sem model cards, sem promoção governada.

**Pergunta:** Que solução de model registry e experiment tracking adotar?

**Alternativas:**

| Opção                                                                                            | Prós                                                                                  | Contras                                                    | Fit                    |
| ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ---------------------- |
| **MLflow**                                                                                       | Open-source de referência, tracking + registry + serving, MLflow 3 com GenAI features | Mais um serviço para operar, UI limitada                   | Alto                   |
| **Weights & Biases**                                                                             | Melhor UX, colaboração, bom para research                                             | Proprietário/SaaS, custo por seat                          | Baixo para open-source |
| **Custom via B-Swarm** — governance voting para promoção de modelos, audit trail para lifecycle  | Integrado com governança nativa                                                       | Mais código para manter, roda o risco de reinventar a roda | Médio                  |
| **MLflow + B-Swarm governance** — MLflow para tracking/registry, B-Swarm para governar promoções | Ferramentas maduras + governança sofisticada                                          | Integração a construir                                     | Alto                   |

**Baseline RADaC:** Nenhum registry. Modelos são strings em configuração Helm.

**Dependências:** ADR-030

______________________________________________________________________

### ADR-033: Vector Database e Arquitetura RAG

<!-- metadata:
  id: ADR-033
  domain: ai_ml
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "Qdrant + Sentence-Transformers"
  references: ["Qdrant", "pgvector", "Milvus", "Weaviate"]
-->

**Contexto:** RAG é implementado via Expert RAG com Qdrant para vetores e Sentence-Transformers para embeddings. A arquitetura precisa definir como knowledge bases são povoadas, indexadas e governadas.

**Pergunta:** Qual vector DB e como integrar RAG com o lakehouse?

**Alternativas:**

| Opção                              | Prós                                               | Contras                               | Fit                      |
| ---------------------------------- | -------------------------------------------------- | ------------------------------------- | ------------------------ |
| **Qdrant** (standalone)            | Alto desempenho, filtros avançados, Rust-native    | Mais um serviço para operar           | Alto                     |
| **pgvector** (extensão PostgreSQL) | Menos moving parts, reutiliza PostgreSQL existente | Performance inferior para >1M vetores | Alto se escala é pequena |
| **Milvus**                         | Escalável, suporte a GPU, cloud-native             | Complexo de operar, Java-based        | Médio                    |
| **Weaviate**                       | Busca híbrida (vetor + keyword), GraphQL API       | Menos maduro que Qdrant em produção   | Médio                    |

**Sub-perguntas:**

1. Como a pipeline de indexação RAG se integra com o lakehouse? (Dados Gold → embedding → vector DB?)
1. A governança deve controlar quais documentos são indexados? (Votação para inclusão no knowledge base?)
1. O vector DB precisa persistir entre restarts ou pode ser reconstruído a partir do lakehouse?

**Baseline RADaC:** Qdrant em `.radac/b-swarm/src/services/embeddings.py`, Sentence-Transformers para gerar embeddings.

**Dependências:** ADR-023, ADR-030

______________________________________________________________________

### ADR-034: Extensibilidade dos Experts

<!-- metadata:
  id: ADR-034
  domain: ai_ml
  status: OPEN
  decided_value: null
  priority: P0
  radac_baseline: "Registro estático em ExpertRegistry._register_defaults()"
  references: ["Plugin architectures", "SPI pattern"]
-->

**Contexto:** O `BaseExpert` define uma interface abstrata limpa para experts. Mas o registro é estático — hardcoded no orchestrator. Para adoção em comunidade, terceiros precisam poder adicionar experts.

**Pergunta:** Como experts são descobertos, registrados e governados?

**Alternativas:**

| Opção                                                                                                            | Prós                                          | Contras                                                     | Fit                   |
| ---------------------------------------------------------------------------------------------------------------- | --------------------------------------------- | ----------------------------------------------------------- | --------------------- |
| **Estático (Helm config)**                                                                                       | Simples, previsível, seguro                   | Não extensível sem redeploy                                 | Baixo para comunidade |
| **Dinâmico (auto-discovery via K8s labels/annotations)**                                                         | Plug-and-play, deploy independente            | Risco de segurança (expert malicioso), complexo de governar | Médio                 |
| **Governado (requer votação para registrar novo expert)**                                                        | Seguro, alinhado com governança, transparente | Fricção para adicionar, lento                               | Alto                  |
| **Registry + approval flow** — registry central com workflow de aprovação (não necessariamente votação completa) | Equilíbrio entre segurança e agilidade        | Precisa de UI/API de gerenciamento                          | Alto                  |

**Baseline RADaC:** `ExpertRegistry._register_defaults()` registra 6 experts hardcoded no orchestrator `main.py`.

**Dependências:** ADR-030, ADR-010

______________________________________________________________________

## Seção 5: Metadados e Catálogo `P1`

### ADR-040: Plataforma de Catálogo de Dados

<!-- metadata:
  id: ADR-040
  domain: metadata
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "DataHub"
  references: ["DataHub", "OpenMetadata", "Apache Atlas", "Amundsen"]
-->

**Contexto:** O catálogo de dados é o coração da governança. Múltiplas opções open-source existem, cada uma com trade-offs de arquitetura.

**Pergunta:** Qual plataforma de catálogo usar?

**Alternativas:**

| Opção                  | Arquitetura              | Prós                                | Contras                                  | Fit                    |
| ---------------------- | ------------------------ | ----------------------------------- | ---------------------------------------- | ---------------------- |
| **DataHub**            | RDB + ES + Graph + Kafka | Event-driven, lineage graph, madura | Complexa de operar (muitas dependências) | Alto (já no RADaC)     |
| **OpenMetadata**       | RDB + ES (sem graph)     | Simples, API-first, DQ embutida     | Menos lineage graph, menos madura        | Alto para simplicidade |
| **Apache Atlas**       | JanusGraph + Solr        | Deep Hadoop integration             | Hadoop-centric, UI datada                | Baixo                  |
| **Custom via B-Swarm** | CRDTs + PostgreSQL       | Integrado, federável via COSMOS     | Reinventar a roda, enorme esforço        | Baixo                  |

**Baseline RADaC:** DataHub no namespace `serving`. Valores em `.radac/helm-values/datahub-values.yaml`.

**Dependências:** ADR-001, ADR-020

______________________________________________________________________

### ADR-041: Modelo e Schema de Metadados

<!-- metadata:
  id: ADR-041
  domain: metadata
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Sem modelo de metadados explícito além do que DataHub fornece"
  references: ["OpenLineage schema", "DataHub entity model", "Dublin Core"]
-->

**Contexto:** Um modelo unificado de metadados permite governança consistente. OpenLineage define padrão para lineage. DataHub e OpenMetadata têm seus próprios modelos de entidade.

**Pergunta:** O OpenDataGov deve definir seu próprio schema de metadados, adotar um padrão existente, ou usar uma camada de adaptação?

**Alternativas:**

| Opção                                                                               | Prós                                                    | Contras                                                  | Fit   |
| ----------------------------------------------------------------------------------- | ------------------------------------------------------- | -------------------------------------------------------- | ----- |
| **Adotar modelo do catálogo escolhido** (DataHub/OpenMetadata)                      | Sem esforço extra, suporte da comunidade                | Lock-in no catálogo, difícil migrar                      | Médio |
| **OpenLineage como base**                                                           | Padrão aberto, foco em lineage, extensível via facets   | Cobre lineage mas não governança/qualidade               | Médio |
| **Schema próprio do OpenDataGov**                                                   | Pode integrar governança B-Swarm, privacy layers, CRDTs | Enorme esforço, precisa de adoção                        | Baixo |
| **Adapter layer** — schema interno que mapeia para DataHub/OpenMetadata/OpenLineage | Portabilidade, flexibilidade                            | Overhead de mapeamento, pode perder features específicas | Alto  |

**Baseline RADaC:** B-Swarm tem modelos internos para governança (AuditEvent, Decision, Vote) mas sem integração com metadados de dados.

**Dependências:** ADR-040

______________________________________________________________________

### ADR-042: Active Metadata e Automação

<!-- metadata:
  id: ADR-042
  domain: metadata
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Inexistente"
  references: ["Data Fabric - Gartner", "Active Metadata Management"]
-->

**Contexto:** Data Fabric se diferencia de Data Mesh por usar "active metadata" — metadados que disparam ações automáticas (auto-classificação, auto-tagging, enforcement de políticas). O B-Swarm poderia ser a engine de automação.

**Pergunta:** O OpenDataGov deve implementar active metadata?

**Alternativas:**

| Opção                                                                                        | Prós                                   | Contras                                           | Fit   |
| -------------------------------------------------------------------------------------------- | -------------------------------------- | ------------------------------------------------- | ----- |
| **Não (metadata passiva)**                                                                   | Simples, previsível                    | Perde automação, mais trabalho manual             | Baixo |
| **Regras declarativas** — políticas YAML que disparam ações quando metadata muda             | Previsível, auditável, GitOps-friendly | Limitado a regras simples                         | Médio |
| **B-Swarm AI-driven** — experts de IA fazem auto-classificação, sugerem tags, detectam PII   | Inteligente, adaptativo, diferenciação | Confiança em IA para classificação, risco de erro | Alto  |
| **Híbrido** — regras para o previsível, IA para descoberta e sugestão (com aprovação humana) | Equilíbrio                             | Complexidade                                      | Alto  |

**Baseline RADaC:** Não há active metadata. DataHub fornece metadata passiva.

**Dependências:** ADR-040, ADR-030

______________________________________________________________________

## Seção 6: Qualidade de Dados `P1`

### ADR-050: Engine de Qualidade de Dados

<!-- metadata:
  id: ADR-050
  domain: data_quality
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Inexistente — sem framework de qualidade"
  references: ["Great Expectations", "Soda", "dbt tests", "Elementary"]
-->

**Contexto:** Qualidade de dados é uma capability core de governança. O RADaC não tem framework de DQ implementado, apesar da metodologia de auditoria descrever qualidade como meta.

**Pergunta:** Qual engine de qualidade adotar?

**Alternativas:**

| Opção                              | Prós                                                              | Contras                                        | Fit   |
| ---------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------- | ----- |
| **Great Expectations**             | De facto standard, declarativa, CI/CD-friendly, docs auto-geradas | Curva de aprendizado, overhead para setup      | Alto  |
| **Soda**                           | DQ-as-code, integrações nativas, Soda Cloud dashboard             | Parte é proprietária (Cloud), menos extensível | Médio |
| **dbt tests**                      | Já integrado se usar dbt, SQL-native                              | Limitado a SQL, sem observabilidade avançada   | Médio |
| **Elementary**                     | Observabilidade + DQ, integrado com dbt, anomaly detection        | Depende de dbt, menos standalone               | Médio |
| **Custom via B-Swarm Data Expert** | Integrado com governança, pode votar em exceções                  | Reinventar DQ é enorme esforço                 | Baixo |

**Baseline RADaC:** Nenhum framework de DQ. Metodologia de auditoria em `.radac/docs/AUDIT_METHODOLOGY.md` define metas de qualidade mas não prescreve ferramenta.

**Dependências:** ADR-020, ADR-024

______________________________________________________________________

### ADR-051: Data Contracts

<!-- metadata:
  id: ADR-051
  domain: data_quality
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Inexistente"
  references: ["DataContract Specification (GitHub)", "Data Contracts - Andrew Jones"]
-->

**Contexto:** Data contracts estão se tornando padrão em 2025-2026 para formalizar expectativas de schema, qualidade e SLA entre produtores e consumidores de dados. É o "contrato social" do data mesh.

**Pergunta:** O OpenDataGov deve implementar data contracts? Se sim, em que formato e com que enforcement?

**Alternativas:**

| Opção                                 | Formato                                   | Enforcement                                  | Fit   |
| ------------------------------------- | ----------------------------------------- | -------------------------------------------- | ----- |
| **Não implementar**                   | N/A                                       | N/A                                          | Baixo |
| **DataContract Specification (YAML)** | YAML padronizado da comunidade            | Validação em CI/CD, integração com DQ engine | Alto  |
| **Protobuf/Avro schema**              | Schema binário                            | Enforcement em Kafka (Schema Registry)       | Médio |
| **JSON Schema**                       | JSON                                      | Validação em API/ingestion layer             | Médio |
| **Custom integrado com governança**   | YAML + votação para aprovação de mudanças | B-Swarm governance para breaking changes     | Alto  |

**Sub-perguntas:**

1. Data contracts devem ser versionados no Git (GitOps)?
1. Breaking changes no contrato devem disparar processo de governança (ADR-012)?
1. Quem é responsável por definir o contrato — produtor, consumidor, ou ambos?

**Baseline RADaC:** Nenhum data contract. Schemas não são formalizados.

**Dependências:** ADR-020, ADR-050, ADR-012

______________________________________________________________________

### ADR-052: Dimensões de Qualidade e Framework de SLA

<!-- metadata:
  id: ADR-052
  domain: data_quality
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Metas da metodologia de auditoria: uptime >99%, incidentes <1/mês, detecção <5min"
  references: ["DAMA-DMBOK quality dimensions", "ISO 25012"]
-->

**Contexto:** DAMA-DMBOK define 6 dimensões de qualidade: Completude, Acurácia, Consistência, Atualidade, Unicidade, Validade. A ISO 25012 expande para 15. A metodologia de auditoria do RADaC define SLAs operacionais.

**Pergunta:** Quais dimensões de qualidade medir e como definir SLAs?

**Sub-perguntas:**

1. Todas as 6 dimensões DAMA são obrigatórias ou são opcionais por dataset?
1. SLAs devem ser definidos por dataset, por domínio, ou globais?
1. Violação de SLA deve disparar alertas, bloquear pipeline, ou iniciar processo de governança?
1. A metodologia de auditoria de 12 semanas deve ser a cadência de revisão de SLAs?

**Baseline RADaC:** Metas no AUDIT_METHODOLOGY.md: uptime \<90% → >99%, incidentes 10+/mês → \<1/mês, detecção horas → \<5min, novo pipeline 4 semanas → 2-5 dias.

**Dependências:** ADR-050, ADR-051

______________________________________________________________________

## Seção 7: Lineage e Observabilidade `P1`

### ADR-060: Padrão de Data Lineage

<!-- metadata:
  id: ADR-060
  domain: lineage
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "DataHub para lineage (sem OpenLineage)"
  references: ["OpenLineage", "DataHub lineage", "Marquez"]
-->

**Contexto:** Lineage end-to-end (source → transformation → dashboard) é crítico para confiança, debugging e compliance. OpenLineage é o padrão aberto emergente com integrações para Airflow, Spark, dbt, Flink.

**Pergunta:** Qual padrão de lineage adotar?

**Alternativas:**

| Opção                      | Prós                                                                 | Contras                                                        | Fit   |
| -------------------------- | -------------------------------------------------------------------- | -------------------------------------------------------------- | ----- |
| **OpenLineage**            | Padrão aberto, integrações Airflow/Spark/dbt, JSON Schema extensível | Precisa de backend (Marquez), maturity variável por integração | Alto  |
| **DataHub lineage nativa** | Já integrado se ADR-040 = DataHub                                    | Proprietário do DataHub, menos integrações                     | Médio |
| **OpenLineage → DataHub**  | Padrão aberto na coleta, DataHub como visualização                   | Dois sistemas, mas melhor dos dois mundos                      | Alto  |
| **Custom via audit chain** | Integrado com governança B-Swarm                                     | Reinventar lineage é enorme esforço                            | Baixo |

**Baseline RADaC:** DataHub listado para "Lineage" na documentação. Sem integração OpenLineage no código.

**Dependências:** ADR-040

______________________________________________________________________

### ADR-061: Arquitetura de Observabilidade

<!-- metadata:
  id: ADR-061
  domain: observability
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "VictoriaMetrics + Grafana + Jaeger + Alertmanager"
  references: ["OpenTelemetry", "VictoriaMetrics", "Grafana"]
-->

**Contexto:** A plataforma precisa de observabilidade em múltiplos níveis: infraestrutura (CPU, memória, rede), data pipelines (freshness, volume, schema), AI/ML (latência de inferência, drift), governança (decisões, votações, vetoes).

**Pergunta:** Um stack unificado ou ferramentas especializadas por domínio?

**Alternativas:**

| Opção                                                                                                | Prós                                              | Contras                                                            | Fit                |
| ---------------------------------------------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------ | ------------------ |
| **Stack unificado** (VictoriaMetrics + Grafana + Jaeger)                                             | Menos ferramentas, visão consolidada, já no RADaC | Data observability e AI observability têm necessidades específicas | Alto para início   |
| **Especializados por domínio** — VicMet para infra, Elementary/Monte Carlo para data, MLflow para AI | Best-of-breed por domínio                         | Múltiplas UIs, complexo                                            | Médio              |
| **Convergência via OTel** — OpenTelemetry como collector unificado → múltiplos backends              | Standard, vendor-neutral, futuro                  | Imaturidade para data observability                                | Alto a médio prazo |

**Baseline RADaC:** VictoriaMetrics (`.radac/helm-values/victoriametrics-values.yaml`), Grafana dashboards pré-configurados (`.radac/helm-charts/lakehouse-umbrella/dashboards/`), Jaeger para tracing (`.radac/b-swarm/kubernetes/observability/`), Alertmanager.

**Dependências:** ADR-020, ADR-030

______________________________________________________________________

### ADR-062: Integração OpenTelemetry

<!-- metadata:
  id: ADR-062
  domain: observability
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Jaeger direto para tracing, Prometheus-compatible para métricas"
  references: ["OpenTelemetry", "OTLP"]
-->

**Contexto:** OpenTelemetry é o padrão de facto para coleta de telemetria (traces, métricas, logs). O B-Swarm usa Jaeger diretamente e métricas Prometheus-compatible, mas sem OTel como camada de coleta.

**Pergunta:** O OpenDataGov deve mandatar OpenTelemetry como padrão de telemetria?

**Alternativas:**

| Opção                                          | Prós                                                 | Contras                                | Fit   |
| ---------------------------------------------- | ---------------------------------------------------- | -------------------------------------- | ----- |
| **Sim, OTel everywhere**                       | Padrão de mercado, vendor-neutral, unified collector | Migração necessária, overhead de agent | Alto  |
| **OTel para novos componentes, legacy mantém** | Migração gradual                                     | Dois padrões coexistindo               | Médio |
| **Não, manter Prometheus + Jaeger direto**     | Simples, já funciona                                 | Fragmentação, perde unificação         | Baixo |

**Baseline RADaC:** `b-swarm/src/observability/tracing.py` usa Jaeger diretamente. `b-swarm/src/observability/metrics.py` usa Prometheus-compatible.

**Dependências:** ADR-061

______________________________________________________________________

### ADR-063: Data Observability

<!-- metadata:
  id: ADR-063
  domain: observability
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Inexistente como conceito separado"
  references: ["Monte Carlo", "Elementary", "Data Observability Engines"]
-->

**Contexto:** Data observability (freshness, volume, schema changes, distribution drift) é distinto de observabilidade de infraestrutura. Detecta problemas de dados antes do impacto no negócio.

**Pergunta:** O OpenDataGov precisa de uma camada dedicada de data observability?

**Alternativas:**

| Opção                                                                                | Prós                                                          | Contras                                     | Fit   |
| ------------------------------------------------------------------------------------ | ------------------------------------------------------------- | ------------------------------------------- | ----- |
| **Integrado com DQ engine** (ADR-050)                                                | Menos ferramentas, DQ + observability juntos                  | Menos sofisticado que ferramentas dedicadas | Alto  |
| **Elementary** (open-source, dbt-native)                                             | Anomaly detection, dbt-integrated, dashboards                 | Depende de dbt                              | Médio |
| **Custom metrics via B-Swarm**                                                       | Data Expert monitora freshness, volume, drift automaticamente | Esforço de desenvolvimento                  | Médio |
| **Extensão do monitoring stack** — dashboards Grafana customizados para data metrics | Reutiliza stack existente                                     | Precisa instrumentar pipelines manualmente  | Médio |

**Baseline RADaC:** Grafana dashboards existem para infraestrutura; nenhum para data observability.

**Dependências:** ADR-050, ADR-061

______________________________________________________________________

## Seção 8: Privacidade e Segurança `P1`

### ADR-070: Arquitetura de Privacidade

<!-- metadata:
  id: ADR-070
  domain: privacy
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Differential privacy com OpenDP, epsilon por camada social"
  references: ["OpenDP", "LGPD", "GDPR", "Differential Privacy - Dwork & Roth"]
-->

**Contexto:** O B-Swarm implementa privacidade diferencial com epsilon por camada: COMUNIDADE=1.0, CLASSE=0.5, COSMOS=0.1. Mas privacidade em produção vai além de DP: mascaramento, tokenização, criptografia, gestão de consentimento, right to be forgotten (LGPD Art. 18).

**Pergunta:** DP é o mecanismo primário ou um componente de um toolkit mais amplo?

**Alternativas:**

| Opção                                | Mecanismos                                               | Prós                          | Contras                          | Fit                      |
| ------------------------------------ | -------------------------------------------------------- | ----------------------------- | -------------------------------- | ------------------------ |
| **DP-only**                          | Laplace, Gaussian, Exponential noise                     | Garantia matemática, inovador | Não cobre masking, RBAC, consent | Baixo isolado            |
| **Toolkit completo**                 | DP + masking + tokenization + encryption + consent mgmt  | Cobertura total               | Complexo                         | Alto                     |
| **DP + RBAC + masking** (pragmático) | DP para analytics, RBAC para acesso, masking para PII    | Equilíbrio                    | Sem consent management           | Alto                     |
| **Privacy-by-layer**                 | Cada camada social tem mecanismos diferentes de proteção | Alinhado com B-Swarm          | Complexo de implementar          | Alto se camadas mantidas |

**Baseline RADaC:** DP em `.radac/b-swarm/src/privacy/differential_privacy.py`. Mecanismos: Laplace, Gaussian. Funções: `privatize_count`, `privatize_sum`, `privatize_mean`, `privatize_histogram`. Budget tracking via `PrivacyBudget`. Epsilon por camada em `LAYER_EPSILON`.

**Dependências:** ADR-071, ADR-072

______________________________________________________________________

### ADR-071: Camadas Sociais — Manter, Mapear ou Substituir

<!-- metadata:
  id: ADR-071
  domain: privacy
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "5 camadas: PESSOAL, FAMILIA, COMUNIDADE, CLASSE, COSMOS"
  references: ["Data Classification Standards", "NIST SP 800-60"]
-->

**Contexto:** As 5 camadas sociais (PESSOAL → FAMILIA → COMUNIDADE → CLASSE → COSMOS) controlam acesso a dados com tipos progressivos (FULL → READ → AGGREGATED → ANONYMIZED → DIFFERENTIAL_PRIVACY → FEDERATED). Cada camada tem frequência de auditoria e quorum de governança próprios. Conceitualmente rico, mas pode não mapear para classificação enterprise padrão.

**Pergunta:** Manter, mapear ou substituir as camadas sociais?

**Alternativas:**

| Opção                                               | Camadas                                                | Fit                                 |
| --------------------------------------------------- | ------------------------------------------------------ | ----------------------------------- |
| **Manter as 5 originais**                           | PESSOAL, FAMILIA, COMUNIDADE, CLASSE, COSMOS           | Alto se público é técnico/acadêmico |
| **Mapear para enterprise**                          | Individual, Team, Department, Organization, Industry   | Alto para adoção corporativa        |
| **Mapear para classificação padrão**                | Public, Internal, Confidential, Restricted, Top Secret | Alto para governo/compliance        |
| **Configurável** — N camadas definidas pelo usuário | Qualquer                                               | Máxima flexibilidade, complexo      |

**Baseline RADaC:** Enum hardcoded em `layers.py`:

```python
class SocialLayer(str, Enum):
    PESSOAL = "pessoal"      # nível 0 (mais privado)
    FAMILIA = "familia"      # nível 1
    COMUNIDADE = "comunidade" # nível 2
    CLASSE = "classe"        # nível 3
    COSMOS = "cosmos"        # nível 4 (mais público)
```

Políticas de acesso por camada configuradas em `LAYER_CONFIGS`. Exemplo: COMUNIDADE pode acessar dados de CLASSE como ANONYMIZED.

**Dependências:** ADR-013

______________________________________________________________________

### ADR-072: Autenticação e Autorização

<!-- metadata:
  id: ADR-072
  domain: security
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "OIDC para IRSA (Terraform), RBAC mencionado mas access_control.py é mínimo"
  references: ["Keycloak", "Zitadel", "OIDC", "OPA"]
-->

**Contexto:** O RADaC menciona JWT, mTLS e RBAC mas não os implementa completamente. Em produção, identity é fundação.

**Pergunta:** Qual stack de identidade e autorização?

**Alternativas:**

| Opção                             | AuthN                  | AuthZ                 | Prós                        | Contras                   |
| --------------------------------- | ---------------------- | --------------------- | --------------------------- | ------------------------- |
| **Keycloak**                      | OIDC/SAML              | RBAC/UMA              | Standard enterprise, maduro | Java/pesado               |
| **Zitadel**                       | OIDC                   | RBAC                  | Cloud-native, Go, API-first | Menos maduro              |
| **Cloud-native**                  | IRSA/Workload Identity | IAM policies          | Nativo, sem overhead        | Cloud lock-in             |
| **OPA (Open Policy Agent) + IdP** | Qualquer IdP           | Policy-as-code (Rego) | Flexível, GitOps-friendly   | Curva de aprendizado Rego |

**Sub-perguntas:**

1. Multi-tenancy é necessário? (Se sim, Keycloak tem suporte nativo a realms)
1. As camadas sociais do B-Swarm devem ser mapeadas para RBAC roles?
1. Autorização fine-grained (row/column level) é necessária?

**Baseline RADaC:** OIDC provider no Terraform EKS (`.radac/terraform/modules/eks/main.tf`).

**Dependências:** ADR-002, ADR-071

______________________________________________________________________

### ADR-073: Estratégia de Criptografia

<!-- metadata:
  id: ADR-073
  domain: security
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Sem implementação explícita de criptografia"
  references: ["AWS KMS", "HashiCorp Vault", "SOPS"]
-->

**Contexto:** Criptografia at-rest e in-transit é baseline. A pergunta é sobre a implementação.

**Pergunta:** Como gerenciar criptografia e segredos?

**Sub-perguntas:**

1. **Key management:** KMS gerenciado (AWS KMS) vs. self-hosted (Vault)?
1. **Encryption at rest:** Server-side (S3 SSE) vs. client-side (CSEK)?
1. **Secret management:** K8s Secrets + Sealed Secrets vs. Vault vs. SOPS?
1. **mTLS entre serviços:** Service mesh (Istio/Linkerd) vs. aplicação?

**Dependências:** ADR-080

______________________________________________________________________

### ADR-074: Soberania e Residência de Dados

<!-- metadata:
  id: ADR-074
  domain: security
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Representação GEOGRAFICA e COSMOS federation implicam awareness jurisdicional"
  references: ["LGPD", "GDPR", "Data Sovereignty"]
-->

**Contexto:** A representação GEOGRAFICA e a federação COSMOS implicam consciência multi-jurisdicional. LGPD e GDPR têm requisitos de residência de dados.

**Pergunta:** O OpenDataGov precisa de awareness jurisdicional built-in?

**Sub-perguntas:**

1. Dados podem cruzar fronteiras jurisdicionais via COSMOS?
1. A representação GEOGRAFICA deve controlar residência de dados?
1. Precisa de suporte a data localization (dados de BR ficam em BR)?

**Dependências:** ADR-013, ADR-010

______________________________________________________________________

## Seção 9: Infraestrutura e Deploy `P1`

### ADR-080: Distribuição Kubernetes

<!-- metadata:
  id: ADR-080
  domain: infrastructure
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "EKS (AWS) com Kind para testes locais"
  references: ["EKS", "GKE", "AKS", "OpenShift", "K3s"]
-->

**Contexto:** O RADaC é testado em EKS/Kind. Mas "OpenDataGov" (dados abertos + governo) pode precisar rodar em ambientes variados.

**Pergunta:** Em quais distribuições K8s o OpenDataGov deve ser testado e suportado?

**Alternativas:**

| Opção                     | Distributions                                  | Prós                            | Contras                    |
| ------------------------- | ---------------------------------------------- | ------------------------------- | -------------------------- |
| **EKS-only**              | AWS EKS                                        | Foco, menor superfície de teste | Lock-in                    |
| **Big 3 clouds**          | EKS, GKE, AKS                                  | Multi-cloud, mercado amplo      | 3x teste, CI/CD complexo   |
| **CNCF-certified + edge** | EKS, GKE, AKS, OpenShift, K3s                  | Máxima portabilidade            | Enorme superfície de teste |
| **Cloud-agnostic focus**  | Kind/K3s como referência, clouds como extensão | Portabilidade by design         | Performance pode variar    |

**Baseline RADaC:** EKS Terraform em `.radac/terraform/modules/eks/`. Kind config em `.radac/local-testing/kind-config.yaml`.

**Dependências:** ADR-002

______________________________________________________________________

### ADR-081: Estratégia de Infrastructure as Code

<!-- metadata:
  id: ADR-081
  domain: infrastructure
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Terraform + Helm"
  references: ["Terraform", "Pulumi", "Crossplane", "Helm"]
-->

**Contexto:** Terraform (IaC para cloud) + Helm (K8s packaging) é o par do RADaC. Alternativas emergentes: Crossplane (K8s-native IaC), Pulumi (IaC em linguagens de programação).

**Pergunta:** Manter Terraform + Helm ou evoluir?

**Alternativas:**

| Opção                 | Prós                                      | Contras                                           | Fit   |
| --------------------- | ----------------------------------------- | ------------------------------------------------- | ----- |
| **Terraform + Helm**  | Maduro, ampla comunidade, já implementado | HCL vs. linguagem real, state management          | Alto  |
| **Crossplane + Helm** | K8s-native, declarativo, GitOps-native    | Menos maduro, curva de aprendizado                | Médio |
| **Pulumi + Helm**     | IaC em Python/Go/TS, type-safe            | Menos adoção enterprise, vendor lock-in potencial | Médio |
| **OpenTofu + Helm**   | Fork open-source do Terraform (pós-BSL)   | Fragmentação de ecossistema                       | Médio |

**Baseline RADaC:** Terraform em `.radac/terraform/` (modules: vpc, eks, s3, iam, rds). Helm em `.radac/helm-charts/`.

**Dependências:** ADR-080

______________________________________________________________________

### ADR-082: GitOps e Modelo de Deploy

<!-- metadata:
  id: ADR-082
  domain: infrastructure
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Sem GitOps — deploy via helm install manual"
  references: ["ArgoCD", "Flux"]
-->

**Contexto:** GitOps é o padrão moderno para deploy contínuo em K8s. O RADaC usa `helm install` manual. Interessante: GitOps + governance voting poderiam se integrar (deploy requer aprovação via votação).

**Pergunta:** Adotar GitOps? Integrar com governança?

**Alternativas:**

| Opção                           | Prós                                               | Contras                               | Fit                           |
| ------------------------------- | -------------------------------------------------- | ------------------------------------- | ----------------------------- |
| **ArgoCD**                      | Mais popular, UI rica, multi-cluster               | Mais um componente, pode ser complexo | Alto                          |
| **Flux**                        | Mais leve, CNCF incubating, better GitOps purity   | Menos UI, curva de aprendizado        | Médio                         |
| **Sem GitOps (manual)**         | Simples                                            | Não escala, sem auditoria de deploy   | Baixo                         |
| **ArgoCD + B-Swarm governance** | Deploy governado, votação para production releases | Integração complexa                   | Alto se ADR-012 inclui deploy |

**Baseline RADaC:** Manual via `helm install` em scripts (`.radac/scripts/setup-cluster.sh`).

**Dependências:** ADR-012

______________________________________________________________________

### ADR-083: Estratégia de Scaling

<!-- metadata:
  id: ADR-083
  domain: infrastructure
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Karpenter com Spot Instances"
  references: ["Karpenter", "KEDA", "Cluster Autoscaler"]
-->

**Contexto:** Workloads de dados (Spark/Trino) e IA (vLLM) têm padrões de scaling diferentes. Dados são batch-heavy; IA é latency-sensitive.

**Pergunta:** Uma estratégia de scaling ou estratégias especializadas?

**Alternativas:**

| Opção                                       | Prós                                              | Contras                         | Fit           |
| ------------------------------------------- | ------------------------------------------------- | ------------------------------- | ------------- |
| **Karpenter para tudo**                     | Simples, AWS-optimized, Spot-aware                | AWS-only                        | Alto para AWS |
| **Karpenter (infra) + KEDA (event-driven)** | Escala baseada em métricas/eventos para pipelines | Dois sistemas                   | Alto          |
| **Cluster Autoscaler (cloud-agnostic)**     | Multi-cloud, standard                             | Menos sofisticado que Karpenter | Médio         |

**Baseline RADaC:** Karpenter provisioners em `.radac/kubernetes/compute/karpenter-provisioners.yaml`. 4 node pools: system (on-demand), compute/kafka/trino (spot).

**Dependências:** ADR-080

______________________________________________________________________

### ADR-084: Experiência de Desenvolvimento Local

<!-- metadata:
  id: ADR-084
  domain: infrastructure
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Kind cluster com MinIO, PostgreSQL, Hive Metastore"
  references: ["Kind", "Docker Compose", "Tilt", "Skaffold"]
-->

**Contexto:** Dev experience é crítico para adoção. O RADaC tem setup local via Kind.

**Pergunta:** Qual experiência de desenvolvimento local oferecer?

**Alternativas:**

| Opção                                                                 | Prós                                | Contras                    | Fit                  |
| --------------------------------------------------------------------- | ----------------------------------- | -------------------------- | -------------------- |
| **Kind + scripts** (atual)                                            | Simula K8s real, testa Helm         | Pesado, lento para iniciar | Médio                |
| **Docker Compose (lightweight)**                                      | Rápido, simples, sem K8s necessário | Não testa Helm/K8s configs | Alto para onboarding |
| **Tilt + Kind**                                                       | Hot-reload, dev workflow otimizado  | Mais uma ferramenta        | Alto para devs       |
| **Múltiplos modos** — Docker Compose (quick start) + Kind (full test) | Cada perfil escolhe                 | Mais para manter           | Alto                 |

**Baseline RADaC:** Kind em `.radac/local-testing/`. Scripts de setup, validate, test, cleanup.

**Dependências:** ADR-080

______________________________________________________________________

## Seção 10: API e Integração `P2`

### ADR-090: Estilo de API

<!-- metadata:
  id: ADR-090
  domain: api
  status: OPEN
  decided_value: null
  priority: P2
  radac_baseline: "REST via FastAPI"
  references: ["REST", "gRPC", "GraphQL", "FastAPI"]
-->

**Contexto:** B-Swarm usa REST via FastAPI. Plataformas de dados modernas frequentemente usam gRPC internamente e REST/GraphQL externamente.

**Pergunta:** Qual estilo de API padronizar?

**Alternativas:**

| Opção                               | Uso                                     | Prós                                     | Contras                                              |
| ----------------------------------- | --------------------------------------- | ---------------------------------------- | ---------------------------------------------------- |
| **REST only (FastAPI)**             | Tudo                                    | Simples, universal                       | Sem streaming eficiente, over-fetching para metadata |
| **REST (externo) + gRPC (interno)** | REST para clientes, gRPC entre serviços | Performance interna, usabilidade externa | Dois padrões                                         |
| **GraphQL para metadata**           | Queries flexíveis de catálogo/lineage   | Evita over-fetching, auto-documentado    | Complexidade server-side                             |
| **REST + GraphQL + gRPC**           | Cada para seu melhor use case           | Best-of-breed                            | 3 padrões para manter                                |

**Baseline RADaC:** FastAPI em `.radac/b-swarm/src/orchestrator/main.py`.

**Dependências:** ADR-001

______________________________________________________________________

### ADR-091: Arquitetura de Eventos

<!-- metadata:
  id: ADR-091
  domain: api
  status: OPEN
  decided_value: null
  priority: P2
  radac_baseline: "Kafka via Strimzi KRaft para streaming de dados; diagrama mermaid mostra NATS e RabbitMQ mas não implementados"
  references: ["Apache Kafka", "NATS", "RabbitMQ"]
-->

**Contexto:** Kafka é o backbone para data streaming. Mas para comunicação leve entre serviços (governança, notificações), Kafka pode ser overkill.

**Pergunta:** Backbone de eventos unificado ou especializado?

**Alternativas:**

| Opção                                    | Prós                       | Contras                                        | Fit   |
| ---------------------------------------- | -------------------------- | ---------------------------------------------- | ----- |
| **Kafka para tudo**                      | Um sistema, simplifica ops | Overkill para mensagens leves, latência > NATS | Médio |
| **Kafka (dados) + NATS (serviços)**      | Cada um no que faz melhor  | Dois sistemas                                  | Alto  |
| **Kafka (dados) + Redis Streams (leve)** | Redis já está no stack     | Redis Streams menos robusto                    | Médio |

**Baseline RADaC:** Kafka Strimzi KRaft em `.radac/helm-values/strimzi-kafka-kraft.yaml`. NATS e RabbitMQ no diagrama mermaid mas sem implementação.

**Dependências:** ADR-020

______________________________________________________________________

### ADR-092: Protocolo de Federação COSMOS

<!-- metadata:
  id: ADR-092
  domain: api
  status: OPEN
  decided_value: null
  priority: P2
  radac_baseline: "Mock HTTP backend; design menciona libp2p"
  references: ["libp2p", "Matrix Protocol", "NATS"]
-->

**Contexto:** COSMOS Federation é a camada de coordenação global — permite que instâncias diferentes do OpenDataGov sincronizem estado via CRDTs. Atualmente é mock com HTTP.

**Pergunta:** Qual protocolo de comunicação para federação?

**Alternativas:**

| Opção               | Prós                                              | Contras                                               | Fit              |
| ------------------- | ------------------------------------------------- | ----------------------------------------------------- | ---------------- |
| **HTTP/gRPC**       | Simples, firewall-friendly, familiar              | Centralizado (precisa de DNS/discovery), não true P2P | Alto para início |
| **libp2p**          | True P2P, NAT traversal, usado por IPFS/Filecoin  | Complexo, biblioteca imatura em Python                | Médio            |
| **Matrix protocol** | Decentralizado, E2E encryption, bom para governos | Overhead, protocolo pesado                            | Médio            |
| **NATS mesh**       | Leve, mesh nativo, cloud-native                   | Menos features P2P que libp2p                         | Médio            |

**Baseline RADaC:** Mock HTTP em `.radac/b-swarm/src/cosmos/federation.py`. CRDTs implementados em `.radac/b-swarm/src/cosmos/crdt.py` (GCounter, PNCounter, LWWRegister, ORSet).

**Dependências:** ADR-010, ADR-074

______________________________________________________________________

### ADR-093: SDK e Client Libraries

<!-- metadata:
  id: ADR-093
  domain: api
  status: OPEN
  decided_value: null
  priority: P2
  radac_baseline: "Sem SDK — apenas API REST"
  references: []
-->

**Contexto:** Para adoção, a plataforma precisa de interfaces além da API REST raw.

**Pergunta:** Quais client libraries oferecer?

**Alternativas (multi-select):**

| Opção                         | Público                      | Prioridade |
| ----------------------------- | ---------------------------- | ---------- |
| **Python SDK**                | Data engineers, ML engineers | Alta       |
| **CLI tool**                  | DevOps, SREs                 | Alta       |
| **Terraform provider**        | Infrastructure teams         | Média      |
| **JavaScript/TypeScript SDK** | Frontend developers          | Baixa      |

**Dependências:** ADR-090

______________________________________________________________________

## Seção 11: Experiência do Usuário `P2`

### ADR-100: Interface Primária

<!-- metadata:
  id: ADR-100
  domain: ux
  status: OPEN
  decided_value: null
  priority: P2
  radac_baseline: "Sem UI customizada — usa Superset (BI), DataHub (catálogo), Grafana (monitoring)"
  references: []
-->

**Contexto:** O RADaC não tem UI própria — reutiliza UIs de ferramentas existentes. Uma plataforma de governança pode precisar de portal unificado.

**Pergunta:** Construir UI customizada ou ser API-first?

**Alternativas:**

| Opção                                  | Prós                             | Contras                                       | Fit                   |
| -------------------------------------- | -------------------------------- | --------------------------------------------- | --------------------- |
| **API-first (sem UI)**                 | Foco no core, menos manutenção   | Barreira de entrada alta, sem "wow factor"    | Alto para developers  |
| **Portal customizado (React/Next.js)** | UX unificada, branding           | Grande investimento em frontend               | Alto se ADR-001 = (b) |
| **Estender UI do catálogo**            | Reutiliza investimento existente | Limitado ao que a ferramenta permite          | Médio                 |
| **Dashboard Grafana customizado**      | Já existe infra, baixo custo     | Grafana não é ideal para governança workflows | Baixo                 |

**Baseline RADaC:** Superset, DataHub, Grafana como UIs.

**Dependências:** ADR-001, ADR-040

______________________________________________________________________

### ADR-101: Dashboard de Governança

<!-- metadata:
  id: ADR-101
  domain: ux
  status: OPEN
  decided_value: null
  priority: P2
  radac_baseline: "Inexistente"
  references: []
-->

**Contexto:** O sistema de votação, audit trail e camadas sociais precisam de visualização para serem úteis.

**Pergunta:** Quais métricas e views de governança expor?

**Sub-perguntas:**

1. Histórico de decisões com status e votos?
1. Padrões de votação por representação?
1. Consumo de privacy budget por camada?
1. Explorador de lineage integrado com governança?
1. Timeline de audit trail?

**Dependências:** ADR-100

______________________________________________________________________

### ADR-102: Portal Self-Service de Dados

<!-- metadata:
  id: ADR-102
  domain: ux
  status: OPEN
  decided_value: null
  priority: P2
  radac_baseline: "Meta da metodologia: reduzir 'time to pipeline' de 4 semanas para 2-5 dias"
  references: ["Data Mesh self-serve platform"]
-->

**Contexto:** A metodologia de auditoria define como meta Q4 a redução de time-to-pipeline de 4 semanas para 2-5 dias. Self-service é chave.

**Pergunta:** O OpenDataGov deve oferecer portal self-service para consumidores de dados?

**Sub-perguntas:**

1. Discovery: busca de datasets com relevância?
1. Access request: workflow de solicitação de acesso governado?
1. Pipeline creation: interface visual para criar pipelines simples?
1. Data preview: prévia de dados com privacy controls aplicados?

**Dependências:** ADR-100, ADR-012

______________________________________________________________________

## Seção 12: Compliance e Regulatório `P1`

### ADR-110: Mapeamento de Frameworks Regulatórios

<!-- metadata:
  id: ADR-110
  domain: compliance
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Sem mapeamento explícito"
  references: ["EU AI Act", "NIST AI RMF 2.0", "LGPD", "GDPR", "ISO/IEC 42001"]
-->

**Contexto:** Múltiplos frameworks regulatórios se aplicam. O OpenDataGov pode ser diferenciado por compliance built-in.

**Pergunta:** Quais frameworks regulatórios suportar explicitamente?

**Alternativas (multi-select):**

| Framework           | Escopo                             | Obrigatório? |
| ------------------- | ---------------------------------- | ------------ |
| **LGPD**            | Dados pessoais (Brasil)            | ?            |
| **GDPR**            | Dados pessoais (EU)                | ?            |
| **EU AI Act**       | Sistemas de IA por risco           | ?            |
| **NIST AI RMF 2.0** | Gestão de risco de IA (voluntário) | ?            |
| **ISO/IEC 42001**   | AI Management System               | ?            |
| **SOX**             | Controles financeiros              | ?            |
| **DAMA-DMBOK**      | Best practices de gestão de dados  | ?            |

**Sub-pergunta:** O compliance deve ser um módulo plugável ou built-in no core?

**Dependências:** ADR-001, ADR-002

______________________________________________________________________

### ADR-111: Classificação de Risco de IA (EU AI Act)

<!-- metadata:
  id: ADR-111
  domain: compliance
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "4 tipos de decisão: EMERGENCIAL, CRITICA, NORMAL, ESTRUTURAL"
  references: ["EU AI Act Art. 6-7 (risk classification)"]
-->

**Contexto:** O EU AI Act classifica sistemas de IA em 4 níveis de risco: Inaceitável, Alto, Limitado, Mínimo. O B-Swarm tem 4 tipos de decisão. O mapeamento não é direto.

**Pergunta:** Como mapear os tipos de decisão B-Swarm para classificação EU AI Act?

**Mapeamento proposto para discussão:**

| B-Swarm     | EU AI Act Risk                          | Controles sugeridos               |
| ----------- | --------------------------------------- | --------------------------------- |
| EMERGENCIAL | Alto (requer supervisão humana Art. 14) | Human-in-the-loop obrigatório     |
| CRITICA     | Alto                                    | Logging completo, explicabilidade |
| NORMAL      | Limitado                                | Transparência sobre uso de IA     |
| ESTRUTURAL  | Mínimo                                  | Documentação básica               |

**Sub-pergunta:** O OpenDataGov deve auto-classificar seus próprios componentes de IA quanto a risco?

**Dependências:** ADR-011, ADR-110

______________________________________________________________________

### ADR-112: Persistência e Integridade do Audit Trail

<!-- metadata:
  id: ADR-112
  domain: compliance
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Hash chain SHA-256 in-memory (list[AuditEvent])"
  references: ["Append-only logs", "Kafka as audit log", "Blockchain/DLT"]
-->

**Contexto:** O audit chain atual (`AuditChain` em `audit.py`) é in-memory com hash SHA-256. Em produção precisa de persistência, imutabilidade e querying eficiente.

**Pergunta:** Como persistir o audit trail?

**Alternativas:**

| Opção                                      | Prós                                              | Contras                                               | Fit   |
| ------------------------------------------ | ------------------------------------------------- | ----------------------------------------------------- | ----- |
| **Kafka (append-only log)**                | Imutável por design, alta throughput, já no stack | Querying limitado sem consumer/index                  | Alto  |
| **PostgreSQL + triggers de imutabilidade** | Querying rico, familiar                           | Menos garantia de imutabilidade, precisa de cuidado   | Médio |
| **Kafka → PostgreSQL**                     | Kafka para ingestão imutável, PG para queries     | Dois sistemas                                         | Alto  |
| **Blockchain/DLT**                         | Máxima garantia de integridade                    | Overhead, complexidade, questionável para uso interno | Baixo |

**Baseline RADaC:** `AuditChain` em `.radac/b-swarm/src/governance/audit.py`. In-memory `list[AuditEvent]` com `_compute_hash()` SHA-256 e `verify_chain()`.

**Dependências:** ADR-091

______________________________________________________________________

### ADR-113: Cobertura DAMA-DMBOK

<!-- metadata:
  id: ADR-113
  domain: compliance
  status: OPEN
  decided_value: null
  priority: P1
  radac_baseline: "Cobertura parcial implícita"
  references: ["DAMA-DMBOK 3.0 - 11 Knowledge Areas"]
-->

**Contexto:** DAMA-DMBOK define 11 knowledge areas. Mapear o OpenDataGov a estas áreas ajuda a identificar gaps.

**Pergunta:** Quais knowledge areas o OpenDataGov deve cobrir e com que profundidade?

| #   | Knowledge Area             | Cobertura RADaC             | OpenDataGov deve cobrir? |
| --- | -------------------------- | --------------------------- | ------------------------ |
| 1   | Data Governance            | B-Swarm governance          | ? (core)                 |
| 2   | Data Architecture          | Lakehouse architecture      | ?                        |
| 3   | Data Modeling & Design     | Sem                         | ?                        |
| 4   | Data Storage & Operations  | S3 + K8s + Helm             | ?                        |
| 5   | Data Security              | Differential Privacy        | ?                        |
| 6   | Data Integration & Interop | Kafka + Debezium + Airflow  | ?                        |
| 7   | Document & Content Mgmt    | Sem                         | ?                        |
| 8   | Reference & Master Data    | Sem                         | ?                        |
| 9   | Data Warehousing & BI      | Trino + Superset            | ?                        |
| 10  | Metadata Management        | DataHub                     | ?                        |
| 11  | Data Quality               | Metodologia mas sem tooling | ?                        |

**Dependências:** ADR-001

______________________________________________________________________

## Seção 13: Custo e Sustentabilidade `P2`

### ADR-120: Estratégia de FinOps

<!-- metadata:
  id: ADR-120
  domain: cost
  status: OPEN
  decided_value: null
  priority: P2
  radac_baseline: "Estimativa de ~$9.000/mês para 10TB/dia (46% menos que managed services)"
  references: ["FinOps Foundation", "Kubecost", "OpenCost"]
-->

**Contexto:** O RADaC promete 46% de economia vs. managed services. Manter essa economia requer monitoramento ativo de custos.

**Pergunta:** O OpenDataGov deve incluir capacidades de FinOps?

**Alternativas:**

| Opção                               | Prós                                                    | Contras                                    | Fit   |
| ----------------------------------- | ------------------------------------------------------- | ------------------------------------------ | ----- |
| **Não (usuário gerencia)**          | Simples                                                 | Perde visibilidade, difícil justificar ROI | Baixo |
| **OpenCost/Kubecost integrado**     | Visibilidade de custo K8s, alocação por namespace/label | Mais um componente                         | Alto  |
| **Dashboards Grafana customizados** | Reutiliza stack existente                               | Menos sofisticado                          | Médio |

**Dependências:** ADR-080

______________________________________________________________________

### ADR-121: Perfis de Deployment (Sizing)

<!-- metadata:
  id: ADR-121
  domain: cost
  status: OPEN
  decided_value: null
  priority: P2
  radac_baseline: "Diagrama com 11 datastores; deploy real com 3"
  references: []
-->

**Contexto:** A lacuna entre visão (11 datastores) e implementação (3) sugere necessidade de perfis claros.

**Pergunta:** Quais perfis de deployment oferecer?

**Perfis sugeridos:**

| Perfil     | Componentes                           | Recursos                  | Use Case                  |
| ---------- | ------------------------------------- | ------------------------- | ------------------------- |
| **dev**    | PostgreSQL + Redis + MinIO + 1 expert | 4 vCPU, 16GB RAM          | Desenvolvimento local     |
| **small**  | + Kafka + Trino + Airflow + DataHub   | 16 vCPU, 64GB RAM         | Equipe pequena, \<1TB/dia |
| **medium** | + Qdrant + Superset + multi-expert    | 64 vCPU, 256GB RAM        | Enterprise, 1-10TB/dia    |
| **large**  | Full stack + GPU + multi-AZ           | 256+ vCPU, 1TB+ RAM, GPUs | Large-scale, >10TB/dia    |

**Dependências:** ADR-023, ADR-002

______________________________________________________________________

### ADR-122: Modelo de Sustentabilidade do Projeto

<!-- metadata:
  id: ADR-122
  domain: cost
  status: OPEN
  decided_value: null
  priority: P2
  radac_baseline: "Projeto individual com AGPL-3.0"
  references: ["CNCF sustainability model", "Open Core"]
-->

**Contexto:** Projetos open-source precisam de modelo de sustentabilidade além de boa vontade.

**Pergunta:** Como sustentar o OpenDataGov a longo prazo?

**Alternativas:**

| Opção                  | Modelo                                    | Prós                                  | Contras                   |
| ---------------------- | ----------------------------------------- | ------------------------------------- | ------------------------- |
| **Community-only**     | Voluntários, doações                      | Baixo custo, pureza open-source       | Risco de abandono         |
| **Open Core**          | Core open, features premium proprietárias | Receita previsível                    | Comunidade pode ressentir |
| **Managed Service**    | SaaS hospedado                            | Receita recorrente                    | Conflito com self-hosted  |
| **Consulting/Support** | Serviço de implantação e suporte          | Alinhado com metodologia de auditoria | Não escala linearmente    |
| **Foundation-backed**  | CNCF, Apache, Linux Foundation            | Governança neutra, credibilidade      | Processo demorado         |

**Dependências:** ADR-003

______________________________________________________________________

## Seção 14: Comunidade e Open-Source `P2`

### ADR-130: Modelo de Contribuição

<!-- metadata:
  id: ADR-130
  domain: community
  status: OPEN
  decided_value: null
  priority: P2
  radac_baseline: "Fork-and-PR simples"
  references: ["CNCF governance", "Apache Way", "BDFL"]
-->

**Contexto:** Projetos open-source maduros precisam de governança de projeto clara.

**Pergunta:** Qual modelo de governança para contribuições?

**Alternativas:**

| Opção                                          | Prós                                | Contras                 | Fit                  |
| ---------------------------------------------- | ----------------------------------- | ----------------------- | -------------------- |
| **BDFL** (Benevolent Dictator for Life)        | Decisões rápidas, visão clara       | Single point of failure | Alto para início     |
| **Meritoccracia Apache-style**                 | Escalável, comprovado               | Burocrático, lento      | Médio a longo prazo  |
| **CNCF-style** (Technical Oversight Committee) | Neutro, credível, multi-stakeholder | Processo pesado         | Se foundation-backed |

**Dependências:** ADR-003, ADR-122

______________________________________________________________________

### ADR-131: Arquitetura de Plugins/Extensões

<!-- metadata:
  id: ADR-131
  domain: community
  status: OPEN
  decided_value: null
  priority: P2
  radac_baseline: "BaseExpert como ponto de extensão para AI experts"
  references: ["Plugin patterns", "SPI", "Micro-kernel architecture"]
-->

**Contexto:** Extensibilidade determina crescimento de comunidade. `BaseExpert` é um ponto de extensão, mas o OpenDataGov pode ter mais: custom governance rules, custom DQ checks, custom catalog connectors, custom privacy mechanisms.

**Pergunta:** Quais pontos de extensão formais definir?

**Pontos candidatos:**

| Ponto de Extensão | Exemplo                  | Governado?          |
| ----------------- | ------------------------ | ------------------- |
| AI Expert         | Novo expert de áudio     | Sim (ADR-034)       |
| DQ Check          | Validação custom de CPF  | Não (auto-registro) |
| Governance Rule   | Regra de compliance LGPD | Sim                 |
| Catalog Connector | Conector para Salesforce | Não                 |
| Privacy Mechanism | K-anonymity              | Sim                 |
| Storage Backend   | Novo cloud provider      | Não                 |

**Dependências:** ADR-034

______________________________________________________________________

### ADR-132: Internacionalização

<!-- metadata:
  id: ADR-132
  domain: community
  status: OPEN
  decided_value: null
  priority: P2
  radac_baseline: "READMEs em PT/EN/ZH; enums em português (POLITICA, ECONOMICA)"
  references: []
-->

**Contexto:** O RADaC tem documentação trilíngue (PT/EN/ZH) mas código com valores em português.

**Pergunta:** Padronizar idioma do código e documentação?

**Alternativas:**

| Opção                              | Código                 | Docs                         | API | Fit                         |
| ---------------------------------- | ---------------------- | ---------------------------- | --- | --------------------------- |
| **Tudo em inglês**                 | English enums, vars    | EN primary, i18n para outros | EN  | Alto para comunidade global |
| **Código EN, docs bilíngue PT/EN** | English enums          | PT + EN                      | EN  | Alto para Brasil + global   |
| **Manter PT no código, EN na API** | PT interno, EN externo | Ambos                        | EN  | Médio                       |

**Sub-pergunta:** Os enums devem mudar? Ex: `POLITICA` → `POLITICAL`, `MILITAR` → `SECURITY`?

**Baseline RADaC:** `Representation.POLITICA`, `SocialLayer.PESSOAL`, etc.

**Dependências:** ADR-013

______________________________________________________________________

## Seção 15: Evolução e Roadmap `P2`

### ADR-140: Modelo de Maturidade e Fases de Rollout

<!-- metadata:
  id: ADR-140
  domain: roadmap
  status: OPEN
  decided_value: null
  priority: P2
  radac_baseline: "B-Swarm phases 1-6; Auditoria Q1-Q4"
  references: ["DCAM maturity levels"]
-->

**Contexto:** O OpenDataGov precisa de um roadmap de fases alinhado com a metodologia de auditoria (Q1-Q4) e com as prioridades P0/P1/P2 deste documento.

**Pergunta:** Quais são as fases de evolução?

**Proposta para discussão:**

| Fase                  | Foco                                          | ADRs Resolvidas   | Alinhamento Auditoria          |
| --------------------- | --------------------------------------------- | ----------------- | ------------------------------ |
| **0 — Definição**     | Este documento; decidir todas as P0           | ADR-001 a ADR-034 | Pre-Q1                         |
| **1 — Foundation**    | Core governance + lakehouse mínimo + 1 expert | P0 decididas      | Q1 (Diagnosis + Quick Wins)    |
| **2 — Stabilization** | Catálogo + DQ + lineage + observabilidade     | P1 decididas      | Q2 (SLAs + Observability)      |
| **3 — Scale**         | Multi-expert + federation + self-service      | P2 decididas      | Q3 (Automation + Self-Service) |
| **4 — Optimization**  | FinOps + community plugins + LTS release      | Todas             | Q4 (Refinement)                |

**Dependências:** Todas as ADRs P0

______________________________________________________________________

### ADR-141: Compatibilidade Retroativa e Versionamento

<!-- metadata:
  id: ADR-141
  domain: roadmap
  status: OPEN
  decided_value: null
  priority: P2
  radac_baseline: "Sem versionamento formal"
  references: ["Semantic Versioning 2.0", "API Versioning"]
-->

**Contexto:** À medida que o OpenDataGov evolui, APIs, schemas de metadados e regras de governança mudarão.

**Pergunta:** Qual estratégia de versionamento?

**Sub-perguntas:**

1. Semantic versioning (MAJOR.MINOR.PATCH) para o projeto como um todo?
1. Versionamento independente por componente (governance v1.2, lakehouse v2.0)?
1. API versioning via path (`/v1/`, `/v2/`) ou header?
1. Qual política de deprecation? (N-1 suportado? Sunset em 6 meses?)

**Dependências:** ADR-090

______________________________________________________________________

### ADR-142: Cadência de Atualização Tecnológica

<!-- metadata:
  id: ADR-142
  domain: roadmap
  status: OPEN
  decided_value: null
  priority: P2
  radac_baseline: "Sem cadência definida"
  references: []
-->

**Contexto:** Os componentes open-source (Kafka, Trino, Spark, etc.) lançam versões frequentemente. O OpenDataGov precisa de estratégia para upgrades.

**Pergunta:** Com que frequência atualizar dependências?

**Alternativas:**

| Opção                                                  | Prós                                        | Contras                         | Fit                  |
| ------------------------------------------------------ | ------------------------------------------- | ------------------------------- | -------------------- |
| **Quarterly (alinhado com metodologia)**               | Previsível, alinhado com ciclo de auditoria | Pode pular patches de segurança | Médio                |
| **Security patches ASAP + quarterly features**         | Segurança garantida, features planejadas    | Mais releases                   | Alto                 |
| **LTS releases** (1 release estável por ano + patches) | Estabilidade para enterprise                | Features atrasam                | Alto para enterprise |

**Dependências:** ADR-140

______________________________________________________________________

## Próximos Passos

1. **Revisão P0** — Decidir ADRs 001-034 (Identidade, Governança, Dados, AI/ML)
1. **Revisão P1** — Decidir ADRs 040-113 (Metadados, Qualidade, Lineage, Privacidade, Infra, Compliance)
1. **Revisão P2** — Decidir ADRs 090-142 (API, UX, Custo, Comunidade, Roadmap)
1. **Derivar implementação** — Cada ADR DECIDED gera tarefas de implementação

______________________________________________________________________

<!--
progress_summary:
  total_adrs: 50
  open: 50
  decided: 0
  deferred: 0
  p0_open: 18
  p1_open: 22
  p2_open: 10
-->
