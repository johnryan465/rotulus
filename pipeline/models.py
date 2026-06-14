from typing import List, Optional
from pydantic import BaseModel, Field

class Titulus(BaseModel):
    title: str = Field(..., description="Full header text of the titulus")
    location_name: str = Field(..., description="Extracted geographic location name")
    latin_text: str = Field(..., description="The main body text of the titulus (usually Latin)")
    page_num: int
    half: str

class Footnote(BaseModel):
    footnote_num: str
    text: str
    page_num: int
    half: str

class Roll(BaseModel):
    roll_num: int
    date_str: Optional[str] = "S.d."
    title: str = Field(..., description="Scholarly description / French title of the roll")
    manuscripts: Optional[str] = Field("", description="Current storage / manuscript locations")
    pdf_source: str
    pdf_pages: List[int]
    tituli: List[Titulus] = []
    footnotes: List[Footnote] = []

class PageContent(BaseModel):
    rolls: List[Roll] = []
    # If a page contains tituli that belong to a roll started on a previous page
    orphaned_tituli: List[Titulus] = []
    orphaned_footnotes: List[Footnote] = []
