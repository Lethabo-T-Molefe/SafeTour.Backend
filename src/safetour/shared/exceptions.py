"""
Cross-cutting application exceptions
====================================
Framework-adjacent errors (auth, generic app failures). Prefer module
``domain.exceptions`` for business-rule violations so domain code stays free
of HTTP / FastAPI concepts.
"""


class AppError(Exception):
    """Base application exception."""

    def __init__(self, message: str = "An unexpected error occurred") -> None:
        self.message = message
        super().__init__(self.message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message)


class ConflictError(AppError):
    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(message)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed") -> None:
        super().__init__(message)
