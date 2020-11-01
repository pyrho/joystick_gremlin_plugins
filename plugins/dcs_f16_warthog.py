import gremlin      # 'Coz it's a Joystick Gremlin module!
import time         # Used for delays between actions in some functions
import threading    # Threading allows the longer functions to be non-blocking
import logging      # Used for logging events and debugging
from gremlin.user_plugin import *
from gremlin.input_devices import keyboard, macro

"""
Constants
"""
mode_global = ModeVariable("Global", "gl")

# I can't figure out how to make this mode thing work. Fuck it.
#mode_alt = ModeVariable("Alternative", "alt")

# Helper for actual throttle button
THROTTLE_BUTTONS = {
    "AP_ENGAGE_DISENGAGE": 26,
    "AP_PATH": 27,
    "AP_ALT": 28,
    "FLAPS_UP": 22,
    "FLAPS_DN": 23,
    "ENG_IGN_R": 32,
    "ENG_IGN_L": 31,
    "EAC_ARM": 24,
    "RDR_NRM": 25,
    "BOAT_AFT": 10,
    "BOAT_FWD": 9,
    "PINKY_AFT": 14,
    "ENG_L": 16,
    "ENG_R": 17,
}

JOYSTICK_BUTTONS = {
    "PADDLE": 4,
    "TRIGGER_FIRST_DETENT": 1,
    "TRIGGER_SECOND_DETENT": 6,
}

# Mapped vJoy buttons
VJOY_BUTTONS = {
    "AP_PITCH_OFF": 1,

    # Autopilot Roll 3-way switch {{{
    "AP_ROLL_HDG_SEL": 2,
    "AP_ROLL_ATT_HOLD": 3,
    "AP_ROLL_STRG_SEL": 4,
    # }}}

    # Flaps mid position
    "FLAPS_MVR": 5,

    "CANOPY_CLOSE": 6,
    "ENG_ING_L_PASSTRU": 7,

    "MFD_ON": 8,
    "UFC_ON": 9,

    "MAIN_PWR": 10,
    "EAC_ARM_PASSTRU": 11,

    "START_2": 12,
    "RDR_NRM_PASSTRU": 13,

    "MACRO_1": 14,
    "ENG_L_PASSTRU": 15,
}

# This information can be retrieved in Joystick Gremlin under Tools>Device Information
JOYSTICK_GUID = "{2AFA7F00-1897-11EB-8002-444553540000}"
THROTTLE_GUID = "{6EB24530-1896-11EB-8001-444553540000}"

joy = gremlin.input_devices.JoystickDecorator( \
                "Joystick - HOTAS Warthog ", \
                JOYSTICK_GUID, \
                mode_global.value)

thrt = gremlin.input_devices.JoystickDecorator( \
                "Throttle - HOTAS Warthog", \
                THROTTLE_GUID, \
                mode_global.value)


"""
Sync stuff at startup
"""
def sync():
    gremlin.util.log("Initial sync")
    joy_proxy = gremlin.input_devices.JoystickProxy()    
    vjoy_proxy = gremlin.joystick_handling.VJoyProxy()

    # AP 3-way switch inital sync
    apPathIsPressed = joy_proxy[gremlin.profile.parse_guid(THROTTLE_GUID)].button(THROTTLE_BUTTONS["AP_PATH"]).is_pressed
    apAltIsPressed = joy_proxy[gremlin.profile.parse_guid(THROTTLE_GUID)].button(THROTTLE_BUTTONS["AP_ALT"]).is_pressed
    vjoy_proxy[1].button(VJOY_BUTTONS["AP_PITCH_OFF"]).is_pressed = (not apPathIsPressed) and (not apAltIsPressed)

    # Flaps 3-way initial sync
    flapsUpIsPressed = joy_proxy[gremlin.profile.parse_guid(THROTTLE_GUID)].button(THROTTLE_BUTTONS["FLAPS_UP"]).is_pressed
    flapsDnIsPressed = joy_proxy[gremlin.profile.parse_guid(THROTTLE_GUID)].button(THROTTLE_BUTTONS["FLAPS_DN"]).is_pressed
    vjoy_proxy[1].button(VJOY_BUTTONS["FLAPS_MVR"]).is_pressed = (not flapsUpIsPressed) and (not flapsDnIsPressed)

    # AP Roll inital state, since this is just a push button, always set it to "middle" at start (which is how it is in the cockpit by default)
    vjoy_proxy[1].button(VJOY_BUTTONS["AP_ROLL_ATT_HOLD"]).is_pressed = True

