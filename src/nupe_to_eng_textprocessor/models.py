
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

    # Source tracking
    source_pdf_page: int
    source_printed_page: int | None = None
    source_excerpt: str | None = None

    # Quality control
    review_required: bool = True
    human_verified: bool = False


class DictionaryPage(BaseModel):
    pdf_page_number: int
    printed_page_number: int | None = None
    entries: list[DictionaryEntry] = Field(default_factory=list)
    page_notes: list[str] = Field(default_factory=list)
