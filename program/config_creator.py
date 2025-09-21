import tkinter as tk
from tkinter import filedialog, messagebox
import configparser
import xml.etree.ElementTree as ET
import os

class ConfigCreator:
    def __init__(self, root):
        self.root = root
        self.root.title("80s TV Frame Config Creator")

        # Frame dimensions
        self.frame_width = 1200  # default mm
        self.frame_height = 700

        # List of holes: list of {'type': 'rect', 'x': x, 'y': y, 'w': w, 'h': h} in mm, x,y center
        self.holes = []

        # Canvas scale: pixels per mm
        self.scale = 1  # 1 pixel = 1 mm for simplicity

        self.canvas_width = self.frame_width * self.scale
        self.canvas_height = self.frame_height * self.scale

        # Resize mode
        self.resize_mode = None  # None, 'left', 'right', 'top', 'bottom', 'topleft', etc.
        self.initial_x = 0
        self.initial_y = 0
        self.click_x = 0
        self.click_y = 0

        # UI elements
        self.create_widgets()

        # Load saved config if exists
        self.load_config()

    def create_widgets(self):
        # Frame for inputs
        input_frame = tk.Frame(self.root)
        input_frame.pack(side=tk.TOP, fill=tk.X)

        tk.Label(input_frame, text="Frame Width (mm):").grid(row=0, column=0)
        self.width_entry = tk.Entry(input_frame)
        self.width_entry.insert(0, str(self.frame_width))
        self.width_entry.grid(row=0, column=1)

        tk.Label(input_frame, text="Frame Height (mm):").grid(row=1, column=0)
        self.height_entry = tk.Entry(input_frame)
        self.height_entry.insert(0, str(self.frame_height))
        self.height_entry.grid(row=1, column=1)

        update_btn = tk.Button(input_frame, text="Update Frame", command=self.update_frame)
        update_btn.grid(row=0, column=2, rowspan=2)

        # Canvas
        self.canvas = tk.Canvas(self.root, width=self.canvas_width, height=self.canvas_height, bg='black')
        self.canvas.pack()

        # Draw initial frame
        self.draw_frame()

        # Buttons
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X)

        add_rect_btn = tk.Button(btn_frame, text="Add Rectangle", command=self.add_rectangle)
        add_rect_btn.pack(side=tk.LEFT)

        add_oval_btn = tk.Button(btn_frame, text="Add Oval", command=self.add_oval)
        add_oval_btn.pack(side=tk.LEFT)

        add_circle_btn = tk.Button(btn_frame, text="Add Circle", command=self.add_circle)
        add_circle_btn.pack(side=tk.LEFT)

        save_btn = tk.Button(btn_frame, text="Save Config", command=self.save_config)
        save_btn.pack(side=tk.LEFT)

        export_svg_btn = tk.Button(btn_frame, text="Export SVG", command=self.export_svg)
        export_svg_btn.pack(side=tk.LEFT)

        # Mouse events for dragging
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        self.dragging = False
        self.drag_item = None
        self.start_x = 0
        self.start_y = 0

    def update_frame(self):
        try:
            self.frame_width = int(self.width_entry.get())
            self.frame_height = int(self.height_entry.get())
            self.canvas_width = self.frame_width * self.scale
            self.canvas_height = self.frame_height * self.scale
            self.canvas.config(width=self.canvas_width, height=self.canvas_height)
            self.draw_frame()
        except ValueError:
            messagebox.showerror("Error", "Invalid dimensions")

    def draw_frame(self):
        self.canvas.delete("all")
        # Draw frame rectangle
        self.canvas.create_rectangle(0, 0, self.canvas_width, self.canvas_height, fill='#8B4513', outline='black', width=2)
        # Draw holes
        for i, hole in enumerate(self.holes):
            hx, hy, hw, hh = hole['x'], hole['y'], hole['w'], hole['h']
            bbox = [hx - hw/2, hy - hh/2, hx + hw/2, hy + hh/2]
            scaled_bbox = [b * self.scale for b in bbox]
            if hole['type'] == 'rect':
                self.canvas.create_rectangle(*scaled_bbox, fill='yellow', outline='red', tags=f"hole_{i}")
            else:
                self.canvas.create_oval(*scaled_bbox, fill='yellow', outline='red', tags=f"hole_{i}")
            # Label
            self.canvas.create_text(hx * self.scale, hy * self.scale, text=str(i+1), font=("Arial", 12, "bold"))

    def add_rectangle(self):
        # Add a default rectangle, offset for each new one to avoid overlap
        offset = len(self.holes) * 50  # 50mm offset per shape
        x = self.frame_width // 2 + offset
        y = self.frame_height // 2 + offset
        w = self.frame_width // 2
        h = self.frame_height // 2
        self.holes.append({'type': 'rect', 'x': x, 'y': y, 'w': w, 'h': h})
        self.draw_frame()

    def add_oval(self):
        offset = len(self.holes) * 50
        x = self.frame_width // 2 + offset
        y = self.frame_height // 2 + offset
        w = 120
        h = 80
        self.holes.append({'type': 'oval', 'x': x, 'y': y, 'w': w, 'h': h})
        self.draw_frame()

    def add_circle(self):
        offset = len(self.holes) * 50
        x = self.frame_width // 2 + offset
        y = self.frame_height // 2 + offset
        r = 50
        w = r * 2
        h = r * 2
        self.holes.append({'type': 'circle', 'x': x, 'y': y, 'w': w, 'h': h})
        self.draw_frame()

    def on_click(self, event):
        margin = 20  # pixels
        # Find if clicked on a hole
        items = self.canvas.find_overlapping(event.x-margin, event.y-margin, event.x+margin, event.y+margin)
        for item in items:
            tags = self.canvas.gettags(item)
            for tag in tags:
                if tag.startswith("hole_"):
                    hole_idx = int(tag.split("_")[1])
                    hole = self.holes[hole_idx]
                    hx, hy, hw, hh = hole['x'], hole['y'], hole['w'], hole['h']
                    cx1 = (hx - hw/2) * self.scale
                    cy1 = (hy - hh/2) * self.scale
                    cx2 = (hx + hw/2) * self.scale
                    cy2 = (hy + hh/2) * self.scale
                    # Check if near edge
                    if abs(event.x - cx1) <= margin:
                        if abs(event.y - cy1) <= margin:
                            self.resize_mode = 'topleft'
                        elif abs(event.y - cy2) <= margin:
                            self.resize_mode = 'bottomleft'
                        else:
                            self.resize_mode = 'left'
                    elif abs(event.x - cx2) <= margin:
                        if abs(event.y - cy1) <= margin:
                            self.resize_mode = 'topright'
                        elif abs(event.y - cy2) <= margin:
                            self.resize_mode = 'bottomright'
                        else:
                            self.resize_mode = 'right'
                    elif abs(event.y - cy1) <= margin:
                        self.resize_mode = 'top'
                    elif abs(event.y - cy2) <= margin:
                        self.resize_mode = 'bottom'
                    else:
                        self.resize_mode = None  # drag
                    self.drag_item = hole_idx
                    self.dragging = True
                    if self.resize_mode is None:
                        self.initial_x = self.holes[hole_idx]['x']
                        self.initial_y = self.holes[hole_idx]['y']
                        self.click_x = event.x
                        self.click_y = event.y
                    else:
                        self.start_x = event.x
                        self.start_y = event.y
                    break

    def on_drag(self, event):
        if self.dragging:
            if self.resize_mode:
                # Resize (incremental)
                dx = event.x - self.start_x
                dy = event.y - self.start_y
                if self.resize_mode == 'left':
                    self.holes[self.drag_item]['x'] += dx / self.scale
                    self.holes[self.drag_item]['w'] -= 2 * dx / self.scale
                elif self.resize_mode == 'right':
                    self.holes[self.drag_item]['w'] += 2 * dx / self.scale
                elif self.resize_mode == 'top':
                    self.holes[self.drag_item]['y'] += dy / self.scale
                    self.holes[self.drag_item]['h'] -= 2 * dy / self.scale
                elif self.resize_mode == 'bottom':
                    self.holes[self.drag_item]['h'] += 2 * dy / self.scale
                elif self.resize_mode == 'topleft':
                    self.holes[self.drag_item]['x'] += dx / self.scale
                    self.holes[self.drag_item]['y'] += dy / self.scale
                    self.holes[self.drag_item]['w'] -= 2 * dx / self.scale
                    self.holes[self.drag_item]['h'] -= 2 * dy / self.scale
                elif self.resize_mode == 'topright':
                    self.holes[self.drag_item]['y'] += dy / self.scale
                    self.holes[self.drag_item]['w'] += 2 * dx / self.scale
                    self.holes[self.drag_item]['h'] -= 2 * dy / self.scale
                elif self.resize_mode == 'bottomleft':
                    self.holes[self.drag_item]['x'] += dx / self.scale
                    self.holes[self.drag_item]['w'] -= 2 * dx / self.scale
                    self.holes[self.drag_item]['h'] += 2 * dy / self.scale
                elif self.resize_mode == 'bottomright':
                    self.holes[self.drag_item]['w'] += 2 * dx / self.scale
                    self.holes[self.drag_item]['h'] += 2 * dy / self.scale
                # Prevent negative sizes
                if self.holes[self.drag_item]['w'] < 10:
                    self.holes[self.drag_item]['w'] = 10
                if self.holes[self.drag_item]['h'] < 10:
                    self.holes[self.drag_item]['h'] = 10
                self.start_x = event.x
                self.start_y = event.y
            else:
                # Drag (absolute)
                self.holes[self.drag_item]['x'] = self.initial_x + (event.x - self.click_x) / self.scale
                self.holes[self.drag_item]['y'] = self.initial_y + (event.y - self.click_y) / self.scale
            self.draw_frame()

    def on_release(self, event):
        self.dragging = False
        self.drag_item = None
        self.resize_mode = None

    def save_config(self):
        # Update frame dimensions from entries
        try:
            self.frame_width = int(self.width_entry.get())
            self.frame_height = int(self.height_entry.get())
            self.canvas_width = self.frame_width * self.scale
            self.canvas_height = self.frame_height * self.scale
            self.canvas.config(width=self.canvas_width, height=self.canvas_height)
            self.draw_frame()
        except ValueError:
            messagebox.showerror("Error", "Invalid dimensions")
            return
        config = configparser.ConfigParser()
        config['frame'] = {
            'width_mm': str(self.frame_width),
            'height_mm': str(self.frame_height)
        }
        config['holes'] = {}
        for i, hole in enumerate(self.holes, 1):
            config['holes'][str(i)] = f"{hole['type']},{int(hole['x'])},{int(hole['y'])},{int(hole['w'])},{int(hole['h'])}"
        # Add other sections as per example
        config['server'] = {'username': 'admin', 'password_hash': 'sha256:...'}  # placeholder
        config['paths'] = {'uploads_dir': './uploads'}
        config['video'] = {'loop': 'true', 'mute': 'false'}
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, '..', 'config.cfg')
        with open(config_path, 'w') as f:
            config.write(f)
        messagebox.showinfo("Saved", "Config saved to config.cfg")

    def load_config(self):
        try:
            config = configparser.ConfigParser()
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(script_dir, '..', 'config.cfg')
            config.read(config_path)
            if 'frame' in config:
                self.frame_width = int(config['frame'].get('width_mm', self.frame_width))
                self.frame_height = int(config['frame'].get('height_mm', self.frame_height))
            if 'holes' in config:
                self.holes = []
                for key, value in config['holes'].items():
                    parts = value.split(',')
                    if len(parts) == 5:
                        typ, x, y, w, h = parts
                        self.holes.append({'type': typ, 'x': float(x), 'y': float(y), 'w': float(w), 'h': float(h)})
            self.canvas_width = self.frame_width * self.scale
            self.canvas_height = self.frame_height * self.scale
            self.canvas.config(width=self.canvas_width, height=self.canvas_height)
            self.width_entry.delete(0, tk.END)
            self.width_entry.insert(0, str(self.frame_width))
            self.height_entry.delete(0, tk.END)
            self.height_entry.insert(0, str(self.frame_height))
            self.draw_frame()
        except Exception as e:
            pass  # ignore if can't load

    def export_svg(self):
        # Create SVG
        svg = ET.Element('svg', xmlns="http://www.w3.org/2000/svg", width=str(self.frame_width), height=str(self.frame_height))
        # Frame rect
        ET.SubElement(svg, 'rect', x="0", y="0", width=str(self.frame_width), height=str(self.frame_height), fill="white", stroke="black", stroke_width="1")
        # Holes
        for hole in self.holes:
            if hole['type'] == 'rect':
                ET.SubElement(svg, 'rect', x=str(hole['x'] - hole['w']/2), y=str(hole['y'] - hole['h']/2), width=str(hole['w']), height=str(hole['h']), fill="white", stroke="black", stroke_width="1")
            elif hole['type'] == 'circle':
                r = hole['w'] / 2
                ET.SubElement(svg, 'circle', cx=str(hole['x']), cy=str(hole['y']), r=str(r), fill="white", stroke="black", stroke_width="1")
            else:  # oval
                ET.SubElement(svg, 'ellipse', cx=str(hole['x']), cy=str(hole['y']), rx=str(hole['w']/2), ry=str(hole['h']/2), fill="white", stroke="black", stroke_width="1")
        tree = ET.ElementTree(svg)
        file_path = filedialog.asksaveasfilename(defaultextension=".svg", filetypes=[("SVG files", "*.svg")])
        if file_path:
            tree.write(file_path)
            messagebox.showinfo("Exported", f"SVG exported to {file_path}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ConfigCreator(root)
    root.mainloop()