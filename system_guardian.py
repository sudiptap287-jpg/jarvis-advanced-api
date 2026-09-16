import psutil
import time

class SystemGuardian:
    def __init__(self):
        # Dangerous thresholds define kiye hain
        self.CPU_THRESHOLD = 85.0      # 85% se upar dangerous
        self.RAM_THRESHOLD = 80.0      # 80% se upar system lag karega
        self.BATTERY_LOW_THRESHOLD = 20 # 20% se kam par alert

    def get_top_resource_hogs(self, track_by="memory", limit=3):
        """
        System ki top heavy apps ko dhoondta hai jo RAM ya CPU crash kar rahi hain.
        track_by: 'memory' ya 'cpu'
        """
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                # Background tasks ki current snapshot lena
                proc_info = proc.info
                processes.append(proc_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        # Sorting logic based on user requirement
        if track_by == "cpu":
            sorted_proc = sorted(processes, key=lambda x: x['cpu_percent'] or 0, reverse=True)
        else:
            sorted_proc = sorted(processes, key=lambda x: x['memory_percent'] or 0, reverse=True)

        return sorted_proc[:limit]

    def check_system_health(self):
        """
        Complete diagnostics run karta hai aur agar kuch kharab hai toh alert create karta hai.
        """
        alerts = []
        
        # 1. CPU Health Check
        cpu_usage = psutil.cpu_percent(interval=0.5)
        if cpu_usage > self.CPU_THRESHOLD:
            alerts.append(f"CRITICAL: CPU usage is extremely high at {cpu_usage}%.")

        # 2. RAM Health Check
        ram = psutil.virtual_memory()
        if ram.percent > self.RAM_THRESHOLD:
            alerts.append(f"WARNING: RAM is almost full at {ram.percent}%. Available memory is only {round(ram.available / (1024**3), 2)} GB.")

        # 3. Battery Health Check
        battery = psutil.sensors_battery()
        if battery:
            if battery.percent <= self.BATTERY_LOW_THRESHOLD and not battery.power_plugged:
                alerts.append(f"ALERT: Battery is critically low at {battery.percent}%. Please connect the charger.")
        
        # 4. Storage Check
        disk = psutil.disk_usage('C:')
        if disk.percent > 90.0:
            alerts.append(f"STORAGE FULL: Drive C has less than 10% space left.")

        # Final Verdict System
        if not alerts:
            status_speech = f"System health is excellent, Commander. CPU is at {cpu_usage}%, and RAM usage is stable at {ram.percent}%."
            return {"status": "HEALTHY", "message": status_speech, "data": {}}
        else:
            combined_alerts = " ".join(alerts)
            return {"status": "CRITICAL", "message": f"Sir, I found some issues. {combined_alerts}", "alerts": alerts}

    def get_network_speed(self):
        """Live network download and upload speed monitor karta hai."""
        net_start = psutil.net_io_counters()
        time.sleep(1) # 1 second ka gap byte-rate nikalne ke liye
        net_end = psutil.net_io_counters()
        
        download_speed = (net_end.bytes_recv - net_start.bytes_recv) / (1024 * 1024) # MB/s
        upload_speed = (net_end.bytes_sent - net_start.bytes_sent) / (1024 * 1024) # MB/s
        
        return f"Current download speed is {round(download_speed, 2)} MB per second, and upload speed is {round(upload_speed, 2)} MB per second."