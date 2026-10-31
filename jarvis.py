#!/usr/bin/env python3
"""
Jarvis - a small voice + text assistant for Windows.

Run:  python jarvis.py            (type commands)
      python jarvis.py --voice    (talk to it: say "Jarvis, <command>")
      python jarvis.py --mute     (no spoken replies)
"""

import argparse
import ast
import datetime
import json
import operator
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import webbrowser

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None

NAME = "Jarvis"
NOTES_FILE = "notes.txt"
speaking = True  # spoken replies on/off

# Apps Jarvis can open. Add your own: "name you say": "program or path".
APPS = {
    "notepad": "notepad",
    "calculator": "calc",
    "paint": "mspaint",
    "command prompt": "cmd",
    "cmd": "cmd",
    "file explorer": "explorer",
    "explorer": "explorer",
    "task manager": "taskmgr",
    "settings": "ms-settings:",
    "chrome": "chrome",
    "edge": "msedge",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "vs code": "code",
    "spotify": "spotify",
}

# Websites Jarvis can open. Add your own here too.
SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "whatsapp": "https://web.whatsapp.com",
    "instagram": "https://www.instagram.com",
    "maps": "https://maps.google.com",
    "claude": "https://claude.ai",
}

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "I would tell you a UDP joke, but you might not get it.",
    "There are 10 kinds of people: those who understand binary and those who don't.",
    "Why did the developer go broke? Because he used up all his cache.",
    "A SQL query walks into a bar, walks up to two tables and asks: can I join you?",
]

HELP = """Things you can say or type:
  open notepad / open chrome / open youtube / open github.com
  play <song>                  (searches YouTube)
  search <anything>            (Google)
  what is 12 times 7           (also: calculate 100 divided by 4)
  who is <person> / tell me about <topic>   (Wikipedia)
  what time is it / what's the date
  note <text> / show notes
  tell me a joke
  lock computer
  mute / unmute
  quit
"""


# ---------------------------------------------------------------- output
def say(text):
    """Print a reply and speak it (if speech is available and not muted)."""
    print(f"{NAME}: {text}")
    if not speaking or pyttsx3 is None:
        return
    try:
        engine = pyttsx3.init()  # fresh engine each time is the most reliable on Windows
        engine.say(text)
        engine.runAndWait()
    except Exception:
        pass


# ---------------------------------------------------------------- helpers
def launch(target):
    if sys.platform != "win32":
        say("Opening apps only works on Windows.")
        return
    subprocess.Popen(["cmd", "/c", "start", "", target])


def open_thing(name):
    name = name.strip()
    if name in SITES:
        webbrowser.open(SITES[name])
        say(f"Opening {name}.")
    elif name in APPS:
        launch(APPS[name])
        say(f"Opening {name}.")
    elif "." in name and " " not in name:
        webbrowser.open(name if name.startswith("http") else "https://" + name)
        say(f"Opening {name}.")
    elif shutil.which(name):
        launch(shutil.which(name))
        say(f"Opening {name}.")
    else:
        say(f"I don't know how to open {name}. You can add it to the APPS list in jarvis.py.")


_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}

_WORDS = [
    ("to the power of", "**"),
    ("multiplied by", "*"),
    ("divided by", "/"),
    ("plus", "+"),
    ("minus", "-"),
    ("times", "*"),
    (" into ", "*"),
    (" over ", "/"),
    (" x ", "*"),
    (" mod ", "%"),
]


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("exponent too large")
        return _OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")


