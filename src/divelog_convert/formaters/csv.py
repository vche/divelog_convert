import csv
import json
from abc import abstractmethod
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
from datetime import datetime, timedelta

from divelog_convert.formater import (
    Diver,
    DiveLogbook,
    DiveAirMix,
    DiveComputer,
    DiveGas,
    DiveEquipment,
    DiveLogLocation,
    DiveLogData,
    DiveLogStats,
    DiveLogEntry,
    DiveLogFormater,
    DiveTank,
    DiveViolation
)


class CsvDiveLogFormater(DiveLogFormater):
    @property
    def ext(self):
        return ".csv"

    @property
    def name(self):
        return "csv"

    def read_dives(self, filename: Path) -> DiveLogbook:
        with open(filename, "r") as dive_file:
            self.log.info(f"Reading dives read from {filename}")
            csv_reader = csv.DictReader(dive_file)
            logbook = DiveLogbook()
            errors = 0
            for row in csv_reader:
                try:
                    self.add_dive_log_entry(logbook, row)
                except Exception as e:
                    self.log.exception(f"Failed to build log entry: {e}")
                    errors += 1
            self.log.info(f"{len(logbook.dives)} dives read from {filename}, {errors} errors")
            return logbook

    def write_dives(self, filename: Path, logbook: DiveLogbook):
        if filename.suffix != self.ext:
            filename = filename.with_suffix(self.ext)

        with open(filename, "w") as dive_file:
            self.log.info(f"Writing {len(logbook.dives)} dives written to {filename}")
            csv_writer = csv.DictWriter(dive_file, fieldnames=self.get_fieldnames())
            csv_writer.writeheader()
            for dive in logbook.dives:
                csv_writer.writerow(self.build_dive_log_row(dive))

    @abstractmethod
    def get_fieldnames(self) -> List[str]:
        ...

    @abstractmethod
    def add_dive_log_entry(self, logbook: DiveLogbook, csv_row: Dict[str, str]) -> DiveLogEntry:
        ...

    @abstractmethod
    def build_dive_log_row(self, entry: DiveLogEntry) -> Dict[str, str]:
        ...


