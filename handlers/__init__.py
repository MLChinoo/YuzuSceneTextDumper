import os
import importlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import final, Type

from configs import BaseConfig

class BaseHandler(ABC):
    @final
    def handle(self, config: BaseConfig):
        config.check_valid()
        return self._handle(config)

    @abstractmethod
    def _handle(self, config: BaseConfig):
        pass

@dataclass
class HandlerMeta:
    name: str
    description: str
    clazz: Type[BaseHandler]
    build_config: Type[BaseConfig]

Handlers = {}

def registry(name: str, description: str, config_class: Type[BaseConfig]):
    def decorator(clazz):
        Handlers[name] = HandlerMeta(
            name=name,
            description=description,
            clazz=clazz,
            build_config=config_class,
        )
        return clazz
    return decorator

handler_dir = os.path.dirname(__file__)
for filename in os.listdir(handler_dir):
    if filename.endswith(".py") and filename != "__init__.py":
        module_name = f"{__name__}.{filename[:-3]}"
        importlib.import_module(module_name)
