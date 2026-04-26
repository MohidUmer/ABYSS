import os
import sys
import threading
import re
import json
import datetime

import customtkinter as ctk
from tkinter import ttk
from tkinter import Canvas
import tkinter.messagebox as messagebox
import logging
from datetime import datetime
import platform

# Matplotlib imports for Neural Map
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

try:
    from PIL import Image, ImageTk, ImageEnhance
except Exception:
    Image = None
    ImageTk = None
    ImageEnhance = None

from modules.utils import setup_logging, ensure_dir, calculate_hash
from modules.browser_parser import get_browser_paths, extract_history_data, save_profile_csv, generate_metadata_log
from modules.notepad_parser import parse_notepad_tabs
from modules.analysis_engine import analyze_artifacts
from modules.report_generator import ReportGenerator

class UI:
    """DFIR-grade design tokens (colors/typography/spacing)."""
    # Palette: deep blue-grey + restrained accent (matching reference image)
    BG = "#0D1117"
    PANEL = "#161B22"
    PANEL_2 = "#1F2430"
    BORDER = "#30363D"
    TEXT = "#E6EDF3"
    TEXT_MUTED = "#8B949E"
    ACCENT = "#58A6FF"     # blue accent
    ACCENT_2 = "#79C0FF"   # lighter blue highlight
    WARN = "#D29922"
    CRIT = "#F85149"
    OK = "#3FB950"

    # Spacing / radii
    PAD_X = 18
    PAD_Y = 14
    RADIUS = 14

    # Typography (Windows-friendly)
    FONT_UI = "Segoe UI"
    FONT_MONO = "Cascadia Mono"
    FONT_BRAND = "Bahnschrift"

    @staticmethod
    def font(size: int, weight: str = "normal"):
        return (UI.FONT_UI, size, weight)

    @staticmethod
    def mono(size: int, weight: str = "normal"):
        return (UI.FONT_MONO, size, weight)

F_MAIN = UI.font(13)
F_TITLE = UI.font(28, "bold")
F_SUB = UI.font(14, "bold")
F_BRAND = (UI.FONT_BRAND, 34, "bold")
F_BRAND_SUB = (UI.FONT_BRAND, 16, "normal")

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")


def _hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def remove_background(img):
    """Remove background by detecting and making the most common color transparent."""
    if Image is None:
        return img
    try:
        img = img.convert("RGBA")
        # Use get_flattened_data for newer Pillow versions
        try:
            datas = img.get_flattened_data()
        except AttributeError:
            datas = img.getdata()
        
        # Find the most common color (likely background)
        color_count = {}
        for item in datas:
            if item[3] > 0:  # Only count non-transparent pixels
                rgb = (item[0], item[1], item[2])
                color_count[rgb] = color_count.get(rgb, 0) + 1
        
        if color_count:
            bg_color = max(color_count, key=color_count.get)
            bg_r, bg_g, bg_b = bg_color
            
            new_data = []
            for item in datas:
                r, g, b, a = item
                if a > 0:
                    # Calculate color distance from background
                    distance = ((r - bg_r)**2 + (g - bg_g)**2 + (b - bg_b)**2)**0.5
                    # If pixel is close to background color, make transparent
                    if distance < 50:  # Threshold for similarity
                        new_data.append((r, g, b, 0))
                    else:
                        new_data.append(item)
                else:
                    new_data.append(item)
            img.putdata(new_data)
        return img
    except Exception:
        return img

def color_grade_logo_base(img_path: str, target_hex: str, size=(220, 220)):
    """Load logo, remove background, resize, and sharpen."""
    if Image is None:
        return None
    try:
        base = Image.open(img_path).convert("RGBA")
        # Remove background first
        base = remove_background(base)
        # Resize with high-quality resampling
        base = base.resize(size, Image.LANCZOS)
        # Apply sharpening for crisp edges
        if ImageEnhance is not None:
            base = ImageEnhance.Sharpness(base).enhance(1.5)
        return base
    except Exception:
        return None


class VoidLoader(ctk.CTkFrame):
    """Circular 'Void' loader that fills from center outward."""
    def __init__(self, master, size=64, color="#C3073F", bg=None):
        super().__init__(master, fg_color="transparent")
        self._size = size
        self._color = color
        self._bg = bg or UI.PANEL
        self._t = 0
        self._running = False

        self._canvas = Canvas(self, width=size, height=size, highlightthickness=0, bg=self._bg)
        self._canvas.pack()

    def start(self):
        if self._running:
            return
        self._running = True
        self._tick()

    def stop(self):
        self._running = False

    def _tick(self):
        if not self._running:
            return
        self._canvas.delete("all")
        cx = cy = self._size / 2
        max_r = (self._size / 2) - 3
        # Fill from center out: animated radius
        frac = (self._t % 100) / 100.0
        r = 6 + frac * (max_r - 6)

        # Outer ring (subtle)
        self._canvas.create_oval(3, 3, self._size - 3, self._size - 3, outline=UI.BORDER, width=2)
        # Inner fill (void pulse)
        self._canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline="", fill=self._color)
        # Soft glow halo
        halo = min(max_r, r + 6)
        self._canvas.create_oval(cx - halo, cy - halo, cx + halo, cy + halo, outline=self._color, width=2)

        self._t += 4
        self.after(30, self._tick)

class AbyssLogHandler(logging.Handler):
    """Custom log handler with syntax highlighting for ABYSS console."""
    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget
        
        # Configure tags
        self.text_widget.tag_config("timestamp", foreground=UI.TEXT_MUTED)
        self.text_widget.tag_config("info", foreground=UI.ACCENT)
        self.text_widget.tag_config("warn", foreground=UI.WARN)
        self.text_widget.tag_config("error", foreground=UI.CRIT)
        self.text_widget.tag_config("default", foreground=UI.TEXT)

    def emit(self, record):
        try:
            msg = self.format(record)
            level = record.levelname
            timestamp = datetime.now().strftime('%H:%M:%S')
            if self.formatter and hasattr(self.formatter, 'formatTime'):
                try:
                    timestamp = self.formatter.formatTime(record)
                except:
                    pass
            clean_msg = record.getMessage()
            
            def append():
                try:
                    self.text_widget.configure(state="normal")
                    self.text_widget.insert(ctk.END, f"[{timestamp}] ", "timestamp")
                    
                    if level == "INFO":
                        self.text_widget.insert(ctk.END, f"INFO: {clean_msg}\n", "info")
                    elif level == "WARNING":
                        self.text_widget.insert(ctk.END, f"WARN: {clean_msg}\n", "warn")
                    elif level in ["ERROR", "CRITICAL"]:
                        self.text_widget.insert(ctk.END, f"ERROR: {clean_msg}\n", "error")
                    else:
                        self.text_widget.insert(ctk.END, f"{level}: {clean_msg}\n", "default")
                except Exception as e:
                    print(f"Log Error: {e}")
                finally:
                    self.text_widget.configure(state="disabled")
                    self.text_widget.yview(ctk.END)
                
            self.text_widget.after(0, append)
        except Exception as e:
            print(f"AbyssLogHandler Emit Error: {e}")

class UnderlineEntry(ctk.CTkFrame):
    """Custom input field that looks like a glowing bottom-line only."""
    def __init__(self, master, placeholder, **kwargs):
        super().__init__(master, fg_color="transparent", height=40)
        self.pack_propagate(False)
        
        self.entry = ctk.CTkEntry(
            self,
            placeholder_text=placeholder,
            fg_color="transparent",
            border_width=0,
            font=F_MAIN,
            text_color=UI.TEXT,
            **kwargs
        )
        self.entry.pack(fill="x", expand=True, side="top")
        
        self.line = ctk.CTkFrame(self, height=2, fg_color=UI.BORDER)
        self.line.pack(fill="x", side="bottom")
        
        self.entry.bind("<FocusIn>", self.on_focus)
        self.entry.bind("<FocusOut>", self.on_leave)
        
    def on_focus(self, event):
        self.line.configure(fg_color=UI.ACCENT)
        
    def on_leave(self, event):
        self.line.configure(fg_color=UI.BORDER)
        
    def get(self):
        return self.entry.get()
        
    def insert(self, index, text):
        self.entry.insert(index, text)

