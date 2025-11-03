# Service Mesh Architecture Planning

## Visão Geral

Este documento detalha o planejamento para implementação de Service Mesh na arquitetura de microserviços do HWA-New. O Service Mesh será fundamental para gerenciar comunicação entre serviços, observabilidade, segurança e controle de tráfego.

## Objetivos

- **Observabilidade Completa**: Tracing distribuído, métricas e logging centralizado
- **Segurança**: mTLS automático, autorização baseada em políticas
- **Controle de Tráfego**: Load balancing avançado, circuit breakers, retries
- **Gerenciamento**: Service discovery, health checks, configuration management

## Opções de Service Mesh

### Istio (Recomendado)

**Vantagens:**
- Solução mais madura e feature-complete
- Integração nativa com Kubernetes
- Suporte enterprise amplo
- Rich set of policies e configurações

**Desvantagens:**
- Complexidade de setup e operação
- Overhead de recursos
- Curva de aprendizado íngreme

### Linkerd

**Vantagens:**
- Setup mais simples e lightweight
- Menor overhead de recursos
- Foco em simplicidade e performance
- Excelente para equipes menores

**Desvantagens:**
- Menos features que Istio
- Menor maturidade em alguns cenários enterprise
- Comunidade menor

## Arquitetura Planejada

### Componentes Core

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Gateway   │────│  Service Mesh   │────│ Microservices   │
│                 │    │    (Istio)      │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Observability │
                    │   Stack         │
                    └─────────────────┘
```

### Data Plane

- **Envoy Proxy**: Sidecar containers em cada pod
- **Service Discovery**: Integração com Kubernetes DNS
- **Load Balancing**: Round-robin, least connections, locality-based
- **Circuit Breaking**: Configuração automática baseada em métricas

### Control Plane

- **Pilot**: Service discovery e configuration
- **Citadel**: Certificate management e mTLS
- **Galley**: Configuration validation
- **Mixer/Telemetry**: Metrics e policy enforcement

## Implementação por Fases

### Fase 1: Setup Básico (2-3 semanas)

#### 1.1 Instalação do Istio

```bash
# Install Istio CLI
curl -L https://istio.io/downloadIstio | sh -
cd istio-*
export PATH=$PWD/bin:$PATH

# Install Istio in Kubernetes
istioctl install --set profile=demo

# Enable sidecar injection
kubectl label namespace default istio-injection=enabled
```

#### 1.2 Gateway Configuration

```yaml
# Gateway configuration
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: hwa-gateway
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - "*"
---
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: hwa-routing
spec:
  hosts:
  - "*"
  gateways:
  - hwa-gateway
  http:
  - match:
    - uri:
        prefix: "/api"
    route:
    - destination:
        host: api-gateway
```

#### 1.3 Service Deployment

```yaml
# Example service deployment with sidecar
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-service
  annotations:
    sidecar.istio.io/status: '{"version":"xyz"}'
spec:
  template:
    metadata:
      labels:
        service: user-service
        version: v1
    spec:
      containers:
      - name: user-service
        image: hwa/user-service:latest
        ports:
        - containerPort: 8080
```

### Fase 2: Segurança (2-3 semanas)

#### 2.1 mTLS Configuration

```yaml
# Enable mTLS globally
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: default
spec:
  mtls:
    mode: STRICT
---
# Authorization policies
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: api-gateway-policy
spec:
  selector:
    matchLabels:
      app: api-gateway
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/default/sa/api-gateway"]
    to:
    - operation:
        methods: ["GET", "POST"]
```

#### 2.2 JWT Authentication

```yaml
apiVersion: security.istio.io/v1beta1
kind: RequestAuthentication
metadata:
  name: jwt-auth
spec:
  selector:
    matchLabels:
      app: api-gateway
  jwtRules:
  - issuer: "hwa-auth-service"
    jwksUri: "https://auth.hwa.com/.well-known/jwks.json"
---
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: jwt-authorization
spec:
  selector:
    matchLabels:
      app: api-gateway
  rules:
  - from:
    - source:
        requestPrincipals: ["*"]
  action: ALLOW
```

### Fase 3: Controle de Tráfego (2-3 semanas)

#### 3.1 Load Balancing e Circuit Breaking

```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: user-service-dr
spec:
  host: user-service
  trafficPolicy:
    loadBalancer:
      simple: LEAST_CONN
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        http1MaxPendingRequests: 10
        maxRequestsPerConnection: 10
    outlierDetection:
      consecutiveErrors: 5
      interval: 10s
      baseEjectionTime: 30s
```

#### 3.2 Canary Deployments

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: user-service-canary
spec:
  hosts:
  - user-service
  http:
  - route:
    - destination:
        host: user-service
        subset: v1
      weight: 90
    - destination:
        host: user-service
        subset: v2
      weight: 10
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: user-service-subsets
spec:
  host: user-service
  subsets:
  - name: v1
    labels:
      version: v1
  - name: v2
    labels:
      version: v2
```

#### 3.3 Fault Injection e Chaos Engineering

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: user-service-fault-injection
spec:
  hosts:
  - user-service
  http:
  - fault:
      delay:
        percentage:
          value: 10.0
        fixedDelay: 5s
      abort:
        percentage:
          value: 5.0
        httpStatus: 503
    route:
    - destination:
        host: user-service
```

### Fase 4: Observabilidade (2-3 semanas)

#### 4.1 Distributed Tracing

```yaml
apiVersion: telemetry.istio.io/v1alpha1
kind: Telemetry
metadata:
  name: mesh-default
spec:
  tracing:
  - providers:
    - name: jaeger
  accessLogging:
  - providers:
    - name: envoy
