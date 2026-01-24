# https://learn.adafruit.com/making-a-pyportal-user-interface-displayio/the-full-code
# SPDX-FileCopyrightText: 2020 Richard Albritton for Adafruit Industries
#
# SPDX-License-Identifier: MIT
import time
import board
import microcontroller
import displayio
import busio
import neopixel

import adafruit_adt7410
import adafruit_touchscreen
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text.label import Label
from adafruit_button import Button
from adafruit_pyportal import PyPortal
from analogio import AnalogIn

# -- additional imports -- #
# import adafruit_connection_manager  # -- appear unused
# import adafruit_requests.  # -- appear unused
import rtc
from os import getenv

# ------------- Constants ------------- #

# Hex Colors
WHITE = 0xFFFFFF
RED = 0xFF0000
YELLOW = 0xFFFF00
GREEN = 0x00FF00
BLUE = 0x0000FF
PURPLE = 0xFF00FF
BLACK = 0x000000

# Default Label styling
TABS_X = 0
TABS_Y = 15

# Default button styling:
BUTTON_HEIGHT = 40
BUTTON_WIDTH = 80

# Default State
view_live = 1
icon = 1
icon_name = "Ruby"
button_mode = 1
switch_state = 0

# For add ons
TESTING = False
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


# Helper for cycling through a number set of 1 to x.
def numberUP(num, max_val):
    num += 1
    if num <= max_val:
        return num
    else:
        return 1


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
    text = pyportal.wrap_nicely(string, max_chars)
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
    attempt = 0
    while attempt < 3:
        try:
            # print("Fetching json from", json_url)
            response = pyportal.network.requests.get(json_url)
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
    return


last_time = time.time()
set_time()

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
pyportal = PyPortal()
pyportal.set_background("/images/loading.bmp")  # Display an image until the loop starts
# NeoPixel will be initialized later with WiFi setup

# Touchscreen setup  
display = board.DISPLAY
# display.rotation = 270  # [ Rotate 270 ]
# screen_width = 240
# screen_height = 320
# reverse orientation
screen_width = 320
screen_height = 240
set_backlight(0.3)

# We want three buttons across the top of the screen
TAB_BUTTON_Y = 0
TAB_BUTTON_HEIGHT = 40  # previously 40
TAB_BUTTON_WIDTH = int(screen_width / 3)

# We want two big buttons at the bottom of the screen
# BIG_BUTTON_HEIGHT = int(screen_height / 3.2)
# BIG_BUTTON_WIDTH = int(screen_width / 2)
# BIG_BUTTON_Y = int(screen_height - BIG_BUTTON_HEIGHT)

# Initializes the display touch screen area
ts = adafruit_touchscreen.Touchscreen(
    board.TOUCH_YD,
    board.TOUCH_YU,
    board.TOUCH_XR,
    board.TOUCH_XL,
    calibration=((5200, 59000), (5800, 57000)),
    size=(screen_width, screen_height),
)

# ------------- WifI Connection ------------- #
ssid = getenv("CIRCUITPY_WIFI_SSID")
password = getenv("CIRCUITPY_WIFI_PASSWORD")

print("Connecting to WiFi...")

try:
    pyportal.network.connect()
    print("Connected to WiFi!")
except (RuntimeError, ConnectionError) as e:
    print(f"Failed to connect to WiFi: {e}")
    raise



# ------------- Display Groups ------------- #
splash = displayio.Group()  # The Main Display Group
view1 = displayio.Group()  # Group for View 1 objects
view2 = displayio.Group()  # Group for View 2 objects
view3 = displayio.Group()  # Group for View 3 objects

# ------------- Setup for Images ------------- #
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
font = bitmap_font.load_font("/fonts/Helvetica-Bold-16.bdf")
font.load_glyphs(b"abcdefghjiklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890- ()")

# Text Label Objects
time_data = Label(font, text="Time Data", color=0xE39300)
time_data.x = TABS_X + 2
time_data.y = TABS_Y
view1.append(time_data)

music_data = Label(font, text="Music Data", color=0xFFFFFF)
music_data.x = TABS_X + 2
music_data.y = TABS_Y
view2.append(music_data)

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
    height=TAB_BUTTON_HEIGHT,  # Static height
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
    height=TAB_BUTTON_HEIGHT,
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
    height=TAB_BUTTON_HEIGHT,
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


# Add all of the main buttons to the splash Group
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

# Set veriables and startup states
button_view1.selected = False
button_view2.selected = True
button_view3.selected = True
# button_switch.label = "OFF"
# button_switch.selected = True

layerVisibility("show", splash, view1)
layerVisibility("hide", splash, view2)
layerVisibility("hide", splash, view3)

# Update out Labels with display text.
text_box(
    time_data,
    TABS_Y + 20,
    "Time {}.".format(get_time()),
    30,
)

# text_box(feed2_label, TABS_Y, "Tap on the Icon button to meet a new friend.", 18)

text_box(
    sensors_label,
    TABS_Y + 20,
    "This screen can display sensor readings and tap Sound to play a WAV file.",
    28,
)

# ------------- Initialization ------------- #
board.DISPLAY.root_group = splash



# ------------- Code Loop ------------- #
while True:
    touch = ts.touch_point
    light = light_sensor.value
    sensor_data.text = "Touch: {}\nLight: {}\nTemp: {:.0f}°F".format(
        touch, light, get_Temperature(adt)
        )
    time_data.text = "Time {}.".format(get_time())

    # Only update music data at specified interval (default 30 seconds)
    if interval_elapsed(30):
        music_data.text = get_music("simple")

    time.sleep(0.1)  # Short sleep for responsive UI



    # ------------- Handle Button Press Detection  ------------- #
    if touch:  # Only do this if the screen is touched
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
                    switch_view(2)
                    while ts.touch_point:
                        pass
                if i == 2 and view_live != 3:  # only if view3 is visible
                    # pyportal.play_file(soundTab)
                    switch_view(3)
                    while ts.touch_point:
                        pass
                # if i == 3:  EtC

