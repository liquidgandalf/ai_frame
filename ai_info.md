# Project_80s_Tv_frame

## Scope of the Project
This project builds a custom wooden picture frame to surround a flat-panel TV.

- The frame will be made from solid plywood in a retro 1980s style.  
- Square/rectangular openings (“windows”) will be cut in the wood, each with a photo-frame surround.  
- A simple mounting system will let the frame slide over the TV.

On the software side:

- The TV will run an app that plays several small videos or photos at once, aligned with the frame openings, so the wall frame shows **“moving memories.”**

---

## Project Structure
/program → All Python3 code
/Build_instructions_and_measurements → CAD drawings, cut plans, assembly notes
ai_info.md → This document (scope, structure, AI rules)
/config.cfg → Configuration (frame size, hole positions, paths, login, etc.)
/uploads → User media (photos/videos), organised by user/year/month/day

markdown
Copy code

---

## Program (Software Component)

### 1️⃣ Configuration Tool
- **Purpose:** Design the frame layout and save all measurements.
- **Features:**
  - Desktop or web app (Python3 + Tkinter/PyQt or simple Flask front-end).
  - Enter:
    - Overall width/height of the wooden cover.
    - Position & size of each cut-out window.
  - Interactive editor: draw/drag square areas over a preview of the TV screen.
  - Writes data to `config.cfg`.
  - Can export an **SVG template** for laser/CNC cutting.

### 2️⃣ Main Playback App
- **Purpose:** Display media inside the cut-outs.
- **Features:**
  - Flask web interface.
  - Reads login credentials and paths from `config.cfg`.
  - **First run = Calibration mode**  
    - Shows numbered yellow squares at cut-out positions, with a light “road-grid” background to aid alignment.
  - **After calibration = Media mode**  
    - Upload photos or short videos for each frame number.
    - Uploads stored neatly:

      ```
      /uploads/<user>/<year>/<month>/<day>/<fileid>_filename.ext
      ```

    - Plays assigned media in each window, looping videos where applicable.

### 3️⃣ Configuration File (`config.cfg`)
Stores:
- Frame dimensions (width/height).
- Hole coordinates & sizes.
- Username + hashed password for the Flask UI.
- **Uploads directory path** (default: `./uploads`).
- Optional video behaviour (loop, mute, etc.).

Example:

```ini
[frame]
width_mm = 1200
height_mm = 700

[holes]
# id = x, y, width, height  (mm or screen pixels)
1 = 100,120,200,150
2 = 350,120,200,150
3 = 600,120,200,150

[server]
username = admin
password_hash = sha256:...

[paths]
uploads_dir = /srv/80s_tv_frame/uploads

[video]
loop = true
mute = false
AI Rules
Keep project files separate from unrelated work.

When writing code, give working examples with short explanations. Prefer Python 3 + Flask/Pygame/PyQt unless asked otherwise.

When writing code, if a .py file is over 500 lines refactor as best you can

add hidden remarks in top of code // explaining dependant files due to refactoring




Never assume physical measurements — request or confirm TV dimensions before drafting cut plans.

For carpentry guidance, include clear dimensions, tool lists, and safety reminders.

Default software environment: Linux Mint or Raspberry Pi OS.

Match the aesthetic to a retro 1980s theme (fonts, colours, layout).

Store layout/media paths in config.cfg; avoid hard-coding.

Ask the user about uncertain design choices (wood finish, screen size, upload policy).

Keep uploads and code separate: /uploads for media, /program for logic.

any new task, or task infomation or task completion keep the ai_tasklist.md uptodate