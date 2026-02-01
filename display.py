# https://learn.adafruit.com/making-a-pyportal-user-interface-displayio/the-full-code
# SPDX-FileCopyrightText: 2020 Richard Albritton for Adafruit Industries
# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
#
# SPDX-License-Identifier: MIT
import time
import board
import microcontroller
import displayio
import busio
import gc

import adafruit_adt7410
import adafruit_touchscreen
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text.label import Label
from adafruit_button import Button
from adafruit_pyportal import PyPortal
from analogio import AnalogIn

# -- additional imports -- #
import adafruit_connection_manager  # -- appear unused
import adafruit_requests  # -- appear unused
import rtc
from os import getenv

from adafruit_esp32spi import adafruit_esp32spi
from adafruit_esp32spi.adafruit_esp32spi_wifimanager import WiFiManager
import neopixel
from digitalio import DigitalInOut

# Get wifi details and more from a settings.toml file
# tokens used by this Demo: CIRCUITPY_WIFI_SSID, CIRCUITPY_WIFI_PASSWORD
# If you are using a board with pre-defined ESP32 Pins:
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)

# Secondary (SCK1) SPI used to connect to WiFi board on Arduino Nano Connect RP2040
if "SCK1" in dir(board):
    spi = busio.SPI(board.SCK1, board.MOSI1, board.MISO1)
else:
    spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

# ------------- WifI Connection ------------- #
status_pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2)
ssid = getenv("CIRCUITPY_WIFI_SSID")
password = getenv("CIRCUITPY_WIFI_PASSWORD")

wifi = WiFiManager(esp, ssid, password, status_pixel=status_pixel)
# ------------- Constants ------------- #

# Hex Colors
WHITE = 0xFFFFFF
RED = 0xFF0000
YELLOW = 0xFFFF00
GREEN = 0x00FF00
BLUE = 0x0000FF
PURPLE = 0xFF00FF
BLACK = 0x000000

SCREEN_WIDTH = 320
SCREEN_HEIGHT = 240

TABS_X = 0
TABS_Y = 40  # previously 40
TAB_BUTTON_WIDTH = int(SCREEN_WIDTH / 3)

# Default State
view_live = 1
icon = 1
icon_name = "Ruby"
button_mode = 1
switch_state = 0

TEXT_OUTPUT_MODE = False  # Set to True for console text output instead of display
TIME_API = "http://worldtimeapi.org/api/ip"
RP_URL = "https://api.radioparadise.com/api/nowplaying_list_v2022?chan=0&source=The%20Main%20Mix&player_id=&sync_id=chan_0&type=channel&mode=wip-channel&list_num=4"
WEATHER = "https://api.weather.gov/stations/KOWD/observations/latest"


# ------------- Functions ------------- #
# Backlight function
# Value between 0 and 1 where 0 is OFF, 0.5 is 50% and 1 is 100% brightness.
def set_backlight(val):
    val = max(0, min(1.0, val))
    try:
        board.DISPLAY.auto_brightness = False
    except AttributeError:
        pass
    board.DISPLAY.brightness = val


# Set visibility of layer
def layerVisibility(state, layer, target):
    try:
        if state == "show":
            time.sleep(0.1)
            layer.append(target)
        elif state == "hide":
            layer.remove(target)
    except ValueError:
        pass


# This will handle switching Images and Icons
def set_image(group, filename):
    """Set the image file for a given goup for display.
    This is most useful for Icons or image slideshows.
        :param group: The chosen group
        :param filename: The filename of the chosen image
    """
    print("Set image to ", filename)
    if group:
        group.pop()
    if not filename:
        return  # we're done, no icon desired
    image = displayio.OnDiskBitmap(filename)
    image_sprite = displayio.TileGrid(image, pixel_shader=image.pixel_shader)
    group.append(image_sprite)


# return a reformatted string with word wrapping using PyPortal.wrap_nicely
def text_box(target, top, string, max_chars):
    # text = pyportal.wrap_nicely(string, max_chars)
    text = string
    new_text = ""
    test = ""

    for w in text:
        new_text += "\n" + w
        test += "M\n"

    text_height = Label(font, text="M", color=0x03AD31)
    text_height.text = test  # Odd things happen without this
    glyph_box = text_height.bounding_box
    target.text = ""  # Odd things happen without this
    target.y = int(glyph_box[3] / 2) + top
    target.text = new_text


