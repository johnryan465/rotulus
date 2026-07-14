from typing import List, Optional
from pydantic import BaseModel, Field

class Entity(BaseModel):
    """A named person/place mentioned within a titulus (e.g. a monk, abbot, or
    saint referenced in the response), normalized for search and mapping."""
    original_name: str = Field(..., description="Name as it appears in the Latin text")
    original_title: Optional[str] = Field("", description="Title/role as it appears in the Latin text")
    footnote_num: Optional[str] = Field(None, description="Footnote number annotating this entity, if any")
    footnote_text: Optional[str] = Field(None, description="Resolved footnote text (filled in by the orchestrator, not the model)")
    normalized_name: str = Field(..., description="Cleaned-up modern form of the name")
    normalized_role: Optional[str] = Field("", description="Cleaned-up role (e.g. 'abbot', 'monk', 'bishop')")
    normalized_dates: Optional[str] = Field("", description="Known/inferred dates for this entity")
    location_name: Optional[str] = Field(None, description="Place associated with this entity, if any")

class Titulus(BaseModel):
    title: str = Field(..., description="Full header text of the titulus")
    location_name: str = Field("", description="Extracted geographic location name")
    latin_text: str = Field("", description="The main body text of the titulus (usually Latin)")
    page_num: int
    half: str
    entities: List[Entity] = []

class Footnote(BaseModel):
    footnote_num: str
    text: str = ""
    page_num: int
    half: str

class Citation(BaseModel):
    """A bibliographic reference to an external work found in a roll's
    apparatus (manuscript/editions header block or footnotes) - e.g. a
    citation of Delisle's earlier 'Rouleaux des morts' catalog, Gallia
    Christiana, or another edition. The actual research signal: Dufour's
    own apparatus citing a predecessor catalog entry that may not have a
    corresponding roll_num in this edition is a lead for an unreferenced roll."""
    cited_work: str = Field(..., description="Author and/or work title being cited, e.g. 'L. Delisle, Rouleaux des morts du IXe au XVe s.'")
    cited_locator: Optional[str] = Field("", description="Page/volume/catalog number within the cited work, e.g. 'p. 89, n° V'")
    raw_text: str = Field("", description="The citation as it appears in the source text, verbatim")

class Roll(BaseModel):
    roll_num: int
    date_str: Optional[str] = "S.d."
    title: str = Field(..., description="Scholarly description / French title of the roll")
    manuscripts: Optional[str] = Field("", description="Current storage / manuscript locations")
    pdf_source: str
    pdf_pages: List[int]
    tituli: List[Titulus] = []
    footnotes: List[Footnote] = []
    citations: List[Citation] = []

class PageContent(BaseModel):
    rolls: List[Roll] = []
    # If a page contains tituli/footnotes/citations that belong to a roll started on a previous page
    orphaned_tituli: List[Titulus] = []
    orphaned_footnotes: List[Footnote] = []
    orphaned_citations: List[Citation] = []
