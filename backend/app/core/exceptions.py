class TradingException(Exception):
    """Base exception for trading-related errors."""

    pass


class ExchangeException(TradingException):
    """Exception raised for exchange API errors."""

    pass


class AIConsultException(TradingException):
    """Exception raised for AI consultation errors."""

    pass


class EmergencyStopException(TradingException):
    """Exception raised when emergency stop is triggered."""

    pass