def get_Temperature(source):
    if source:  # Only if we have the temperature sensor
        celsius = source.temperature
    else:  # No temperature sensor
        celsius = microcontroller.cpu.temperature
    return (celsius * 1.8) + 32


def get_time():
    """ return the time to display """
    # Get the struct_time
    time_now = time.localtime()
    return f"{time_now.tm_hour:02d}:{time_now.tm_min:02d}"


def get_json(json_url: str, error_msg: str):
    """ simplify getting the URL
    """
    gc.collect()
    # print("Using Testing path")
    attempts = 0
    while attempts < 5:
        try:
            response = wifi.get(json_url)
            return response.json()
        except (TimeoutError,
                RuntimeError,
                adafruit_requests.OutOfRetries) as e:
            if attempts == 4:
                import supervisor
                supervisor.reload()
            print(f"attempt {attempts} for {error_msg}: {e}")
            attempts += 1
            time.sleep(2)


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
        elif response_type == "simple":
            return (f"{item['title']} {item['artist']} {item['album']}")
        else:
            return item
    return "Error"

def get_fahrenheit(celsius: float) -> float:
    """ convert temperature to fahrenheit"""
    return (celsius * 9/5) + 32

def get_weather() -> str:
    """ retrieve the weather"""
    response = get_json(WEATHER, "get weather")
    if response:
        try:
            temp = response['properties']['temperature']['value']
            temp_float = float(temp)
            temp_far = get_fahrenheit(temp_float)
            result = f"{temp_far:.1f} F {temp} C"
            return result
        except (KeyError, TypeError) as e:
            print(f"value error {e}")
    return "failed to get weather"


last_time = 0
interval_info = [0, time.time(), [10, 30]]

def interval_sequence() -> tuple[bool, int]:
    """ advance frame by set number of seconds
        return the next interval
        
        interval_info[0] is the current interval
        interval_info[1] is the last time
        :rtype: tuple[bool, int]
    """
    
    def next_interval(current_interval, last_interval):
        if current_interval == last_interval-1:
            return 0
        return current_interval + 1
    
    global interval_info
    interval_list = interval_info[2]
    delta = time.time() - interval_info[1]
    if delta > interval_list[interval_info[0]]:
        interval_info[0] = next_interval(interval_info[0], len(interval_list))
        interval_info[1] = time.time()
        return True, interval_info[0]
    return False, interval_info[0]
        
    # current interval is interval


def interval_elapsed(interval: int = 30):
    """ check if interval elapsed """
    global last_time
    delta = time.time() - last_time
    if delta > interval:
        last_time = time.time()
        return True
    return False

# ------------- Inputs and Outputs Setup ------------- #
light_sensor = AnalogIn(board.LIGHT)
try:
    # attempt to init. the temperature sensor
    i2c_bus = busio.I2C(board.SCL, board.SDA)
    adt = adafruit_adt7410.ADT7410(i2c_bus, address=0x48)
    adt.high_resolution = True
except ValueError:
    # Did not find ADT7410. Probably running on Titano or Pynt
    adt = None

# ------------- Screen Setup ------------- #
# pyportal = PyPortal()
# pyportal.set_background("/images/loading.bmp")  # Display an image until the loop starts

if not TEXT_OUTPUT_MODE:
    # Touchscreen setup  
    display = board.DISPLAY
    set_backlight(0.3)
    ts = adafruit_touchscreen.Touchscreen(
        board.TOUCH_XL, board.TOUCH_XR,
        board.TOUCH_YD, board.TOUCH_YU,
        calibration=((5200, 59000), (5800, 57000)),
        size=(320, 240))


# ------------- Display Groups ------------- #
splash = displayio.Group()  # The Main Display Group
view1 = displayio.Group()  # Group for View 1 objects
view2 = displayio.Group()  # Group for View 2 objects
view3 = displayio.Group()  # Group for View 3 objects

# ------------- Setup for Images ------------- #
if not TEXT_OUTPUT_MODE:
    bg_group = displayio.Group()
    splash.append(bg_group) 
    set_image(bg_group, "/images/BGimage.bmp")

icon_group = displayio.Group()
icon_group.x = 180
icon_group.y = 120
icon_group.scale = 1
view2.append(icon_group)

