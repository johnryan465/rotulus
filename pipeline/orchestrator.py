import sqlite3
import os
from typing import Optional
from .models import PageContent, Roll, Titulus, Footnote
from .processor import PageProcessor
from .provider import PageProvider

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
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS rolls")
        cursor.execute("""
            CREATE TABLE rolls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_num INTEGER UNIQUE,
                date_str TEXT,
                title TEXT,
                manuscripts TEXT,
                pdf_source TEXT,
                pdf_pages TEXT,
                is_verified INTEGER DEFAULT 0
            )
        """)
        cursor.execute("DELETE FROM tituli")
        cursor.execute("DELETE FROM footnotes")
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

    def _save_titulus(self, roll_num: int, tit: Titulus):
        conn = self._get_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM rolls WHERE roll_num = ?", (roll_num,))
        row = cursor.fetchone()
        if row:
            rid = row[0]
            cursor.execute("""
                INSERT INTO tituli (roll_id, title, location_name, latin_text, pdf_page, pdf_half)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (rid, tit.title, tit.location_name, tit.latin_text, tit.page_num, tit.half))
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

    def run(self, dry_run=False):
        if not dry_run:
            self.reset_db()
            
        for text, metadata in self.provider.get_pages():
            metadata['expected_next_roll'] = self.expected_next_roll
            print(f"Processing {metadata['filename']}...")
            
            page_content = self.processor.process_page(text, metadata)
            
            # 1. Handle new rolls defined on this page
            for roll in page_content.rolls:
                if not dry_run:
                    self._save_roll(roll)
                self.active_roll_num = roll.roll_num
                self.expected_next_roll = roll.roll_num + 1
                
                # Save tituli and footnotes attached to this roll object
                if not dry_run:
                    for tit in roll.tituli:
                        self._save_titulus(roll.roll_num, tit)
                    for fn in roll.footnotes:
                        self._save_footnote(roll.roll_num, fn)
            
            # 2. Handle orphaned content (belongs to active roll)
            if self.active_roll_num and not dry_run:
                for tit in page_content.orphaned_tituli:
                    self._save_titulus(self.active_roll_num, tit)
                for fn in page_content.orphaned_footnotes:
                    self._save_footnote(self.active_roll_num, fn)
                
                # Update page list for the active roll
                conn = self._get_db_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT pdf_pages FROM rolls WHERE roll_num = ?", (self.active_roll_num,))
                row = cursor.fetchone()
                if row:
                    pl = [p.strip() for p in row[0].split(",") if p.strip()]
                    if str(metadata['page_num']) not in pl:
                        pl.append(str(metadata['page_num']))
                        cursor.execute("UPDATE rolls SET pdf_pages = ? WHERE roll_num = ?", (",".join(pl), self.active_roll_num))
                conn.commit()
                conn.close()

        print("Pipeline run complete.")
