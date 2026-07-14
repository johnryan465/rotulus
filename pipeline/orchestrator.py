import sqlite3
import os
from typing import Optional
from .models import PageContent, Roll, Titulus, Footnote, Entity, Citation
from .processor import PageProcessor
from .provider import PageProvider
from .validation import validate_roll_num
from database import init_db, reset_db as _reset_db_schema

class PipelineOrchestrator:
    def __init__(self, db_path: str, provider: PageProvider, processor: PageProcessor):
        self.db_path = db_path
        self.provider = provider
        self.processor = processor
        self.active_roll_num: Optional[int] = None
        self.expected_next_roll = 1

    def _get_db_conn(self):
        return sqlite3.connect(self.db_path)

    def reset_db(self):
        conn = self._get_db_conn()
        _reset_db_schema(conn)
        conn.close()

    def _is_page_processed(self, pdf_idx: int, page_num: int, half: str) -> bool:
        conn = self._get_db_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM processed_pages WHERE pdf_idx = ? AND page_num = ? AND half = ?",
            (pdf_idx, page_num, half),
        )
        row = cursor.fetchone()
        conn.close()
        return row is not None

    def _mark_page_processed(self, pdf_idx: int, page_num: int, half: str):
        conn = self._get_db_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO processed_pages (pdf_idx, page_num, half, status) VALUES (?, ?, ?, 'done')",
            (pdf_idx, page_num, half),
        )
        conn.commit()
        conn.close()

    def _save_roll(self, roll: Roll):
        conn = self._get_db_conn()
        cursor = conn.cursor()
        pages_str = ",".join(map(str, roll.pdf_pages))
        cursor.execute("""
            INSERT OR IGNORE INTO rolls (roll_num, date_str, title, manuscripts, pdf_source, pdf_pages)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (roll.roll_num, roll.date_str, roll.title, roll.manuscripts, roll.pdf_source, pages_str))
        conn.commit()
        conn.close()

    def _save_titulus(self, roll_num: int, tit: Titulus) -> Optional[int]:
        conn = self._get_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM rolls WHERE roll_num = ?", (roll_num,))
        row = cursor.fetchone()
        tit_id = None
        if row:
            rid = row[0]
            cursor.execute("""
                INSERT INTO tituli (roll_id, title, location_name, latin_text, pdf_page, pdf_half)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (rid, tit.title, tit.location_name, tit.latin_text, tit.page_num, tit.half))
            tit_id = cursor.lastrowid
            for ent in tit.entities:
                cursor.execute("""
                    INSERT INTO entities (titulus_id, original_name, original_title, footnote_num, footnote_text,
                                           normalized_name, normalized_role, normalized_dates, location_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (tit_id, ent.original_name, ent.original_title, ent.footnote_num, ent.footnote_text,
                      ent.normalized_name, ent.normalized_role, ent.normalized_dates, ent.location_name))
        conn.commit()
        conn.close()
        return tit_id

    def _save_citation(self, roll_num: int, cit: Citation):
        conn = self._get_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM rolls WHERE roll_num = ?", (roll_num,))
        row = cursor.fetchone()
        if row:
            rid = row[0]
            cursor.execute("""
                INSERT INTO citations (roll_id, cited_work, cited_locator, raw_text)
                VALUES (?, ?, ?, ?)
            """, (rid, cit.cited_work, cit.cited_locator, cit.raw_text))
        conn.commit()
        conn.close()

    def _save_footnote(self, roll_num: int, fn: Footnote):
        conn = self._get_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM rolls WHERE roll_num = ?", (roll_num,))
        row = cursor.fetchone()
        if row:
            rid = row[0]
            cursor.execute("""
                INSERT INTO footnotes (roll_id, pdf_page, pdf_half, footnote_num, text)
                VALUES (?, ?, ?, ?, ?)
            """, (rid, fn.page_num, fn.half, fn.footnote_num, fn.text))
        conn.commit()
        conn.close()

    def _resolve_entity_footnotes(self, roll_num: int):
        """Backfill entities.footnote_text by matching footnote_num against
        this roll's footnotes, now that both have been saved. Decouples entity
        extraction from having to see the whole page's footnotes at once."""
        conn = self._get_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM rolls WHERE roll_num = ?", (roll_num,))
        row = cursor.fetchone()
        if row:
            rid = row[0]
            cursor.execute("""
                UPDATE entities
                SET footnote_text = (
                    SELECT text FROM footnotes
                    WHERE footnotes.roll_id = ? AND footnotes.footnote_num = entities.footnote_num
                )
                WHERE footnote_text IS NULL AND footnote_num IS NOT NULL
                  AND titulus_id IN (SELECT id FROM tituli WHERE roll_id = ?)
            """, (rid, rid))
        conn.commit()
        conn.close()

    def run(self, dry_run=False, reset=False):
        if not dry_run:
            if reset:
                self.reset_db()
            else:
                conn = self._get_db_conn()
                init_db(conn)
                conn.close()
                # Resuming a previous run: active_roll_num/expected_next_roll only
                # live in memory, so a fresh process (after an interruption) must
                # recover them from the DB before validating any new roll - otherwise
                # every processor's output looks implausible against a stale
                # "expected roll 1" and gets misattributed to the wrong roll.
                conn = self._get_db_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(roll_num) FROM rolls")
                row = cursor.fetchone()
                conn.close()
                if row and row[0] is not None:
                    self.active_roll_num = row[0]
                    self.expected_next_roll = row[0] + 1
                    print(f"Resumed: recovered active_roll_num={self.active_roll_num}, "
                          f"expected_next_roll={self.expected_next_roll} from DB.")

        for text, metadata in self.provider.get_pages():
            pdf_idx, page_num, half = metadata['pdf_idx'], metadata['page_num'], metadata['half']

            if not dry_run and self._is_page_processed(pdf_idx, page_num, half):
                continue

            metadata['expected_next_roll'] = self.expected_next_roll
            print(f"Processing {metadata['filename']}...")

            page_content = self.processor.process_page(text, metadata)

            # 1. Handle new rolls defined on this page
            for roll in page_content.rolls:
                # A genuinely new roll can never repeat or precede the roll already in
                # progress - Dufour's numbering only increases through the document, so
                # roll_num <= active_roll_num is always a mis-extraction (e.g. a footnote
                # marker or back-reference misread as a new roll header), not a real roll.
                is_backward = self.active_roll_num is not None and roll.roll_num <= self.active_roll_num
                if is_backward or not validate_roll_num(roll.roll_num, pdf_idx, self.expected_next_roll):
                    reason = f"<= active roll {self.active_roll_num}" if is_backward else f"expected ~{self.expected_next_roll}"
                    print(f"  REJECTED implausible roll_num {roll.roll_num} ({reason}) - not corrupting "
                          f"sequence state, but salvaging its tituli/footnotes/citations onto active roll "
                          f"{self.active_roll_num} instead of discarding them (likely a continuation page "
                          f"or back-reference misread as a new roll header).")
                    page_content.orphaned_tituli.extend(roll.tituli)
                    page_content.orphaned_footnotes.extend(roll.footnotes)
                    page_content.orphaned_citations.extend(roll.citations)
                    continue

                if not dry_run:
                    self._save_roll(roll)
                self.active_roll_num = roll.roll_num
                self.expected_next_roll = roll.roll_num + 1

                if not dry_run:
                    for tit in roll.tituli:
                        self._save_titulus(roll.roll_num, tit)
                    for fn in roll.footnotes:
                        self._save_footnote(roll.roll_num, fn)
                    for cit in roll.citations:
                        self._save_citation(roll.roll_num, cit)
                    self._resolve_entity_footnotes(roll.roll_num)

            # 2. Handle orphaned content (belongs to active roll)
            if self.active_roll_num and not dry_run:
                for tit in page_content.orphaned_tituli:
                    self._save_titulus(self.active_roll_num, tit)
                for fn in page_content.orphaned_footnotes:
                    self._save_footnote(self.active_roll_num, fn)
                for cit in page_content.orphaned_citations:
                    self._save_citation(self.active_roll_num, cit)
                self._resolve_entity_footnotes(self.active_roll_num)

                # Update page list for the active roll
                conn = self._get_db_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT pdf_pages FROM rolls WHERE roll_num = ?", (self.active_roll_num,))
                row = cursor.fetchone()
                if row:
                    pl = [p.strip() for p in row[0].split(",") if p.strip()]
                    if str(page_num) not in pl:
                        pl.append(str(page_num))
                        cursor.execute("UPDATE rolls SET pdf_pages = ? WHERE roll_num = ?", (",".join(pl), self.active_roll_num))
                conn.commit()
                conn.close()

            if not dry_run:
                self._mark_page_processed(pdf_idx, page_num, half)

        print("Pipeline run complete.")
