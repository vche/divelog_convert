from asyncio import PidfdChildWatcher
from logging import Logger, DEBUG
from tracemalloc import take_snapshot
from numpy import isin
import xmltodict
from dicttoxml import dicttoxml
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path
from datetime import datetime, timedelta

from divelog_convert.formater import (
    DiveSuit,
    Diver,
    DiveAirMix,
    DiveComputer,
    DiveEquipment,
    DiveLogbook,
    DiveLogLocation,
    DiveLogData,
    DiveLogStats,
    DiveLogEntry,
    DiveLogFormater,
    DiveTank,
    DiveUnitTemperature,
    DiveViolation
)


def datetime_from_iso(datestr: str, logger: Logger) -> datetime:
    # Try to convert from iso string with then without timezone
    try:
        return datetime.strptime(datestr, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        try:
            return datetime.strptime(datestr, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            logger.warning(f"Couldn't parse datetime, not in ISO format: {datestr}")
            return None


def list_append_uniq(value_list, value):
    # Append a value to an array only if it is not already here
    if value not in value_list:
        value_list.append(value)


class XmlDiveLogFormater(DiveLogFormater):

    def read_dives(self, filename: Path) -> Tuple[int, DiveLogbook]:
        with open(filename, "r") as dive_file:
            self.log.info(f"Reading dives read from {filename}")
            dive_dict = xmltodict.parse(dive_file.read())
            errors, logbook = self.parse_xml_dict(dive_dict)
            self.log.info(f"{len(logbook.dives)} dives read from {filename}, {errors} errors")
            return logbook

    def write_dives(self, filename: Path, logbook: DiveLogbook):
        if filename.suffix != self.ext:
            filename = filename.with_suffix(self.ext)

        with open(filename, "w") as dive_file:
            self.log.info(f"Writing {len(logbook.dives)} dives written to {filename}")
            dive_dict = self.build_xml_dict(logbook)
            xml_data = dicttoxml(dive_dict)
            dive_file.write(xml_data)

    @abstractmethod
    def parse_xml_dict(self, xml_dict: Dict[str, Any]) -> List[DiveLogEntry]:
        ...

    @abstractmethod
    def build_xml_dict(self, entry: DiveLogEntry) -> Dict[str, Any]:
        ...


class UddfDiveLogFormater(XmlDiveLogFormater):
    @property
    def ext(self):
        return ".uddf"

    @property
    def name(self):
        return "uddf"


    @property
    def name(self):
        return "diviac"

    def __init__(self, config=None):
        super().__init__(config)
        self._ref_dict = {}

    def _parse_owner(self, logbook: DiveLogbook, owner_dict: Dict[str, Any]):
        if owner_dict:
            logbook.diver = Diver(
                first_name=owner_dict['personal']['firstname'] or self._config.diver_first_name,
                last_name=owner_dict['personal']['lastname'] or self._config.diver_last_name,
            )

            equipment = owner_dict.get('equipment')
            if equipment:
                for pdc in equipment.get('divecomputer', []):
                    pdc_obj = DiveComputer(
                        manufacturer = pdc.get("manufacturer"),
                        type = pdc.get("name"),
                        sn = pdc.get("serialnumber")
                    )
                    logbook.pdcs[pdc_obj.uuid()] = pdc_obj
                    self._ref_dict[pdc['@id']] = pdc_obj

                for suit in equipment.get('suit', []):
                    suit_obj = DiveSuit(name = suit.get("name"), type = suit.get("suittype"))
                    logbook.suits[suit_obj.uuid()] = suit_obj
                    self._ref_dict[suit['@id']] = suit_obj

                for tank in equipment.get('tank', []):
                    tank_obj = DiveTank(name = tank.get("name"), volume = tank.get("tankvolume"))
                    logbook.tanks[tank_obj.uuid()] = tank_obj
                    self._ref_dict[tank['@id']] = tank_obj

    def _parse_buddies(self, logbook: DiveLogbook, buddies: Optional[Dict[Union[str, Any], List[Dict[str, Any]]]]):
        if buddies:
            buddies_list = buddies if isinstance(buddies, list) else [buddies]
            for bud in buddies_list:
                if 'firstname' in bud['personal'] and 'lastname' in bud['personal']:
                    bud_obj = Diver(first_name=bud['personal']['firstname'], last_name=bud['personal']['lastname'])
                    logbook.buddies[bud_obj.uuid()] = bud_obj
                    self._ref_dict[bud['@id']] = bud_obj

    def _parse_locations(self, logbook: DiveLogbook, locs: Optional[Dict[str, Any]]):
        if locs:
            loc_list = locs if isinstance(locs, list) else [locs]
            for loc in loc_list:
                geo = loc.get("geography", {})
                addr = geo.get("address", {})
                loc_obj = DiveLogLocation(
                    divesite = loc.get("name"),
                    gps = (geo.get("latitude"), geo.get("longitude")),
                    locname = geo.get("location"),
                    city = addr.get("city"),
                    state_province = addr.get("province"),
                    street = addr.get("street"),
                    country = addr.get("country"),
                )
                logbook.locations[loc_obj.uuid()] = loc_obj
                self._ref_dict[loc['@id']] = loc_obj

    def _parse_gas(self, logbook: DiveLogbook, gas: Optional[Dict[Union[str, Any], List[Dict[str, Any]]]]):
        if gas:
            gas_list = gas if isinstance(gas, list) else [gas]
            for gas in gas_list:
                gas_obj = DiveAirMix(
                    name=gas['name'],
                    o2=float(gas.get('o2', 0.0)),
                    n2=float(gas.get('n2', 0.0)),
                    h2=float(gas.get('h2', 0.0)),
                    he=float(gas.get('he', 0.0)),
                    ar=float(gas.get('ar', 0.0)),
                )
                logbook.airmix[gas_obj.uuid()] = gas_obj
                self._ref_dict[gas['@id']] = gas_obj

    def _parse_dives(self, logbook: DiveLogbook, dives: Optional[Dict[Union[str, Any], List[Dict[str, Any]]]]):
        groups = dives.get('repetitiongroup')
        groups = groups if isinstance(groups, list) else [groups]
        errors = 0
        for group in groups:
            dives = group['dive'] if isinstance(group['dive'], list) else [group['dive']]            
            for dive in dives:
                try:
                    self._parse_dive(logbook, dive)
                except KeyError as e:
                    self.log.error(f"Cannot parse dive: {e}")
                    self.exception(e)
                    errors = errors + 1
        return errors

    def _process_link(self, logbook: DiveLogbook, dive: DiveLogEntry, links: Union[Dict[str,Any], List[Dict[str,Any]]]):
        if links:
            links_list = links if isinstance(links, list) else [links]
        else:
            links_list = []
        
        for link in links_list:
            ref = link.get("@ref")
            target = self._ref_dict.get(ref)
            
            if target:
                if isinstance(target, Diver):
                    list_append_uniq(dive.buddies, target)
                elif isinstance(target, DiveLogLocation):
                    dive.location = target
                elif isinstance(target, DiveComputer):
                    list_append_uniq(dive.equipment.pdc, target)
                elif isinstance(target, DiveSuit):
                    list_append_uniq(dive.equipment.suit, target)
                elif isinstance(target, DiveAirMix):
                    list_append_uniq(dive.equipment.airmixes, target)
                elif isinstance(target, DiveTank):
                    list_append_uniq(dive.equipment.tanks, target)

    def _parse_dive_data(
        self, logbook: DiveLogbook, dive_samples: Dict[str, Any]
    ) -> Tuple[int, List[DiveViolation], List[DiveLogData]]:
        #  TODO: simplify, too complex
        dive_data = []
        all_violations = set()
        last_ts = None
        global_period = 0
        last_datapoint = None
        for dive_sample in dive_samples.get("waypoint", []):
            # Compute violation in this sample and overall during the dive
            violations = []
            alarms = dive_sample.get("alarm", [])
            if alarms and not isinstance(alarms, list):
                alarms = [alarms]
            for elt in alarms:
                if elt == "ascent":
                    viol = DiveViolation.ASCENT
                elif elt == "deco":
                    viol = DiveViolation.DECO
                elif elt == "surface":
                    viol = DiveViolation.SURFACE
                else:
                    viol = DiveViolation.ERROR
                violations.append(viol)
                all_violations.add(viol)

            # Compute sampling period and timestamp
            if dive_sample.get('divetime') is not None:
                ts = float(dive_sample['divetime'])
            elif last_datapoint:
                ts = last_datapoint.timestamp_s
            else:
                ts = 0.0
            if last_ts:
                global_period += (ts - last_ts)
            last_ts = ts

            # If no depth, didn't change, use previous datapoint
            if dive_sample.get('depth') is not None:
                depth = float(dive_sample['depth'])
            elif last_datapoint:
                depth = last_datapoint.depth
            else:
                depth = 0.0

            # Temperature from kelvins to configured unit
            temp = dive_sample.get('temperature')
            if temp is not None:
                temp = self._config.unit_temperature.from_unit(
                    DiveUnitTemperature.KELVIN, float(dive_sample['temperature'])
                )
            elif last_datapoint:
                temp = last_datapoint.temp
            else:
                temp = 0
            
            # If no airmix (should be in the first sample), use previous sample,or from logbook or default to air
            airmix_link = dive_sample.get('switchmix')
            if airmix_link:
                airmix = self._process_link(logbook, dive_entry, airmix_link)
            elif last_datapoint:
                airmix = last_datapoint.airmix
            elif logbook.airmix:
                airmix = list(logbook.airmix.values())[0]
            else:
                airmix = DiveAirMix()
                logbook.add_airmix(airmix)

            float(dive_sample['tankpressure']) if dive_sample.get('tankpressure') is not None else None,
            tank_pressure = dive_sample.get('tankpressure')
            if tank_pressure is not None:
                tank_pressure = dive_sample['tankpressure']
            elif last_datapoint:
                tank_pressure = last_datapoint.pressure
            else:
                tank_pressure = None

            # Create datapoint
            last_datapoint = DiveLogData(
                timestamp_s = ts,
                depth = depth,
                temp = temp,
                airmix= airmix,
                pressure = tank_pressure,
                violations = violations,
            )
            dive_data.append(last_datapoint)
        sampling_period = round(global_period/(len(dive_data)-1)) if len(dive_data)>0 else 0
        return sampling_period, list(all_violations), dive_data


    def _parse_dive(self, logbook: DiveLogbook, dive: Dict[str, Any]):
        equipment_used = dive["informationbeforedive"].get("equipmentused", {})
        equipment_used.update(dive["informationafterdive"].get("equipmentused", {}))
        tankdata = dive.get("tankdata", {})
        sampling_period, all_violations, dive_data = self._parse_dive_data(logbook, dive.get("samples", {}))
        notes = equipment_used.get("notes", {})
        if "para" in notes:
            notes = notes["para"]

        if len(dive_data) > 0 and dive_data[0].temp is not None:
            surfacetemp = self._config.unit_temperature.to_unit(DiveUnitTemperature.KELVIN, dive_data[0].temp)
        else:
            surfacetemp = None

        dive_entry = DiveLogEntry(
            dive_num = dive["informationbeforedive"]["divenumber"],
            diver = logbook.diver,
            stats = DiveLogStats(
                start_datetime = datetime_from_iso(dive["informationbeforedive"].get("datetime"), self.log),
                maxdepth = dive["informationafterdive"].get("greatestdepth", 0.0),
                avgdepth = dive["informationafterdive"].get("averagedepth", 0.0),
                mintemp = self._config.unit_temperature.from_unit(
                    DiveUnitTemperature.KELVIN, dive["informationafterdive"].get("lowesttemperature")
                ),
                pressure_in = float(tankdata.get("tankpressurebegin", 0.0)),
                pressure_out = float(tankdata.get("tankpressureend", 0.0)),
                violations = all_violations,
                airtemp = self._config.unit_temperature.from_unit(
                    DiveUnitTemperature.KELVIN, dive["informationbeforedive"].get("airtemperature")
                ),
                surfacetemp = surfacetemp,
                visibility = dive["informationafterdive"].get("visibility", 0.0),
            ),
            equipment = DiveEquipment(weight = int(equipment_used.get("leadquantity", 0))),
            notes = notes,
            rating = equipment_used.get("rating", {}).get("ratingvalue"),
            data = dive_data,
        )
        dive_entry.stats.duration = timedelta(seconds = int(dive["informationafterdive"].get("diveduration", 0)))
        dive_entry.equipment.pdc.sampling_period = sampling_period

        # Update the dive with the references
        self._process_link(logbook, dive_entry, dive["informationbeforedive"].get("link"))
        self._process_link(logbook, dive_entry, dive["informationafterdive"].get("link"))
        self._process_link(logbook, dive_entry, dive["informationbeforedive"].get("equipmentused", {}).get("link"))
        self._process_link(logbook, dive_entry, dive["informationafterdive"].get("equipmentused", {}).get("link"))
        self._process_link(logbook, dive_entry, tankdata.get("link"))

        logbook.add_dive(dive_entry)

    def parse_xml_dict(self, xml_dict: Dict[str, Any]) -> Tuple[int, DiveLogbook]:
        logbook = DiveLogbook()
        udf_data = xml_dict['uddf']
        self._parse_owner(logbook, udf_data.get('diver', {}).get('owner'))
        self._parse_buddies(logbook, udf_data.get('diver', {}).get('buddy'))
        self._parse_locations(logbook, udf_data.get('divesite', {}).get("site"))
        self._parse_gas(logbook, udf_data.get('gasdefinitions', {}).get("mix"))
        errors = self._parse_dives(logbook, udf_data.get("profiledata"))

        print(logbook)
        return errors, logbook

    def build_xml_dict(self, logbook: DiveLogbook) -> Dict[str, Any]:
        return {}
