from dataclasses import dataclass, field


@dataclass
class DialogueTranslation:
    speaker_alias: str
    text: str


@dataclass
class DialogueEntry:
    original_speaker: str
    translations: dict[str, DialogueTranslation]


@dataclass
class Chapter:
    storage: str
    entries: list[DialogueEntry] = field(default_factory=list)


@dataclass
class StoryTranscript:
    supported_languages: list[str] = field(default_factory=lambda: ["jp"])
    chapters: list[Chapter] = field(default_factory=list)