sync()

# ================================== Utils
"""
Layer shifting via joystick paddle.
In-house "mode-switch"
"""
def shiftIsOn():
    joy_proxy = gremlin.input_devices.JoystickProxy()
    return joy_proxy[gremlin.profile.parse_guid(THROTTLE_GUID)].button(THROTTLE_BUTTONS["PINKY_AFT"]).is_pressed

def shiftedAndPasstru(event, vjoy, shiftedButton, passtruButton):
    if shiftIsOn():
        vjoy[1].button(shiftedButton).is_pressed = event.is_pressed
    else:
        vjoy[1].button(passtruButton).is_pressed = event.is_pressed

# ================================== Macros
MACROS = {
    "fcr": macro.Macro(),
    "mmc": macro.Macro(),
} 

# I hate python
## FCR/Radar/Right Hardpoint Macro
# MACROS["fcr"].press("leftcontrol")
MACROS["fcr"].press("leftshift")
MACROS["fcr"].tap("f1")
MACROS["fcr"].pause(0.2)
MACROS["fcr"].tap("f2")
MACROS["fcr"].pause(0.2)
MACROS["fcr"].tap("f3")
# MACROS["fcr"].release("leftcontrol")
MACROS["fcr"].release("leftshift")

## MMC, STSTA,MFD,UFC,MAP,GPS,DL Macro
# MACROS["mmc"].press("leftcontrol")
MACROS["mmc"].press("leftshift")
MACROS["mmc"].tap("f4")
MACROS["fcr"].pause(0.2)
MACROS["mmc"].tap("f5")
MACROS["fcr"].pause(0.2)
MACROS["mmc"].tap("f6")
MACROS["fcr"].pause(0.2)
MACROS["mmc"].tap("f7")
MACROS["fcr"].pause(0.2)
MACROS["mmc"].tap("f8")
MACROS["fcr"].pause(0.2)
MACROS["mmc"].tap("f9")
MACROS["fcr"].pause(0.2)
MACROS["mmc"].tap("f10")
# MACROS["mmc"].release("leftcontrol")
MACROS["mmc"].release("leftshift")

# ================================== Throttle
# Autopilot roll 3-way emulation {{{
AP_ROLL_CYCLE_STATE = 0
"""
This function make the "Enagage/Disengage" button on the throttle act as a three way switch.
Each press will cycle the switch down.
The  ing position is in the middle
Cycle between autopilot ROLL modes.
From sync, this starts in the middle position as ATT_HOLD
"""
@thrt.button(THROTTLE_BUTTONS["AP_ENGAGE_DISENGAGE"])
def apRollCycle(event, vjoy):
    global AP_ROLL_CYCLE_STATE
    if (not event.is_pressed):
        return
        
    if AP_ROLL_CYCLE_STATE == 0:
        vjoy[1].button(VJOY_BUTTONS["AP_ROLL_ATT_HOLD"]).is_pressed = False
        vjoy[1].button(VJOY_BUTTONS["AP_ROLL_STRG_SEL"]).is_pressed = True
        AP_ROLL_CYCLE_STATE = 1
    elif AP_ROLL_CYCLE_STATE == 1:
        vjoy[1].button(VJOY_BUTTONS["AP_ROLL_STRG_SEL"]).is_pressed = False
        vjoy[1].button(VJOY_BUTTONS["AP_ROLL_HDG_SEL"]).is_pressed = True
        AP_ROLL_CYCLE_STATE = 2
    elif AP_ROLL_CYCLE_STATE == 2:
        vjoy[1].button(VJOY_BUTTONS["AP_ROLL_HDG_SEL"]).is_pressed = False
        vjoy[1].button(VJOY_BUTTONS["AP_ROLL_ATT_HOLD"]).is_pressed = True
        AP_ROLL_CYCLE_STATE = 0
