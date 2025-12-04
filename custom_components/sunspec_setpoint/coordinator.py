import logging
import datetime
import asyncio
import sunspec2.modbus.client as client
from sunspec2.modbus.client import SunSpecModbusClientDeviceTCP

from typing import Any
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant import config_entries
from homeassistant.helpers.typing import ConfigType
from homeassistant.core import HomeAssistant, State
from .const import *

_LOGGER = logging.getLogger(__name__)

class PvCurtailingCoordinator(DataUpdateCoordinator):
    def __init__(
            self,
            hass: HomeAssistant,
            config_entry: config_entries.ConfigEntry,
    ) -> None:
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name="PV_Curtailing_coordinator",
            config_entry=None,
            update_interval=datetime.timedelta(seconds=UPDATE_INTERVAL),
        )
        self.setpoint_W: int | None = None          # Holds setpoint in Watt
        self.last_setpoint_W: int | None = None     # Last sent setpoint
        self.W: float | None = None                 # Holds power of inverter
        self.setpoint_pct: float | None = None      # Holds setpoint in percentage
        self.last_import_pwr: float | None = None   # Holds previous import pwr from DSMR
        self.last_export_pwr: float | None = None   # Holds previous export pwr from DSMR
        self.d = None                               # SunSpec client device
        self.WRtg: int | None = None                # Rated inverter power
        self.shutdown_flag: bool = False            # flag for disabling async_update_data()
        self.system_switch: bool = False            # System on or off, set by switch entity
        self.sleep: bool = False                    # Sleep mode on or off (when reconnecting)
        self.sunspec_setup_success: bool = False    # Indicate whether sunspec connection was successfully set up

        # SunSpec models and offsets
        self.measurands_mid: int | None = None
        self.controls_mid: int | None = None
        self.rating_mid: int | None = None
        self.W_offset: int | None = None
        self.WRtg_offset: int | None = None
        self.WMaxLimPct_offset: int | None = None

        # unpack config
        config = hass.data[DOMAIN][CONFIG]
        self.inj_trf_ent_id: str = config[CONF_INJ_TARIFF_STEP][CONF_INJ_TARIFF_ENT_ID]
        self.pwr_imp_ent_id: str = config[CONF_ENERGY_METER_STEP][CONF_PWR_IMP_ENT_ID]
        self.pwr_exp_ent_id: str = config[CONF_ENERGY_METER_STEP][CONF_PWR_EXP_ENT_ID]
        self.IP:             str = config[CONF_CONNECT_STEP][CONF_IP]
        self.PORT                = int(config[CONF_CONNECT_STEP][CONF_PORT])
        self.SLAVE_ID            = int(config[CONF_CONNECT_STEP][CONF_SLAVE_ID])
        self.brand: Brand        = Brand(str(config[CONF_USER_STEP][CONF_INVERTER_BRAND]).lower())
    
    async def _async_setup(self) -> None:
        """Set up coordinator"""

    def sunspec_setup(self) -> None:
        """Connect to SunSpec device for config through yaml"""

        _LOGGER.info("Setting up SunSpec connection")
        self.shutdown_flag = False
        # Connect to inverter with sunspec
        try:
            self.d = client.SunSpecModbusClientDeviceTCP(slave_id=self.SLAVE_ID, ipaddr=self.IP, ipport=self.PORT)
            self.d.scan()
        except Exception as e:
            _LOGGER.error(f"Failed to connect to SunSpec device, error: {e}")
            return
        
        # Check which models and offsets to use for read and write
        self.set_models_and_offsets(d=self.d)
        if None in [self.rating_mid, self.controls_mid, self.measurands_mid]:
            self.shutdown_flag = True
            return

        # Get power rating of inverter
        rating = self.offset_get(d=self.d, mid=self.rating_mid, trg_offset=self.WRtg_offset) # pyright: ignore[reportArgumentType]
        if rating != None:
            self.WRtg = int(rating)
        _LOGGER.info(f"Max rated power read from SunSpec device: {rating} W")

        # SunSpec setup successful
        self.sunspec_setup_success = True
    
    async def _async_update_data(self) -> dict[str, Any]:
        """Read, calculate setpoint and write every {UPDATE_INTERVAL} seconds"""
        if self.shutdown_flag or self.sleep:
            return {}
        
        if self.d == None:
            await self.try_reconnect()
            return {}

        # Read states from dependant sensors
        inj_tariff_state = self.hass.states.get(self.inj_trf_ent_id)
        pwr_import_state = self.hass.states.get(self.pwr_imp_ent_id)
        pwr_export_state = self.hass.states.get(self.pwr_exp_ent_id)

        # temporary type fix
        if (
            inj_tariff_state == None or
            pwr_import_state == None or
            pwr_export_state == None
        ):
            _LOGGER.error("An entity needed for this integration has no value")
            return {}

        # Exctract data from dependant sensors
        inj_tariff = float(inj_tariff_state.state)
        pwr_import = self.convert_pwr_state_to_watt(pwr_import_state)
        pwr_export = self.convert_pwr_state_to_watt(pwr_export_state)

        # Read inverter power through SunSpec
        if self.measurands_mid != None and self.W_offset != None:
            self.W = await self.offset_read(d=self.d, mid=self.measurands_mid, trg_offset=self.W_offset)
        else:
            return {}
        
        # Calculate setpoints for inverter power and send it to inverter
        if self.system_switch:
            if self.W != None and self.WRtg != None and pwr_export != None and pwr_import != None:
                self.setpoint_W = self.calc_setpoint_W(inj_tariff, pwr_import, pwr_export, self.W, pwr_rated=self.WRtg)
                self.setpoint_pct = self.calc_setpoint_pct(sp_W=self.setpoint_W, pwr_rated=self.WRtg)
                if not (self.last_setpoint_W == self.WRtg and self.setpoint_W == self.WRtg):  # Don't keep sending 100% setpoints       
                    await self.write_setpoint(d=self.d, sp_pct=self.setpoint_pct)
            else:
                _LOGGER.warning("Missing data for setpoint calculation, so no setpoint has been sent to the inverter")

        # If system switch is off, set sp to 100% and only send it once
        else:
            self.setpoint_W = self.WRtg
            self.setpoint_pct = 100
            if not (self.last_setpoint_W == self.WRtg):
                await self.write_setpoint(d=self.d, sp_pct=self.setpoint_pct)
        
        # Save last state of energy meter
        self.last_export_pwr = pwr_export
        self.last_import_pwr = pwr_import

        return {
            "setpoint_W": self.setpoint_W,
            "setpoint_pct": self.setpoint_pct,
        }
    
    def convert_pwr_state_to_watt(self, state: State) -> float | None:
        try:
            value = float(state.state)
        except:
            _LOGGER.warning(f"The state \"{state.state}\" of provided power entity {state.entity_id} could not be parsed as a number")
            return None
        unit = state.attributes.get("unit_of_measurement", None)
        if unit == "kW":
            return value * 1e3
        elif unit == "W":
            return value
        elif unit == "mW" or unit == "MW":
            return value / 1e3
        else:
            _LOGGER.error(f"Provided power entity {state.entity_id} has no known unit")
            return None
    
    def calc_setpoint_W(self, inj_tariff: float, pwr_import: float, pwr_export: float, pwr_PV: float, pwr_rated: float) -> int:
        # Only update setpoint if energy meter data has been updated
        if pwr_import == self.last_import_pwr and pwr_export == self.last_export_pwr and self.setpoint_W != None:
            sp = self.setpoint_W
            return round(sp)
        
        if inj_tariff >= INJ_CUTOFF_TARIFF:
            return round(pwr_rated)
        
        if pwr_import > 5 and inj_tariff < INJ_CUTOFF_TARIFF:
            sp = min(pwr_PV + pwr_import, pwr_rated)  # don't go above max power
            _LOGGER.info(f"PV setpoint calculated during curtailing and importing from grid, PV: {pwr_PV} W, import: {pwr_import} W, export: {pwr_export} W, setpoint: {sp} W")
            return round(sp)

        else: # injecting during negative price
            sp = max(pwr_PV - pwr_export, 0)  # no negative power
            _LOGGER.info(f"PV setpoint calculated during curtailing and exporting to grid, PV: {pwr_PV} W, import: {pwr_import} W, export: {pwr_export} W, setpoint: {sp} W")
            return round(sp)
    
    def calc_setpoint_pct(self, sp_W: int, pwr_rated: float) -> float:
        """Calc setpoint in percentage from setpoint in Watt"""
        sp_pct = (sp_W / pwr_rated) * 100
        return round(sp_pct, 2)  # percentage with 2 decimals
    
    async def offset_read(self, d, mid: int, trg_offset: int) -> float | None:
        """Read a point from the SunSpec device and return the scaled value"""
        for name, point in d.models[mid][0].points.items():
            if point.offset == trg_offset:
                try:
                    point.read()
                except Exception as e:
                    _LOGGER.error(f"Failed to read sunspec register, trying to reconnect now. Read error: {e}")
                    await self.try_reconnect()
                val = point.cvalue
                return val
        _LOGGER.error(f"SunSpec point with model id {mid} and offset {trg_offset} was not found and could not be read")
        return None
    
    def offset_get(self, d, mid: int, trg_offset: int) -> float | None:
        """Get a value from SunSpec device python instance, without reading"""
        for name, point in d.models[mid][0].points.items():
            if point.offset == trg_offset:
                val = point.cvalue
                return val
        _LOGGER.error(f"SunSpec point with model id {mid} and offset {trg_offset} was not found")
        return None
    
    def set_models_and_offsets(self, d) -> None:
        """Check which models are available on the SunSpec device"""
        # Measurands model:
        if DER_MEASURE_AC_MID in d.models:
            self.measurands_mid = DER_MEASURE_AC_MID
            self.W_offset = W_OFFSET_7XX
        elif INVERTER_SINGLE_PHASE_MID in d.models:
            self.measurands_mid = INVERTER_SINGLE_PHASE_MID
            self.W_offset = W_OFFSET_1XX
        elif INVERTER_SPLIT_PHASE_MID in d.models:
            self.measurands_mid = INVERTER_SPLIT_PHASE_MID
            self.W_offset = W_OFFSET_1XX
        elif INVERTER_THREE_PAHSE_MID in d.models:
            self.measurands_mid = INVERTER_THREE_PAHSE_MID
            self.W_offset = W_OFFSET_1XX
        else:
            _LOGGER.error("No measurands model was found on the SunSpec device, this integration will now freeze")
            self.shutdown_flag = True
            return
        
        # Control model:
        if DER_CTL_AC_MID in d.models:
            self.controls_mid = DER_CTL_AC_MID
            self.WMaxLimPct_offset = WMAXLIMPCT_OFFSET_7XX
        elif CONTROLS_MID in d.models:
            self.controls_mid = CONTROLS_MID
            self.WMaxLimPct_offset = WMAXLIMPCT_OFFSET_1XX
        else:
            _LOGGER.error("No controls model was found on the SunSpec device, this integration will now freeze")
            self.shutdown_flag = True
            return
        
        # Rating model:
        if DER_CAPACITY_MID in d.models:
            self.rating_mid = DER_CAPACITY_MID
            self.WRtg_offset = WRTG_OFFSET_7XX
        elif NAMEPLATE_MID in d.models:
            self.rating_mid = NAMEPLATE_MID
            self.WRtg_offset = WRTG_OFFSET_1XX
        else:
            _LOGGER.error("No ratings model was found on the SunSpec device, this integration will now freeze")
            self.shutdown_flag = True
            return
    
    async def write_setpoint(self, d, sp_pct: float) -> None:
        """Write a power setpoint to the SunSpec device, tailored to its brand"""
        for name, point in d.models[self.controls_mid][0].points.items():
            if point.offset == self.WMaxLimPct_offset:
                try:
                    point.read()
                except Exception as e:
                    _LOGGER.error(f"Failed to read sunspec register, trying to reconnect now. Read error: {e}")
                    await self.try_reconnect()

                # SMA
                if self.brand == Brand.SMA:
                    point.cvalue = sp_pct
                    try:
                        point.write()
                        _LOGGER.info(f"Setpoint sent to inverter: {sp_pct} %")
                        self.last_setpoint_W = self.setpoint_W
                    except Exception as e:
                        _LOGGER.error(f"Failed to write setpoint to inverter: {e}")
                        return
                
                #SolarEdge
                elif self.brand == Brand.SOLAREDGE:
                    self.last_setpoint_W = self.setpoint_W
                    _LOGGER.warning("Writing setpoints to this inverter is not yet implemented, but is planned for the future")
                else:
                    _LOGGER.error("Writing setpoint to this inverter brand is not implemented")
                    return
    
    async def try_reconnect(self) -> None:
        """Create reconnection loop while not connected"""
        is_connected = False
        try_counter = 0
        sleep_time = 60

        while not is_connected:
            self.sleep = True
            await asyncio.sleep(sleep_time)
            try:
                self.d = None
                self.d = await self.hass.async_add_executor_job(self.connect_and_scan)  # blocking call
                if len(self.d.models) == 0:
                    _LOGGER.error("Modbus client succesfully reconnected to slave, but no SunSpec models are available. This integration will now shut down, a manual restart of Home Assistant is required to resume.")
                    self.shutdown_flag = True
                    return
                is_connected = True
                self.sleep = False
                _LOGGER.info("Modbus client successfully reconnected to slave")
            except Exception as e:
                try_counter += 1
                if try_counter > 3:
                    sleep_time = 600
                _LOGGER.warning(f"Failed reconnecting to SunSpec device, reconnecting in {sleep_time} s")
    
    def connect_and_scan(self) -> SunSpecModbusClientDeviceTCP:
        d = client.SunSpecModbusClientDeviceTCP(slave_id=self.SLAVE_ID, ipaddr=self.IP, ipport=self.PORT)
        d.scan()
        return d