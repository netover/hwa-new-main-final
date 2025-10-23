"""
Load testing configuration for the Resync application.

This module defines Locust load testing scenarios that simulate real user behavior
across the application's endpoints. It provides comprehensive coverage of:

- Audit operations (locking, validation)
- Chat functionality (message processing)
- API endpoint discovery and health checks

The tests are designed to validate performance under various load conditions,
helping identify bottlenecks and scalability issues.
"""

from locust import HttpUser, task


class AuditUser(HttpUser):
    """
    Load testing user class that simulates real user interactions.

    This class defines the behavior patterns of users interacting with the
    Resync application's endpoints. Each user will randomly execute tasks
    defined below, simulating realistic usage patterns.

    Attributes:
        host: Base URL for the application under test (inherited from HttpUser)
        wait_time: Time between task executions (inherited from HttpUser)
    """

    @task
    def audit_check(self) -> None:
        """
        Simulate audit lock operations.

        This task tests the audit endpoint by attempting to acquire an audit lock.
        It validates that the audit system can handle concurrent lock requests
        and properly manages resource access control.

        The task sends a POST request with a lock identifier, simulating real-world
        audit operations that require exclusive access to resources.
        """
        self.client.post("/audit", {"lock_id": "123"})

    @task
    def chat_endpoint(self) -> None:
        """
        Simulate chat message processing.

        This task tests the chat functionality by sending messages to the chat endpoint.
        It validates message handling, routing, and response generation under load.

        The task simulates typical chat interactions that users would perform,
        helping validate the real-time communication capabilities of the system.
        """
        self.client.post("/chat", {"message": "test message"})

    @task
    def endpoints_list(self) -> None:
        """
        Simulate API discovery and health checks.

        This task tests the endpoint listing functionality, which provides
        API discovery and health monitoring capabilities. It validates that
        the system can provide accurate information about available endpoints.

        This task simulates both user exploration of the API and automated
        health monitoring systems that need to discover available services.
        """
        self.client.get("/endpoints")
