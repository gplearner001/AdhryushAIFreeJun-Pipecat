from abc import ABC, abstractmethod
from dataclasses import dataclass, fields
from typing import Any, Dict, List, Type

from .. import exceptions


@dataclass
class BaseResource(ABC):
    """Base class for all resource objects."""

    def __init__(self, data: Dict[str, Any]):
        # Match only declared fields; raise on extra keys
        names = {f.name for f in fields(self)}
        unknown = set(data) - names
        if unknown:
            raise TypeError(f"Unknown fields: {unknown}")
        for field in names:
            setattr(self, field, data.get(field))


class BaseResourceManager(ABC):
    """Base class for all resource managers."""

    def __init__(
        self, client: Any, resource: Type[BaseResource], paths: Dict[str, str]
    ):
        self.client = client
        self.resource = resource
        self.paths = paths

    @abstractmethod
    def create(self) -> BaseResource:
        raise exceptions.NotImplementedException(
            msg="Method 'create()' is not implemented."
        )

    def list(self) -> List[BaseResource]:
        if self.paths.get("list", None) is None:
            raise exceptions.NotImplementedException(
                msg="Method 'list()' is not implemented."
            )
        res = self.client.request("GET", self.paths["list"])
        return [self.resource(item) for item in res.json()]

    def retrieve(self, id) -> BaseResource:
        if self.paths.get("retrieve", None) is None:
            raise exceptions.NotImplementedException(
                msg="Method 'retrieve()' is not implemented."
            )
        res = self.client.request("GET", self.paths["retrieve"].format(id))
        return self.resource(res.json())

    def update(self, id) -> BaseResource:
        if self.paths.get("update", None) is None:
            raise exceptions.NotImplementedException(
                msg="Method 'update()' is not implemented."
            )
        res = self.client.request("PATCH", self.paths["update"].format(id))
        return self.resource(res.json())

    def delete(self, id) -> None:
        if self.paths.get("delete", None) is None:
            raise exceptions.NotImplementedException(
                msg="Method 'delete()' is not implemented."
            )
        _ = self.client.request("DELETE", self.paths["delete"].format(id))
        return None


class AsyncBaseResourceManager(ABC):
    """Base class for all async resource managers."""

    def __init__(
        self, client: Any, resource: type[BaseResource], paths: Dict[str, str]
    ):
        self.client = client
        self.resource = resource
        self.paths = paths

    @abstractmethod
    async def create(self) -> BaseResource:
        raise exceptions.NotImplementedException(
            msg="Method 'create()' is not implemented."
        )

    async def list(self) -> List[BaseResource]:
        if self.paths.get("list", None) is None:
            raise exceptions.NotImplementedException(
                msg="Method 'list()' is not implemented."
            )
        res = await self.client.request("GET", self.paths["list"])
        return [self.resource(item) for item in res.json()]

    async def retrieve(self, id) -> BaseResource:
        if self.paths.get("retrieve", None) is None:
            raise exceptions.NotImplementedException(
                msg="Method 'retrieve()' is not implemented."
            )
        res = await self.client.request("GET", self.paths["retrieve"].format(id))
        return self.resource(res.json())

    async def update(self, id) -> BaseResource:
        if self.paths.get("update", None) is None:
            raise exceptions.NotImplementedException(
                msg="Method 'update()' is not implemented."
            )
        res = self.client.request("PATCH", self.paths["update"].format(id))
        return self.resource(res.json())

    async def delete(self, id) -> None:
        if self.paths.get("delete", None) is None:
            raise exceptions.NotImplementedException(
                msg="Method 'delete()' is not implemented."
            )
        _ = await self.client.request("DELETE", self.paths["delete"].format(id))
        return None
