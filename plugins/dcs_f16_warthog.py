import gremlin      # 'Coz it's a Joystick Gremlin module!
import time         # Used for delays between actions in some functions
import threading    # Threading allows the longer functions to be non-blocking
import logging      # Used for logging events and debugging

"""
Constants
"""
MODES = ["Default"]

# Helper for actual throttle button
THROTTLE_BUTTONS = {
    "AP_ENGAGE_DISENGAGE": 26,
    "AP_PATH": 27,
    "AP_ALT": 28,
    "FLAPS_UP": 22,
    "FLAPS_DN": 23
}

# Mapped vJoy buttons
VJOY_BUTTONS = {
    "AP_PITCH_OFF": 1,

    # Autopilot Roll 3-way switch {{{
    "AP_ROLL_HDG_SEL": 2,
    "AP_ROLL_ATT_HOLD": 3,
    "AP_ROLL_STRG_SEL": 4,
    # }}}

    "FLAPS_MVR": 5
}

# This information can be retrieved in Joystick Gremlin under Tools>Device Information
JOYSTICK_GUID = "{9F3CAC80-1B1C-11EB-8002-444553540000}"
THROTTLE_GUID = "{6EB24530-1896-11EB-8001-444553540000}"

"""
Sync stuff at startup
"""
def sync():
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

joy = gremlin.input_devices.JoystickDecorator( \
                "Joystick - HOTAS Warthog ", \
                JOYSTICK_GUID, \
                 MODES[0] )

thrt = gremlin.input_devices.JoystickDecorator( \
                "Throttle - HOTAS Warthog", \
                THROTTLE_GUID, \
                MODES[0] )

# Autopilot roll 3-way emulation {{{
AP_ROLL_CYCLE_STATE = 0
"""
This function make the "Enagage/Disengage" button on the throttle act as a three way switch.
Each press will cycle the switch down.
The starting position is in the middle
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

'''
gremlin.util.log("in there")
'''