from teler import exceptions


class BaseClient:
    """Base HTTP Client."""

    def __init__(
        self,
        api_key: str,
        **kwargs,
    ):
        if not api_key:
            raise exceptions.BadParametersException(
                param="api_key", msg="api_key is a required param"
            )
        self.api_key = api_key
