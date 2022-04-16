import logging
from typing import Dict, List, Optional
from pathlib import Path
from divelog_convert.formater import DiveLogConfig, DiveLogEntry, DiveLogFormater
from divelog_convert.formaters.csv import DiviacCsvDiveLogFormater
from divelog_convert.formaters.dl7 import DL7DiveLogFormater, DL7DiverlogDiveLogFormater


class DiveLogConverterError(Exception):
    pass


class DiveLogConverter():

    def __init__(self, config=None):
        self._config = config or DiveLogConfig()
        self.log = logging.getLogger(self.__class__.__name__)
        self.encoders = [
            DiviacCsvDiveLogFormater(self._config),
            DL7DiveLogFormater(self._config),
            DL7DiverlogDiveLogFormater(self._config)
        ]
        self.decoders = [DiviacCsvDiveLogFormater(self._config)]

    def _get_formater(self, formaters: List[DiveLogFormater], filename: Path, format: str) -> DiveLogFormater:
        for formater in formaters:  
            if format == formater.name or ((not format) and (formater.ext == filename.suffix)):
                return formater
        raise DiveLogConverterError(f"No formater found for file '{filename}', format '{format}', valids: {formaters}")

    def parse_dives(self, filename: str, format: Optional[str] = None) -> List[DiveLogEntry]:
        filepath = Path(filename)
        formater = self._get_formater(self.decoders, filepath, format)
        return formater.read_dives(filepath)

    def dump_dives(self, dives: List[DiveLogEntry], filename: str, format: Optional[str] = None):
        filepath = Path(filename)
        formater = self._get_formater(self.encoders, filepath, format)
        return formater.write_dives(filepath, dives)

    def convert(
        self,
        input_filename: str,
        output_filename: str, 
        input_format: Optional[str]=None,
        output_format: Optional[str]=None
    ):
        dives = self.parse_dives(input_filename, input_format)
        self.dump_dives(dives, output_filename, output_format)

