import voluptuous as vol
import logging

from typing import Any
from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import selector, EntitySelector, EntityFilterSelectorConfig
from .const import *

_LOGGER = logging.getLogger(__name__)

def map_default_ID(brand: Brand) -> int | None:
    """Map inverter brand to default slave ID"""
    if brand in SLAVE_ID_MAP:
        return SLAVE_ID_MAP[brand]
    else:
        return None

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_INVERTER_BRAND): selector({
            "select": {
                "options": [brand.value for brand in Brand]
            }
        })
    }
)

ENERGY_METER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PWR_IMP_ENT_ID): EntitySelector(EntityFilterSelectorConfig(domain="sensor")),
        vol.Required(CONF_PWR_EXP_ENT_ID): EntitySelector(EntityFilterSelectorConfig(domain="sensor")),
    }
)

INJ_TARIFF_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_INJ_TARIFF_ENT_ID): EntitySelector(EntityFilterSelectorConfig(domain="sensor")),
    }
)

class PvCurtailmentConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for the PV Curtailment integration setup"""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Invoked when a user initiates a config flow via the UI
        In this step, the inverter brand is selected
        """
        errors = {}
        self.data = {}
        if user_input is not None:
            self.brand = Brand(user_input[CONF_INVERTER_BRAND])
            self.data[CONF_USER_STEP] = user_input
            return await self.async_step_connect()
        
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)
    
    async def async_step_connect(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Configure IP, port and modbus slave ID"""
        CONNECT_SCHEMA = vol.Schema(
            {
                vol.Required(CONF_IP): str,
                vol.Required(CONF_PORT): vol.Coerce(int),
                vol.Required(CONF_SLAVE_ID, default=map_default_ID(brand=self.brand)): vol.Coerce(int),
            }
        )
        errors = {}

        if user_input is not None:
            try:
                validated_schema = CONNECT_SCHEMA(user_input)
            except Exception as e:
                errors["base"] = "invalid_input"
            
            if not errors:
                self.data[CONF_CONNECT_STEP] = user_input
                return await self.async_step_energy_meter()
        
        return self.async_show_form(step_id="connect", data_schema=CONNECT_SCHEMA, errors=errors)
    
    async def async_step_energy_meter(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Configure energy meter entity IDs"""
        errors = {}

        if user_input is not None:
            self.data[CONF_ENERGY_METER_STEP] = user_input
            return await self.async_step_inj_tariff()
        
        return self.async_show_form(step_id="energy_meter", data_schema=ENERGY_METER_SCHEMA, errors=errors)
    
    async def async_step_inj_tariff(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Configure SDAC injection tariff entity ID"""
        errors = {}

        if user_input is not None:
            self.data[CONF_PRICES_STEP] = user_input
            return self.async_create_entry(title=DOMAIN, data=self.data)
        
        return self.async_show_form(step_id="inj_tariff", data_schema=INJ_TARIFF_SCHEMA)