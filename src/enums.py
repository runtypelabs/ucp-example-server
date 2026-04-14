"""Enumerations for the UCP sample server."""

import enum


class CheckoutStatus(str, enum.Enum):
  INCOMPLETE = "incomplete"
  REQUIRES_ESCALATION = "requires_escalation"
  READY_FOR_COMPLETE = "ready_for_complete"
  COMPLETE_IN_PROGRESS = "complete_in_progress"
  COMPLETED = "completed"
  CANCELED = "canceled"


class OrderStatus(str, enum.Enum):
  PROCESSING = "processing"
