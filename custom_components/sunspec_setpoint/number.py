import logging
import voluptuous as vol

from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.components.number import NumberEntity, PLATFORM_SCHEMA
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import UnitOfPower
from .const import(
    CONF_INJ_TARIFF_ENT_ID,
    CONF_PWR_IMP_ENT_ID,
    CONF_PWR_EXP_ENT_ID,
    CONF_PWR_PV_ENT_ID,
    INJ_CUTOFF_TARIFF,
)   

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_INJ_TARIFF_ENT_ID): str,
        vol.Required(CONF_PWR_IMP_ENT_ID): str,
        vol.Required(CONF_PWR_EXP_ENT_ID): str,
        vol.Required(CONF_PWR_PV_ENT_ID): str
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

    async_add_entities([SetpointNumber(hass, pwr_ent_ids)])
    _LOGGER.info("SunSpec Setpoint platform was set up")
    
class SetpointNumber(NumberEntity):
    _attr_name = "test_input"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = 0
    _attr_native_max_value = 1000

    def __init__(self, hass: HomeAssistant, pwr_ent_ids: dict[str, str]) -> None:
        super().__init__()

        self.pwr_ent_ids = pwr_ent_ids
        self.hass = hass

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        _LOGGER.info(f"Number setpoint changed to: {value}.")
    
    async def async_update(self) -> None:
        inj_tariff_state = self.hass.states.get(self.pwr_ent_ids[CONF_INJ_TARIFF_ENT_ID])
        pwr_import_state = self.hass.states.get(self.pwr_ent_ids[CONF_PWR_IMP_ENT_ID])
        pwr_export_state = self.hass.states.get(self.pwr_ent_ids[CONF_PWR_EXP_ENT_ID])
        pwr_PV_state = self.hass.states.get(self.pwr_ent_ids[CONF_PWR_PV_ENT_ID])

        inj_tariff = float(inj_tariff_state.state) # pyright: ignore[reportOptionalMemberAccess]
        pwr_import = float(pwr_import_state.state) # pyright: ignore[reportOptionalMemberAccess]
        pwr_export = float(pwr_export_state.state) # pyright: ignore[reportOptionalMemberAccess]
        pwr_PV     = float(pwr_PV_state.state)     # pyright: ignore[reportOptionalMemberAccess]

        setpoint = self.calc_setpoint(inj_tariff, pwr_import, pwr_export, pwr_PV)
        await self.async_set_native_value(setpoint)


    def calc_setpoint(self, inj_tariff, pwr_import, pwr_export, pwr_PV) -> float:
        max_PV_power = 4000  # assumed max (needs to be fetched from sunspec)
        if inj_tariff >= INJ_CUTOFF_TARIFF:
            return round(max_PV_power)
        
        if pwr_import > 0 and inj_tariff < INJ_CUTOFF_TARIFF:
            sp = min(pwr_PV + pwr_import, max_PV_power)  # don't go above max power
            return round(sp)

        else: # injecting during negative price
            sp = max(pwr_PV - pwr_export, 0)  # no negative power
            return round(sp)