import attr
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from enum import Enum


class DiveViolation(Enum):
    ASCENT="Ascent rate violation"
    DECO="Decompression violation"


class DiveUnitDistance(Enum):
    METER="m"
    FEET="ft"


class DiveUnitTemperature(Enum):
    CELSIUS="C"
    FAHRENHEIT="F"
    KERVIN="K"


class DiveUnitPressure(Enum):
    BAR="bar"
    PSI="psi"


class DiveUnitVolume(Enum):
    LITER="L"
    CUBICFEET="CF"


class DiveLogItem:
    def uuid(self):
        return f"{self.__class__.__name__}-{self.strid()}".replace(" ","_").lower() if self.strid() else None
    
    def strid(self):
        return ""

@attr.s
class DiveLogConfig:
    # TODO load defaults from config file
    diver_first_name = attr.ib(default="Vivien", type=str)
    diver_last_name = attr.ib(default="Chene", type=str)
    unit_distance = attr.ib(default=DiveUnitDistance.METER, type=DiveUnitDistance)
    unit_temperature = attr.ib(default=DiveUnitTemperature.CELSIUS, type=DiveUnitTemperature)
    unit_pressure = attr.ib(default=DiveUnitPressure.BAR, type=DiveUnitPressure)
    unit_volume = attr.ib(default=DiveUnitVolume.LITER, type=DiveUnitVolume)
    pdc_manufacturer = attr.ib(default="Uwatec", type = str)
    pdc_type = attr.ib(default="SmartZ", type=str)
    pdc_sn = attr.ib(default="123456", type=str)
 
    diviac_date_format_ddmmyy = attr.ib(default=True, type=bool)
    diviac_time_format_24 = attr.ib(default=True, type=bool)

    def get_diviac_date_format(self):
        return "%d-%m-%Y" if self.diviac_date_format_ddmmyy else "%m-%d-%Y"

    def get_diviac_time_format(self):
        return "%H:%M" if self.diviac_time_format_24 else "%I:%M%p"

    def get_diviac_date_time_format(self):
        date_fmt = "%d-%m-%Y" if self.diviac_date_format_ddmmyy else "%m-%d-%Y"
        time_fmt = "%H:%M" if self.diviac_time_format_24 else "%I:%M%p"
        return f"{self.get_diviac_date_format()} {self.get_diviac_time_format()}"

@attr.s
class DiveLogLocation(DiveLogItem):
    divesite = attr.ib(default=None, type=str)
    gps = attr.ib(default=None, type = tuple[float, float])
    locname = attr.ib(default=None, type=str)
    city = attr.ib(default=None, type=str)
    state_province = attr.ib(default=None, type=str)
    street = attr.ib(default=None, type=str)
    country = attr.ib(default=None, type=str)

    def __attrs_post_init__(self):
        if not self.divesite and self.locname:
            self.divesite = self.locname

    def strid(self):
        return self.divesite

@attr.s
class Diver(DiveLogItem):
    first_name = attr.ib(type = str)
    last_name = attr.ib(default = "", type = str)

    @classmethod
    def from_full_name(cls, full_name: str):
        tokens = full_name.split(" ")
        return cls(first_name=tokens[0], last_name=" ".join(tokens[1:]))

    def strid(self):
        return f"{self.first_name} {self.last_name}" if self.first_name and self.last_name else ""


@attr.s
class DiveSuit(DiveLogItem):
    name = attr.ib(type = str)
    type = attr.ib(default = None, type = str)

    def strid(self):
        return self.name


@attr.s
class DiveAirMix(DiveLogItem):
    name = attr.ib(default = None, type = str)
    o2 = attr.ib(default = 0.21, type = float)
    n2 = attr.ib(default = 0.79, type = float)
    he = attr.ib(default = 0.0, type = float)
    ar = attr.ib(default = 0.0, type = float)
    h2 = attr.ib(default = 0.0, type = float)

    def is_air(self) -> bool:
        return abs(0.21 - self.o2 ) < 0.001

    def po2(self):
        return int(self.o2 * 100)

    def __attrs_post_init__(self):
        # If only o2 is specified, fill n2
        if not self.n2:
            mix = self.h2 + self.ar + self.he
            self.n2 = 1 - (self.o2 + mix)
        # If no name is specified, build one, either "air" or based on o2 level
        if not self.name:
            if self.is_air():
                self.name = "air"
            else:
                self.name = "o2-{int(self.02*100)}"
        

    def strid(self):
        return self.name


@attr.s
class DiveTank(DiveLogItem):
    name = attr.ib(type = str)
    volume = attr.ib(default = 0, type = int)

    def strid(self):
        return f"{self.name} {self.volume}" if self.name and self.volume else ""


@attr.s
class DiveComputer(DiveLogItem):
    dive_num = attr.ib(default=1, type = int)
    manufacturer = attr.ib(default="", type = str)
    firmware = attr.ib(default="", type = str)
    type = attr.ib(default=None, type=str)
    sn = attr.ib(default=None, type=str)
    sampling_period = attr.ib(default=1, type=int)

    def strid(self):
        return f"{self.type} {self.sn}" if self.type and self.sn else ""


