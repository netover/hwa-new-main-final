# TODO - Correções Pyright

## 🎯 **Status Geral: PLANEJAMENTO CONCLUÍDO**

Plano detalhado criado para correção sistemática dos **942 problemas** identificados pelo Pyright.

## 📊 **Indicadores de Progresso**

### **Problemas por Categoria:**
- 🔴 **Interface/Protocolo:** ~150 problemas (críticos)
- 🟡 **Tipagem de Parâmetros:** ~200 problemas (alta prioridade)
- 🟠 **Atributos Não Definidos:** ~250 problemas (média prioridade)
- 🔵 **Expressões Awaitables:** ~100 problemas (média prioridade)
- 🟢 **Testes:** ~242 problemas (baixa prioridade)

### **Arquivos Mais Afetados:**
- `resync/api/*.py` - ~300 problemas
- `tests/*.py` - ~400 problemas
- `resync/core/*.py` - ~150 problemas
- Outros módulos - ~92 problemas

---

## 🔴 **FASE 1: Problemas Críticos (Interface/Protocolo)**

### **TAREFA 1.1: Interfaces IKnowledgeGraph** ✅ **PLANEJADA**
- [ ] SUBTAREFA 1.1.1: Analisar interfaces atuais
- [ ] SUBTAREFA 1.1.2: Implementar métodos ausentes
- [ ] SUBTAREFA 1.1.3: Atualizar implementações

### **TAREFA 1.2: Interfaces IAuditQueue** ✅ **PLANEJADA**
- [ ] SUBTAREFA 1.2.1: Analisar métodos ausentes
- [ ] SUBTAREFA 1.2.2: Implementar métodos obrigatórios
- [ ] SUBTAREFA 1.2.3: Corrigir contratos de tipos

### **TAREFA 1.3: Interfaces ITWSClient** ✅ **PLANEJADA**
- [ ] SUBTAREFA 1.3.1: Analisar métodos de invalidação
- [ ] SUBTAREFA 1.3.2: Implementar métodos de cache
- [ ] SUBTAREFA 1.3.3: Atualizar implementações

### **TAREFA 1.4: Problemas de Protocolo** ✅ **PLANEJADA**
- [ ] SUBTAREFA 1.4.1: Verificar protocolos assíncronos
- [ ] SUBTAREFA 1.4.2: Corrigir protocolos de contexto

---

## 🟡 **FASE 2: Tipagem de Parâmetros**

### **TAREFA 2.1: APIs Principais** ✅ **PLANEJADA**
- [ ] SUBTAREFA 2.1.1: Corrigir resync/api/admin.py
- [ ] SUBTAREFA 2.1.2: Corrigir resync/api/endpoints.py
- [ ] SUBTAREFA 2.1.3: Corrigir resync/api/dependencies.py

### **TAREFA 2.2: Modelos de Validação** ✅ **PLANEJADA**
- [ ] SUBTAREFA 2.2.1: Corrigir validações Pydantic
- [ ] SUBTAREFA 2.2.2: Corrigir modelos de resposta
- [ ] SUBTAREFA 2.2.3: Corrigir enums e constantes

### **TAREFA 2.3: Endpoints e Handlers** ✅ **PLANEJADA**
- [ ] SUBTAREFA 2.3.1: Corrigir handlers assíncronos
- [ ] SUBTAREFA 2.3.2: Corrigir parâmetros de função

---

## 🟠 **FASE 3: Atributos Não Definidos**

### **TAREFA 3.1: Classes Core** ✅ **PLANEJADA**
- [ ] SUBTAREFA 3.1.1: Corrigir atributos em modelos de dados
- [ ] SUBTAREFA 3.1.2: Corrigir atributos em serviços
- [ ] SUBTAREFA 3.1.3: Corrigir atributos em configurações

### **TAREFA 3.2: Interfaces** ✅ **PLANEJADA**
- [ ] SUBTAREFA 3.2.1: Atualizar definições de interface
- [ ] SUBTAREFA 3.2.2: Corrigir implementações de interface

### **TAREFA 3.3: Testes** ✅ **PLANEJADA**
- [ ] SUBTAREFA 3.3.1: Corrigir atributos em mocks de teste

---

## 🔵 **FASE 4: Expressões Awaitables**

### **TAREFA 4.1: Expressões Awaitables** ✅ **PLANEJADA**
- [ ] SUBTAREFA 4.1.1: Corrigir uso de await incorreto
- [ ] SUBTAREFA 4.1.2: Corrigir iteração assíncrona
- [ ] SUBTAREFA 4.1.3: Corrigir programação assíncrona

### **TAREFA 4.2: Context Managers** ✅ **PLANEJADA**
- [ ] SUBTAREFA 4.2.1: Implementar protocolos de contexto
- [ ] SUBTAREFA 4.2.2: Corrigir uso de context managers

---

## 🟢 **FASE 5: Problemas de Testes**

### **TAREFA 5.1: Testes de Integração** ✅ **PLANEJADA**
- [ ] SUBTAREFA 5.1.1: Corrigir testes de integração
- [ ] SUBTAREFA 5.1.2: Corrigir testes de performance
- [ ] SUBTAREFA 5.1.3: Corrigir testes de validação

### **TAREFA 5.2: Arquivos de Mutantes** ✅ **PLANEJADA**
- [ ] SUBTAREFA 5.2.1: Corrigir testes especializados

### **TAREFA 5.3: Scripts e Utilitários** ✅ **PLANEJADA**
- [ ] SUBTAREFA 5.3.1: Corrigir scripts auxiliares
- [ ] SUBTAREFA 5.3.2: Corrigir utilitários

---

## 📈 **Controle de Qualidade**

### **Checkpoints de Validação:**
- [ ] **Após Fase 1:** Interfaces críticas funcionando
- [ ] **Após Fase 2:** APIs principais sem erros de parâmetros
- [ ] **Após Fase 3:** Atributos definidos corretamente
- [ ] **Após Fase 4:** Código assíncrono funcionando
- [ ] **Após Fase 5:** Todos os testes passando

### **Métricas de Sucesso:**
- [ ] **Problemas críticos:** < 10 (redução >90%)
- [ ] **Problemas de parâmetros:** < 50 (redução >75%)
- [ ] **Problemas de atributos:** < 100 (redução >60%)
- [ ] **Problemas assíncronos:** < 25 (redução >75%)
- [ ] **Cobertura de tipos:** > 90%

## 🚀 **Próximos Passos Imediatos**

1. **Iniciar implementação** da Fase 1
2. **Configurar ambiente de desenvolvimento** com Pyright
3. **Criar branch específica** para correções
4. **Implementar correções críticas** primeiro

## 📋 **Recursos Necessários**

### **Ferramentas:**
- [ ] Pyright configurado com regras específicas
- [ ] mypy para validação adicional
- [ ] pytest para testes de regressão

### **Equipe:**
- [ ] 2-3 desenvolvedores Python experientes
- [ ] 1 arquiteto técnico para decisões de design
- [ ] 1 QA para validação de funcionalidades

### **Ambiente:**
- [ ] IDE com Pyright/Pylance habilitado
- [ ] CI/CD configurado para verificações de tipos
- [ ] Ambiente de desenvolvimento isolado

**Este TODO garante acompanhamento detalhado e controle de qualidade durante todo o processo de correção.**
