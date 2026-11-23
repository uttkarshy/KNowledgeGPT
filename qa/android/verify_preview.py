"""Exercise the installed Android UI over ADB and capture public store screens."""
import pathlib
import re
import subprocess
import time
import xml.etree.ElementTree as ET

OUT = pathlib.Path("phone-screens")
OUT.mkdir(exist_ok=True)
PACKAGE = "com.utkarshlabs.knowledgegpt"


def adb(*args):
    return subprocess.check_output(["adb", *args], timeout=30)


def node(label, widget=None):
    deadline = time.monotonic() + 65
    while time.monotonic() < deadline:
        try:
            adb("shell", "uiautomator", "dump", "/sdcard/kg-ui.xml")
            tree = ET.fromstring(adb("shell", "cat", "/sdcard/kg-ui.xml"))
            for item in tree.iter("node"):
                if label in (item.get("text"), item.get("content-desc")) and (not widget or item.get("class") == widget):
                    return item
        except (ET.ParseError, subprocess.SubprocessError):
            pass
        time.sleep(1)
    capture("diagnostic")
    (OUT / "diagnostic.xml").write_bytes(adb("shell", "cat", "/sdcard/kg-ui.xml"))
    raise RuntimeError("Screen did not show " + label)


def tap(label, widget=None):
    bounds = list(map(int, re.findall(r"\d+", node(label, widget).attrib["bounds"])))
    adb("shell", "input", "tap", str((bounds[0]+bounds[2])//2), str((bounds[1]+bounds[3])//2))


def capture(name):
    time.sleep(1)
    (OUT / (name + ".png")).write_bytes(adb("exec-out", "screencap", "-p"))


adb("shell", "am", "start", "-n", PACKAGE + "/.MainActivity")
node("Create an account")
capture("01-welcome")
tap("Sign in")
node("Email")
capture("02-sign-in")
tap("Email", "android.widget.EditText")
adb("shell", "input", "text", "reader")
node("reader", "android.widget.EditText")
keyboard = adb("shell", "dumpsys", "input_method").decode()
if "mInputShown=true" in keyboard or "mIsInputViewShown=true" in keyboard:
    adb("shell", "input", "keyevent", "4")
node("Password")
adb("shell", "input", "keyevent", "4")
node("Create an account")
tap("Create an account")
node("Name (optional)")
capture("03-registration")
adb("shell", "am", "force-stop", PACKAGE)
adb("shell", "am", "start", "-n", PACKAGE + "/.MainActivity")
node("Create an account")
print("PASS welcome, sign-in, keyboard input, Android Back, registration, cold restart")
