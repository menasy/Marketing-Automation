class DomainException(Exception):  # noqa: N818
    """Base exception for all domain-layer business rule violations and errors."""

    pass


class NormalizationError(DomainException):
    """Raised when incoming raw ad data cannot be normalized to canonical domain schema."""

    pass


class InsufficientDataError(DomainException):
    """Raised when insufficient historical records exist to establish baseline statistics."""

    pass


class AnomalyCalculationError(DomainException):
    """Raised when statistical calculation fails during anomaly evaluation."""

    pass


class LLMValidationError(DomainException):
    """Raised when LLM generated briefing fails strict validation against source data."""

    pass


class LLMServiceError(DomainException):
    """Raised when an error occurs in the LLM provider service.

    Covers API errors, timeouts, network issues, and configuration failures.
    """

    pass