# }}}


# Autopilot pitch virtual 3rd state {{{
def toggleSwitchMiddle(event, vjoy, joy, otherUp, otherDown, virtualButton):
    if event.is_pressed:
        vjoy[1].button(virtualButton).is_pressed = False
    else:
        j = joy[gremlin.profile.parse_guid(THROTTLE_GUID)]
        bPath = otherUp
        bAlt = otherDown
        if not j.button(bPath).is_pressed and not j.button(bAlt).is_pressed:
            vjoy[1].button(virtualButton).is_pressed = True

@thrt.button(THROTTLE_BUTTONS["AP_PATH"])
def apPath(event, vjoy, joy):
     toggleSwitchMiddle(event, vjoy, joy, THROTTLE_BUTTONS["AP_PATH"], THROTTLE_BUTTONS["AP_ALT"], VJOY_BUTTONS["AP_PITCH_OFF"])

@thrt.button(THROTTLE_BUTTONS["AP_ALT"])
def apAlt(event, vjoy, joy):
    toggleSwitchMiddle(event, vjoy, joy, THROTTLE_BUTTONS["AP_PATH"], THROTTLE_BUTTONS["AP_ALT"], VJOY_BUTTONS["AP_PITCH_OFF"])
# }}}

# Flaps virtual 3rd state {{{
@thrt.button(THROTTLE_BUTTONS["FLAPS_UP"])
def flapsUp(event, vjoy, joy):
    toggleSwitchMiddle(event, vjoy, joy, THROTTLE_BUTTONS["FLAPS_UP"], THROTTLE_BUTTONS["FLAPS_DN"], VJOY_BUTTONS["FLAPS_MVR"])

@thrt.button(THROTTLE_BUTTONS["FLAPS_DN"])
def flapsUp(event, vjoy, joy):
    toggleSwitchMiddle(event, vjoy, joy, THROTTLE_BUTTONS["FLAPS_UP"], THROTTLE_BUTTONS["FLAPS_DN"], VJOY_BUTTONS["FLAPS_MVR"])
# }}}

@thrt.button(THROTTLE_BUTTONS["ENG_IGN_L"])
def engIgnLeft(event, vjoy):
    shiftedAndPasstru(event, vjoy, VJOY_BUTTONS["CANOPY_CLOSE"], VJOY_BUTTONS["ENG_ING_L_PASSTRU"])

@thrt.button(THROTTLE_BUTTONS["EAC_ARM"])
def eacArm(event, vjoy):
    shiftedAndPasstru(event, vjoy, VJOY_BUTTONS["MAIN_PWR"], VJOY_BUTTONS["EAC_ARM_PASSTRU"])

@thrt.button(THROTTLE_BUTTONS["RDR_NRM"])
def rdrNrm(event, vjoy):
    shiftedAndPasstru(event, vjoy, VJOY_BUTTONS["START_2"], VJOY_BUTTONS["RDR_NRM_PASSTRU"])

@thrt.button(THROTTLE_BUTTONS["ENG_L"])
def engLeft(event, vjoy):
    if event.is_pressed and shiftIsOn():
        macro.MacroManager().queue_macro(MACROS["fcr"])

@thrt.button(THROTTLE_BUTTONS["ENG_R"])
def engLeft(event, vjoy):
    if event.is_pressed and shiftIsOn():
        macro.MacroManager().queue_macro(MACROS["mmc"])


# ================================== Joystick

'''
gremlin.util.log("in there")
'''