@attr.s
class DiveLogStats:
    start_datetime = attr.ib(default=None, type=datetime)
    end_datetime = attr.ib(default=None, type=datetime)
    maxdepth = attr.ib(default=0.0, type = float)
    avgdepth = attr.ib(default=0.0, type = float)
    maxo2 = attr.ib(default=0.0, type = float)
    po2 = attr.ib(default=0.0, type = float)
    mintemp = attr.ib(default=0.0, type = float)
    pressure_in = attr.ib(default=0.0, type = float)
    pressure_out = attr.ib(default=0.0, type = float)
    violations = attr.ib(factory=list, type=list[DiveViolation])
    airtemp = attr.ib(default=0.0, type = float)
    surfacetemp = attr.ib(default=0.0, type = float)

    @property
    def duration(self) -> timedelta:
        return self.end_datetime - self.start_datetime

    @duration.setter
    def duration(self, value: timedelta):
        self.end_datetime = self.start_datetime + value

    def duration_hms(self) -> Tuple[int, int, int]:
        hours, rem = divmod(self.duration.total_seconds(), 3600)
        minutes, seconds = divmod(rem, 60)
        return int(hours), int(minutes), int(seconds)

    def duration_min(self) -> int:
        return int(self.duration.total_seconds()/60)


@attr.s
class DiveGas:
    tank = attr.ib(default=None, type=DiveTank)
    airmix = attr.ib(factory=DiveAirMix, type=DiveAirMix)

@attr.s
class DiveEquipment:
    pdc = attr.ib(factory=DiveComputer, type=DiveComputer)
    suit = attr.ib(default=None, type=DiveSuit)
    weight = attr.ib(default=0, type=int)
    gas = attr.ib(factory=list, type=list[DiveGas])


@attr.s
class DiveLogData:
    timestamp_s = attr.ib(default=0.0, type = float)
    depth = attr.ib(default=0.0, type = float)
    temp = attr.ib(default=0.0, type = float)
    pressure = attr.ib(default=0.0, type = float)
    airmix = attr.ib(factory=DiveAirMix, type = DiveAirMix)
    violations = attr.ib(factory=list, type=list[DiveViolation])


@attr.s
class DiveLogEntry:
    location = attr.ib(factory=DiveLogLocation, type=DiveLogLocation)
    diver = attr.ib(factory=list, type=Diver)
    buddies = attr.ib(factory=list, type=list[Diver])
    stats = attr.ib(factory=DiveLogStats, type=DiveLogStats)
    equipment = attr.ib(factory=DiveEquipment, type=DiveEquipment)
    data = attr.ib(factory=list, type=list[DiveLogData])
    notes = attr.ib(default="", type=str)
    rating = attr.ib(default=0, type=int)


def add_dive_item(item_list: Dict[str, DiveLogItem], item: DiveLogItem):
    if not item or not item.uuid():
        return None
    uuid = item.uuid()
    if uuid not in item_list:
        item_list[uuid] = item
    return item_list[uuid]


@attr.s
class DiveLogbook:
    diver = attr.ib(default=None, type=dict[Diver])
    locations = attr.ib(factory=dict, type=dict[DiveLogLocation])
    buddies = attr.ib(factory=dict, type=dict[Diver])
    airmix = attr.ib(factory=dict, type=dict[DiveAirMix])
    suits = attr.ib(factory=dict, type=dict[DiveSuit])
    tanks = attr.ib(factory=dict, type=dict[DiveTank])
    pdcs = attr.ib(factory=dict, type=dict[DiveComputer])

    dives = attr.ib(factory=list, type=list[DiveLogEntry])

    def add_airmix(self, item: DiveAirMix):
        return add_dive_item(self.airmix, item)

    def add_dive(self, dive: DiveLogEntry):
        # Add items to the main logbook list if not already there
        buddies = []
        for buddy in dive.buddies:
            new_buddy = add_dive_item(self.buddies, buddy)
            if new_buddy:
                buddies.append(new_buddy)
            dive.buddies = buddies

        dive.location = add_dive_item(self.locations, dive.location)
        dive.equipment.pdc = add_dive_item(self.pdcs, dive.equipment.pdc)
        if dive.equipment.suit:
            dive.equipment.suit = add_dive_item(self.suits, dive.location)

        for gas in dive.equipment.gas:
            gas.airmix = self.add_airmix(gas.airmix)
            if gas.tank:
                gas.tank = add_dive_item(self.tanks, gas.tank)

        self.dives.append(dive)


class DiveLogFormater(ABC):

    @property
    @abstractmethod
    def ext(self):
        ...

    @property
    @abstractmethod
    def name(self):
        ...

    def __init__(self, config=None):
        self._config = config or DiveLogConfig()
        self.log = logging.getLogger(self.__class__.__name__)
    
    def __repr__(self):
        return f"'{self.name}' ({self.ext})"

    @abstractmethod
    def read_dives(self, filename: Path) -> DiveLogbook:
        ...

    @abstractmethod
    def write_dives(self, filename: Path, logbook: DiveLogbook):
        ...