```

#### 4.2 Métricas Customizadas

```yaml
apiVersion: telemetry.istio.io/v1alpha1
kind: Telemetry
metadata:
  name: custom-metrics
spec:
  metrics:
  - providers:
    - name: prometheus
    overrides:
    - tagOverrides:
        request_method:
          value: "request.method"
      match:
        metric: REQUEST_COUNT
        mode: CLIENT_AND_SERVER
```

#### 4.3 Log Aggregation

```yaml
apiVersion: telemetry.istio.io/v1alpha1
kind: Telemetry
metadata:
  name: access-logs
spec:
  accessLogging:
  - providers:
    - name: envoy
      filter:
        expression: "response.code >= 400"
```

## Integração com Componentes Existentes

### API Gateway Integration

O API Gateway existente será integrado como um serviço adicional no mesh:

```python
# resync/api/gateway.py - Service Mesh Integration
class ServiceMeshIntegration:
    def __init__(self, mesh_config: Dict[str, Any]):
        self.mesh_enabled = mesh_config.get("enabled", False)
        self.istio_gateway = mesh_config.get("istio_gateway")
        self.service_discovery = mesh_config.get("service_discovery")

    async def register_with_mesh(self):
        """Register API Gateway with service mesh"""
        if self.mesh_enabled:
            # Register service endpoints
            # Configure mesh policies
            # Setup health checks
            pass
```

### Service Discovery Enhancement

```python
# resync/core/service_discovery.py - Mesh Integration
class MeshAwareServiceDiscovery:
    def __init__(self):
        self.mesh_backend = IstioBackend()
        self.kubernetes_backend = KubernetesBackend()

    async def discover_with_mesh(self, service_name: str):
        """Enhanced discovery with mesh awareness"""
        # Get service endpoints from Kubernetes
        k8s_endpoints = await self.kubernetes_backend.discover_services(service_name)

        # Enrich with mesh information
        mesh_info = await self.mesh_backend.get_service_mesh_info(service_name)

        # Combine and return enhanced service information
        return self._merge_endpoints(k8s_endpoints, mesh_info)
```

## Monitoramento e Operação

### Dashboard de Observabilidade

```
Grafana Dashboard Structure:
├── Service Mesh Overview
│   ├── Service Health Status
│   ├── Traffic Flow Metrics
│   └── Error Rates
├── Istio Control Plane
│   ├── Pilot Metrics
│   ├── Citadel Metrics
│   └── Galley Configuration
├── Data Plane Performance
│   ├── Envoy Proxy Metrics
│   ├── Circuit Breaker Status
│   └── Connection Pool Usage
└── Security Monitoring
    ├── mTLS Status
    ├── Authorization Policies
    └── Security Event Logs
```

### Alerting Rules

```yaml
# Prometheus Alerting Rules
groups:
- name: istio.alerts
  rules:
  - alert: IstioHighRequestLatency
    expr: istio_request_duration_milliseconds{quantile="0.5"} > 1000
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High request latency in Istio mesh"

  - alert: IstioCircuitBreakerOpen
    expr: istio_circuit_breaker_open > 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Circuit breaker opened in Istio mesh"
```

## Migração Strategy

### Abordagem Incremental

1. **Setup do Mesh**: Instalar Istio sem modificar aplicações
2. **Observabilidade**: Adicionar tracing e métricas gradualmente
3. **Segurança**: Implementar mTLS por namespace
4. **Tráfego**: Migrar load balancing para Istio
5. **Canary**: Testar novos deployments com canary releases

### Rollback Plan

- **Quick Rollback**: Desabilitar sidecar injection
- **Gradual Rollback**: Remover policies uma por vez
- **Emergency Rollback**: Remover Istio completamente

## Métricas de Sucesso

### Performance
- Latência adicional < 10ms por hop
- CPU overhead < 5% por sidecar
- Memory overhead < 50MB por sidecar

### Confiabilidade
- Uptime do control plane > 99.9%
- Service discovery accuracy > 99.99%
- mTLS handshake success rate > 99.9%

### Segurança
- 100% mTLS encryption in mesh
- Policy enforcement accuracy > 99.9%
- Zero security incidents from mesh misconfiguration

## Timeline e Recursos

### Timeline Detalhado

- **Semana 1-2**: Setup básico e POC
- **Semana 3-4**: Segurança (mTLS + authorization)
- **Semana 5-6**: Controle de tráfego
- **Semana 7-8**: Observabilidade completa
- **Semana 9-12**: Migração gradual dos serviços

### Equipe Necessária

- **2 SREs/Platform Engineers**: Setup e operação do mesh
- **1 Security Engineer**: Políticas de segurança
- **1 DevOps Engineer**: CI/CD e deployment
- **1 Observability Engineer**: Monitoring e alerting

### Custos Estimados

- **Infraestrutura**: +20-30% overhead em recursos
- **Licenciamento**: Istio open source (gratuito)
- **Treinamento**: 2-3 dias por pessoa
- **Migração**: 2-3 sprints de desenvolvimento

## Conclusão

A implementação do Service Mesh será um marco importante na evolução da arquitetura do HWA-New, proporcionando:

- **Escalabilidade**: Load balancing inteligente e auto-scaling
- **Observabilidade**: Tracing distribuído e métricas detalhadas
- **Segurança**: mTLS e políticas de autorização consistentes
- **Resiliência**: Circuit breakers e fault injection
- **Operabilidade**: Gerenciamento simplificado de microserviços

O Istio foi escolhido como solução principal devido à sua maturidade, conjunto de features e integração nativa com Kubernetes, que já é nossa plataforma de orquestração.



