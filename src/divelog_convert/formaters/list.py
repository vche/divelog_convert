from typing import Dict, List, Optional
from pathlib import Path
from divelog_convert.formater import (ArchiveFormater, DiveLogbook)


class ListArchiveFormater(ArchiveFormater):
    ext = "file1,file2,..."
    name = "file list"
    file_separator = ","

    @classmethod
    def match_file(cls, filename: Path):
        # Override the file matcher to detect a file list and not a suffix
        files = str(filename).split(cls.file_separator)
        print(f"pipo convert match files {files}")
        return len(files) > 1

    def read_logbooks(self, filename: Path) -> List[DiveLogbook]:
        self.logbook_files = str(filename).split(self.file_separator)
        self.log.info(f"Opening files {self.logbook_files}")
        return self.logbook_files

    def write_logbooks(self, filename: Path, logbooks: List[DiveLogbook], ):
        # Write down logbooks in temp dir, and compress it
        raise NotImplementedError("List export not implemented yet.")
