#!/usr/bin/env python3
"""
FLAC to MKV Converter for Blu-ray Audio
Converts FLAC audio files into an MKV video with album artwork and track titles.
Preserves original audio quality and creates chapters for each track.
"""

import os
import sys
import subprocess
import json
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import mutagen
from mutagen.flac import FLAC


class FlacToMkvConverter:
    def __init__(self):
        self.flac_files = []
        self.cover_art_path = ""
        self.output_path = ""
        self.temp_dir = None
        
    def select_flac_files(self):
        """Select FLAC audio files"""
        files = filedialog.askopenfilenames(
            title="Select FLAC files",
            filetypes=[("FLAC files", "*.flac"), ("All files", "*.*")]
        )
        if files:
            self.flac_files = sorted(files)  # Sort to maintain track order
            return True
        return False
    
    def select_cover_art(self):
        """Select album cover art"""
        file = filedialog.askopenfilename(
            title="Select album cover art",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
        )
        if file:
            self.cover_art_path = file
            return True
        return False
    
    def select_output_path(self):
        """Select output MKV file path"""
        file = filedialog.asksaveasfilename(
            title="Save MKV as",
            defaultextension=".mkv",
            filetypes=[("MKV files", "*.mkv"), ("All files", "*.*")]
        )
        if file:
            self.output_path = file
            return True
        return False
    
    def get_track_metadata(self, flac_path):
        """Extract metadata from FLAC file"""
        try:
            audio = FLAC(flac_path)
            title = audio.get('TITLE', [os.path.splitext(os.path.basename(flac_path))[0]])[0]
            artist = audio.get('ARTIST', ['Unknown Artist'])[0]
            album = audio.get('ALBUM', ['Unknown Album'])[0]
            track_num = audio.get('TRACKNUMBER', ['1'])[0]
            
            # Get audio properties
            sample_rate = audio.info.sample_rate
            bits_per_sample = audio.info.bits_per_sample
            channels = audio.info.channels
            duration = audio.info.length
            
            return {
                'title': title,
                'artist': artist,
                'album': album,
                'track_number': track_num,
                'duration': duration,
                'sample_rate': sample_rate,
                'bits_per_sample': bits_per_sample,
                'channels': channels
            }
        except Exception as e:
            print(f"Error reading metadata from {flac_path}: {e}")
            return {
                'title': os.path.splitext(os.path.basename(flac_path))[0],
                'artist': 'Unknown Artist',
                'album': 'Unknown Album',
                'track_number': '1',
                'duration': 0,
                'sample_rate': 44100,
                'bits_per_sample': 16,
                'channels': 2
            }
    
    def create_video_frame(self, cover_art_path, track_title, track_number, artist, album):
        """Create a video frame with album art and track info"""
        # Standard widescreen dimensions (1920x1080)
        width, height = 1920, 1080
        
        # Create new image with black background
        frame = Image.new('RGB', (width, height), color='black')
        draw = ImageDraw.Draw(frame)
        
        # Load and resize cover art for left side
        try:
            cover = Image.open(cover_art_path)
            # Resize cover art to fit left side with some padding
            cover_size = min(height - 100, width // 2 - 100)  # Leave 50px padding on each side
            cover = cover.resize((cover_size, cover_size), Image.Resampling.LANCZOS)
            
            # Center the cover art on the left side
            cover_x = (width // 2 - cover_size) // 2
            cover_y = (height - cover_size) // 2
            frame.paste(cover, (cover_x, cover_y))
        except Exception as e:
            print(f"Error loading cover art: {e}")
            # Draw a placeholder rectangle if cover art fails to load
            placeholder_size = min(height - 100, width // 2 - 100)
            placeholder_x = (width // 2 - placeholder_size) // 2
            placeholder_y = (height - placeholder_size) // 2
            draw.rectangle([placeholder_x, placeholder_y, 
                          placeholder_x + placeholder_size, 
                          placeholder_y + placeholder_size], 
                          outline='white', width=2)
            draw.text((placeholder_x + placeholder_size//2, placeholder_y + placeholder_size//2), 
                     "No Cover Art", fill='white', anchor='mm')
        
        # Add text on the right side
        try:
            # Try to load a nice font, fallback to default if not available
            try:
                title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 72)
                info_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
                small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
            except:
                title_font = ImageFont.load_default()
                info_font = ImageFont.load_default()
                small_font = ImageFont.load_default()
            
            # Text area starts at middle of screen
            text_start_x = width // 2 + 50
            text_width = width // 2 - 100
            
            # Track number and title
            track_text = f"{track_number:02d}. {track_title}"
            y_pos = height // 2 - 100
            
            # Word wrap for long titles
            lines = self.wrap_text(track_text, title_font, text_width, draw)
            for line in lines:
                draw.text((text_start_x, y_pos), line, fill='white', font=title_font)
                y_pos += 80
            
            # Artist and album info
            y_pos += 40
            draw.text((text_start_x, y_pos), artist, fill='lightgray', font=info_font)
            y_pos += 60
            draw.text((text_start_x, y_pos), album, fill='lightgray', font=small_font)
            
        except Exception as e:
            print(f"Error adding text to frame: {e}")
        
        return frame
    
    def wrap_text(self, text, font, max_width, draw):
        """Wrap text to fit within specified width"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)  # Single word longer than max_width
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def convert_to_mkv(self, progress_callback=None):
        """Convert FLAC files to MKV with video frames"""
        if not self.flac_files or not self.cover_art_path or not self.output_path:
            raise ValueError("Missing required files or output path")
        
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp(prefix="flac_to_mkv_")
        
        try:
            total_duration = 0
            chapter_data = []
            video_segments = []
            audio_segments = []
            
            for i, flac_file in enumerate(self.flac_files):
                if progress_callback:
                    progress_callback(f"Processing track {i+1}/{len(self.flac_files)}", 
                                    (i * 50) // len(self.flac_files))
                
                # Get metadata
                metadata = self.get_track_metadata(flac_file)
                
                # Create video frame
                frame = self.create_video_frame(
                    self.cover_art_path,
                    metadata['title'],
                    metadata['track_number'],
                    metadata['artist'],
                    metadata['album']
                )
                
                # Save frame as image
                frame_path = os.path.join(self.temp_dir, f"frame_{i:03d}.png")
                frame.save(frame_path, "PNG")
                
                # Create video segment from static image
                video_path = os.path.join(self.temp_dir, f"video_{i:03d}.mkv")
                duration = metadata['duration']
                
                # Create video with preserved audio quality
                cmd = [
                    'ffmpeg', '-y',
                    '-loop', '1', '-i', frame_path,  # Static image
                    '-i', flac_file,  # Audio input
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                    '-c:a', 'copy',  # Copy audio without re-encoding to preserve quality
                    '-t', str(duration),
                    '-pix_fmt', 'yuv420p',
                    '-r', '1',  # 1 fps for static image
                    video_path
                ]
                
                subprocess.run(cmd, check=True, capture_output=True)
                video_segments.append(video_path)
                
                # Add chapter information
                chapter_data.append({
                    'start': total_duration,
                    'end': total_duration + duration,
                    'title': f"{metadata['track_number']:02d}. {metadata['title']}"
                })
                
                total_duration += duration
            
            if progress_callback:
                progress_callback("Combining segments...", 50)
            
            # Create chapter file
            chapter_file = os.path.join(self.temp_dir, "chapters.txt")
            self.create_chapter_file(chapter_file, chapter_data)
            
            # Combine all video segments
            concat_file = os.path.join(self.temp_dir, "concat.txt")
            with open(concat_file, 'w') as f:
                for video_path in video_segments:
                    f.write(f"file '{video_path}'\n")
            
            if progress_callback:
                progress_callback("Creating final MKV...", 75)
            
            # Final concatenation with chapters
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat', '-safe', '0', '-i', concat_file,
                '-i', chapter_file,
                '-c', 'copy',
                '-map_metadata', '1',
                self.output_path
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            if progress_callback:
                progress_callback("Complete!", 100)
            
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            raise RuntimeError(f"FFmpeg error: {error_msg}")
        except Exception as e:
            raise RuntimeError(f"Conversion error: {str(e)}")
        finally:
            # Cleanup temporary files
            if self.temp_dir and os.path.exists(self.temp_dir):
                import shutil
                try:
                    shutil.rmtree(self.temp_dir)
                except:
                    pass  # Ignore cleanup errors
    
    def create_chapter_file(self, chapter_file, chapter_data):
        """Create chapter metadata file for MKV"""
        with open(chapter_file, 'w') as f:
            f.write(";FFMETADATA1\n")
            for i, chapter in enumerate(chapter_data):
                start_time = int(chapter['start'] * 1000)  # Convert to milliseconds
                end_time = int(chapter['end'] * 1000)
                f.write(f"[CHAPTER]\n")
                f.write(f"TIMEBASE=1/1000\n")
                f.write(f"START={start_time}\n")
                f.write(f"END={end_time}\n")
                f.write(f"title={chapter['title']}\n")


class ConverterGUI:
    def __init__(self):
        self.converter = FlacToMkvConverter()
        self.root = tk.Tk()
        self.root.title("FLAC to MKV Converter")
        self.root.geometry("600x500")
        
        self.setup_gui()
    
    def setup_gui(self):
        """Setup the GUI interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="FLAC to MKV Converter", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # FLAC files selection
        ttk.Label(main_frame, text="FLAC Files:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.flac_label = ttk.Label(main_frame, text="No files selected", 
                                   foreground="gray")
        self.flac_label.grid(row=1, column=1, sticky=tk.W, padx=(10, 0))
        
        ttk.Button(main_frame, text="Select FLAC Files", 
                  command=self.select_flac_files).grid(row=2, column=0, sticky=tk.W, pady=5)
        
        # Cover art selection
        ttk.Label(main_frame, text="Cover Art:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.cover_label = ttk.Label(main_frame, text="No cover art selected", 
                                    foreground="gray")
        self.cover_label.grid(row=3, column=1, sticky=tk.W, padx=(10, 0))
        
        ttk.Button(main_frame, text="Select Cover Art", 
                  command=self.select_cover_art).grid(row=4, column=0, sticky=tk.W, pady=5)
        
        # Output path selection
        ttk.Label(main_frame, text="Output MKV:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.output_label = ttk.Label(main_frame, text="No output path selected", 
                                     foreground="gray")
        self.output_label.grid(row=5, column=1, sticky=tk.W, padx=(10, 0))
        
        ttk.Button(main_frame, text="Select Output Path", 
                  command=self.select_output_path).grid(row=6, column=0, sticky=tk.W, pady=5)
        
        # Convert button
        self.convert_btn = ttk.Button(main_frame, text="Convert to MKV", 
                                     command=self.start_conversion, state="disabled")
        self.convert_btn.grid(row=7, column=0, columnspan=2, pady=20)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='determinate')
        self.progress.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready")
        self.status_label.grid(row=9, column=0, columnspan=2, pady=5)
        
        # Info text
        info_text = ("This tool converts FLAC audio files to MKV video format with album artwork.\n"
                    "Each track becomes a chapter with preserved audio quality.\n"
                    "Requires: FFmpeg, Python libraries (PIL, mutagen)")
        
        info_label = ttk.Label(main_frame, text=info_text, wraplength=580, 
                              justify=tk.CENTER, foreground="gray")
        info_label.grid(row=10, column=0, columnspan=2, pady=20)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
    
    def select_flac_files(self):
        """Handle FLAC file selection"""
        if self.converter.select_flac_files():
            count = len(self.converter.flac_files)
            self.flac_label.config(text=f"{count} files selected", foreground="black")
            self.check_ready()
    
    def select_cover_art(self):
        """Handle cover art selection"""
        if self.converter.select_cover_art():
            filename = os.path.basename(self.converter.cover_art_path)
            self.cover_label.config(text=filename, foreground="black")
            self.check_ready()
    
    def select_output_path(self):
        """Handle output path selection"""
        if self.converter.select_output_path():
            filename = os.path.basename(self.converter.output_path)
            self.output_label.config(text=filename, foreground="black")
            self.check_ready()
    
    def check_ready(self):
        """Check if all required inputs are selected"""
        if (self.converter.flac_files and 
            self.converter.cover_art_path and 
            self.converter.output_path):
            self.convert_btn.config(state="normal")
    
    def update_progress(self, status, progress):
        """Update progress bar and status"""
        self.status_label.config(text=status)
        self.progress['value'] = progress
        self.root.update_idletasks()
    
    def start_conversion(self):
        """Start the conversion process"""
        self.convert_btn.config(state="disabled")
        self.progress['value'] = 0
        
        try:
            self.converter.convert_to_mkv(self.update_progress)
            messagebox.showinfo("Success", "MKV file created successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Conversion failed: {str(e)}")
        finally:
            self.convert_btn.config(state="normal")
            self.status_label.config(text="Ready")
            self.progress['value'] = 0
    
    def run(self):
        """Run the GUI application"""
        self.root.mainloop()


def check_dependencies():
    """Check if required dependencies are available"""
    missing = []
    
    # Check FFmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing.append("FFmpeg")
    
    # Check Python libraries
    try:
        import PIL
    except ImportError:
        missing.append("Pillow (pip install Pillow)")
    
    try:
        import mutagen
    except ImportError:
        missing.append("mutagen (pip install mutagen)")
    
    return missing


def main():
    """Main entry point"""
    print("FLAC to MKV Converter")
    print("=" * 30)
    
    # Check dependencies
    missing = check_dependencies()
    if missing:
        print("Missing dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nPlease install missing dependencies and try again.")
        return 1
    
    # Check if running with GUI or command line
    if len(sys.argv) == 1:
        # GUI mode
        try:
            app = ConverterGUI()
            app.run()
        except Exception as e:
            print(f"GUI Error: {e}")
            print("Try running in command line mode with arguments.")
            return 1
    else:
        print("Command line mode not yet implemented. Please run without arguments for GUI.")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())