def calculate(text):
    """Turn 'what is 5 plus 3' style text into a number. Raises on failure."""
    expr = " " + text.lower() + " "
    for word, symbol in _WORDS:
        expr = expr.replace(word, symbol)
    expr = expr.replace(",", "").replace("?", "").strip()
    result = _eval(ast.parse(expr, mode="eval"))
    if isinstance(result, float):
        result = int(result) if result.is_integer() else round(result, 6)
    return result


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "JarvisAssistant/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wiki_summary(topic):
    """Return the first couple of sentences from Wikipedia, or None."""
    query = urllib.parse.urlencode(
        {"action": "query", "list": "search", "srsearch": topic, "format": "json", "srlimit": 1}
    )
    hits = http_json(f"https://en.wikipedia.org/w/api.php?{query}")["query"]["search"]
    if not hits:
        return None
    title = hits[0]["title"].replace(" ", "_")
    data = http_json("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title))
    extract = data.get("extract", "").strip()
    if not extract:
        return None
    summary = ". ".join(extract.split(". ")[:2]).strip()
    return summary if summary.endswith(".") else summary + "."


def greeting():
    hour = datetime.datetime.now().hour
    part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
    return f"Good {part}! How can I help?"


# ---------------------------------------------------------------- brain
def handle(cmd):
    """Run one command. Returns False when Jarvis should quit."""
    global speaking
    c = cmd.lower().strip().rstrip(".?!")
    if not c:
        return True

    if c in ("quit", "exit", "bye", "goodbye", "stop", "shut down jarvis"):
        say("Goodbye!")
        return False

    if c in ("help", "what can you do"):
        print(HELP)
        say("Here's what I can do. The list is on your screen.")
        return True

    if c == "mute":
        speaking = False
        print(f"{NAME}: Muted.")
        return True
    if c == "unmute":
        speaking = True
        say("Voice is back on.")
        return True

    if c in ("hi", "hello", "hey", "hello jarvis", "hi jarvis"):
        say(greeting())
        return True

    # notes
    if re.search(r"\b(show|read|open) (my )?notes$", c):
        try:
            with open(NOTES_FILE, encoding="utf-8") as f:
                lines = f.read().strip().splitlines()
            say("Your notes: " + "; ".join(lines[-5:]) if lines else "You have no notes yet.")
        except FileNotFoundError:
            say("You have no notes yet.")
        return True
    m = re.match(r"^(?:take a |make a |add a )?note[: ]+(.+)$", c)
    if m:
        with open(NOTES_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M} - {m.group(1)}\n")
        say("Noted.")
        return True

    # open things
    m = re.match(r"^(?:open|launch|start) (.+)$", c)
    if m:
        open_thing(m.group(1))
        return True

    # play on YouTube
    m = re.match(r"^play (.+?)(?: on youtube)?$", c)
    if m:
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(m.group(1))
        webbrowser.open(url)
        say(f"Searching YouTube for {m.group(1)}.")
        return True

    # web search
    m = re.match(r"^(?:search for|search|google|look up) (.+)$", c)
    if m:
        webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote_plus(m.group(1)))
        say(f"Searching Google for {m.group(1)}.")
        return True

    # math
    m = re.match(r"^(?:calculate|what is|what's|whats) (.+)$", c)
    if m and (c.startswith("calculate") or re.search(r"\d", m.group(1))):
        try:
            say(f"The answer is {calculate(m.group(1))}.")
            return True
        except Exception:
            if c.startswith("calculate"):
                say("Sorry, I couldn't work that out.")
                return True

    # time and date
    words = c.split()
    if "time" in words:
        say(datetime.datetime.now().strftime("It's %I:%M %p."))
        return True
    if "date" in words or "day" in words:
        say(datetime.datetime.now().strftime("Today is %A, %d %B %Y."))
        return True

    # Wikipedia
    m = re.match(r"^(?:who is|who was|what is|what's|what are|tell me about|wikipedia) (.+)$", c)
    if m:
        topic = re.sub(r"^(a|an|the) ", "", m.group(1))
        try:
            summary = wiki_summary(topic)
        except Exception:
            say("I couldn't reach Wikipedia. Check your internet connection.")
            return True
        say(summary or f"I couldn't find anything on {topic}.")
        return True

    if "joke" in words:
        say(random.choice(JOKES))
        return True

    if "lock" in words and any(w in words for w in ("computer", "pc", "screen", "laptop")):
        if sys.platform == "win32":
            say("Locking.")
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
        else:
            say("Locking only works on Windows.")
        return True

    say("Sorry, I didn't get that. Say 'help' to see what I can do.")
    return True


# ---------------------------------------------------------------- voice
def listen(recognizer, mic):
    try:
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.listen(source, timeout=6, phrase_time_limit=8)
        return recognizer.recognize_google(audio)
    except (sr.WaitTimeoutError, sr.UnknownValueError):
        return ""
    except sr.RequestError:
        say("I can't reach the speech service. Check your internet.")
        time.sleep(3)
        return ""


def voice_loop():
    """Returns 'quit' if the user said goodbye, otherwise 'text'."""
    if sr is None:
        say("Voice needs the SpeechRecognition package. Run: pip install SpeechRecognition pyaudio")
        return "text"
    try:
        recognizer = sr.Recognizer()
        mic = sr.Microphone()
    except Exception:
        say("I can't access a microphone. If PyAudio is missing, run: pip install pyaudio")
        return "text"

    say(f"Voice mode on. Say '{NAME}' followed by a command. Press Ctrl+C to stop.")
    while True:
        heard = listen(recognizer, mic)
        if not heard:
            continue
        print(f"You: {heard}")
        low = heard.lower()
        if NAME.lower() not in low:
            continue
        command = low.split(NAME.lower(), 1)[1].strip(" ,.")
        if not command:
            say("Yes?")
            command = listen(recognizer, mic).lower()
            if not command:
                continue
            print(f"You: {command}")
        if not handle(command):
            return "quit"


# ---------------------------------------------------------------- main
def text_loop():
    say(f"{NAME} online. Type a command, 'help' for ideas, or 'voice' to talk to me.")
    while True:
        try:
            cmd = input("You: ")
        except EOFError:
            return
        if cmd.strip().lower() == "voice":
            if voice_loop() == "quit":
                return
            continue
        if not handle(cmd):
            return


def main():
    global speaking
    parser = argparse.ArgumentParser(description="Jarvis voice/text assistant")
    parser.add_argument("--voice", action="store_true", help="start in voice mode")
    parser.add_argument("--mute", action="store_true", help="don't speak replies")
    args = parser.parse_args()

    if args.mute or pyttsx3 is None:
        speaking = False

    try:
        if args.voice and voice_loop() == "quit":
            return
        text_loop()
    except KeyboardInterrupt:
        print()
        say("Goodbye!")


if __name__ == "__main__":
    main()
