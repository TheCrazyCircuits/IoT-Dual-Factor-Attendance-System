import sys
import os
import json
import time
import csv
import threading
from datetime import datetime
import serial
import serial.tools.list_ports
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog

# Appearance settings
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AttendanceApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("IoT Attendance Tracking System - Live Desktop Dashboard")
        self.geometry("980x700")
        self.minsize(900, 600)

        # Serial Connection State
        self.serial_conn = None
        self.is_connected = False
        self.read_thread = None
        self.running = True

        # Attendance Data
        self.attendance_records = []
        self.total_count = 0
        self.last_student = "None"
        self.last_roll = "----"

        # Build UI
        self.build_ui()

        # Bring window to front
        self.lift()
        self.attributes('-topmost', True)
        self.after(500, lambda: self.attributes('-topmost', False))
        self.focus_force()

        # Auto-detect COM8 or first serial port
        self.auto_connect_default()

        # Update Clock
        self.update_clock()

        # Protocol for clean exit
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def build_ui(self):
        # 1. Top Header Frame
        header = ctk.CTkFrame(self, corner_radius=10, fg_color="#161b22")
        header.pack(fill="x", padx=15, pady=(15, 10))

        # Title & Subtitle
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", padx=15, pady=12)

        title_lbl = ctk.CTkLabel(
            title_box, 
            text="🎓 IoT Dual-Factor Attendance Tracker", 
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#58a6ff"
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = ctk.CTkLabel(
            title_box, 
            text="Live Hardware Monitor (RFID + Keypad + Arduino + ESP32)", 
            font=ctk.CTkFont(size=12),
            text_color="#8b949e"
        )
        subtitle_lbl.pack(anchor="w")

        # Connection Controls
        conn_box = ctk.CTkFrame(header, fg_color="transparent")
        conn_box.pack(side="right", padx=15, pady=12)

        self.clock_lbl = ctk.CTkLabel(
            conn_box, 
            text="", 
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#c9d1d9"
        )
        self.clock_lbl.pack(anchor="e", pady=(0, 5))

        ctrl_row = ctk.CTkFrame(conn_box, fg_color="transparent")
        ctrl_row.pack(anchor="e")

        self.port_menu = ctk.CTkComboBox(
            ctrl_row, 
            values=self.get_available_ports(), 
            width=110,
            state="readonly"
        )
        self.port_menu.pack(side="left", padx=5)

        self.refresh_btn = ctk.CTkButton(
            ctrl_row, 
            text="🔄", 
            width=32, 
            fg_color="#21262d", 
            hover_color="#30363d",
            command=self.refresh_ports
        )
        self.refresh_btn.pack(side="left", padx=3)

        self.connect_btn = ctk.CTkButton(
            ctrl_row, 
            text="Connect", 
            width=90,
            fg_color="#238636",
            hover_color="#2ea043",
            font=ctk.CTkFont(weight="bold"),
            command=self.toggle_connection
        )
        self.connect_btn.pack(side="left", padx=5)

        self.status_badge = ctk.CTkLabel(
            ctrl_row, 
            text="● OFFLINE", 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#f85149"
        )
        self.status_badge.pack(side="left", padx=(8, 0))

        # 2. Stat Cards Row
        stat_row = ctk.CTkFrame(self, fg_color="transparent")
        stat_row.pack(fill="x", padx=15, pady=5)
        stat_row.columnconfigure((0, 1, 2), weight=1, uniform="stat")

        # Stat Card 1: Total Present
        card1 = ctk.CTkFrame(stat_row, corner_radius=10, fg_color="#161b22", border_width=1, border_color="#30363d")
        card1.grid(row=0, column=0, padx=5, sticky="nsew", pady=5)

        ctk.CTkLabel(card1, text="TOTAL ATTENDEES", font=ctk.CTkFont(size=11, weight="bold"), text_color="#8b949e").pack(anchor="w", padx=15, pady=(10, 0))
        self.count_stat_lbl = ctk.CTkLabel(card1, text="0", font=ctk.CTkFont(size=32, weight="bold"), text_color="#3fb950")
        self.count_stat_lbl.pack(anchor="w", padx=15, pady=(0, 10))

        # Stat Card 2: Last Logged Student
        card2 = ctk.CTkFrame(stat_row, corner_radius=10, fg_color="#161b22", border_width=1, border_color="#30363d")
        card2.grid(row=0, column=1, padx=5, sticky="nsew", pady=5)

        ctk.CTkLabel(card2, text="LAST REGISTERED STUDENT", font=ctk.CTkFont(size=11, weight="bold"), text_color="#8b949e").pack(anchor="w", padx=15, pady=(10, 0))
        self.student_stat_lbl = ctk.CTkLabel(card2, text="None (----)", font=ctk.CTkFont(size=20, weight="bold"), text_color="#58a6ff")
        self.student_stat_lbl.pack(anchor="w", padx=15, pady=(5, 10))

        # Stat Card 3: Link & Verification Mode
        card3 = ctk.CTkFrame(stat_row, corner_radius=10, fg_color="#161b22", border_width=1, border_color="#30363d")
        card3.grid(row=0, column=2, padx=5, sticky="nsew", pady=5)

        ctk.CTkLabel(card3, text="HARDWARE STATUS", font=ctk.CTkFont(size=11, weight="bold"), text_color="#8b949e").pack(anchor="w", padx=15, pady=(10, 0))
        self.hw_stat_lbl = ctk.CTkLabel(card3, text="RFID + Keypad Active", font=ctk.CTkFont(size=16, weight="bold"), text_color="#d29922")
        self.hw_stat_lbl.pack(anchor="w", padx=15, pady=(5, 10))

        # 3. Main Table Section
        table_container = ctk.CTkFrame(self, corner_radius=10, fg_color="#161b22", border_width=1, border_color="#30363d")
        table_container.pack(fill="both", expand=True, padx=15, pady=10)

        # Table Header Row
        tbl_top = ctk.CTkFrame(table_container, fg_color="transparent")
        tbl_top.pack(fill="x", padx=15, pady=(12, 6))

        tbl_title = ctk.CTkLabel(tbl_top, text="📋 Live Attendance Log", font=ctk.CTkFont(size=16, weight="bold"), text_color="#c9d1d9")
        tbl_title.pack(side="left")

        # Table Action Buttons
        btn_box = ctk.CTkFrame(tbl_top, fg_color="transparent")
        btn_box.pack(side="right")

        sim_john_btn = ctk.CTkButton(
            btn_box, 
            text="Simulate John (101)", 
            width=130, 
            height=28,
            fg_color="#1f6feb",
            hover_color="#388bfd",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self.send_command("CMD:TRIGGER:John:101")
        )
        sim_john_btn.pack(side="left", padx=4)

        sim_alice_btn = ctk.CTkButton(
            btn_box, 
            text="Simulate Alice (102)", 
            width=130, 
            height=28,
            fg_color="#8957e5",
            hover_color="#a371f7",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self.send_command("CMD:TRIGGER:Alice:102")
        )
        sim_alice_btn.pack(side="left", padx=4)

        export_btn = ctk.CTkButton(
            btn_box, 
            text="Export CSV 💾", 
            width=100, 
            height=28,
            fg_color="#238636",
            hover_color="#2ea043",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.export_csv
        )
        export_btn.pack(side="left", padx=4)

        clear_btn = ctk.CTkButton(
            btn_box, 
            text="Clear", 
            width=65, 
            height=28,
            fg_color="#da3633",
            hover_color="#f85149",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.clear_logs
        )
        clear_btn.pack(side="left", padx=4)

        # Style Treeview
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Custom.Treeview",
            background="#0d1117",
            foreground="#c9d1d9",
            fieldbackground="#0d1117",
            rowheight=32,
            font=("Segoe UI", 11)
        )
        style.configure(
            "Custom.Treeview.Heading",
            background="#21262d",
            foreground="#58a6ff",
            relief="flat",
            font=("Segoe UI", 11, "bold")
        )
        style.map("Custom.Treeview", background=[("selected", "#1f6feb")])

        # Treeview Widget
        cols = ("idx", "time", "roll", "name", "method", "status")
        self.tree = ttk.Treeview(
            table_container, 
            columns=cols, 
            show="headings", 
            style="Custom.Treeview",
            selectmode="browse"
        )

        self.tree.heading("idx", text="#")
        self.tree.heading("time", text="Time Logged")
        self.tree.heading("roll", text="Roll Number")
        self.tree.heading("name", text="Student Name")
        self.tree.heading("method", text="Verification Method")
        self.tree.heading("status", text="Status")

        self.tree.column("idx", width=45, anchor="center")
        self.tree.column("time", width=120, anchor="center")
        self.tree.column("roll", width=110, anchor="center")
        self.tree.column("name", width=160, anchor="w")
        self.tree.column("method", width=150, anchor="center")
        self.tree.column("status", width=90, anchor="center")

        # Scrollbar
        scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(15, 0), pady=(0, 15))
        scrollbar.pack(side="right", fill="y", padx=(0, 15), pady=(0, 15))

    def update_clock(self):
        now = datetime.now().strftime("%I:%M:%S %p  |  %d %b %Y")
        self.clock_lbl.configure(text=now)
        self.after(1000, self.update_clock)

    def get_available_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        return ports if ports else ["No Ports"]

    def refresh_ports(self):
        ports = self.get_available_ports()
        self.port_menu.configure(values=ports)
        if ports and ports[0] != "No Ports":
            self.port_menu.set(ports[0])

    def auto_connect_default(self):
        ports = self.get_available_ports()
        target = "COM8" if "COM8" in ports else (ports[0] if ports and ports[0] != "No Ports" else None)
        if target:
            self.port_menu.set(target)
            self.connect_serial(target)

    def toggle_connection(self):
        if self.is_connected:
            self.disconnect_serial()
        else:
            port = self.port_menu.get()
            if port and port != "No Ports":
                self.connect_serial(port)

    def connect_serial(self, port):
        try:
            self.serial_conn = serial.Serial(port, 115200, timeout=1, dsrdtr=False, rtscts=False)
            self.is_connected = True
            self.connect_btn.configure(text="Disconnect", fg_color="#da3633", hover_color="#f85149")
            self.status_badge.configure(text=f"● ONLINE ({port})", text_color="#3fb950")
            self.hw_stat_lbl.configure(text=f"Linked to {port}", text_color="#3fb950")

            # Start background reading thread
            self.read_thread = threading.Thread(target=self.serial_read_loop, daemon=True)
            self.read_thread.start()

            # Ping controller
            self.send_command("CMD:PING")
        except Exception as e:
            self.is_connected = False
            self.status_badge.configure(text="● ERROR", text_color="#f85149")
            messagebox.showerror("Connection Error", f"Could not connect to {port}:\n{str(e)}")

    def disconnect_serial(self):
        self.is_connected = False
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.close()
            except:
                pass
        self.connect_btn.configure(text="Connect", fg_color="#238636", hover_color="#2ea043")
        self.status_badge.configure(text="● OFFLINE", text_color="#f85149")
        self.hw_stat_lbl.configure(text="Disconnected", text_color="#8b949e")

    def send_command(self, cmd):
        if self.is_connected and self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.write((cmd + "\n").encode("utf-8"))
            except Exception as e:
                print("Serial send error:", e)

    def serial_read_loop(self):
        while self.running and self.is_connected:
            try:
                if self.serial_conn and self.serial_conn.is_open:
                    line = self.serial_conn.readline()
                    if line:
                        decoded = line.decode("utf-8", errors="replace").strip()
                        if decoded:
                            self.process_serial_line(decoded)
            except serial.SerialException:
                # Connection lost
                self.after(0, self.disconnect_serial)
                break
            except Exception:
                time.sleep(0.05)

    def process_serial_line(self, line):
        print(f"[SERIAL]: {line}")

        # Check for structured DATA packet: [DATA] {"name":"John","roll":"101",...}
        if "[DATA]" in line:
            json_str = line[line.find("[DATA]") + 6:].strip()
            try:
                data = json.loads(json_str)
                name = data.get("name", "Unknown")
                roll = data.get("roll", "----")
                method = data.get("method", "Direct")
                self.after(0, self.add_attendance_record, roll, name, method)
            except Exception as e:
                print("JSON parse error:", e)

    def add_attendance_record(self, roll, name, method):
        now_time = datetime.now().strftime("%I:%M:%S %p")
        self.total_count += 1
        self.last_student = name
        self.last_roll = roll

        record = {
            "idx": self.total_count,
            "time": now_time,
            "roll": roll,
            "name": name,
            "method": method,
            "status": "Present"
        }
        self.attendance_records.append(record)

        # Insert at the top of the table
        self.tree.insert(
            "", 
            0, 
            values=(
                record["idx"],
                record["time"],
                record["roll"],
                record["name"],
                record["method"],
                record["status"]
            )
        )

        # Update Stat Cards
        self.count_stat_lbl.configure(text=str(self.total_count))
        self.student_stat_lbl.configure(text=f"{name} ({roll})")

    def export_csv(self):
        if not self.attendance_records:
            messagebox.showinfo("Export", "No attendance records to export yet!")
            return

        filename = f"attendance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=filename,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if path:
            try:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["#", "Timestamp", "Roll Number", "Student Name", "Verification Method", "Status"])
                    for r in self.attendance_records:
                        writer.writerow([r["idx"], r["time"], r["roll"], r["name"], r["method"], r["status"]])
                messagebox.showinfo("Export Success", f"Attendance exported successfully to:\n{path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to save CSV:\n{str(e)}")

    def clear_logs(self):
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all attendance records?"):
            self.attendance_records.clear()
            self.total_count = 0
            self.last_student = "None"
            self.last_roll = "----"

            for item in self.tree.get_children():
                self.tree.delete(item)

            self.count_stat_lbl.configure(text="0")
            self.student_stat_lbl.configure(text="None (----)")
            self.send_command("CMD:CLEAR")

    def on_closing(self):
        self.running = False
        self.disconnect_serial()
        self.destroy()

if __name__ == "__main__":
    app = AttendanceApp()
    app.mainloop()
