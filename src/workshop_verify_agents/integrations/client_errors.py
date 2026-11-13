"""Provider-neutral errors for optional client construction."""


class ClientProviderError(RuntimeError):
    """A safe provider-selection or client-construction error."""