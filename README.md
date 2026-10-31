# Jarvis

A small voice + text assistant for Windows, written in Python.

It can open apps and websites, search Google, play songs on YouTube, do math, look things up on Wikipedia, take notes, tell the time and jokes, and lock your PC. Replies are printed and spoken aloud.

## Setup (Windows, cmd)

You need Python 3.9 or newer (python.org, tick "Add Python to PATH").

```cmd
cd Jarvis
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```cmd
python jarvis.py            :: type your commands
python jarvis.py --voice    :: talk to it, say "Jarvis, open notepad"
python jarvis.py --mute     :: no spoken replies
```

In text mode, type `voice` to switch to voice mode. Type `help` to see everything it understands.

## Voice mode

Voice mode needs a microphone, an internet connection (speech recognition uses Google's free web service), and PyAudio:

```cmd
pip install pyaudio
```

If PyAudio fails to install, text mode still works fully.

## Customize

Open `jarvis.py` and edit the `APPS` and `SITES` dictionaries at the top to add your own apps and websites.

## Examples

- `open chrome`, `open youtube`, `open github.com`
- `play lo-fi beats`
- `search best python tutorials`
- `what is 12 times 7`
- `who is Albert Einstein`
- `note buy milk`, `show notes`
- `what time is it`, `tell me a joke`, `lock computer`
