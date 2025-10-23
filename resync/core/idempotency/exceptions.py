"""
Exceções específicas do sistema de idempotency.
"""


class IdempotencyError(Exception):
    """Exceção base para o sistema de idempotency"""
    pass


class IdempotencyKeyError(IdempotencyError):
    """Exceção para erros relacionados à chave de idempotency"""
    pass


class IdempotencyStorageError(IdempotencyError):
    """Exceção para erros de armazenamento"""
    pass


class IdempotencyConflictError(IdempotencyError):
    """Exceção para conflitos de idempotency"""
    pass
