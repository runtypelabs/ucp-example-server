"""Custom exceptions for the UCP Merchant Server."""


class UcpError(Exception):
  def __init__(self, message, code="INTERNAL_ERROR", status_code=500):
    self.message = message
    self.code = code
    self.status_code = status_code
    super().__init__(self.message)


class ResourceNotFoundError(UcpError):
  def __init__(self, message):
    super().__init__(message, code="RESOURCE_NOT_FOUND", status_code=404)


class IdempotencyConflictError(UcpError):
  def __init__(self, message):
    super().__init__(message, code="IDEMPOTENCY_CONFLICT", status_code=409)


class CheckoutNotModifiableError(UcpError):
  def __init__(self, message):
    super().__init__(message, code="CHECKOUT_NOT_MODIFIABLE", status_code=409)


class OutOfStockError(UcpError):
  def __init__(self, message, status_code=400):
    super().__init__(message, code="OUT_OF_STOCK", status_code=status_code)


class PaymentFailedError(UcpError):
  def __init__(self, message, code="PAYMENT_FAILED", status_code=402):
    super().__init__(message, code=code, status_code=status_code)


class CartNotModifiableError(UcpError):
  def __init__(self, message):
    super().__init__(message, code="CART_NOT_MODIFIABLE", status_code=409)


class InvalidRequestError(UcpError):
  def __init__(self, message):
    super().__init__(message, code="INVALID_REQUEST", status_code=400)
