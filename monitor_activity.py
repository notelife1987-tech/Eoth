import subprocess, time, os
while True:
    try:
        # Count total processes
        ps_count = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        process_count = len(ps_count.stdout.split("\n")) - 1
        
        timestamp = time.strftime("%H:%M:%S")
        
        # Log if activity spikes (more than baseline processes)
        if process_count > 15:  # Adjust threshold as needed
            with open("activity_log.txt", "a") as f:
                f.write(f"{timestamp} - HIGH ACTIVITY: {process_count} processes\n")
            print(f"🚨 {timestamp} - Activity spike: {process_count} processes")
        else:
            print(f"✅ {timestamp} - Quiet: {process_count} processes")
            
        time.sleep(30)
        
    except KeyboardInterrupt:
        break
