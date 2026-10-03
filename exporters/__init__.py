import importlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from models.story_transcript import StoryTranscript


class BaseExporter(ABC):
    @abstractmethod
    def export(
        self,
        transcript: StoryTranscript,
        outfile: str | Path,
        *,
        language: str,
    ) -> None:
        pass


@dataclass
class ExporterMeta:
    name: str
    description: str
    clazz: type[BaseExporter]


Exporters: dict[str, ExporterMeta] = {}


def registry(name: str, description: str):
    def decorator(clazz: type[BaseExporter]):
        Exporters[name] = ExporterMeta(
            name=name,
            description=description,
            clazz=clazz,
        )
        return clazz

    return decorator


exporter_dir = Path(__file__).parent
for filepath in sorted(exporter_dir.glob("*_exporter.py")):
    importlib.import_module(f"{__name__}.{filepath.stem}")
