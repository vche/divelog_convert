from typing import Dict, List, Optional
from pathlib import Path
from divelog_convert.formater import (ArchiveFormater, DiveLogbook)
from zipfile import ZipFile


class ZipArchiveFormater(ArchiveFormater):
    ext = ".zip"
    name = "zip"

    def read_logbooks(self, filename: Path) -> List[DiveLogbook]:        
        self.log.info(f"Opening archive {filename}")
        self.log.debug(f"Extracting to temp folder {self.temp_path}")
        self.archive_file = ZipFile(filename, 'r')
        return self.archive_file.namelist()

    def write_logbooks(self, filename: Path, logbooks: List[DiveLogbook], ):
        # Write down logbooks in temp dir, and compress it
        raise NotImplementedError("Zip export not implemented yet.")
