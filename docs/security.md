# Guia de Segurança do Resync

Este documento descreve as práticas e mecanismos de segurança implementados na aplicação Resync para proteger dados e funcionalidades sensíveis.

## 1. Autenticação de Endpoints Administrativos

Certas operações na API do Resync são consideradas administrativas e podem ter um impacto significativo na performance ou no estado da aplicação. Para proteger essas operações, utilizamos um mecanismo de autenticação **HTTP Basic Auth**.

### Endpoint Protegido: Invalidação de Cache

- **Endpoint**: `POST /api/v1/cache/invalidate`
- **Descrição**: Este endpoint permite invalidar o cache de dados do TWS, forçando o sistema a buscar informações frescas na próxima requisição. É uma operação útil para manutenção, mas que pode impactar a performance se usada indevidamente.
- **Proteção**: O acesso a este endpoint requer um nome de usuário e senha de administrador.

### Modo de Uso

Para executar a invalidação do cache, você deve fornecer as credenciais de administrador na sua requisição HTTP.

#### Exemplo com `curl`

O exemplo abaixo demonstra como invalidar todo o cache do sistema (`scope=system`). Você deve usar as credenciais configuradas nas suas variáveis de ambiente.

```bash
curl -X POST "http://localhost:8000/api/v1/cache/invalidate?scope=system" \
     -u <seu_usuario_admin>:<sua_senha_admin>
```

- O parâmetro `-u admin:admin` instrui o `curl` a usar o usuário `admin` e a senha `admin` para a autenticação Basic Auth.
- Se as credenciais estiverem incorretas ou ausentes, a API retornará um erro `HTTP 401 Unauthorized`.

> **Nota de Segurança**: As credenciais `admin:admin` são um padrão para desenvolvimento. Em um ambiente de produção, é fundamental que essas credenciais sejam alteradas e gerenciadas de forma segura através de variáveis de ambiente.