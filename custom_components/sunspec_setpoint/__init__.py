import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from .coordinator import PvCurtailingCoordinator

from .const import (
    DOMAIN,
    SMA,
    CONF_INJ_TARIFF_ENT_ID,
    CONF_INVERTER_BRAND,
    CONF_IP,
    CONF_PORT,
    CONF_PWR_EXP_ENT_ID,
    CONF_PWR_IMP_ENT_ID,
    CONF_SLAVE_ID,
    COORDINATOR,
)

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

DOMAIN_SCHEMA = vol.Schema(
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

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    # validate config
    domain_config = DOMAIN_SCHEMA(config[DOMAIN])

    # initialise coordinator
    pv_coordinator = PvCurtailingCoordinator(
        hass=hass,
        config=domain_config,
    )

    hass.data[DOMAIN] = pv_coordinator

    await async_load_platform(
        hass=hass,
        component="switch",
        platform=DOMAIN,
        discovered={},
        hass_config=config
    )

    await async_load_platform(
        hass=hass,
        component="sensor",
        platform=DOMAIN,
        discovered={},
        hass_config=config
    )
    return True