import os
import subprocess
import threading
import math
# pyrefly: ignore [missing-import]
import customtkinter as ctk
from tkinter import filedialog, messagebox
# pyrefly: ignore [missing-import]
import imageio_ffmpeg
import re

class VideoSplitterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Video Splitter - 5 Seconds")
        self.geometry("650x450")
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # --- Variables ---
        self.video_path_var = ctk.StringVar()
        self.output_dir_var = ctk.StringVar()
        self.project_name_var = ctk.StringVar()

        # --- UI Elements ---
        self.grid_columnconfigure(1, weight=1)

        # Title Label
        self.lbl_title = ctk.CTkLabel(self, text="Auto Video Splitter", font=("Helvetica", 24, "bold"))
        self.lbl_title.grid(row=0, column=0, columnspan=3, pady=(20, 10))

        # Video File Selection
        self.lbl_video = ctk.CTkLabel(self, text="Video File:")
        self.lbl_video.grid(row=1, column=0, padx=20, pady=(20, 10), sticky="w")
        self.entry_video = ctk.CTkEntry(self, textvariable=self.video_path_var, width=300)
        self.entry_video.grid(row=1, column=1, padx=(0, 20), pady=(20, 10), sticky="ew")
        self.btn_video = ctk.CTkButton(self, text="Browse", command=self.browse_video, width=100)
        self.btn_video.grid(row=1, column=2, padx=(0, 20), pady=(20, 10))

        # Output Directory Selection
        self.lbl_output = ctk.CTkLabel(self, text="Output Directory:")
        self.lbl_output.grid(row=2, column=0, padx=20, pady=10, sticky="w")
        self.entry_output = ctk.CTkEntry(self, textvariable=self.output_dir_var, width=300)
        self.entry_output.grid(row=2, column=1, padx=(0, 20), pady=10, sticky="ew")
        self.btn_output = ctk.CTkButton(self, text="Browse", command=self.browse_output, width=100)
        self.btn_output.grid(row=2, column=2, padx=(0, 20), pady=10)

        # Project Name
        self.lbl_project = ctk.CTkLabel(self, text="Project Name:")
        self.lbl_project.grid(row=3, column=0, padx=20, pady=10, sticky="w")
        self.entry_project = ctk.CTkEntry(self, textvariable=self.project_name_var, width=300)
        self.entry_project.grid(row=3, column=1, padx=(0, 20), pady=10, sticky="ew")

        # Progress
        self.lbl_status = ctk.CTkLabel(self, text="Ready", text_color="gray")
        self.lbl_status.grid(row=4, column=0, columnspan=3, padx=20, pady=(20, 5))
        
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=5, column=0, columnspan=3, padx=40, pady=10, sticky="ew")
        self.progress_bar.set(0)

        # Start Button
        self.btn_start = ctk.CTkButton(self, text="Start Splitting (5 Sec)", command=self.start_splitting_thread, height=40, font=("Helvetica", 14, "bold"))
        self.btn_start.grid(row=6, column=0, columnspan=3, padx=20, pady=20)

    def browse_video(self):
        filename = filedialog.askopenfilename(
            title="Select Video",
            filetypes=(("Video Files", "*.mp4 *.avi *.mkv *.mov"), ("All Files", "*.*"))
        )
        if filename:
            self.video_path_var.set(filename)

    def browse_output(self):
        directory = filedialog.askdirectory(title="Select Output Directory")
        if directory:
            self.output_dir_var.set(directory)

    def start_splitting_thread(self):
        video_path = self.video_path_var.get()
        output_dir = self.output_dir_var.get()
        project_name = self.project_name_var.get()

        if not video_path or not os.path.exists(video_path):
            messagebox.showerror("Error", "Please select a valid video file.")
            return
        if not output_dir or not os.path.exists(output_dir):
            messagebox.showerror("Error", "Please select a valid output directory.")
            return
        if not project_name:
            messagebox.showerror("Error", "Please enter a project name.")
            return

        self.btn_start.configure(state="disabled")
        self.progress_bar.set(0)
        self.lbl_status.configure(text="Initializing ffmpeg...", text_color="white")
        
        # Run in a separate thread so GUI doesn't freeze
        thread = threading.Thread(target=self.split_video, args=(video_path, output_dir, project_name))
        thread.daemon = True
        thread.start()

    def split_video(self, video_path, output_dir, project_name):
        try:
            # imageio_ffmpeg provides an ffmpeg executable path even if not installed on system
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            
            # Create project directory
            project_dir = os.path.join(output_dir, project_name)
            os.makedirs(project_dir, exist_ok=True)
            
            self.lbl_status.configure(text="Calculating video duration...")
            duration = self.get_video_duration(ffmpeg_exe, video_path)
            
            if duration <= 0:
                self.update_gui_error("Could not determine video duration. The file might be corrupted or not a valid video.")
                return

            clip_duration = 5 # seconds
            total_clips = math.ceil(duration / clip_duration)
            
            # We use ffmpeg's segment muxer. -c copy is very fast and doesn't re-encode,
            # but it splits at keyframes so it might not be *exactly* 5 seconds if keyframes are sparse.
            # However, for a fast splitter, this is the standard approach. If exact times are needed,
            # re-encoding (-c:v libx264) is required, which takes much longer. We'll use -c copy for speed.
            output_pattern = os.path.join(project_dir, f"{project_name}_clip_%03d.mp4")
            
            cmd = [
                ffmpeg_exe,
                "-y", # overwrite output
                "-i", video_path,
                "-c", "copy",
                "-map", "0",
                "-segment_time", str(clip_duration),
                "-f", "segment",
                "-reset_timestamps", "1",
                output_pattern
            ]
            
            self.lbl_status.configure(text=f"Splitting into ~{total_clips} clips... Please wait.")
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                print(stderr)
                self.update_gui_error("An error occurred during splitting. Check console output.")
                return
                
            self.update_gui_success(f"Successfully created {total_clips} clips in:\n{project_dir}")

        except Exception as e:
            self.update_gui_error(f"Error: {str(e)}")

    def get_video_duration(self, ffmpeg_exe, video_path):
        # Extract duration by parsing ffmpeg stderr
        cmd = [ffmpeg_exe, "-i", video_path]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        _, stderr = process.communicate()
        
        # Look for "Duration: 00:00:00.00"
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = float(match.group(3))
            return hours * 3600 + minutes * 60 + seconds
        return 0

    def update_gui_success(self, message):
        self.after(0, self._update_gui_success, message)
        
    def _update_gui_success(self, message):
        self.progress_bar.set(1.0)
        self.lbl_status.configure(text="Finished!", text_color="green")
        messagebox.showinfo("Success", message)
        self.btn_start.configure(state="normal")

    def update_gui_error(self, message):
        self.after(0, self._update_gui_error, message)
        
    def _update_gui_error(self, message):
        self.lbl_status.configure(text="Failed.", text_color="red")
        messagebox.showerror("Error", message)
        self.btn_start.configure(state="normal")

if __name__ == "__main__":
    app = VideoSplitterApp()
    app.mainloop()
