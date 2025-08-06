import speech_recognition as sr, subprocess, time, datetime
r = sr.Recognizer()
r.energy_threshold = 300
with sr.Microphone() as source:
    r.adjust_for_ambient_noise(source, duration=2)
    while True:
        try:
            print("Listening for Take Note...")
            audio = r.listen(source, timeout=5)
            text = r.recognize_sphinx(audio)
            if "take note" in text.lower():
                filename = "/storage/emulated/0/Download/note_" + time.strftime("%Y-%m-%d_%H%M%S") + ".wav"
                subprocess.run(["termux-microphone-record", "-f", filename, "-l", "5"])
                subprocess.run(["termux-toast", f"Note saved as {filename}"])
                subprocess.run(["termux-tts-speak", "Noteworthy transmission stored in the matrix"])
        except:
            pass
