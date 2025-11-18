import logging
import voluptuous as vol

from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import SensorEntity, PLATFORM_SCHEMA
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.const import UnitOfPower
from .coordinator import PvCurtailingCoordinator
from .const import(
    CONF_INJ_TARIFF_ENT_ID,
    CONF_PWR_IMP_ENT_ID,
    CONF_PWR_EXP_ENT_ID,
    CONF_PWR_PV_MAX,
    CONF_INVERTER_BRAND,
    CONF_IP,
    CONF_PORT,
    CONF_SLAVE_ID,
    SMA,
)

_LOGGER = logging.getLogger(__name__)

def validate_brand(brand_str: str):
    """
    Check if configured inverter brand is in the supported brands list
    Names of brands are in lower case for easier comparison 
    """
    supported_brands = [
    SMA,
    ]

    if brand_str.lower() not in supported_brands:
        raise vol.Invalid("The configured inverter brand is not supported by this integration")
    return brand_str

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_INJ_TARIFF_ENT_ID): cv.string,
        vol.Required(CONF_PWR_IMP_ENT_ID): cv.string,
        vol.Required(CONF_PWR_EXP_ENT_ID): cv.string,
        vol.Required(CONF_INVERTER_BRAND): vol.All(str, validate_brand),
        vol.Required(CONF_IP): cv.string,
        vol.Required(CONF_PORT): vol.Coerce(int),
        vol.Required(CONF_SLAVE_ID): vol.Coerce(int),
    }
)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    _LOGGER.info("Setup of sunspec setpoint was initialised")
    # initialise coordinator
    pv_coordinator = PvCurtailingCoordinator(
        hass=hass,
        config=config,
    )

    await hass.async_add_executor_job(pv_coordinator.sunspec_setup)  # Connect with SunSpec device (blocking call)

    async_add_entities([SetpointSensor(coordinator=pv_coordinator), InverterPowerSensor(coordinator=pv_coordinator)])
    _LOGGER.info("SunSpec Setpoint platform was set up")

class SetpointSensor(CoordinatorEntity, SensorEntity): # pyright: ignore[reportIncompatibleVariableOverride]
    """Sensor to store and show power setpoint for inverter"""

    _attr_name = "PV setpoint"
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: PvCurtailingCoordinator) -> None:
        super().__init__(coordinator=coordinator)
        self.coordinator = coordinator
    
    @property
    def native_value(self) -> float | None: # pyright: ignore[reportIncompatibleVariableOverride]
        """Return setpoint so it gets stored by HA in the sensor"""
        return self.coordinator.setpoint_W

class InverterPowerSensor(CoordinatorEntity, SensorEntity): # pyright: ignore[reportIncompatibleVariableOverride]
    """Sensor to store and show production power of inverter"""

    _attr_name = "Inverter power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: PvCurtailingCoordinator) -> None:
        super().__init__(coordinator=coordinator)
        self.coordinator = coordinator

    @property
    def native_value(self) -> float | None: # pyright: ignore[reportIncompatibleVariableOverride]
        """Return power of inverter so it gets storen by HA in the sensor"""
        return self.coordinator.W