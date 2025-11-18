DOMAIN = "sunspec_setpoint"

CONF_INJ_TARIFF_ENT_ID = "injection_tariff_entity_id"
CONF_PWR_IMP_ENT_ID = "power_import_entity_id"
CONF_PWR_EXP_ENT_ID = "power_export_entity_id"
CONF_PWR_PV_MAX = "power_PV_max"  # [W]
CONF_INVERTER_BRAND = "inverter_brand"
CONF_IP = "ip_address"
CONF_PORT = "port"
CONF_SLAVE_ID = "slave_id"

INJ_CUTOFF_TARIFF = 50  # [€/MwH]

# Supported brands
SMA = "sma"

# SunSpec model IDs
NAMEPLATE_MID = 120
INVERTER_SINGLE_PHASE_MID = 101
INVERTER_SPLIT_PHASE_MID = 102
INVERTER_THREE_PAHSE_MID = 103
CONTROLS_MID = 123

# SunSpec offsets
WRTG_OFFSET = 3  # rated nominal power of inverter
W_OFFSET = 14  # generating power of inverter