# ---------- Text Boxes ------------- #
# Set the font and preload letters
# source https://github.com/olikraus/u8g2/tree/master/tools/font/bdf
#
font = bitmap_font.load_font("/fonts/Helvetica-Bold-16.bdf")
font.load_glyphs(b"abcdefghjiklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890- ()")
font_large = bitmap_font.load_font("/fonts/helvB24.bdf")
font_large.load_glyphs(b"abcdefghjiklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890- ()")
font_mid = bitmap_font.load_font("/fonts/luBS19.bdf")
font_mid.load_glyphs(b"abcdefghjiklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890- ()")
# Text Label Objects
time_data = Label(font_mid, text="Time Data", color=0xE39300)
time_data.x = TABS_X + 2
time_data.y = TABS_Y + 10
view1.append(time_data)

music_data = Label(font_mid, text="Music Data", color=0xFFFFFF)
music_data.x = TABS_X + 2
music_data.y = TABS_Y
view2.append(music_data)

music_rating = Label(font_large, text="0", color=0xFFFFFF, 
    padding_right=8,
    padding_top=8,
    padding_bottom=8,
    padding_left=8,)
music_rating.anchor_point = (1.0, 1.0)
music_rating.anchored_position = (SCREEN_WIDTH - 20, SCREEN_HEIGHT - 20)
view2.append(music_rating)

sensors_label = Label(font, text="Data View", color=0x03AD31)
sensors_label.x = TABS_X
sensors_label.y = TABS_Y
view3.append(sensors_label)

sensor_data = Label(font, text="Data View", color=0x03AD31)
sensor_data.x = TABS_X + 16  # Indents the text layout
sensor_data.y = 150
view3.append(sensor_data)

# ---------- Display Buttons ------------- #
# This group will make it easy for us to read a button press later.
buttons = []

# Main User Interface Buttons
button_view1 = Button(
    x=0,  # Start at furthest left
    y=0,  # Start at top
    width=TAB_BUTTON_WIDTH,  # Calculated width
    height=TABS_Y,  # Static height
    label="Time",
    label_font=font,
    label_color=0xFF7E00,
    fill_color=0x5C5B5C,
    outline_color=0x767676,
    selected_fill=0x1A1A1A,
    selected_outline=0x2E2E2E,
    selected_label=0x525252,
)
buttons.append(button_view1)  # adding this button to the buttons group

button_view2 = Button(
    x=TAB_BUTTON_WIDTH,  # Start after width of a button
    y=0,
    width=TAB_BUTTON_WIDTH,
    height=TABS_Y,
    label="Music",
    label_font=font,
    label_color=0xFF7E00,
    fill_color=0x5C5B5C,
    outline_color=0x767676,
    selected_fill=0x1A1A1A,
    selected_outline=0x2E2E2E,
    selected_label=0x525252,
)
buttons.append(button_view2)  # adding this button to the buttons group

button_view3 = Button(
    x=TAB_BUTTON_WIDTH * 2,  # Start after width of 2 buttons
    y=0,
    width=TAB_BUTTON_WIDTH,
    height=TABS_Y,
    label="Sensor",
    label_font=font,
    label_color=0xFF7E00,
    fill_color=0x5C5B5C,
    outline_color=0x767676,
    selected_fill=0x1A1A1A,
    selected_outline=0x2E2E2E,
    selected_label=0x525252,
)
buttons.append(button_view3)  # adding this button to the buttons group


# Add main buttons to the splash Group
for b in buttons:
    splash.append(b)


# pylint: disable=global-statement
def switch_view(what_view):
    global view_live
    if what_view == 1:
        button_view1.selected = False
        button_view2.selected = True
        button_view3.selected = True
        layerVisibility("hide", splash, view2)
        layerVisibility("hide", splash, view3)
        layerVisibility("show", splash, view1)
    elif what_view == 2:
        # global icon
        button_view1.selected = True
        button_view2.selected = False
        button_view3.selected = True
        layerVisibility("hide", splash, view1)
        layerVisibility("hide", splash, view3)
        layerVisibility("show", splash, view2)
    else:
        button_view1.selected = True
        button_view2.selected = True
        button_view3.selected = False
        layerVisibility("hide", splash, view1)
        layerVisibility("hide", splash, view2)
        layerVisibility("show", splash, view3)

    # Set global button state
    view_live = what_view
    print("View {view_num:.0f} On".format(view_num=what_view))


# pylint: enable=global-statement

# Set variables and startup states
button_view1.selected = False
button_view2.selected = True
button_view3.selected = True
# button_switch.label = "OFF"
# button_switch.selected = True

layerVisibility("show", splash, view1)
layerVisibility("hide", splash, view2)
layerVisibility("hide", splash, view3)

