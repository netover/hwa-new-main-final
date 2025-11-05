"""Load testing configuration for the Resync application.

O módulo descreve cenários de carga Locust que simulam o uso dos
principais endpoints da plataforma Resync.
"""

from locust import HttpUser, task


class AuditUser(HttpUser):
    """Usuário de teste que dispara tarefas de auditoria, chat e descoberta."""

    @task
    def audit_check(self) -> None:
        """Valida a obtenção de locks de auditoria sob carga."""
        self.client.post("/audit", {"lock_id": "123"})

    @task
    def chat_endpoint(self) -> None:
        """Envia mensagens simulando conversas em tempo real."""
        self.client.post("/chat", {"message": "test message"})

    @task
    def endpoints_list(self) -> None:
        """Consulta a listagem de endpoints para validação de saúde."""
        self.client.get("/endpoints")




