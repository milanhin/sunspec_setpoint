import logging
import voluptuous as vol

from datetime import timedelta
from homeassistant.core import HomeAssistant, State
from homeassistant.components.number import NumberEntity, PLATFORM_SCHEMA
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import UnitOfPower
from .const import(
    CONF_INJ_TARIFF_ENT_ID,
    CONF_PWR_IMP_ENT_ID,
    CONF_PWR_EXP_ENT_ID,
    CONF_PWR_PV_ENT_ID,
    INJ_CUTOFF_TARIFF,
    CONF_PWR_PV_MAX,
)   

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_INJ_TARIFF_ENT_ID): cv.string,
        vol.Required(CONF_PWR_IMP_ENT_ID): cv.string,
        vol.Required(CONF_PWR_EXP_ENT_ID): cv.string,
        vol.Required(CONF_PWR_PV_ENT_ID): cv.string,
        vol.Required(CONF_PWR_PV_MAX): vol.Coerce(int),
    }
)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    pwr_ent_ids = {}
    pwr_ent_ids[CONF_INJ_TARIFF_ENT_ID] = config[CONF_INJ_TARIFF_ENT_ID]
    pwr_ent_ids[CONF_PWR_IMP_ENT_ID] = config[CONF_PWR_IMP_ENT_ID]
    pwr_ent_ids[CONF_PWR_EXP_ENT_ID] = config[CONF_PWR_EXP_ENT_ID]
    pwr_ent_ids[CONF_PWR_PV_ENT_ID] = config[CONF_PWR_PV_ENT_ID]
    pwr_pv_max = config[CONF_PWR_PV_MAX]

    async_add_entities([SetpointNumber(hass, pwr_ent_ids, pwr_pv_max)])
    _LOGGER.info("SunSpec Setpoint platform was set up")
    
class SetpointNumber(NumberEntity):
    _attr_name = "test_input"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = 0
    _attr_native_max_value = 1000

    def __init__(
        self,
        hass: HomeAssistant,
        pwr_ent_ids: dict[str, str],
        pwr_pv_max: int,
    ) -> None:
        super().__init__()

        self.pwr_ent_ids = pwr_ent_ids
        self.hass = hass
        self.pwr_pv_max = pwr_pv_max

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        _LOGGER.info(f"Number setpoint changed to: {value}.")
    
    async def async_update(self) -> None:
        inj_tariff_state = self.hass.states.get(self.pwr_ent_ids[CONF_INJ_TARIFF_ENT_ID])
        pwr_import_state = self.hass.states.get(self.pwr_ent_ids[CONF_PWR_IMP_ENT_ID])
        pwr_export_state = self.hass.states.get(self.pwr_ent_ids[CONF_PWR_EXP_ENT_ID])
        pwr_PV_state = self.hass.states.get(self.pwr_ent_ids[CONF_PWR_PV_ENT_ID])

        # temporary type fix
        if inj_tariff_state == None: return None
        if pwr_import_state == None: return None
        if pwr_export_state == None: return None
        if pwr_PV_state == None: return None

        inj_tariff = self.convert_pwr_state_to_watt(inj_tariff_state)
        pwr_import = self.convert_pwr_state_to_watt(pwr_import_state)
        pwr_export = self.convert_pwr_state_to_watt(pwr_export_state)
        pwr_PV     = self.convert_pwr_state_to_watt(pwr_PV_state)

        setpoint = self.calc_setpoint(inj_tariff, pwr_import, pwr_export, pwr_PV)
        await self.async_set_native_value(setpoint)


    def calc_setpoint(self, inj_tariff: float, pwr_import: float, pwr_export: float, pwr_PV: float) -> float:
        max_PV_power = self.pwr_pv_max
        if inj_tariff >= INJ_CUTOFF_TARIFF:
            return round(max_PV_power)
        
        if pwr_import > 20 and inj_tariff < INJ_CUTOFF_TARIFF:
            sp = min(pwr_PV + pwr_import, max_PV_power)  # don't go above max power
            _LOGGER.info(f"PV setpoint sent during curtailing and importing from grid, PV: {pwr_PV} W, import: {pwr_import} W, export: {pwr_export} W, setpoint: {sp} W")
            return round(sp)

        else: # injecting during negative price
            sp = max(pwr_PV - pwr_export, 0)  # no negative power
            _LOGGER.info(f"PV setpoint sent during curtailing and exporting to grid, PV: {pwr_PV} W, import: {pwr_import} W, export: {pwr_export} W, setpoint: {sp} W")
            return round(sp)
    
    def convert_pwr_state_to_watt(self, state: State) -> float:
        value = float(state.state)
        unit = state.attributes.get("unit_of_measurement", None)
        if unit == "kW":
            return value * 1e3
        elif unit == "W":
            return value
        elif unit == "mW" or unit == "MW":
            return value / 1e3
        else:
            _LOGGER.error(f"Provided power entity {state.entity_id} has to known unit")
            return 0