# Update out Labels with display text.
# text_box(
#     time_data,
#     TABS_Y + 5,
#     get_time(),
#     30,
# )

# text_box(feed2_label, TABS_Y, "Tap on the Icon button to meet a new friend.", 18)
# text_box(
#     sensors_label,
#     TABS_Y + 20,
#     "This screen can display sensor readings and tap Sound to play a WAV file.",
#     28,
# )


def update_weather_panel():
    weather_text = get_weather()
    time_data.text = get_time() + "\n" + weather_text

def update_rating(rating):
    """ update the rating """
    if rating < 3:
        music_rating.color = 0xFF0000  # red
        music_rating.background_color = 0xFFFF00
    elif rating < 4:
        music_rating.color = 0xFF8000  # orange
        music_rating.background_color = 0xFF0000
    elif rating < 5:
        music_rating.color = 0xFFFF00  # yellow
        music_rating.background_color = 0x0000EE
    elif rating < 6:
        music_rating.color = 0x00FF00  # green
        music_rating.background_color = 0x0000FF
    elif rating < 7:
        music_rating.color = 0x0000FF  # blue
        music_rating.background_color = 0xFFFF00
    elif rating < 8:
        music_rating.color = 0x4B0082  # indigo
        music_rating.background_color = 0xFFFF00
    elif rating < 9:
        music_rating.color = 0x8000FF  # violet
        music_rating.background_color = 0xFFFF00
    music_rating.text = str(rating)


def update_music() -> None:
    music_info = get_music("json")

    if TEXT_OUTPUT_MODE:
        # Console text output mode
        if music_info:
            print("=" * 50)
            print(f"Title:  {music_info['title']}")
            print(f"Artist: {music_info['artist']}")
            print(f"Album:  {music_info['album']} ({music_info['year']})")
            print(f"Rating: {music_info['listener_rating']}")
            print("=" * 50)
        else:
            print("Music loading error")
    else:
        # PyPortal display output mode
        text_height = Label(font, text="M", color=0x03AD31)
        text_height.text = "M\n"  # Odd things happen without this
        glyph_box = text_height.bounding_box
        music_data.text = ""  # Odd things happen without this
        music_data.y = int(glyph_box[3] / 2) + TABS_Y + 20
        music_data.color = 0xFF7E00
        if music_info:
            music_data.text = (
                music_info['title'] + "\n" +
                music_info['artist'] + "\n" +
                music_info['album'] + " "  + music_info['year']
                )
            update_rating(music_info['listener_rating'])
        else:
            music_data.text = "Loading error"

# ------------- Initialization ------------- #
if not TEXT_OUTPUT_MODE:
    board.DISPLAY.root_group = splash
last_time = time.time()
set_time()
update_weather_panel()

# ------------- Code Loop ------------- #
while True:
    touch = ts.touch_point
    light = light_sensor.value

    sensor_data.text = "Touch: {}\nLight: {}\nTemp: {:.0f}°F".format(
        touch, light, get_Temperature(adt)
        )

    #time_data.text = "Time {}".format(get_time())

    interval_advance, next_panel = interval_sequence()
    if interval_advance:
        if next_panel == 0:
            update_weather_panel()
            switch_view(1)
        elif next_panel == 1:
            update_music()
            switch_view(2)

    # Only update music data at specified interval (default 30 seconds)
    # if interval_elapsed(30):
    #     update_music()
    #     if view_live != 2 and not TEXT_OUTPUT_MODE:
    #         switch_view(2)
        # else:
        #     switch_view(1)

#    time.sleep(0.1)  # Short sleep for responsive UI



    # ------------- Handle Button Press Detection  ------------- #
    if touch and not TEXT_OUTPUT_MODE:  # Only do this if the screen is touched
        # loop with buttons using enumerate() to number each button group as i
        for i, b in enumerate(buttons):
            if b.contains(touch):  # Test each button to see if it was pressed
                print("button{} pressed".format(i))
                if i == 0 and view_live != 1:  # only if view1 is visible
                    # pyportal.play_file(soundTab)
                    switch_view(1)
                    while ts.touch_point:
                        pass
                if i == 1 and view_live != 2:  # only if view2 is visible
                    # pyportal.play_file(soundTab)
                    update_music()
                    switch_view(2)
                    while ts.touch_point:
                        pass
                if i == 2 and view_live != 3:  # only if view3 is visible
                    # pyportal.play_file(soundTab)
                    switch_view(3)
                    while ts.touch_point:
                        pass
                # if i == 3:  EtC