class DiviacCsvDiveLogFormater(CsvDiveLogFormater):
    DIVIAC_CSV_FIELDS = [
        "Dive #",
        "Date",
        "Trip",
        "Location",
        "Dive Site",
        "lat",
        "lng",
        "Dive operator",
        "Dive buddy",
        "Dive tags",
        "Weather",
        "Water",
        "Water type",
        "Waves",
        "Current",
        "Visibility",
        "Air temp",
        "Surface temp",
        "Bottom temp",
        "Weight",
        "Time in",
        "Time out",
        "Duration",
        "Max depth",
        "Avg depth",
        "O2 %",
        "Pressure in",
        "Pressure out",
        "Gas consumption",
        "Tank volume",
        "Tank type",
        "Notes",
        "Marine life sightings",
        "Dive profile data",
    ]

    @property
    def name(self):
        return "diviac"

    def __init__(self, config=None):
        super().__init__(config)
        self._datetime_fmt = self._config.get_diviac_date_time_format()
        self._date_fmt =self._config.get_diviac_date_format()
        self._time_fmt =self._config.get_diviac_time_format()
    
    def get_fieldnames(self) -> List[str]:
        return self.DIVIAC_CSV_FIELDS

    def _parse_location(self, location:str) -> Tuple[str, str, str]:
        """Extract city/state/country from a comma separated location.

        if only one token, city is assumed.
        if only 2 tokens, 'city,country'
        if more tha 2 tokens, 'city,[state,.,...],country'
        """
        tokens = location.split(",")
        tokens_count = len(tokens)
        city = tokens[0]
        country = tokens[tokens_count -1] if tokens_count > 1 else None
        state = ",".join(tokens[1:tokens_count-1]) if tokens_count > 2 else None
        return city, state, country


    def _dive_datetime(self, date: str, time: str) -> datetime:
        """Build a date time object based on the date and time strings and diviac config."""
        return datetime.strptime(f"{date} {time}", self._datetime_fmt)

    def _strip_unit(self, strvalue: str) -> Optional[float]:
        """Strip unit string from a value but returning the first space separated field."""
        numvalue = strvalue.split(" ")[0]
        return float(numvalue) if numvalue else None

    def _parse_dive_data(
            self, dive_raw_data: str, airmix: DiveAirMix
        ) -> Tuple[int, List[DiveViolation], List[DiveLogData]]:
        dive_samples = json.loads(dive_raw_data)
        dive_data = []
        all_violations = set()
        last_ts = None
        global_period = 0
        for dive_sample in dive_samples:
            # Compute violation in this sample and overall during the dive
            violations = []
            for elt in dive_sample[3]:
                try:
                    viol = DiveViolation(elt)
                    violations.append(viol)
                    all_violations.add(viol)
                except ValueError:
                    self.log.error(f"Unrecognized dive violation '{elt}'")

            # Compute sampling period
            ts = float(dive_sample[0]) if dive_sample[0] else 0.0
            if last_ts:
                global_period += (ts - last_ts)
            last_ts = ts

            dive_data.append(DiveLogData(
                timestamp_s = ts,
                depth = float(dive_sample[1]) if dive_sample[1] is not None else None,
                temp = float(dive_sample[2]) if dive_sample[2] is not None else None,
                pressure = float(dive_sample[4]) if dive_sample[4] is not None else None,
                violations = violations,
                airmix= airmix
            ))
        sampling_period = round(global_period/(len(dive_samples)-1))
        return sampling_period, list(all_violations), dive_data

    def add_dive_log_entry(self, logbook: DiveLogbook, csv_row: Dict[str, str]) -> DiveLogEntry:
        city, state, country = self._parse_location(csv_row.get("Location"))
        po2 = csv_row.get("O2 %").replace("%", "") if csv_row.get("O2 %") else 0
        airmix = logbook.add_airmix(DiveAirMix(o2=float(po2)/100))

        sampling_period, all_violations, dive_data = self._parse_dive_data(
            csv_row.get("Dive profile data", "[]"), airmix
        )
        dive = DiveLogEntry(
            diver = Diver(first_name=self._config.diver_first_name, last_name=self._config.diver_last_name),
            buddies = [Diver.from_full_name(csv_row.get("Dive buddy"))],
            location = DiveLogLocation(
                divesite = csv_row.get("Dive Site"),
                gps = (self._strip_unit(csv_row.get("lat")), self._strip_unit(csv_row.get("lng"))),
                locname = csv_row.get("Location"),
                city = city,
                state_province = state,
                country = country,
            ),
            stats = DiveLogStats(
                start_datetime = self._dive_datetime(csv_row.get("Date", ""), csv_row.get("Time in", "")),                
                maxdepth = self._strip_unit(csv_row.get("Max depth")),
                avgdepth = self._strip_unit(csv_row.get("Avg depth")),                
                mintemp = self._strip_unit(csv_row.get("Bottom temp")),
                pressure_in = self._strip_unit(csv_row.get("Pressure in")),
                pressure_out = self._strip_unit(csv_row.get("Pressure out")),
                violations = all_violations,
                airtemp = self._strip_unit(csv_row.get("Air temp")),
                surfacetemp = self._strip_unit(csv_row.get("Surface temp")),
            ),
            equipment = DiveEquipment(
                pdc = DiveComputer(
                    dive_num = int(csv_row.get("Dive #", 0)),
                    sampling_period = sampling_period, 
                    manufacturer = self._config.pdc_manufacturer,
                    type = self._config.pdc_type,
                    sn = self._config.pdc_sn,
                ),
                weight = int(csv_row.get("Weight")) if csv_row.get("Weight") else 0,
                gas = [DiveGas(
                    tank = DiveTank(
                        name = csv_row.get("Tank type"),
                        volume = int(self._strip_unit(csv_row.get("Tank volume"))) if csv_row.get("Tank volume") else 0,
                    ),
                    airmix = airmix,
                )],
            ),
            notes = csv_row.get(" Notes", ""),
            data = dive_data,
        )
        dive.stats.duration = timedelta(minutes = int(csv_row.get("Duration", 0)))

        logbook.add_dive(dive)
        return logbook

    def _add_temp_unit(self, value: Union[int, float]) -> str:
        return f"{value} °{self._config.unit_temperature.value}" if value is not None else None

    def _add_distance_unit(self, value: Union[int, float]) -> str:
        return f"{value} {self._config.unit_distance.value}" if value is not None else None

    def _add_pressure_unit(self, value: Union[int, float]) -> str:
        return f"{value} {self._config.unit_pressure.value}" if value is not None else None
 
    def _add_volume_unit(self, value: Union[int, float]) -> str:
        return f"{value} {self._config.unit_volume.value}" if value is not None else None

    def build_dive_log_row(self, entry: DiveLogEntry) -> Dict[str, str]:
        row = dict.fromkeys(self.get_fieldnames(), "")

        row["Dive #"] = entry.equipment.pdc.dive_num
        row["Date"] = entry.stats.start_datetime.strftime(self._date_fmt)
        if entry.location:
            row["Location"] = entry.location.locname
            row["Dive Site"] = entry.location.divesite
            row["lat"], row["lng"] = entry.location.gps
        if entry.buddies:
            row["Dive buddy"] = entry.buddies[0].strid()
        row["Time in"] = entry.stats.start_datetime.strftime(self._time_fmt)
        row["Time out"] = entry.stats.end_datetime.strftime(self._time_fmt)
        row["Duration"] = entry.stats.duration_min()
        row["Air temp"] = self._add_temp_unit(entry.stats.airtemp)
        row["Surface temp"] = self._add_temp_unit(entry.stats.surfacetemp)
        row["Bottom temp"] = self._add_temp_unit(entry.stats.mintemp)
        row["Max depth"] = self._add_distance_unit(entry.stats.maxdepth)
        row["Avg depth"] = self._add_distance_unit(entry.stats.avgdepth)
        row["Pressure in"] = self._add_pressure_unit(entry.stats.pressure_in)
        row["Pressure out"] = self._add_pressure_unit(entry.stats.pressure_out)
        row["O2 %"] = f"{entry.data[0].airmix.po2()}%"
        row["Weight"] = entry.equipment.weight
        row["Notes"] = entry.notes
        if entry.equipment.gas[0].tank:
            row["Tank volume"] = self._add_volume_unit(entry.equipment.gas[0].tank.volume)
            row["Tank type"] = entry.equipment.gas[0].tank.name

        row["Dive profile data"] = []
        for sample in entry.data:
            row["Dive profile data"].append([
                sample.timestamp_s,
                sample.depth,
                sample.temp,
                [viol.value for viol in sample.violations],
                sample.pressure or ""
            ])
        
        return row
