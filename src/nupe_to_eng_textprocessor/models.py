
from pydantic import BaseModel, Field


class Sense(BaseModel):
    part_of_speech: str | None = None
    definition_en: str
    category_code: str | None = None


class DictionaryEntry(BaseModel):
    headword: str
    alternative_spellings: list[str] = Field(default_factory=list)
    senses: list[Sense] = Field(default_factory=list)
    additional_information: list[str] = Field(default_factory=list)
    source_page: int
    source_excerpt: str
    review_required: bool = True


class DictionaryPage(BaseModel):
    page_number: int
    entries: list[DictionaryEntry] = Field(default_factory=list)
    page_notes: list[str] = Field(default_factory=list)