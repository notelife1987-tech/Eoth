import subprocess, time, os
print("🎙️ Voice Note Recorder Active")
print("Commands: \"record\" = 5sec note, \"long\" = 10sec note, \"quit\" = exit")
while True:
    try:
        command = input("🔴 Ready: ").strip().lower()
        if "record" in command:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"/storage/emulated/0/Download/note_{timestamp}.wav"
            print("🎵 Recording 5 seconds...")
            subprocess.run(["termux-microphone-record", "-f", filename, "-l", "5"])
            os.system(f"termux-toast \"Note saved!\"")
            os.system("termux-tts-speak \"Noteworthy transmission stored in the matrix\"")
            print(f"✅ Saved: {filename}")
        elif "long" in command:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"/storage/emulated/0/Download/long_note_{timestamp}.wav"
            print("🎵 Recording 10 seconds...")
            subprocess.run(["termux-microphone-record", "-f", filename, "-l", "10"])
            os.system("termux-toast \"Long note saved\"")
            print(f"✅ Long note saved: {filename}")
        elif "quit" in command:
            print("👋 Voice recorder stopped")
            break
    except KeyboardInterrupt:
        print("\n👋 Exiting voice recorder")
        break
    except Exception as e:
        print(f"⚠️ Error: {e}")