class AbyssSuite(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ABYSS | Advanced Binary Yield & Systematic Scrape")
        self.geometry("1100x800")
        self.configure(fg_color=UI.BG)
        
        self.case_metadata = {}
        self.browser_paths = []
        self.log_file = setup_logging()
        self._vault_export_dir = None
        self._vault_tree_node_to_path = {}
        self._vault_current_dir = None
        self._vault_selected_file = None
        self._vault_preview_cache = {}   # path -> {"data": str, "hex": str, "skin_base": str, "sha": str}
        self._vault_preview_job = None
        self._hash_cache = {}            # path -> sha256
        # CustomTkinter forbids bind_all; bind at root window instead.
        self.bind("<Control-f>", self._shortcut_focus_evidence_search)

        # Wizard state (persists across phases/back)
        self._wiz_case_id = ctk.StringVar()
        self._wiz_inv_name = ctk.StringVar()
        self._wiz_agency = ctk.StringVar()
        self._wiz_op_sig = ctk.StringVar()
        self._wiz_hostname = ctk.StringVar(value=(platform.node() or "UNKNOWN"))
        self._wiz_output_path = ctk.StringVar(value="reports")
        self._wiz_desc_value = ""
        
        self.show_wizard_frame()

    def _shortcut_focus_evidence_search(self, event=None):
        # Placeholder for future: keep shortcut reserved (elite tools feel \"keyboard-native\")
        # For now, just jump to Evidence Vault.
        try:
            if hasattr(self, "tab_view"):
                self.tab_view.set("Evidence Vault")
        except Exception:
            pass

    def show_wizard_frame(self):
        self.wizard_frame = ctk.CTkFrame(
            self,
            fg_color=UI.PANEL,
            corner_radius=UI.RADIUS,
            border_width=1,
            border_color=UI.BORDER
        )
        # Bigger center box
        self.wizard_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.84, relheight=0.84)

        # Use grid so we can keep header/footer fixed and middle scrollable
        for w in self.wizard_frame.winfo_children():
            w.destroy()
        self.wizard_frame.grid_rowconfigure(1, weight=1)
        self.wizard_frame.grid_columnconfigure(0, weight=1)

        # ---- Primary Branding (center top) ----
        brand_frame = ctk.CTkFrame(self.wizard_frame, fg_color="transparent")
        brand_frame.grid(row=0, column=0, sticky="ew", pady=(22, 6))
        brand_frame.grid_columnconfigure(0, weight=1)

        self._logo_src_path = os.path.join("assets", "abyss_logo.png")
        self._logo_target_hex = "#FF6B35"  # Orange-red color
        self._logo_pulse_phase = 0
        self._logo_ctk_img = None
        self._logo_animation_enabled = True  # Can be disabled for performance

        # Logo and title side by side
        logo_container = ctk.CTkFrame(brand_frame, fg_color="transparent")
        logo_container.grid(row=0, column=0)
        logo_container.grid_columnconfigure(1, weight=1)

        self.logo_label = ctk.CTkLabel(logo_container, text="")
        self.logo_label.grid(row=0, column=0, padx=(0, 12))

        title_label = ctk.CTkLabel(
            logo_container,
            text="NEW INVESTIGATION CASE",
            font=UI.font(24, "bold"),
            text_color=UI.TEXT
        )
        title_label.grid(row=0, column=1)

        # Mode toggle: New vs Open Existing
        mode_frame = ctk.CTkFrame(brand_frame, fg_color="transparent")
        mode_frame.grid(row=1, column=0, sticky="w", pady=(12, 0), padx=32)
        mode_frame.grid_columnconfigure(0, weight=0)
        mode_frame.grid_columnconfigure(1, weight=0)

        self._wiz_mode_var = ctk.StringVar(value="new")
        
        new_radio = ctk.CTkRadioButton(
            mode_frame, 
            text="New Investigation", 
            variable=self._wiz_mode_var, 
            value="new",
            command=self._on_wizard_mode_change,
            font=UI.font(12),
            text_color=UI.TEXT
        )
        new_radio.grid(row=0, column=0, sticky="w", padx=(0, 30))
        
        open_radio = ctk.CTkRadioButton(
            mode_frame, 
            text="Open Existing Report", 
            variable=self._wiz_mode_var, 
            value="open",
            command=self._on_wizard_mode_change,
            font=UI.font(12),
            text_color=UI.TEXT
        )
        open_radio.grid(row=0, column=1, sticky="w")

        # start logo animation (safe if Pillow missing; label stays empty)
        # Slower animation for better performance
        self._render_logo_pulse()

        # ---- Single-page scrollable form with three sections ----
        scrollable_frame = ctk.CTkScrollableFrame(
            self.wizard_frame,
            fg_color="transparent",
            label_text=""
        )
        scrollable_frame.grid(row=1, column=0, sticky="nsew", padx=32, pady=(0, 0))
        scrollable_frame.grid_columnconfigure(0, weight=1)

        def section_card(parent, title: str):
            wrap = ctk.CTkFrame(parent, fg_color=UI.PANEL_2, corner_radius=UI.RADIUS, border_width=1, border_color=UI.BORDER)
            wrap.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(wrap, text=title, font=UI.font(16, "bold"), text_color=UI.TEXT).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 2))
            return wrap

        def field(parent, row_idx, label, var=None, placeholder="", hint="", readonly=False, suffix=None, bind_validate=False):
            ctk.CTkLabel(parent, text=label, font=UI.font(12, "bold"), text_color=UI.TEXT).grid(row=row_idx, column=0, sticky="w", padx=18, pady=(8, 2))
            cell = ctk.CTkFrame(parent, fg_color="transparent")
            cell.grid(row=row_idx + 1, column=0, sticky="ew", padx=18)
            cell.grid_columnconfigure(0, weight=1)

            entry = ctk.CTkEntry(cell, textvariable=var, placeholder_text=placeholder, fg_color=UI.PANEL, text_color=UI.TEXT, font=UI.mono(11), border_color=UI.BORDER)
            entry.grid(row=0, column=0, sticky="ew")
            if readonly:
                entry.configure(state="readonly")
            if suffix is not None:
                suffix.grid(row=0, column=1, padx=(8, 0))

            if bind_validate:
                entry.bind("<KeyRelease>", self._validate_form)

            if hint:
                ctk.CTkLabel(parent, text=hint, font=UI.font(10), text_color=UI.TEXT_MUTED, wraplength=760, justify="left").grid(
                    row=row_idx + 2, column=0, sticky="w", padx=18, pady=(4, 6)
                )
            return entry

        # Set default values
        if not self._wiz_case_id.get().strip():
            self._wiz_case_id.set("ABYSS-20260423-001")
        if not self._wiz_inv_name.get().strip():
            self._wiz_inv_name.set("")
        if not self._wiz_hostname.get().strip():
            self._wiz_hostname.set(platform.node() or "UNKNOWN")
        if not self._wiz_output_path.get().strip():
            self._wiz_output_path.set("reports/")

        # Section 1: Case Information (for new investigation)
        self.card1 = section_card(scrollable_frame, "Case Information")
        self.card1.grid(row=0, column=0, sticky="nsew", pady=(0, 12))

        # Section for opening existing report
        self.card_open = section_card(scrollable_frame, "Open Existing Report")
        # Don't grid it initially, only show when mode is "open"

        # Add fields for opening existing report
        self._wiz_report_path = ctk.StringVar()
        self._wiz_report_sig = ctk.StringVar()

        report_path_field = field(
            self.card_open, 1,
            "Report Path",
            var=self._wiz_report_path,
            placeholder="Select existing report directory...",
            hint="Path to the ABYSS report directory (e.g., reports/ABYSS-20260423-001)",
            bind_validate=True
        )

        # Browse button for report path
        browse_btn = ctk.CTkButton(
            self.card_open,
            text="Browse",
            width=100,
            command=self._browse_report_path,
            fg_color=UI.ACCENT,
            hover_color=UI.ACCENT_2,
            text_color="white",
            font=UI.font(11)
        )
        browse_btn.grid(row=2, column=0, sticky="e", padx=18, pady=(4, 8))

        report_sig_field = field(
            self.card_open, 4,
            "Digital Signature",
            var=self._wiz_report_sig,
            placeholder="Enter signature used to lock the case...",
            hint="Digital signature that was used when the case was created (required for tamper verification).",
            bind_validate=True
        )

        self.case_id = field(
            self.card1, 1,
            "Case ID",
            var=self._wiz_case_id,
            placeholder="ABYSS-20260423-001",
            hint="Unique identifier for case correlation and custody tracking.",
            bind_validate=True
        )
        self.inv_name = field(
            self.card1, 4,
            "Investigator Name",
            var=self._wiz_inv_name,
            placeholder="Lead Agent [YourName]",
            hint="Assigns accountability for the collected evidence.",
            bind_validate=True
        )
        self.inv_agency = field(
            self.card1, 7,
            "Agency/ID",
            var=self._wiz_agency,
            placeholder="Agency Name or Badge ID",
            hint="Organization or identification number for the investigator.",
            bind_validate=True
        )
        self.inv_sig = field(
            self.card1, 10,
            "Digital Signature",
            var=self._wiz_op_sig,
            placeholder="[e.g., Cryptographic Key or Dept Code]",
            hint="Digital signature required to lock the case files; used for tamper detection.",
            bind_validate=True
        )

        # Section 2: System Context
        self.card2 = section_card(scrollable_frame, "System Context")
        self.card2.grid(row=1, column=0, sticky="nsew", pady=(0, 12))

        self.sys_hostname = field(
            self.card2, 1,
            "System Name",
            var=self._wiz_hostname,
            placeholder=f"System hostname will be auto-detected",
            hint="(Pre-filled/Read-Only) Defines the source of the evidence.",
            readonly=True
        )

        # Path to Save with inline browse button
        ctk.CTkLabel(self.card2, text="Path to Save", font=UI.font(12, "bold"), text_color=UI.TEXT).grid(row=4, column=0, sticky="w", padx=18, pady=(8, 2))
        path_cell = ctk.CTkFrame(self.card2, fg_color="transparent")
        path_cell.grid(row=5, column=0, sticky="ew", padx=18)
        path_cell.grid_columnconfigure(0, weight=1)
        
        self.output_path = ctk.CTkEntry(
            path_cell,
            textvariable=self._wiz_output_path,
            placeholder_text="reports/",
            fg_color=UI.PANEL,
            text_color=UI.TEXT,
            font=UI.mono(11),
            border_color=UI.BORDER
        )
        self.output_path.grid(row=0, column=0, sticky="ew")
        self.output_path.bind("<KeyRelease>", self._validate_form)
        
        browse_btn = ctk.CTkButton(path_cell, text="📂", width=42, fg_color=UI.PANEL, hover_color=UI.PANEL_2, text_color=UI.TEXT, corner_radius=10, command=self._browse_output_path)
        browse_btn.grid(row=0, column=1, padx=(8, 0))
        
        ctk.CTkLabel(self.card2, text="Default location for export; click 📂 to choose a custom path.", font=UI.font(10), text_color=UI.TEXT_MUTED, wraplength=760, justify="left").grid(
            row=6, column=0, sticky="w", padx=18, pady=(4, 6)
        )

        # Section 3: About
        self.card3 = section_card(scrollable_frame, "About")
        self.card3.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        self.card3.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.card3, text="Description", font=UI.font(12, "bold"), text_color=UI.TEXT).grid(row=1, column=0, sticky="w", padx=18, pady=(8, 2))
        self.case_desc = ctk.CTkTextbox(self.card3, height=120, fg_color=UI.PANEL, text_color=UI.TEXT, font=UI.mono(11))
        self.case_desc.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 6))
        self._set_textbox_placeholder(self.case_desc, "Briefly outline the investigation scope (e.g., 'Internal data leak analysis').")
        if self._wiz_desc_value.strip():
            self.case_desc.delete("0.0", "end")
            self.case_desc.insert("0.0", self._wiz_desc_value)
            self.case_desc.configure(text_color=UI.TEXT)
        self.case_desc.bind("<KeyRelease>", self._validate_form)
        ctk.CTkLabel(self.card3, text="Provides context for the final forensic report.", font=UI.font(10), text_color=UI.TEXT_MUTED).grid(
            row=3, column=0, sticky="w", padx=18, pady=(0, 10)
        )

        # Bottom controls (loader + engage)
        bottom = ctk.CTkFrame(self.wizard_frame, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", padx=32, pady=(8, 10))
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_columnconfigure(1, weight=0)

        self.void_loader = VoidLoader(bottom, size=58, color=self._logo_target_hex, bg=UI.PANEL)
        self.void_loader.grid(row=0, column=1, sticky="e")

        # Create centered button without logo, medium size
        button_container = ctk.CTkFrame(bottom, fg_color="transparent")
        button_container.grid(row=0, column=0, sticky="nsew")
        button_container.grid_columnconfigure(0, weight=1)

        self.btn_start = ctk.CTkButton(
            button_container,
            text="EXECUTE PROCESS",
            command=self.finish_wizard,
            fg_color=self._logo_target_hex,
            hover_color="#E55A2B",
            text_color=UI.TEXT,
            font=UI.font(13, "bold"),
            height=40,
            width=200,
            corner_radius=10,
            state="disabled"
        )
        self.btn_start.grid(row=0, column=0, pady=0)

        # Footer branding line
        self.footer_lbl = ctk.CTkLabel(
            self.wizard_frame,
            text="ABYSS ENGINE v3.3.8-STABLE | KERNEL_LINK: [Detecting...]",
            font=UI.mono(10),
            text_color=UI.TEXT_MUTED
        )
        self.footer_lbl.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self.footer_lbl.configure(anchor="center")

        # Initial validation
        self._validate_form()

    def _validate_form(self, _=None):
        """Enable execute button only when all required fields are filled."""
        mode = self._wiz_mode_var.get()
        
        if mode == "new":
            case_id = self._wiz_case_id.get().strip()
            inv_name = self._wiz_inv_name.get().strip()
            sig = self._wiz_op_sig.get().strip()
            output_path = self._wiz_output_path.get().strip()
            desc = self.case_desc.get("0.0", "end").strip() if hasattr(self, "case_desc") else self._wiz_desc_value
            
            # Check if description is still placeholder
            if "Briefly outline the investigation scope" in desc:
                desc = ""
            
            # Enable button only if all fields are filled
            all_filled = all([case_id, inv_name, sig, output_path, desc])
        else:
            # For opening existing report
            report_path = self._wiz_report_path.get().strip()
            report_sig = self._wiz_report_sig.get().strip()
            all_filled = all([report_path, report_sig])
        
        if all_filled:
            self.btn_start.configure(state="normal")
        else:
            self.btn_start.configure(state="disabled")

    def _on_wizard_mode_change(self):
        """Handle mode change between new investigation and opening existing report."""
        mode = self._wiz_mode_var.get()
        
        if mode == "new":
            self.card1.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
            self.card2.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
            self.card3.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
            self.card_open.grid_remove()
            self.btn_start.configure(text="INITIATE PROTOCOL")
        else:
            self.card1.grid_remove()
            self.card2.grid_remove()
            self.card3.grid_remove()
            self.card_open.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
            self.btn_start.configure(text="OPEN REPORT")
        
        self._validate_form()

    def _browse_report_path(self):
        """Browse for existing report directory."""
        from tkinter import filedialog
        report_dir = filedialog.askdirectory(
            title="Select ABYSS Report Directory",
            initialdir="reports"
        )
        if report_dir:
            self._wiz_report_path.set(report_dir)
            self._validate_form()

    def _render_sidebar_logo(self):
        """Render logo for sidebar - smaller version."""
        if Image is None or ImageTk is None:
            return
        try:
            if not os.path.exists(self._sidebar_logo_src_path):
                return
            
            # Load and resize logo for sidebar (smaller size)
            base = Image.open(self._sidebar_logo_src_path).convert("RGBA")
            base = base.resize((80, 80), Image.LANCZOS)
            # Remove background
            base = remove_background(base)
            # Apply sharpening
            if ImageEnhance is not None:
                base = ImageEnhance.Sharpness(base).enhance(1.5)
            
            self._sidebar_logo_ctk_img = ctk.CTkImage(light_image=base, dark_image=base, size=(80, 80))
            self.sidebar_logo_label.configure(image=self._sidebar_logo_ctk_img)
        except Exception:
            pass

    def _set_textbox_placeholder(self, textbox: ctk.CTkTextbox, placeholder: str):
        # Simple placeholder behavior for CTkTextbox
        def on_focus_in(_):
            if textbox.get("0.0", "end").strip() == placeholder:
                textbox.delete("0.0", "end")
                textbox.configure(text_color=UI.TEXT)

        def on_focus_out(_):
            if not textbox.get("0.0", "end").strip():
                textbox.insert("0.0", placeholder)
                textbox.configure(text_color=UI.TEXT_MUTED)

        textbox.bind("<FocusIn>", on_focus_in)
        textbox.bind("<FocusOut>", on_focus_out)
        if not textbox.get("0.0", "end").strip():
            textbox.insert("0.0", placeholder)
            textbox.configure(text_color=UI.TEXT_MUTED)

    def _browse_output_path(self):
        try:
            import tkinter.filedialog as fd
            path = fd.askdirectory(title="Select Output Directory")
            if path:
                self._wiz_output_path.set(path)
        except Exception:
            pass

    def _render_logo_pulse(self):
        """Render logo for wizard with pulse effect."""
        # Check if animation is disabled
        if hasattr(self, "_logo_animation_enabled") and not self._logo_animation_enabled:
            return
            
        try:
            if not self.logo_label.winfo_exists():
                return
        except:
            return

        if not os.path.exists(self._logo_src_path):
            return
        if Image is None or ImageTk is None:
            # Pillow missing: show a minimal fallback label
            try:
                self.logo_label.configure(text="(logo unavailable: install pillow)", text_color=UI.TEXT_MUTED, font=UI.mono(10))
            except:
                pass
            return

        if not hasattr(self, "_logo_base_img") or self._logo_base_img is None:
            self._logo_base_img = color_grade_logo_base(self._logo_src_path, self._logo_target_hex, size=(210, 210))

        base = getattr(self, "_logo_base_img", None)
        if base is None:
            return

        # Pulse brightness between ~0.92 and ~1.08 (cheap operation)
        phase = (self._logo_pulse_phase % 160) / 160.0
        pulse = 0.92 + 0.16 * (0.5 - abs(phase - 0.5)) * 2.0
        img = base
        if ImageEnhance is not None:
            img = ImageEnhance.Brightness(base).enhance(pulse)

        self._logo_ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(210, 210))
        try:
            self.logo_label.configure(image=self._logo_ctk_img)
        except:
            return

        self._logo_pulse_phase += 2
        self.after(150, self._render_logo_pulse)  # Slower animation for better performance

    def finish_wizard(self):
        mode = self._wiz_mode_var.get()
        
        if mode == "new":
            # Required for chain-of-custody locking
            case_id = self._wiz_case_id.get().strip()
            inv = self._wiz_inv_name.get().strip()
            agency = self._wiz_agency.get().strip()
            sig = self._wiz_op_sig.get().strip()
            desc = self.case_desc.get("0.0", "end").strip() if hasattr(self, "case_desc") else self._wiz_desc_value
            # If placeholder is still present, treat as empty
            if "Briefly outline the investigation scope" in desc:
                desc = ""

            if any(not v for v in (case_id, inv, sig, desc)):
                messagebox.showerror("Validation Error", "Incomplete Initialization Parameters.")
                return
            
            # Check if case ID already exists (prevent overwriting)
            output_path = self._wiz_output_path.get().strip()
            case_dir = os.path.join(output_path, case_id)
            if os.path.exists(case_dir):
                response = messagebox.askyesno("Case ID Already Exists", 
                                               f"A case with ID '{case_id}' already exists at:\n{case_dir}\n\n"
                                               "Do you want to overwrite the existing case? "
                                               "This will permanently delete all data in the existing case directory.")
                if not response:
                    return
                
            self.case_metadata = {
                "investigator": inv,
                "agency": agency if agency else "N/A",
                "signature": sig,
                "case_id": case_id,
                "description": desc,
                "hostname": self._wiz_hostname.get().strip(),
                "output_path": self._wiz_output_path.get().strip()
            }
        else:
            # Open existing report
            report_path = self._wiz_report_path.get().strip()
            report_sig = self._wiz_report_sig.get().strip()
            
            if not os.path.exists(report_path):
                messagebox.showerror("Error", f"Report directory not found: {report_path}")
                return
            
            # Try to load case metadata from the existing report
            case_desc_path = os.path.join(report_path, "Case-Description.txt")
            if not os.path.exists(case_desc_path):
                messagebox.showerror("Error", "Invalid report directory: Case-Description.txt not found")
                return
            
            # Read case description
            try:
                with open(case_desc_path, 'r', encoding='utf-8') as f:
                    case_desc_content = f.read()
                
                # Check if there's a signature file to verify against
                sig_file_path = os.path.join(report_path, "signature.txt")
                stored_sig = None
                if os.path.exists(sig_file_path):
                    with open(sig_file_path, 'r', encoding='utf-8') as f:
                        stored_sig = f.read().strip()
                else:
                    # Extract signature from Case-Description.txt for legacy reports
                    sig_match = re.search(r'Digital Signature:\s*(.+)', case_desc_content)
                    if sig_match:
                        stored_sig = sig_match.group(1).strip()
                
                # Verify signature matches (strip whitespace for robustness)
                # Verify if signature exists (either from signature.txt or Case-Description.txt)
                if stored_sig and report_sig.strip():
                    if stored_sig.strip() != report_sig.strip():
                        messagebox.showerror("Signature Verification Failed", 
                                            "Signature doesn't match. Access denied.")
                        return
                elif stored_sig and not report_sig.strip():
                    # Signature exists but user didn't provide one
                    messagebox.showerror("Signature Required", 
                                        "This report is protected. Please enter the digital signature.")
                    return
                
                # If no signature file exists (legacy reports), allow access
                if not stored_sig:
                    # For legacy reports without signature file, just proceed
                    pass
                
                # Parse basic metadata from case description (simple parsing for now)
                self.case_metadata = {
                    "investigator": "Unknown",
                    "agency": "N/A",
                    "signature": report_sig,
                    "case_id": os.path.basename(report_path),
                    "description": case_desc_content,
                    "hostname": "Unknown",
                    "output_path": report_path
                }
                
                # Set the vault export directory to the existing report path
                self._vault_export_dir = report_path
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load case metadata: {e}")
                return
        
        self.wizard_frame.destroy()
        self.show_main_gui()
        
        # Disable logo animation for better performance
        self._logo_animation_enabled = False
        
        # Populate vault with existing report files after GUI is shown
        if mode == "open" and self._vault_export_dir:
            self.after(100, lambda: self.populate_vault(self._vault_export_dir))

    def show_main_gui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- SIDEBAR ---
        sidebar = ctk.CTkFrame(self, width=300, corner_radius=0, fg_color=UI.PANEL, border_width=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(5, weight=1)  # Make target vectors row expandable

        # Logo instead of LOG text
        self._sidebar_logo_src_path = os.path.join("assets", "abyss_logo.png")
        self._sidebar_logo_ctk_img = None
        
        logo_container = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_container.grid(row=0, column=0, padx=UI.PAD_X, pady=(26, 8), sticky="w")
        
        self.sidebar_logo_label = ctk.CTkLabel(logo_container, text="")
        self.sidebar_logo_label.grid(row=0, column=0)
        self._render_sidebar_logo()
        
        log_name = ctk.CTkLabel(sidebar, text=self.case_metadata['investigator'], font=UI.font(12), text_color=UI.TEXT_MUTED)
        log_name.grid(row=1, column=0, padx=UI.PAD_X, pady=(0, 8), sticky="w")
        
        # ID and OP below
        case_info = f"ID: {self.case_metadata['case_id']}\nOP: {self.case_metadata['investigator']}"
        info_lbl = ctk.CTkLabel(sidebar, text=case_info, justify="left", font=UI.mono(11), text_color=UI.ACCENT)
        info_lbl.grid(row=2, column=0, padx=UI.PAD_X, pady=(0, 8), sticky="w")
        
        # Separator line
        separator = ctk.CTkFrame(sidebar, height=1, fg_color=UI.BORDER)
        separator.grid(row=3, column=0, sticky="ew", padx=UI.PAD_X, pady=(0, 12))

        # Target Vectors - Radio button style list
        mod_lbl = ctk.CTkLabel(sidebar, text="TARGET VECTORS", font=UI.font(12, "bold"), text_color=UI.TEXT_MUTED)
        mod_lbl.grid(row=4, column=0, padx=UI.PAD_X, pady=(10, 8), sticky="w")
        
        # Create a frame for the radio button list
        vectors_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        vectors_frame.grid(row=5, column=0, sticky="nsew", padx=UI.PAD_X, pady=(0, 0))
        vectors_frame.grid_columnconfigure(0, weight=1)
        
        # Radio button variables
        self.var_browser = ctk.StringVar(value="on")
        self.var_notepad = ctk.StringVar(value="on")
        self.var_os_mem = ctk.StringVar(value="on")
        self.var_phantom = ctk.StringVar(value="on")
        self.var_ghost = ctk.StringVar(value="on")
        
        # Custom radio button style using checkboxes
        self.chk_browser = ctk.CTkCheckBox(
            vectors_frame, text="Browser History", font=F_MAIN,
            fg_color=UI.ACCENT, hover_color=UI.ACCENT_2, border_color=UI.BORDER,
            checkbox_width=20, checkbox_height=20, corner_radius=4
        )
        self.chk_browser.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        self.chk_browser.select()
        
        self.chk_notepad = ctk.CTkCheckBox(
            vectors_frame, text="Notepad TabState", font=F_MAIN,
            fg_color=UI.ACCENT, hover_color=UI.ACCENT_2, border_color=UI.BORDER,
            checkbox_width=20, checkbox_height=20, corner_radius=4
        )
        self.chk_notepad.grid(row=1, column=0, sticky="ew", pady=(0, 2))
        self.chk_notepad.select()
        
        self.chk_os_mem = ctk.CTkCheckBox(
            vectors_frame, text="Deep OS Memory", font=F_MAIN,
            fg_color=UI.CRIT, hover_color="#F5786D", border_color=UI.BORDER,
            checkbox_width=20, checkbox_height=20, corner_radius=4
        )
        self.chk_os_mem.grid(row=2, column=0, sticky="ew", pady=(0, 2))
        self.chk_os_mem.select()
        
        self.chk_phantom = ctk.CTkCheckBox(
            vectors_frame, text="DNS / Registry", font=F_MAIN,
            fg_color=UI.CRIT, hover_color="#F5786D", border_color=UI.BORDER,
            checkbox_width=20, checkbox_height=20, corner_radius=4
        )
        self.chk_phantom.grid(row=3, column=0, sticky="ew", pady=(0, 2))
        self.chk_phantom.select()
        
        self.chk_ghost = ctk.CTkCheckBox(
            vectors_frame, text="Search Index", font=F_MAIN,
            fg_color=UI.CRIT, hover_color="#F5786D", border_color=UI.BORDER,
            checkbox_width=20, checkbox_height=20, corner_radius=4
        )
        self.chk_ghost.grid(row=4, column=0, sticky="ew", pady=(0, 2))
        self.chk_ghost.select()

        # Run Button - at very bottom
        self.run_button = ctk.CTkButton(sidebar, text="EXECUTE", command=self.start_extraction, 
                                        fg_color=UI.ACCENT, hover_color=UI.ACCENT_2,
                                        text_color="black", font=F_SUB, height=42, corner_radius=12)
        self.run_button.grid(row=6, column=0, padx=UI.PAD_X, pady=(20, 12), sticky="ew")

        # --- TERMINAL / VAULT TABS ---
        self.tab_view = ctk.CTkTabview(
            self,
            fg_color="transparent",
            text_color=UI.TEXT,
            segmented_button_selected_color=UI.PANEL,
            segmented_button_selected_hover_color=UI.PANEL_2
        )
        self.tab_view.grid(row=0, column=1, padx=UI.PAD_X, pady=UI.PAD_Y, sticky="nsew")
        
        self.tab_terminal = self.tab_view.add("Console")
        self.tab_vault = self.tab_view.add("Evidence Vault")
        
        # --- CONSOLE TAB (SIMPLE) ---
        self.tab_terminal.grid_columnconfigure(0, weight=1)
        self.tab_terminal.grid_rowconfigure(0, weight=1)
        
        # Log Console
        log_frame = ctk.CTkFrame(self.tab_terminal, fg_color=UI.PANEL, corner_radius=UI.RADIUS)
        log_frame.grid(row=0, column=0, sticky="nsew", pady=(10, 10))
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)
        
        self.log_textbox = ctk.CTkTextbox(log_frame, state="disabled", font=UI.mono(11), fg_color=UI.PANEL_2, text_color=UI.TEXT)
        self.log_textbox.grid(row=0, column=0, padx=2, pady=2, sticky="nsew")
        
        # Status Bar
        status_bar = ctk.CTkFrame(self.tab_terminal, fg_color=UI.BG, corner_radius=10)
        status_bar.grid(row=1, column=0, sticky="ew", pady=(0, 0))
        status_bar.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(status_bar, text="Status", font=UI.font(12, "bold"), text_color=UI.TEXT_MUTED).grid(row=0, column=0, padx=10, pady=8)
        self.progress_bar = ctk.CTkProgressBar(status_bar, progress_color=UI.ACCENT, fg_color=UI.PANEL, height=10)
        self.progress_bar.grid(row=0, column=1, sticky="ew", padx=10)
        self.progress_bar.set(0)
        self.status_label = ctk.CTkLabel(status_bar, text="Awaiting directive…", font=UI.mono(11), text_color=UI.TEXT)
        self.status_label.grid(row=0, column=2, padx=10, pady=5)
        
        # --- EVIDENCE VAULT TAB (AUTOPSY STYLE) ---
        self.tab_vault.grid_columnconfigure(0, weight=1)
        self.tab_vault.grid_columnconfigure(1, weight=3)
        self.tab_vault.grid_rowconfigure(0, weight=1)
        self.tab_vault.grid_rowconfigure(1, weight=0)
        
        # LEFT PANE (Forensic Tree Viewer)
        left_col = ctk.CTkFrame(self.tab_vault, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        tree_frame = ctk.CTkFrame(left_col, fg_color=UI.PANEL, corner_radius=UI.RADIUS)
        tree_frame.pack(fill="both", expand=True)
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(1, weight=1)
        
        # Evidence label inside tree frame for symmetry
        ctk.CTkLabel(tree_frame, text="Evidence", font=UI.font(13, "bold"), text_color=UI.TEXT).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background=UI.PANEL, foreground=UI.TEXT, fieldbackground=UI.PANEL, borderwidth=0, font=UI.mono(12))
        style.map("Treeview", background=[("selected", UI.ACCENT)], foreground=[("selected", "black")])
        
        self.tree_viewer = ttk.Treeview(tree_frame, show="tree")
        self.tree_viewer.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.tree_viewer.bind("<<TreeviewOpen>>", self._on_vault_tree_open)
        self.tree_viewer.bind("<<TreeviewSelect>>", self._on_vault_tree_select)

        # RIGHT PANE (Resizable PanedWindow for Top/Bottom)
        right_col = ctk.CTkFrame(self.tab_vault, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right_col.grid_columnconfigure(0, weight=1)
        right_col.grid_rowconfigure(0, weight=1)
        
        # Use PanedWindow for resizable split
        self.paned_window = ttk.PanedWindow(right_col, orient="vertical")
        self.paned_window.grid(row=0, column=0, sticky="nsew")
        
        # Top: Folder contents
        top_right = ctk.CTkFrame(self.paned_window, fg_color=UI.PANEL, corner_radius=UI.RADIUS)
        self.paned_window.add(top_right, weight=1)
        top_right.grid_columnconfigure(0, weight=1)
        top_right.grid_rowconfigure(1, weight=1)
        
        self.vault_header = ctk.CTkLabel(top_right, text="Evidence Directory", font=UI.font(14, "bold"), text_color=UI.TEXT)
        self.vault_header.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        # File listing (Autopsy-like)
        listing_frame = ctk.CTkFrame(top_right, fg_color="transparent")
        listing_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        listing_frame.grid_columnconfigure(0, weight=1)
        listing_frame.grid_rowconfigure(0, weight=1)

        self.vault_listing = ttk.Treeview(listing_frame, columns=("size", "name", "type", "modified"), show="headings", selectmode="browse")
        self.vault_listing.heading("size", text="Size")
        self.vault_listing.heading("name", text="Name")
        self.vault_listing.heading("type", text="Type")
        self.vault_listing.heading("modified", text="Modified")
        self.vault_listing.column("size", width=100, anchor="w")
        self.vault_listing.column("name", width=380, anchor="w")
        self.vault_listing.column("type", width=120, anchor="w")
        self.vault_listing.column("modified", width=180, anchor="w")
        self.vault_listing.grid(row=0, column=0, sticky="nsew")
        self.vault_listing.bind("<<TreeviewSelect>>", self._on_vault_listing_select)
        self.vault_listing.bind("<Double-1>", self._on_vault_listing_double_click)

        listing_scroll = ttk.Scrollbar(listing_frame, orient="vertical", command=self.vault_listing.yview)
        self.vault_listing.configure(yscrollcommand=listing_scroll.set)
        listing_scroll.grid(row=0, column=1, sticky="ns")

        # Bottom: File View
        bot_right = ctk.CTkFrame(self.paned_window, fg_color=UI.PANEL, corner_radius=UI.RADIUS)
        self.paned_window.add(bot_right, weight=2)
        bot_right.grid_columnconfigure(0, weight=1)
        bot_right.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(bot_right, text="Preview", font=UI.font(14, "bold"), text_color=UI.TEXT).grid(row=0, column=0, sticky="w", padx=10, pady=5)

        # Preview bar with mode selector and current selection
        preview_bar = ctk.CTkFrame(bot_right, fg_color=UI.PANEL_2, corner_radius=8)
        preview_bar.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))
        preview_bar.grid_columnconfigure(2, weight=1)
        
        # Current selection indicator
        self.preview_selection_label = ctk.CTkLabel(preview_bar, text="No file selected", font=UI.mono(11), text_color=UI.TEXT_MUTED, anchor="w")
        self.preview_selection_label.grid(row=0, column=0, padx=10, pady=8, sticky="w")
        
        # Action buttons (eye and folder)
        action_frame = ctk.CTkFrame(preview_bar, fg_color="transparent")
        action_frame.grid(row=0, column=1, padx=5, pady=5)
        
        self.btn_open_file = ctk.CTkButton(action_frame, text="👁", width=35, height=28, fg_color=UI.PANEL, hover_color=UI.ACCENT, text_color=UI.TEXT, corner_radius=6, command=self._open_file_default)
        self.btn_open_file.grid(row=0, column=0, padx=2)
        
        self.btn_open_location = ctk.CTkButton(action_frame, text="📁", width=35, height=28, fg_color=UI.PANEL, hover_color=UI.ACCENT, text_color=UI.TEXT, corner_radius=6, command=self._open_file_location)
        self.btn_open_location.grid(row=0, column=1, padx=2)
        
        # Mode selector buttons
        mode_frame = ctk.CTkFrame(preview_bar, fg_color="transparent")
        mode_frame.grid(row=0, column=2, sticky="e", padx=10, pady=5)
        
        self.preview_mode_var = ctk.StringVar(value="Data")
        
        self.mode_data_btn = ctk.CTkRadioButton(mode_frame, text="Data", variable=self.preview_mode_var, value="Data", 
                                                 command=self._on_preview_mode_change, font=UI.font(11), text_color=UI.TEXT)
        self.mode_data_btn.grid(row=0, column=0, padx=5)
        
        self.mode_hex_btn = ctk.CTkRadioButton(mode_frame, text="Hex", variable=self.preview_mode_var, value="Hex", 
                                                command=self._on_preview_mode_change, font=UI.font(11), text_color=UI.TEXT)
        self.mode_hex_btn.grid(row=0, column=1, padx=5)
        
        self.mode_skin_btn = ctk.CTkRadioButton(mode_frame, text="Skin", variable=self.preview_mode_var, value="Skin", 
                                                 command=self._on_preview_mode_change, font=UI.font(11), text_color=UI.TEXT)
        self.mode_skin_btn.grid(row=0, column=2, padx=5)

        # Single display area that changes based on selected mode
        self.viewer_display_frame = ctk.CTkFrame(bot_right, fg_color=UI.PANEL_2, corner_radius=8)
        self.viewer_display_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.viewer_display_frame.grid_columnconfigure(0, weight=1)
        self.viewer_display_frame.grid_rowconfigure(0, weight=1)
        
        # Data mode display
        self.viewer_data_text = ctk.CTkTextbox(self.viewer_display_frame, state="disabled", font=UI.mono(12), fg_color=UI.PANEL_2, text_color=UI.TEXT)
        self.viewer_data_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Data mode image viewer
        self.viewer_data_image = ctk.CTkLabel(self.viewer_display_frame, text="")
        
        # Data mode CSV table viewer
        self.viewer_data_csv_frame = ctk.CTkScrollableFrame(self.viewer_display_frame, fg_color=UI.PANEL_2, corner_radius=8)
        self.viewer_data_csv_frame.grid_columnconfigure(0, weight=1)
        
        # Hex mode display with side panel
        hex_container = ctk.CTkFrame(self.viewer_display_frame, fg_color="transparent")
        hex_container.grid(row=0, column=0, sticky="nsew")
        hex_container.grid_columnconfigure(0, weight=1)
        hex_container.grid_columnconfigure(1, weight=0)
        hex_container.grid_rowconfigure(0, weight=1)
        
        # Main hex viewer
        self.viewer_hex_text = ctk.CTkTextbox(hex_container, state="disabled", font=UI.mono(12), fg_color=UI.PANEL_2, text_color=UI.TEXT)
        self.viewer_hex_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Entropy heatmap bar
        self.entropy_bar = ctk.CTkFrame(hex_container, width=20, fg_color=UI.PANEL, corner_radius=4)
        self.entropy_bar.grid(row=0, column=1, sticky="ns", padx=(5, 0))
        
        # Data interpreter side panel
        hex_side_panel = ctk.CTkFrame(hex_container, width=200, fg_color=UI.PANEL, corner_radius=8)
        hex_side_panel.grid(row=0, column=2, sticky="ns", padx=(5, 0))
        hex_side_panel.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(hex_side_panel, text="Data Interpreter", font=UI.font(11, "bold"), text_color=UI.TEXT).grid(row=0, column=0, padx=5, pady=(5, 10))
        
        self.hex_interpreter_text = ctk.CTkTextbox(hex_side_panel, state="disabled", font=UI.mono(10), fg_color=UI.PANEL_2, text_color=UI.TEXT, height=200)
        self.hex_interpreter_text.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
        
        # Skin mode display - scrollable list format
        self.viewer_skin_frame = ctk.CTkScrollableFrame(self.viewer_display_frame, fg_color=UI.PANEL_2, corner_radius=8)
        self.viewer_skin_frame.grid_columnconfigure(0, weight=1)
        
        # Skin info labels (will be populated dynamically)
        self.skin_info_labels = {}
        
        # Hide all viewers initially, show based on mode
        self.viewer_data_text.grid_remove()
        self.viewer_data_image.grid_remove()
        self.viewer_data_csv_frame.grid_remove()
        self.hex_container = hex_container  # Store reference
        hex_container.grid_remove()
        self.viewer_skin_frame.grid_remove()
        self.viewer_data_text.grid(row=0, column=0, sticky="nsew")  # Show data by default

        # Setup Logging Handler (keep StreamHandler for external terminal)
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

        # Remove any previous GUI handlers (avoid duplicates on re-init)
        logger.handlers = [h for h in logger.handlers if not isinstance(h, AbyssLogHandler)]

        # Ensure file handler exists for our log file
        has_file = any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == str(self.log_file) for h in logger.handlers)
        if not has_file:
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(file_handler)
        
        # Ensure stream handler exists so logs appear in CMD/PowerShell
        has_stream = any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
        if not has_stream:
            stream_handler = logging.StreamHandler(stream=sys.stdout)
            stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(stream_handler)

        gui_handler = AbyssLogHandler(self.log_textbox)
        gui_handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(gui_handler)
        
        logging.info("ABYSS Framework Initialized.")

    def update_status(self, text, progress):
        # Thread-safe: engine runs in a worker thread.
        def apply():
            try:
                self.status_label.configure(text=text)
                self.progress_bar.set(progress)
            except Exception:
                pass
        self.after(0, apply)

    # -------------------------
    # Evidence Vault (Autopsy-like)
    # -------------------------
    def _vault_clear_listing(self):
        for item in self.vault_listing.get_children():
            self.vault_listing.delete(item)

    def _vault_set_text(self, textbox, content: str):
        textbox.configure(state="normal")
        textbox.delete("0.0", "end")
        textbox.insert("0.0", content)
        textbox.configure(state="disabled")

    def _display_image_preview(self, path: str):
        """Display image in data mode image viewer."""
        if Image is None or ImageTk is None:
            return
        try:
            # Hide all other data viewers first
            self.viewer_data_text.grid_remove()
            self.viewer_data_csv_frame.grid_remove()
            
            img = Image.open(path)
            # Resize image to fit viewer
            max_size = (600, 400)
            img.thumbnail(max_size, Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self.viewer_data_image.configure(image=ctk_img, text="")
            # Ensure image viewer is visible
            self.viewer_data_image.grid(row=0, column=0, sticky="nsew")
        except Exception as e:
            self.viewer_data_text.grid_remove()
            self.viewer_data_csv_frame.grid_remove()
            self.viewer_data_image.configure(image=None, text=f"Error loading image: {e}")
            self.viewer_data_image.grid(row=0, column=0, sticky="nsew")

    def _display_csv_preview(self, path: str):
        """Display CSV file as table in scrollable frame (async for performance)."""
        # Hide all other data viewers first
        self.viewer_data_text.grid_remove()
        self.viewer_data_image.grid_remove()
        
        # Show loading indicator
        for widget in self.viewer_data_csv_frame.winfo_children():
            widget.destroy()
        loading_label = ctk.CTkLabel(self.viewer_data_csv_frame, text="Loading CSV...", text_color=UI.TEXT_MUTED)
        loading_label.pack(padx=10, pady=10)
        self.viewer_data_csv_frame.grid(row=0, column=0, sticky="nsew")
        
        def load_csv_async():
            try:
                import pandas as pd
                # Reduce to 20 rows for better performance
                df = pd.read_csv(path, nrows=20)
                
                def apply():
                    if self._vault_selected_file != path:
                        return
                    
                    # Clear loading indicator
                    for widget in self.viewer_data_csv_frame.winfo_children():
                        widget.destroy()
                    
                    # Use simple Treeview for CSV with horizontal scrolling
                    csv_tree = ttk.Treeview(self.viewer_data_csv_frame, columns=list(df.columns), show="headings", selectmode="browse")
                    
                    # Configure columns
                    for col in df.columns:
                        csv_tree.heading(col, text=str(col))
                        csv_tree.column(col, width=200, anchor="w")
                    
                    # Add data
                    for _, row in df.iterrows():
                        csv_tree.insert("", "end", values=list(row))
                    
                    # Add scrollbars
                    csv_scroll_x = ttk.Scrollbar(self.viewer_data_csv_frame, orient="horizontal", command=csv_tree.xview)
                    csv_scroll_y = ttk.Scrollbar(self.viewer_data_csv_frame, orient="vertical", command=csv_tree.yview)
                    csv_tree.configure(xscrollcommand=csv_scroll_x.set, yscrollcommand=csv_scroll_y.set)
                    
                    # Configure grid weights for proper expansion
                    self.viewer_data_csv_frame.grid_rowconfigure(0, weight=1)
                    self.viewer_data_csv_frame.grid_columnconfigure(0, weight=1)
                    
                    csv_tree.grid(row=0, column=0, sticky="nsew")
                    csv_scroll_x.grid(row=1, column=0, sticky="ew")
                    csv_scroll_y.grid(row=0, column=1, sticky="ns")
                    
                    self.viewer_data_csv_frame.grid_columnconfigure(0, weight=1)
                    self.viewer_data_csv_frame.grid_rowconfigure(0, weight=1)
                    
                    # Ensure CSV frame is visible
                    self.viewer_data_csv_frame.grid(row=0, column=0, sticky="nsew")
                
                self.after(0, apply)
            except Exception as e:
                def apply_error():
                    for widget in self.viewer_data_csv_frame.winfo_children():
                        widget.destroy()
                    error_label = ctk.CTkLabel(self.viewer_data_csv_frame, text=f"Error loading CSV: {e}", text_color=UI.CRIT)
                    error_label.pack(padx=10, pady=10)
                self.after(0, apply_error)
        
        threading.Thread(target=load_csv_async, daemon=True).start()

    def _safe_read_text_preview(self, path: str, max_bytes: int = 262144) -> str:
        try:
            with open(path, "rb") as f:
                data = f.read(max_bytes)
            for enc in ("utf-8", "utf-16le"):
                try:
                    return data.decode(enc)
                except Exception:
                    pass
            return data.decode("utf-8", errors="replace")
        except Exception as e:
            return f"[Error reading file preview]\\n{e}"

    def _hex_dump_preview(self, path: str, max_bytes: int = 32768) -> str:  # Reduced for better performance
        try:
            with open(path, "rb") as f:
                b = f.read(max_bytes)
            
            # Magic byte detection (first 4 bytes)
            magic_bytes = b[:4]
            magic_hex = " ".join(f"{x:02X}" for x in magic_bytes)
            
            # Known file signatures
            magic_signatures = {
                b"\x89PNG": "PNG image",
                b"\xff\xd8\xff": "JPEG image",
                b"GIF8": "GIF image",
                b"BM": "BMP image",
                b"PK\x03\x04": "ZIP archive",
                b"PK\x05\x06": "ZIP archive (empty)",
                b"Rar!": "RAR archive",
                b"\x7fELF": "ELF executable",
                b"MZ": "PE/EXE executable",
                b"\xca\xfe\xba\xbe": "Mach-O binary",
            }
            
            detected_type = "Unknown"
            for sig, name in magic_signatures.items():
                if b.startswith(sig):
                    detected_type = name
                    break
            
            lines = []
            lines.append(f"MAGIC BYTES (first 4): {magic_hex} -> {detected_type}")
            lines.append("=" * 70)
            lines.append("")

            for off in range(0, len(b), 16):
                chunk = b[off:off + 16]
                # Format: 8-char offset | 16 hex bytes (grouped in 2s) | ASCII
                hex_groups = []
                for i in range(0, len(chunk), 2):
                    group = chunk[i:i+2]
                    if len(group) == 2:
                        hex_groups.append(f"{group[0]:02X} {group[1]:02X}")
                    else:
                        hex_groups.append(f"{group[0]:02X}  ")
                hex_part = "  ".join(hex_groups[:8])  # 8 groups of 2 bytes
                ascii_part = "".join(chr(x) if 32 <= x <= 126 else "." for x in chunk)
                lines.append(f"{off:08X}  {hex_part:<48}  {ascii_part}")
            
            if os.path.getsize(path) > max_bytes:
                lines.append("")
                lines.append(f"[truncated hex preview to first {max_bytes} bytes]")
            
            # Update data interpreter with first 8 bytes
            self._update_data_interpreter(b[:8])
            # Update entropy heatmap
            self._update_entropy_heatmap(b)
            
            return "\\n".join(lines)
        except Exception as e:
            return f"[Error generating hex preview]\\n{e}"
    
    def _update_data_interpreter(self, bytes_data: bytes):
        """Update data interpreter side panel with MFT-like structured format."""
        if len(bytes_data) < 4:
            self._vault_set_text(self.hex_interpreter_text, "Insufficient data")
            return
        
        # Clear previous content
        self.hex_interpreter_text.configure(state="normal")
        self.hex_interpreter_text.delete("0.0", "end")
        
        # Display in structured MFT-like format with better spacing
        lines = []
        lines.append("BYTE INTERPRETER")
        lines.append("-" * 30)
        lines.append("")
        
        # Raw bytes (formatted in groups of 4)
        hex_groups = []
        for i in range(0, len(bytes_data), 4):
            group = " ".join(f"{b:02X}" for b in bytes_data[i:i+4])
            hex_groups.append(group)
        lines.append(f"Raw: {'  '.join(hex_groups)}")
        lines.append("")
        
        # Integer values with labels
        if len(bytes_data) >= 4:
            int_le = int.from_bytes(bytes_data[:4], byteorder='little', signed=False)
            int_be = int.from_bytes(bytes_data[:4], byteorder='big', signed=False)
            lines.append(f"DWORD LE: {int_le:,}")
            lines.append(f"DWORD BE: {int_be:,}")
            lines.append("")
        
        # 64-bit values
        if len(bytes_data) >= 8:
            qword_le = int.from_bytes(bytes_data[:8], byteorder='little', signed=False)
            qword_be = int.from_bytes(bytes_data[:8], byteorder='big', signed=False)
            lines.append(f"QWORD LE: {qword_le:,}")
            lines.append(f"QWORD BE: {qword_be:,}")
            lines.append("")
        
        # Timestamp interpretation
        if len(bytes_data) >= 4:
            ts_le = int.from_bytes(bytes_data[:4], byteorder='little', signed=False)
            ts_be = int.from_bytes(bytes_data[:4], byteorder='big', signed=False)
            try:
                from datetime import datetime
                dt_le = datetime.fromtimestamp(ts_le).strftime('%Y-%m-%d %H:%M:%S')
                dt_be = datetime.fromtimestamp(ts_be).strftime('%Y-%m-%d %H:%M:%S')
                lines.append(f"TIME LE: {dt_le}")
                lines.append(f"TIME BE: {dt_be}")
            except Exception:
                lines.append("TIME: Invalid")
            lines.append("")
        
        # ASCII interpretation
        ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in bytes_data)
        lines.append(f"ASCII: {ascii_str}")
        
        self.hex_interpreter_text.insert("0.0", "\n".join(lines))
        self.hex_interpreter_text.configure(state="disabled")
    
    def _update_entropy_heatmap(self, bytes_data: bytes):
        """Update entropy heatmap bar based on data density."""
        try:
            # Calculate entropy in chunks
            chunk_size = 256
            chunks = [bytes_data[i:i+chunk_size] for i in range(0, len(bytes_data), chunk_size)]
            
            # Clear previous entropy bars
            for widget in self.entropy_bar.winfo_children():
                widget.destroy()
            
            for chunk in chunks:
                if len(chunk) < 2:
                    continue
                
                # Calculate entropy
                entropy = 0
                for byte_val in set(chunk):
                    p = chunk.count(byte_val) / len(chunk)
                    if p > 0:
                        entropy -= p * (p.bit_length() - 1)
                
                # Normalize to 0-255 (entropy typically 0-8)
                normalized_entropy = min(255, int((entropy / 8) * 255))
                
                # Color based on entropy (low=green, high=red)
                if normalized_entropy < 85:
                    color = "#3FB950"  # Green (low entropy)
                elif normalized_entropy < 170:
                    color = "#D29922"  # Yellow (medium entropy)
                else:
                    color = "#F85149"  # Red (high entropy/encrypted)
                
                entropy_bar = ctk.CTkFrame(self.entropy_bar, height=2, fg_color=color)
                entropy_bar.pack(fill="x", pady=0)
        except Exception:
            pass

    def _open_file_default(self):
        """Open selected file in default Windows application."""
        if self._vault_selected_file and os.path.isfile(self._vault_selected_file):
            os.startfile(self._vault_selected_file)

    def _open_file_location(self):
        """Open file location in Windows Explorer."""
        if self._vault_selected_file and os.path.isfile(self._vault_selected_file):
            import subprocess
            subprocess.run(['explorer', '/select,', self._vault_selected_file])

    def _on_preview_mode_change(self):
        """Handle preview mode radio button change."""
        mode = self.preview_mode_var.get()
        # Hide all viewers
        self.viewer_data_text.grid_remove()
        self.viewer_data_image.grid_remove()
        self.viewer_data_csv_frame.grid_remove()
        self.hex_container.grid_remove()
        self.viewer_skin_frame.grid_remove()
        # Show selected mode
        if mode == "Data":
            # Show appropriate data viewer based on file type
            if self._vault_selected_file:
                ext = os.path.splitext(self._vault_selected_file)[1].lower()
                if ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp'):
                    self.viewer_data_image.grid(row=0, column=0, sticky="nsew")
                elif ext == '.csv':
                    self.viewer_data_csv_frame.grid(row=0, column=0, sticky="nsew")
                else:
                    self.viewer_data_text.grid(row=0, column=0, sticky="nsew")
            else:
                self.viewer_data_text.grid(row=0, column=0, sticky="nsew")
        elif mode == "Hex":
            self.hex_container.grid(row=0, column=0, sticky="nsew")
        elif mode == "Skin":
            self.viewer_skin_frame.grid(row=0, column=0, sticky="nsew")

    def _render_skin_info(self, path: str):
        """Populate skin info frame with file metadata in list format."""
        try:
            size = os.path.getsize(path)
            ctime = datetime.fromtimestamp(os.path.getctime(path)).strftime('%Y-%m-%d %H:%M:%S')
            mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M:%S')
            atime = datetime.fromtimestamp(os.path.getatime(path)).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            size, ctime, mtime, atime = "N/A", "N/A", "N/A", "N/A"
        
        # Get MFT timestamps (simulated - actual MFT requires Windows API)
        mft_created = ctime
        mft_modified = mtime
        mft_entry_modified = mtime
        
        # Signature lock status
        signature_status = "LOCKED" if self.case_metadata.get('signature') else "UNLOCKED"
        signature_color = "#3FB950" if signature_status == "LOCKED" else "#F85149"
        
        # Clear previous content
        for widget in self.viewer_skin_frame.winfo_children():
            widget.destroy()
        
        # Add section headers and data
        sections = [
            ("HASH BLOCK", [
                ("SHA-256", "computing..."),
                ("MD5", "computing...")
            ]),
            ("MFT TIMESTAMPS", [
                ("Created Time", mft_created),
                ("Modified Time", mft_modified),
                ("MFT Entry Modified", mft_entry_modified),
                ("Last Accessed", atime)
            ]),
            ("SIGNATURE LOCK STATUS", [
                ("Status", signature_status, signature_color),
                ("Case Signature", self.case_metadata.get('signature', 'N/A'))
            ])
        ]
        
        row = 0
        for section_title, items in sections:
            # Section header
            header = ctk.CTkLabel(self.viewer_skin_frame, text=section_title, font=UI.font(12, "bold"), text_color=UI.ACCENT)
            header.grid(row=row, column=0, sticky="w", padx=10, pady=(10, 5))
            row += 1
            
            # Section items
            for item in items:
                if len(item) == 3:
                    label, value, color = item
                    value_label = ctk.CTkLabel(self.viewer_skin_frame, text=f"{label}: {value}", font=UI.mono(11), text_color=color)
                else:
                    label, value = item
                    value_label = ctk.CTkLabel(self.viewer_skin_frame, text=f"{label}: {value}", font=UI.mono(11), text_color=UI.TEXT)
                value_label.grid(row=row, column=0, sticky="w", padx=20, pady=2)
                row += 1
            
            # Separator
            sep = ctk.CTkFrame(self.viewer_skin_frame, height=1, fg_color=UI.BORDER)
            sep.grid(row=row, column=0, sticky="ew", padx=10, pady=(5, 10))
            row += 1

    def _update_skin_hash_async(self, path: str):
        def work():
            if path in self._hash_cache:
                h = self._hash_cache[path]
            else:
                try:
                    h = calculate_hash(path)
                    self._hash_cache[path] = h
                except Exception as e:
                    h = f"[hash error] {e}"

            def apply():
                # Update the SHA-256 and MD5 labels in the skin frame
                for widget in self.viewer_skin_frame.winfo_children():
                    if isinstance(widget, ctk.CTkLabel):
                        text = widget.cget("text")
                        if text.startswith("SHA-256:"):
                            widget.configure(text=f"SHA-256: {h}")
                        elif text.startswith("MD5:"):
                            widget.configure(text=f"MD5: {h[:32]}")

            self.after(0, apply)

        threading.Thread(target=work, daemon=True).start()

    def _show_system_profile(self):
        from modules.system_profiler import get_system_profile
        profile = get_system_profile()
        lines = ["System Profile", "-" * 60]
        for k in sorted(profile.keys()):
            lines.append(f"{k}: {profile[k]}")
        content = "\\n".join(lines) + "\\n"
        self._vault_set_text(self.viewer_data_text, content)
        self._vault_set_text(self.viewer_hex_text, content)
        # Clear skin frame
        for widget in self.viewer_skin_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(self.viewer_skin_frame, text=content, font=UI.mono(11), text_color=UI.TEXT).pack(padx=10, pady=10)
        self.vault_header.configure(text="System Profile (SID / Host Metadata)")
        self._vault_clear_listing()

    def _vault_insert_tree_node(self, parent, text, path=None, is_dir=False, is_system_profile=False):
        node_id = self.tree_viewer.insert(parent, "end", text=text, open=False)
        if is_system_profile:
            self._vault_tree_node_to_path[node_id] = {"kind": "system_profile"}
        else:
            self._vault_tree_node_to_path[node_id] = {"kind": "path", "path": path, "is_dir": is_dir}
        if is_dir:
            self.tree_viewer.insert(node_id, "end", text="(loading...)")
        return node_id

    def _vault_build_tree_root(self, export_dir: str):
        self.tree_viewer.delete(*self.tree_viewer.get_children())
        self._vault_tree_node_to_path = {}
        self._vault_export_dir = export_dir

        root_label = f"📁 Evidence Root ({os.path.basename(os.path.normpath(export_dir))})"
        root_id = self._vault_insert_tree_node("", root_label, path=export_dir, is_dir=True)
        self.tree_viewer.item(root_id, open=True)

        self._vault_expand_tree_dir(root_id, export_dir)

    def _vault_expand_tree_dir(self, node_id, dir_path: str):
        children = self.tree_viewer.get_children(node_id)
        if len(children) == 1 and self.tree_viewer.item(children[0], "text") == "(loading...)":
            self.tree_viewer.delete(children[0])

        try:
            entries = [e for e in os.listdir(dir_path) if os.path.isdir(os.path.join(dir_path, e))]
            entries.sort(key=lambda s: s.lower())
            existing_texts = {self.tree_viewer.item(c, "text") for c in self.tree_viewer.get_children(node_id)}
            for name in entries:
                text = f"📁 {name}"
                if text in existing_texts:
                    continue
                p = os.path.join(dir_path, name)
                self._vault_insert_tree_node(node_id, text, path=p, is_dir=True)
        except Exception:
            pass

    def _on_vault_tree_open(self, event):
        sel = self.tree_viewer.focus()
        info = self._vault_tree_node_to_path.get(sel)
        if not info or info.get("kind") != "path":
            return
        if info.get("is_dir") and info.get("path"):
            self._vault_expand_tree_dir(sel, info["path"])

    def _on_vault_tree_select(self, event):
        sel = self.tree_viewer.focus()
        info = self._vault_tree_node_to_path.get(sel)
        if not info:
            return
        if info.get("kind") == "system_profile":
            self._show_system_profile()
            return

        path = info.get("path")
        if path and os.path.isdir(path):
            self._vault_set_current_dir(path)

    def _vault_set_current_dir(self, path: str):
        self._vault_current_dir = path
        self._vault_selected_file = None
        self.vault_header.configure(text=f"Evidence Directory: {path}")
        self._vault_clear_listing()

        try:
            entries = os.listdir(path)
        except Exception as e:
            self._vault_set_text(self.viewer_data_text, f"Error reading directory:\n{e}\n")
            self._vault_set_text(self.viewer_hex_text, f"Error reading directory:\n{e}\n")
            for widget in self.viewer_skin_frame.winfo_children():
                widget.destroy()
            ctk.CTkLabel(self.viewer_skin_frame, text=f"Error reading directory:\n{e}\n", font=UI.mono(11), text_color=UI.CRIT).pack(padx=10, pady=10)
            return

        dirs = []
        files = []
        for name in entries:
            full = os.path.join(path, name)
            if os.path.isdir(full):
                # Hide System Profile folder from vault
                if name.lower() != "system profile":
                    dirs.append(name)
            else:
                files.append(name)
        
        # Sort directories and files (case-insensitive)
        dirs.sort(key=str.lower)
        files.sort(key=str.lower)

        if self._vault_export_dir and os.path.normpath(path) != os.path.normpath(self._vault_export_dir):
            self.vault_listing.insert("", "end", iid="__up__", values=("", "..", "Folder", ""))

        for name in dirs:
            full = os.path.join(path, name)
            self.vault_listing.insert("", "end", iid=full, values=("", name, "Folder", ""))

        for name in files:
            full = os.path.join(path, name)
            try:
                size = os.path.getsize(full)
                mtime = datetime.fromtimestamp(os.path.getmtime(full)).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                size, mtime = "", ""
            self.vault_listing.insert("", "end", iid=full, values=(f"{size}", name, "File", f"{mtime}"))

        self._vault_set_text(self.viewer_data_text, "Select a file to preview.\n")
        self._vault_set_text(self.viewer_hex_text, "Select a file to preview.\n")
        for widget in self.viewer_skin_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(self.viewer_skin_frame, text="Select a file to preview.", font=UI.mono(11), text_color=UI.TEXT_MUTED).pack(padx=10, pady=10)

    def _on_vault_listing_select(self, event):
        # Debounce heavy preview work to keep UI smooth when scrolling.
        if self._vault_preview_job is not None:
            try:
                self.after_cancel(self._vault_preview_job)
            except Exception:
                pass
                                
        def run_preview():
            sel = self.vault_listing.selection()
            if not sel:
                self.preview_selection_label.configure(text="No file selected")
                return
            iid = sel[0]
            if iid == "__up__":
                self._vault_selected_file = None
                return

            path = iid
            if os.path.isdir(path):
                self._vault_selected_file = None
                self.preview_selection_label.configure(text=os.path.basename(path) + " (Folder)")
                msg = f"[Folder]\n{path}\n"
                self._vault_set_text(self.viewer_data_text, msg)
                self._vault_set_text(self.viewer_hex_text, msg)
                for widget in self.viewer_skin_frame.winfo_children():
                    widget.destroy()
                ctk.CTkLabel(self.viewer_skin_frame, text=msg, font=UI.mono(11), text_color=UI.TEXT).pack(padx=10, pady=10)
                return

            if not os.path.isfile(path):
                self.preview_selection_label.configure(text="No file selected")
                return

            self._vault_selected_file = path
            self.preview_selection_label.configure(text=os.path.basename(path))

            # Check cache first for all file types
            cached = self._vault_preview_cache.get(path)
            if cached:
                # Display appropriate content based on file type in Data mode
                ext = os.path.splitext(path)[1].lower()
                if ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp'):
                    self._display_image_preview(path)
                elif ext == '.csv':
                    self._display_csv_preview(path)
                else:
                    self._vault_set_text(self.viewer_data_text, cached.get("data", ""))
                self._vault_set_text(self.viewer_hex_text, cached.get("hex", ""))
                # Re-render skin info from cache
                self._render_skin_info(self._vault_selected_file)
                if cached.get("sha"):
                    self._hash_cache[path] = cached["sha"]
                # Auto-refresh after short delay to ensure proper display
                self.after(300, lambda: self._refresh_current_file())
                return

            # Display appropriate content based on file type in Data mode
            ext = os.path.splitext(path)[1].lower()
            if ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp'):
                self._display_image_preview(path)
                self._vault_set_text(self.viewer_hex_text, "Loading preview…\n")
                self._render_skin_info(path)
            elif ext == '.csv':
                self._display_csv_preview(path)
                self._vault_set_text(self.viewer_hex_text, "Loading preview…\n")
                self._render_skin_info(path)
            else:
                # Hide image and CSV viewers for text files
                self.viewer_data_image.grid_remove()
                self.viewer_data_csv_frame.grid_remove()
                self.viewer_data_text.grid(row=0, column=0, sticky="nsew")
                self._vault_set_text(self.viewer_data_text, "Loading preview…\n")
                self._vault_set_text(self.viewer_hex_text, "Loading preview…\n")
                self._render_skin_info(path)

            def worker():
                data = self._safe_read_text_preview(path)
                hexv = self._hex_dump_preview(path)

                def apply():
                    if self._vault_selected_file != path:
                        return
                    sha = self._hash_cache.get(path)
                    self._vault_set_text(self.viewer_data_text, data)
                    self._vault_set_text(self.viewer_hex_text, hexv)
                    self._render_skin_info(path)
                    self._update_skin_hash_async(path)
                    # Auto-refresh after loading to ensure proper display
                    self.after(300, lambda: self._refresh_current_file())

                self.after(0, apply)

            threading.Thread(target=worker, daemon=True).start()

        self._vault_preview_job = self.after(50, run_preview)  # Faster response

    def _refresh_current_file(self):
        """Refresh the currently selected file to ensure proper display."""
        if not self._vault_selected_file:
            return
        
        path = self._vault_selected_file
        ext = os.path.splitext(path)[1].lower()
        
        # Re-display based on file type
        if ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp'):
            self._display_image_preview(path)
        elif ext == '.csv':
            self._display_csv_preview(path)
        else:
            # For text files, ensure text viewer is visible
            self.viewer_data_image.grid_remove()
            self.viewer_data_csv_frame.grid_remove()
            self.viewer_data_text.grid(row=0, column=0, sticky="nsew")


    def _on_vault_listing_double_click(self, event):
        sel = self.vault_listing.selection()
        if not sel:
            return
        iid = sel[0]
        if iid == "__up__":
            if self._vault_current_dir:
                parent = os.path.dirname(self._vault_current_dir)
                if parent and os.path.isdir(parent):
                    self._vault_set_current_dir(parent)
            return

        path = iid
        if os.path.isdir(path):
            self._vault_set_current_dir(path)

    def populate_vault(self, export_dir):
        self._vault_build_tree_root(export_dir)
        self._vault_set_current_dir(export_dir)
        self.preview_mode_var.set("Data")

    def start_extraction(self):
        logging.info("Initiating ABYSS extraction sequence...")
        print("DEBUG: EXECUTE SCRAPE clicked.")
        run_browser = self.chk_browser.get()
        run_notepad = self.chk_notepad.get()
        run_os = self.chk_os_mem.get()
        
        if not run_browser and not run_notepad and not run_os:
            messagebox.showerror("ABYSS Protocol", "Select at least one extraction vector.")
            return

        self.tab_view.set("Console")
        self.run_button.configure(state="disabled")
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("0.0", "end")
        self.log_textbox.configure(state="disabled")
        
        print(f"DEBUG: Starting thread with Browser={run_browser}, Notepad={run_notepad}, OS={run_os}")
        threading.Thread(target=self.run_forensic_engine, args=(run_browser, run_notepad, run_os), daemon=True).start()

    def _set_busy(self, is_busy: bool, label: str = ""):
        # Lightweight UX: reflect busy state without blocking UI.
        def apply():
            try:
                self.run_button.configure(state="disabled" if is_busy else "normal")
                if label:
                    self.status_label.configure(text=label)
            except Exception:
                pass
        self.after(0, apply)

    def run_forensic_engine(self, run_browser, run_notepad, run_os):
        print("DEBUG: run_forensic_engine thread started.")
        try:
            logging.info(f"--- ABYSS Protocol Engaged | ID: {self.case_metadata['case_id']} ---")
            
            ensure_dir("reports")
            all_artifacts = []
            carved_urls = []
            ads_targets = []
            
            try:
                from modules.lazarus_module import carve_sqlite_freelist, check_zone_identifiers
                from modules.intelligence_engine import generate_user_persona, generate_master_correlator
                
                if run_browser:
                    self.update_status("Vector: Browser Artifacts...", 0.2)
                    logging.info("Isolating Chromium & Firefox Databases...")
                    self.browser_paths = get_browser_paths()
                    
                    # Group by browser for metadata log generation
                    browser_profiles = {}
                    
                    for browser, path, profile_name in self.browser_paths:
                        logging.info(f"Scraping [{browser}] Profile: {profile_name} -> {path}")
                        browser_data = extract_history_data(path, browser, profile_name)
                        
                        # Save per-profile CSV if export directory is set
                        if self._vault_export_dir:
                            browser_output_dir = os.path.join(self._vault_export_dir, "Extraction", f"{browser}_Raw")
                            csv_path, start_date, end_date = save_profile_csv(
                                browser_data, browser, profile_name, browser_output_dir
                            )
                        else:
                            logging.warning(f"[{browser}] No export directory set, skipping CSV save")
                            csv_path, start_date, end_date = None, None, None
                        
                        # Track for metadata log
                        if browser not in browser_profiles:
                            browser_profiles[browser] = {}
                        browser_profiles[browser][profile_name] = {
                            'csv_path': csv_path,
                            'record_count': len(browser_data),
                            'start_date': start_date,
                            'end_date': end_date
                        }
                        
                        all_artifacts.extend(browser_data)
                        
                        # Platinum: Carve SQLite Free-Lists for Deleted History
                        known_urls = {item.get("Content", "") for item in browser_data}
                        carved = carve_sqlite_freelist(path, known_urls)
                        if carved:
                            logging.warning(f"[Lazarus] Carved {len(carved)} deleted URLs from {browser}!")
                            carved_urls.extend(carved)
                            
                        ads_targets.append(path)
                    
                    # Generate metadata logs for each browser if export directory is set
                    if self._vault_export_dir:
                        for browser, profile_data in browser_profiles.items():
                            browser_output_dir = os.path.join(self._vault_export_dir, "Extraction", f"{browser}_Raw")
                            generate_metadata_log(browser, browser_output_dir, profile_data)
                    
                if run_notepad:
                    self.update_status("Vector: TabState Memory...", 0.4)
                    logging.info("Scraping Volatile TabState Binaries...")
                    notepad_data = parse_notepad_tabs()
                    all_artifacts.extend(notepad_data)
                    
                    for item in notepad_data:
                        if item.get("File Path"): ads_targets.append(item["File Path"])
                    
                self.update_status("Vector: Low-Level Registry & Cache...", 0.5)
                logging.info("Initiating Low-Level File System and Registry Scrape...")
                from modules.registry_parser import parse_registry_artifacts
                from modules.dns_parser import get_dns_cache, identify_private_leaks
                
                # 1. Registry
                reg_artifacts = parse_registry_artifacts()
                all_artifacts.extend(reg_artifacts)
                
                # 2. DNS Cache (Incognito Detection)
                dns_cache = get_dns_cache()
            
                if run_os:
                    self.update_status("Vector: Deep OS Memory...", 0.6)
                    from modules.os_artifacts import get_search_index_ghosts, get_jump_lists, get_srum_data, get_recall_snapshots
                    
                    # Jump Lists
                    jump_data = get_jump_lists()
                    all_artifacts.extend(jump_data)
                    
                    # Search Index
                    search_data = get_search_index_ghosts()
                    all_artifacts.extend(search_data)
                    
                    # SRUM
                    srum_data = get_srum_data()
                    all_artifacts.extend(srum_data)
                    
                    # Windows Recall
                    recall_data = get_recall_snapshots()
                    all_artifacts.extend(recall_data)
                    
                self.update_status("Analyzing Artifacts...", 0.7)
                logging.info("Cross-Referencing Indicators of Compromise...")
                analyzed_artifacts = analyze_artifacts(all_artifacts)
                
                # Platinum: AI Persona Generation
                persona_report = generate_user_persona(analyzed_artifacts)
                
                # Platinum: Alternate Data Streams
                ads_data = check_zone_identifiers(ads_targets)
                if ads_data:
                    logging.warning(f"Detected {len(ads_data)} Zone.Identifier (Mark of the Web) Streams!")
                
                # 3. Identify Leaks (DNS vs History)
                leaks = identify_private_leaks(dns_cache, analyzed_artifacts)
                if leaks:
                    logging.warning(f"DETECTED {len(leaks)} POTENTIAL INCOGNITO/PRIVATE LEAKS IN DNS CACHE!")
                
                self.update_status("Packaging Evidence Containers...", 0.9)
                logging.info("Generating Cryptographically Secured Suite...")
                report_gen = ReportGenerator(self.case_metadata)
                export_dir = report_gen.generate(
                    analyzed_artifacts,
                    self.browser_paths,
                    leaks=leaks,
                    persona=persona_report,
                    ads_data=ads_data,
                    carved_urls=carved_urls
                )

                # Generate Master Correlator for Neural Map
                logging.info("Generating Master Correlator for Neural Map...")
                generate_master_correlator(export_dir)

                # Generate Neural Map HTML
                logging.info("Generating Neural Map visualization...")
                from modules.neural_map import generate_neural_map_html
                generate_neural_map_html(export_dir)

                self.populate_vault(export_dir)
                self.tab_view.set("Evidence Vault")
                
                self.update_status(f"ABYSS Complete. Container: {export_dir}", 1.0)
                logging.info(f"SCRAPE SUCCESSFUL. Output -> {export_dir}")
            except Exception as inner_e:
                raise inner_e
                
        except Exception as e:
            print(f"CRITICAL THREAD ERROR: {e}")
            import traceback
            traceback.print_exc()
            logging.error(f"SYSTEM FAULT: {e}")
            self.update_status("Protocol Failed", 0.0)
            messagebox.showerror("ABYSS System Fault", f"Critical engine failure: {e}")
        finally:
            self.run_button.configure(state="normal")


if __name__ == "__main__":
    app = AbyssSuite()
    app.mainloop()
