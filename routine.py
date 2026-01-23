import time
from os import getenv

TESTING = True
TIME_API = "http://worldtimeapi.org/api/ip"
RP_URL = "https://api.radioparadise.com/api/nowplaying_list_v2022?chan=0&source=The%20Main%20Mix&player_id=&sync_id=chan_0&type=channel&mode=wip-channel&list_num=4"

if not TESTING:
    import adafruit_connection_manager
    import adafruit_requests
    import board
    import busio
    import neopixel
    import rtc
    from digitalio import DigitalInOut

    # Use these imports for adafruit_esp32spi version 11.0.0 and up.
    # Note that frozen libraries may not be up to date.
    # import adafruit_esp32spi
    # from adafruit_esp32spi.wifimanager import WiFiManager
    from adafruit_esp32spi import adafruit_esp32spi
    from adafruit_esp32spi.adafruit_esp32spi_wifimanager import WiFiManager

    # Get wifi details and more from a settings.toml file
    # tokens used by this Demo: CIRCUITPY_WIFI_SSID, CIRCUITPY_WIFI_PASSWORD
    ssid = getenv("CIRCUITPY_WIFI_SSID")
    password = getenv("CIRCUITPY_WIFI_PASSWORD")

    print("ESP32 local time")

    # If you are using a board with pre-defined ESP32 Pins:
    esp32_cs = DigitalInOut(board.ESP_CS)
    esp32_ready = DigitalInOut(board.ESP_BUSY)
    esp32_reset = DigitalInOut(board.ESP_RESET)

    # If you have an externally connected ESP32:
    # esp32_cs = DigitalInOut(board.D9)
    # esp32_ready = DigitalInOut(board.D10)
    # esp32_reset = DigitalInOut(board.D5)

    # Secondary (SCK1) SPI used to connect to WiFi board on Arduino Nano Connect RP2040
    if "SCK1" in dir(board):
        spi = busio.SPI(board.SCK1, board.MOSI1, board.MISO1)
    else:
        spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
    esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

    """Use below for Most Boards"""
    status_pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2)
    wifi = WiFiManager(esp, ssid, password, status_pixel=status_pixel)


def alt_get_json(json_url: str, error_msg: str):
    """ for testing on the mac
    """
    import json 
    import requests
    while True:
        try:
            # print(f"Fetching json {json_url}")
            response = requests.get(json_url)
            return response.json()
        except OSError as e:
            print(f"Failed to {error_msg}, retrying {e}\n")
            return

def get_json(json_url: str, error_msg: str):
    """ simplify getting the URL
    """
    attempt = 0
    if TESTING:
        return alt_get_json(json_url, error_msg)
    while attempt < 3:
        try:
            # print("Fetching json from", json_url)
            response = wifi.get(json_url)
            return response.json()
        except OSError as e:
            print(f"Failed to {error_msg} retrying {e}\n")
            attempt += 1
            continue


def set_time():
    """ Routine to set the time
    """

    json = get_json(TIME_API, "get time")
    current_time = json["datetime"]
    the_date, the_time = current_time.split("T")
    year, month, mday = (int(x) for x in the_date.split("-"))
    the_time = the_time.split(".")[0]
    hours, minutes, seconds = (int(x) for x in the_time.split(":"))
    year_day = json["day_of_year"]
    week_day = json["day_of_week"]
    is_dst = json["dst"]

    now = time.struct_time((year, month, mday, hours, minutes, seconds, week_day, year_day, is_dst))
    print(now)
    if not TESTING:
        the_rtc = rtc.RTC()
        the_rtc.datetime = now


def get_music(response_type: str = 'str') -> str:
    """ retrieve the music and return a string
    """
    response = get_json(RP_URL, "get music")
    if response:
        val = response["song"]
        item = val[0]
        if response_type == "str":
            return (f"Song:{item['title']} Artist:{item['artist']} Album:{item['album']} Year:{item['year']} Rating:{item['listener_rating']}")
        else:
            return item
    return

def get_time() -> str:
    """ return the time to display """
    # Get the struct_time
    time_now = time.localtime()
    return f"{time_now.tm_hour:02d}:{time_now.tm_min:02d}"



set_time()

while True:
    if TESTING:
        print("\n\n" + "-"*10 + "\n")
    print(get_time())
    print(get_music())
    if TESTING:
        print("\n" + "-"*10 + "\n")
        exit()
    time.sleep(30)
