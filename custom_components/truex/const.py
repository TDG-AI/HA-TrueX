"""Constants for the TrueX Smart Home integration."""

from __future__ import annotations

from enum import StrEnum
import logging

from homeassistant.const import Platform

DOMAIN = "truex"
LOGGER = logging.getLogger(__package__)

# Config flow keys
CONF_CLIENT_ID = "client_id"
CONF_SECRET = "secret"
CONF_API_URL = "api_url"
CONF_SCHEMA = "schema"
CONF_USERNAME = "username"
CONF_TOKEN_INFO = "token_info"
CONF_UID = "uid"

# Default API URL
DEFAULT_API_URL = "https://openapi-cube.tdgiotengine.com"

# Signals
TRUEX_DISCOVERY_NEW = "truex_discovery_new"
TRUEX_HA_SIGNAL_UPDATE_ENTITY = "truex_entry_update"

# Polling interval in seconds
POLL_INTERVAL = 30

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]


class DPCode(StrEnum):
    """Data Point Codes used by Tuya devices.

    https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
    """

    # Switch
    SWITCH = "switch"
    SWITCH_1 = "switch_1"
    SWITCH_2 = "switch_2"
    SWITCH_3 = "switch_3"
    SWITCH_4 = "switch_4"
    SWITCH_5 = "switch_5"
    SWITCH_6 = "switch_6"
    SWITCH_7 = "switch_7"
    SWITCH_8 = "switch_8"
    SWITCH_LED = "switch_led"
    SWITCH_LED_1 = "switch_led_1"
    SWITCH_LED_2 = "switch_led_2"

    # Light
    BRIGHT_VALUE = "bright_value"
    BRIGHT_VALUE_V2 = "bright_value_v2"
    COLOUR_DATA = "colour_data"
    COLOUR_DATA_V2 = "colour_data_v2"
    TEMP_VALUE = "temp_value"
    TEMP_VALUE_V2 = "temp_value_v2"
    WORK_MODE = "work_mode"

    # Climate
    MODE = "mode"
    TEMP_SET = "temp_set"
    TEMP_CURRENT = "temp_current"
    FAN_SPEED_ENUM = "fan_speed_enum"
    HUMIDITY_CURRENT = "humidity_current"
    HUMIDITY_SET = "humidity_set"

    # Sensor
    VA_TEMPERATURE = "va_temperature"
    VA_HUMIDITY = "va_humidity"
    CUR_POWER = "cur_power"
    CUR_VOLTAGE = "cur_voltage"
    CUR_CURRENT = "cur_current"
    ADD_ELE = "add_ele"
    BATTERY_PERCENTAGE = "battery_percentage"
    BATTERY_STATE = "battery_state"
    PM25_VALUE = "pm25_value"
    CO2_VALUE = "co2_value"
    CH2O_VALUE = "ch2o_value"
    VOC_VALUE = "voc_value"
    BRIGHT_STATE = "bright_state"
    BRIGHT_VALUE_SENSOR = "bright_value"
    TEMP_CURRENT_SENSOR = "temp_current"
    HUMIDITY_VALUE = "humidity_value"

    # Binary sensor
    DOORCONTACT_STATE = "doorcontact_state"
    PIR = "pir"
    WATERSENSOR_STATE = "watersensor_state"
    SMOKE_SENSOR_STATUS = "smoke_sensor_status"
    SMOKE_SENSOR_STATE = "smoke_sensor_state"
    GAS_SENSOR_STATUS = "gas_sensor_status"
    GAS_SENSOR_STATE = "gas_sensor_state"
    CO_STATE = "co_state"
    CO_STATUS = "co_status"

    # Cover
    CONTROL = "control"
    PERCENT_CONTROL = "percent_control"
    POSITION = "position"
    PERCENT_STATE = "percent_state"

    # General
    CHILD_LOCK = "child_lock"
    COUNTDOWN_1 = "countdown_1"
    FAULT = "fault"


class DeviceCategory(StrEnum):
    """Tuya device categories."""

    # Switch / Socket
    KG = "kg"
    """Switch"""
    CZ = "cz"
    """Socket"""
    PC = "pc"
    """Power strip"""
    DLQ = "dlq"
    """Circuit breaker"""

    # Light
    DJ = "dj"
    """Light"""
    XDD = "xdd"
    """Ceiling light"""
    FWD = "fwd"
    """Ambiance light"""
    DC = "dc"
    """String lights"""
    DD = "dd"
    """Strip lights"""
    TGKG = "tgkg"
    """Dimmer switch"""
    TGQ = "tgq"
    """Dimmer"""
    FSD = "fsd"
    """Ceiling fan light"""

    # Sensor
    WSDCG = "wsdcg"
    """Temperature and humidity sensor"""
    PM25 = "pm2.5"
    """PM2.5 detector"""
    CO2BJ = "co2bj"
    """CO2 detector"""
    LDCG = "ldcg"
    """Luminance sensor"""
    ZNDB = "zndb"
    """Smart electricity meter"""
    HJJCY = "hjjcy"
    """Air quality monitor"""

    # Climate
    KT = "kt"
    """Air conditioner"""
    WK = "wk"
    """Thermostat"""
    KTKZQ = "ktkzq"
    """AC controller"""

    # Binary sensor
    MCS = "mcs"
    """Contact sensor"""
    PIR_CAT = "pir"
    """Motion sensor"""
    SJ = "sj"
    """Water leak detector"""
    YWBJ = "ywbj"
    """Smoke alarm"""
    RQBJ = "rqbj"
    """Gas alarm"""
    COBJ = "cobj"
    """CO detector"""

    # Cover
    CL = "cl"
    """Curtain"""
    CLKG = "clkg"
    """Curtain switch"""
    CKMKZQ = "ckmkzq"
    """Garage door opener"""
    MC = "mc"
    """Door/window controller"""
