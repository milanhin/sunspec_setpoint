from enum import StrEnum

DOMAIN = "sunspec_setpoint"
COORDINATOR = "coordinator"

CONF_INJ_TARIFF_ENT_ID = "injection_tariff_entity_id"
CONF_PWR_IMP_ENT_ID = "power_import_entity_id"
CONF_PWR_EXP_ENT_ID = "power_export_entity_id"
CONF_INVERTER_BRAND = "inverter_brand"
CONF_IP = "ip_address"
CONF_PORT = "port"
CONF_SLAVE_ID = "slave_id"

INJ_CUTOFF_TARIFF = 200  # [€/MwH] (200 as temporary testing value)
UPDATE_INTERVAL = 10  # [s]

# Supported brands
class Brand(StrEnum):
    """
    All supported brands should be configured here
    Names of brands are in lower case for easier comparison
    """
    SMA = "sma"
    SOLAREDGE = "solaredge"

# SunSpec model IDs
    # 100 series
NAMEPLATE_MID = 120
INVERTER_SINGLE_PHASE_MID = 101
INVERTER_SPLIT_PHASE_MID = 102
INVERTER_THREE_PAHSE_MID = 103
CONTROLS_MID = 123
    # 700 series
DER_MEASURE_AC_MID = 701
DER_CAPACITY_MID = 702
DER_CTL_AC_MID = 704

# SunSpec offsets
    # 100 series
WRTG_OFFSET_1XX = 3  # rated nominal power of inverter
W_OFFSET_1XX = 14  # AC power
WMAXLIMPCT_OFFSET_1XX = 5  # Set power output to specified level
    # 700 series
WRTG_OFFSET_7XX = 2
W_OFFSET_7XX = 10
WMAXLIMPCT_OFFSET_7XX = 15