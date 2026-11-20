"""Alert delivery channels. Each notifier raises NotifierError on failure."""


class NotifierError(Exception):
    """Delivery failed; the outbox will retry later."""
