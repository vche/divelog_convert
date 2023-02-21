import copy
import logging
from typing import Dict, List, Optional
from pathlib import Path
from divelog_convert.formater import DiveLogConfig, DiveLogbook, Formater
from divelog_convert.formaters.csv import DiviacCsvDiveLogFormater
from divelog_convert.formaters.dl7 import DL7DiveLogFormater, DL7DiverlogDiveLogFormater
from divelog_convert.formaters.xml import UddfDiveLogFormater
from divelog_convert.formaters.zip import ZipArchiveFormater


class DiveLogConverterError(Exception):
    pass


class DiveLogConverter():

    def __init__(self, config=None):
        self._config = config or DiveLogConfig()
        self.log = logging.getLogger(self.__class__.__name__)
        self.file_encoders = [
            DiviacCsvDiveLogFormater,
            DL7DiveLogFormater,
            DL7DiverlogDiveLogFormater,
            UddfDiveLogFormater,
        ]
        self.file_decoders = [
            DiviacCsvDiveLogFormater,
            UddfDiveLogFormater,
            DL7DiveLogFormater,
            DL7DiverlogDiveLogFormater,
        ]
        self.archive_decoders = [ ZipArchiveFormater ]
        self.decoders = self.file_decoders + self.archive_decoders
        self.encoders = self.file_encoders

    def _get_formater(self, formaters: List[Formater], filename: Path, format: str, exc: bool = True) -> Formater:
        for formater in formaters:  
            if format == formater.name or ((not format) and (formater.ext == filename.suffix)):
                return formater
        if not exc:
            return None
        raise DiveLogConverterError(f"No formater found for file '{filename}', format '{format}', valids: {formaters}")

    def parse_logbook(self, filename: str, format: Optional[str] = None, open_func = None) -> DiveLogbook:
        filepath = Path(filename)
        formater = self._get_formater(self.decoders, filepath, format)
        return formater(self._config, filepath, open_func=open_func).read_dives(filename)

    def parse_archive(self, filename: str, archive_formater: Formater = None) -> DiveLogbook:
        filepath = Path(filename)
        logbooks = []
        with archive_formater(self._config, filepath) as archive:
            for logbook_file in archive.get_log_books():
                logbook = self.parse_logbook(logbook_file, open_func=archive.archive_file.open)
                if logbook:
                    logbooks.append(logbook)
        return self.merge_logbooks(logbooks)

    def dump_logbook(self, logbook: DiveLogbook, filename: str, format: Optional[str] = None):
        if logbook:
            filepath = Path(filename)
            formater = self._get_formater(self.encoders, filepath, format)
            return formater(self._config, filepath).write_dives(filepath, logbook)

    def merge_logbooks(self, logbooks: List[DiveLogbook]) -> DiveLogbook:
        if not logbooks:
            return None
        print(logbooks)
        logbook = copy.deepcopy(logbooks[0])
        for logbook_elt in logbooks[1:]:
            logbook.merge(logbook_elt)
        return logbook

    def convert(
        self,
        input_filename: str,
        output_filename: str, 
        input_format: Optional[str]=None,
        output_format: Optional[str]=None
    ):
        # Check if the file is an archive and decode it
        archive_formater = self._get_formater(self.archive_decoders, Path(input_filename), input_format, exc = False)
        if archive_formater:
            logbook = self.parse_archive(input_filename, archive_formater)
        else:
            # Not an archive
            logbook = self.parse_logbook(input_filename, input_format)

        self.dump_logbook(logbook, output_filename, output_format)
