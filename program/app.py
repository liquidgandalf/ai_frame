# Flask app for 80s TV Frame media display
# Depends on config.cfg for settings

import os
import configparser
from flask import Flask, request, render_template_string, redirect, url_for, session, flash, send_file
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import hashlib
import threading
import pygame
import sys
import json
import socket
import qrcode
from PIL import Image
from flask_session import Session
import sqlite3
import random

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Change in production
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Load config
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), '..', 'config.cfg')
config.read(config_path)

# Frame and display settings
frame_width_mm = int(config['frame']['width_mm'])
frame_height_mm = int(config['frame']['height_mm'])
screen_width_px = int(config['display']['screen_width_px'])
screen_height_px = int(config['display']['screen_height_px'])
offset_x = int(config['display'].get('offset_x', 0))
offset_y = int(config['display'].get('offset_y', 0))

# Scale factors
scale_x = screen_width_px / frame_width_mm
scale_y = screen_height_px / frame_height_mm

# Holes
holes = []
for key, value in config['holes'].items():
    parts = value.split(',')
    typ, x, y, w, h = parts
    holes.append({
        'id': int(key),
        'type': typ,
        'x_mm': float(x),
        'y_mm': float(y),
        'w_mm': float(w),
        'h_mm': float(h),
        'x_px': float(x) * scale_x + offset_x,
        'y_px': float(y) * scale_y + offset_y,
        'w_px': float(w) * scale_x,
        'h_px': float(h) * scale_y
    })

# Initialize image indices
current_image_index = {hole['id']: 0 for hole in holes}

# Server settings
username = config['server']['username']
password_hash = config['server']['password_hash']

# User management
users_file = os.path.join(os.path.dirname(__file__), '..', 'users.json')

def load_users():
    if os.path.exists(users_file):
        with open(users_file) as f:
            return json.load(f)
    return []

def save_users(users):
    with open(users_file, 'w') as f:
        json.dump(users, f, indent=4)

users = load_users()

# Paths
uploads_dir = config['paths']['uploads_dir']
if not os.path.isabs(uploads_dir):
    uploads_dir = os.path.join(os.path.dirname(__file__), '..', uploads_dir)
os.makedirs(uploads_dir, exist_ok=True)

# Database
db_path = os.path.join(os.path.dirname(__file__), '..', 'media.db')

def init_db():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS media (
        id INTEGER PRIMARY KEY,
        filepath TEXT UNIQUE,
        user TEXT,
        rotation INTEGER,
        crop_x REAL, crop_y REAL, crop_w REAL, crop_h REAL,
        frames TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

def add_media_to_db(filepath, user=None, rotation=None, crop_x=None, crop_y=None, crop_w=None, crop_h=None, frames='all'):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute('INSERT OR IGNORE INTO media (filepath, user, rotation, crop_x, crop_y, crop_w, crop_h, frames) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                  (filepath, user, rotation, crop_x, crop_y, crop_w, crop_h, frames))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

# Video settings
video_loop = config['video'].getboolean('loop')
video_mute = config['video'].getboolean('mute')

# Media storage: list of file_paths
media = []
current_hole_to_update = 0
last_cycle_time = datetime.now()

# Display mode
display_mode = config['display'].get('mode', 'calibrate')  # 'calibrate' or 'media'

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def load_media():
    # Load all media files from uploads_dir
    media_temp = []
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    for root, dirs, files in os.walk(uploads_dir):
        for file in files:
            filepath = os.path.join(root, file)
            media_temp.append(filepath)
            # Check if in db, if not add
            c.execute('SELECT id FROM media WHERE filepath = ?', (filepath,))
            if not c.fetchone():
                add_media_to_db(filepath)
    conn.close()
    # Sort by modification time, newest first
    media_temp.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    global media
    media = media_temp

load_media()

# Initialize with random indices
if media:
    for hole in holes:
        current_image_index[hole['id']] = random.randint(0, len(media)-1)

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        pwd_hash = hashlib.sha256(pwd.encode()).hexdigest()
        # Check users first
        user_found = None
        for u in users:
            if u['username'] == user and u['password_hash'] == pwd_hash:
                user_found = u
                break
        if user_found:
            session['logged_in'] = True
            session['username'] = user
            session.permanent = True
            if display_mode == 'media':
                return redirect(url_for('media_page'))
            else:
                return redirect(url_for('calibrate'))
        # If no users, allow config
        elif not users and user == username and pwd_hash == password_hash:
            session['logged_in'] = True
            session['username'] = user
            return redirect(url_for('add_user'))
        else:
            flash('Invalid credentials')
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head><title>Login</title></head>
    <body>
    <h1>Login to 80s TV Frame</h1>
    <form method="post">
        Username: <input type="text" name="username"><br>
        Password: <input type="password" name="password"><br>
        <input type="submit" value="Login">
    </form>
    {% with messages = get_flashed_messages() %}
        {% if messages %}
            <ul>
            {% for message in messages %}
                <li>{{ message }}</li>
            {% endfor %}
            </ul>
        {% endif %}
    {% endwith %}
    </body>
    </html>
    ''')

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        new_user = request.form['username']
        new_pwd = request.form['password']
        # Check if user exists
        if any(u['username'] == new_user for u in users):
            flash('User already exists')
        else:
            users.append({'username': new_user, 'password_hash': hashlib.sha256(new_pwd.encode()).hexdigest(), 'role': 'admin'})
            save_users(users)
            session['logged_in'] = True
            session['username'] = new_user
            session.permanent = True
            flash('Admin user added successfully')
            return redirect(url_for('calibrate'))
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head><title>Add Admin User</title></head>
    <body>
    <h1>Add New Admin User</h1>
    <form method="post">
        Username: <input type="text" name="username" required><br>
        Password: <input type="password" name="password" required><br>
        <input type="submit" value="Add User">
    </form>
    {% with messages = get_flashed_messages() %}
        {% if messages %}
            <ul>
            {% for message in messages %}
                <li>{{ message }}</li>
            {% endfor %}
            </ul>
        {% endif %}
    {% endwith %}
    </body>
    </html>
    ''')

@app.route('/calibrate')
def calibrate():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    # Calibration page: smaller view with move controls
    scale = 0.5  # smaller view
    html = f'''
    <!DOCTYPE html>
    <html>
    <head><title>Calibration</title><style>
    body {{ margin: 20px; }}
    .container {{ position: relative; width: {screen_width_px * scale}px; height: {screen_height_px * scale}px; background: repeating-linear-gradient(0deg, #f0f0f0, #f0f0f0 10px, #e0e0e0 10px, #e0e0e0 20px), repeating-linear-gradient(90deg, #f0f0f0, #f0f0f0 10px, #e0e0e0 10px, #e0e0e0 20px); border: 1px solid black; }}
    .hole {{ position: absolute; background: yellow; border: 2px solid red; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px; }}
    .controls {{ margin-top: 20px; }}
    button {{ margin: 5px; padding: 10px; }}
    </style></head>
    <body>
    <h1>Calibration Mode</h1>
    <p>Adjust the layout to align with the physical frame. Current offset: X={offset_x}, Y={offset_y}</p>
    <div class="container">
    '''
    for hole in holes:
        x = (hole["x_px"] - offset_x) * scale
        y = (hole["y_px"] - offset_y) * scale
        w = hole["w_px"] * scale
        h = hole["h_px"] * scale
        html += f'<div class="hole" style="left: {x - w/2}px; top: {y - h/2}px; width: {w}px; height: {h}px;">{hole["id"]}</div>'
    html += '''
    </div>
    <div class="controls">
    <button onclick="adjust(0,-1)">Up 1px</button>
    <button onclick="adjust(0,-10)">Up 10px</button><br>
    <button onclick="adjust(-1,0)">Left 1px</button>
    <button onclick="adjust(1,0)">Right 1px</button><br>
    <button onclick="adjust(0,1)">Down 1px</button>
    <button onclick="adjust(0,10)">Down 10px</button><br>
    <button onclick="adjust(0,0,true)">Reset to 0</button>
    </div>
    <br><button onclick="commit()">Commit Calibration</button>
    <br><a href="/switch_mode/media">Switch to Media Mode</a> | <a href="/media">Admin Media Upload</a>
    <script>
    function adjust(dx, dy, reset=false) {
        if (reset) {
            fetch('/adjust_offset?reset=1').then(() => location.reload());
        } else {
            fetch(`/adjust_offset?dx=${dx}&dy=${dy}`).then(() => location.reload());
        }
    }
    function commit() {
        if (confirm('Commit current calibration and switch to media mode?')) {
            fetch('/commit_calibration').then(() => location.href='/media');
        }
    }
    </script>
    </body></html>
    '''
    return html

@app.route('/adjust_offset')
def adjust_offset():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    global offset_x, offset_y
    if 'reset' in request.args:
        offset_x = 0
        offset_y = 0
    else:
        dx = int(request.args.get('dx', 0))
        dy = int(request.args.get('dy', 0))
        offset_x += dx
        offset_y += dy
    # Save to config
    config.set('display', 'offset_x', str(offset_x))
    config.set('display', 'offset_y', str(offset_y))
    with open(config_path, 'w') as f:
        config.write(f)
    # Update holes
    for hole in holes:
        hole['x_px'] = hole['x_mm'] * scale_x + offset_x
        hole['y_px'] = hole['y_mm'] * scale_y + offset_y
    return '', 204

@app.route('/switch_mode/<mode>')
def switch_mode(mode):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    global display_mode
    if mode in ['calibrate', 'media']:
        display_mode = mode
        config.set('display', 'mode', display_mode)
        with open(config_path, 'w') as f:
            config.write(f)
    return redirect(request.referrer or url_for('calibrate'))

@app.route('/commit_calibration')
def commit_calibration():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    global display_mode
    display_mode = 'media'
    config.set('display', 'mode', 'media')
    with open(config_path, 'w') as f:
        config.write(f)
    return redirect(url_for('media_page'))

@app.route('/media', methods=['GET', 'POST'])
def media_page():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            # Create directory structure: uploads_dir/user/year/month/day/timestamp_filename
            now = datetime.now()
            user = session['username']
            path = os.path.join(uploads_dir, user, str(now.year), f"{now.month:02d}", f"{now.day:02d}")
            os.makedirs(path, exist_ok=True)
            timestamp = int(now.timestamp() * 1000)  # milliseconds
            fileid = f"{timestamp}_{filename}"
            filepath = os.path.join(path, fileid)
            file.save(filepath)
            add_media_to_db(filepath, user=session.get('username'))
            load_media()  # Reload media list
    # Display page
    scale = min(1.0, window.innerWidth / screen_width_px, window.innerHeight / screen_height_px)  # but since it's server side, assume 0.5 or calculate client side
    # For simplicity, use fixed scale, say 0.3 for phone
    phone_scale = 0.3
    html = f'''
    <!DOCTYPE html>
    <html>
    <head><title>Media Mode</title><meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no"><style>
    body {{ margin: 0; background: black; color: white; font-family: Arial, sans-serif; overflow: hidden; }}
    .upload-form {{ position: fixed; top: 0; left: 0; right: 0; background: rgba(0,0,0,0.9); padding: 10px; z-index: 10; display: none; }}
    .upload-form select, .upload-form input[type="file"], .upload-form input[type="submit"] {{ margin: 5px; padding: 8px; font-size: 16px; }}
    .logout {{ position: absolute; top: 10px; right: 10px; }}
    .tv-layout {{ position: relative; width: {screen_width_px * phone_scale}px; height: {screen_height_px * phone_scale}px; margin: 50px auto; background: #111; border: 2px solid white; }}
    .hole {{ position: absolute; }}
    .hole img, .hole video {{ width: 100%; height: 100%; object-fit: cover; }}
    .show-upload {{ position: fixed; top: 10px; left: 10px; z-index: 11; }}
    @media (orientation: landscape) {{ body {{ /* landscape styles */ }} }}
    </style></head>
    <body>
    <button class="show-upload" onclick="toggleUpload()">Upload Media</button>
    <a href="/logout" class="logout">Logout</a>
    <div class="upload-form" id="uploadForm">
    <h2>Upload Media</h2>
    <form method="post" enctype="multipart/form-data">
        File: <input type="file" name="file" accept="image/*,video/*">
        <input type="submit" value="Upload">
    </form>
    </div>
    <div class="tv-layout" id="tvLayout">
    '''
    for hole in holes:
        index = current_image_index[hole['id']]
        if index < len(media):
            filepath = media[index]
            filename = os.path.basename(filepath)
            ext = os.path.splitext(filepath)[1].lower()
            x = hole['x_px'] * phone_scale
            y = hole['y_px'] * phone_scale
            w = hole['w_px'] * phone_scale
            h = hole['h_px'] * phone_scale
            if ext in ['.mp4', '.webm', '.ogg']:
                thumb = f'<video id="thumb-{hole["id"]}" controls><source src="/media_file_all/{index}" type="video/{ext[1:]}"></video>'
            else:
                thumb = f'<img id="thumb-{hole["id"]}" src="/media_file_all/{index}" alt="{filename}">'
            html += f'<div id="hole-{hole["id"]}" class="hole" style="left: {x - w/2}px; top: {y - h/2}px; width: {w}px; height: {h}px;">{thumb}</div>'
    html += '''
    </div>
    <div style="text-align: center; margin-top: 10px;">
    <a href="/switch_mode/calibrate">Reconfigure Layout</a>
    </div>
    <script>
    let mediaLength = {len(media)};
    let longPressTimer;
    let longPressed = false;
    let startX, startY;
    let currentIndex;

    function toggleUpload() {{
        let form = document.getElementById('uploadForm');
        form.style.display = form.style.display === 'none' ? 'block' : 'none';
    }}

    function deleteMedia(index) {{
        if (confirm('Delete this media?')) {{
            fetch(`/delete_media/${{index}}`).then(() => location.reload());
        }}
    }}

    function rotateLeft(index) {{
        fetch(`/rotate_media/${{index}}`).then(() => updateFrames());
    }}

    function rotateRight(index) {{
        fetch(`/rotate_right/${{index}}`).then(() => updateFrames());
    }}

    function updateFrames() {{
        fetch('/current_indices')
        .then(r => r.json())
        .then(indices => {{
            for (let holeId in indices) {{
                let index = indices[holeId];
                if (index < mediaLength) {{
                    let thumb = document.getElementById('thumb-' + holeId);
                    if (thumb.tagName === 'IMG') {{
                        thumb.src = '/media_file_all/' + index;
                    }} else if (thumb.tagName === 'VIDEO') {{
                        thumb.querySelector('source').src = '/media_file_all/' + index;
                        thumb.load();
                    }}
                }}
            }}
        }});
    }}

    function handleTouchStart(event, holeId) {{
        startX = event.touches[0].clientX;
        startY = event.touches[0].clientY;
        longPressed = false;
        longPressTimer = setTimeout(() => {{
            longPressed = true;
        }}, 500);
    }}

    function handleTouchMove(event) {{
        if (!longPressed) return;
        event.preventDefault();
    }}

    function handleTouchEnd(event, holeId) {{
        clearTimeout(longPressTimer);
        if (!longPressed) return;
        let endX = event.changedTouches[0].clientX;
        let endY = event.changedTouches[0].clientY;
        let dx = endX - startX;
        let dy = endY - startY;
        fetch('/current_indices')
        .then(r => r.json())
        .then(indices => {{
            let index = indices[holeId];
            if (Math.abs(dx) > Math.abs(dy)) {{
                if (dx > 50) {{
                    rotateRight(index);
                }} else if (dx < -50) {{
                    rotateLeft(index);
                }}
            }} else {{
                if (dy > 50) {{
                    deleteMedia(index);
                }} else if (dy < -50) {{
                    // further options, for now rotate 180
                    fetch(`/rotate_media/${{index}}`).then(() => fetch(`/rotate_media/${{index}}`).then(() => updateFrames()));
                }}
            }}
        }});
    }}

    // Add listeners to holes
    {''.join([f"document.getElementById('hole-{hole['id']}').addEventListener('touchstart', (e) => handleTouchStart(e, {hole['id']})); document.getElementById('hole-{hole['id']}').addEventListener('touchmove', handleTouchMove); document.getElementById('hole-{hole['id']}').addEventListener('touchend', (e) => handleTouchEnd(e, {hole['id']}));" for hole in holes])}

    setInterval(updateFrames, 5000);
    </script>
    </body></html>'''
    return html

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/media_file/<int:hole_id>')
def media_file(hole_id):
    if hole_id in media:
        return send_file(media[hole_id])
    return '', 404

@app.route('/media_file_all/<int:index>')
def media_file_all(index):
    if 0 <= index < len(media):
        return send_file(media[index])
    return '', 404

@app.route('/delete_media/<int:index>')
def delete_media(index):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if 0 <= index < len(media):
        filepath = media[index]
        # remove from db
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('DELETE FROM media WHERE filepath = ?', (filepath,))
        conn.commit()
        conn.close()
        # remove file
        if os.path.exists(filepath):
            os.remove(filepath)
        load_media()
    return '', 204

@app.route('/rotate_media/<int:index>')
def rotate_media(index):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if 0 <= index < len(media):
        filepath = media[index]
        # load image
        img = Image.open(filepath)
        img = img.rotate(-90, expand=True)  # rotate 90 deg left
        img.save(filepath)
        # update db rotation to 0
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('UPDATE media SET rotation = 0 WHERE filepath = ?', (filepath,))
        conn.commit()
        conn.close()
    return '', 204

@app.route('/rotate_right/<int:index>')
def rotate_right(index):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if 0 <= index < len(media):
        filepath = media[index]
        # load image
        img = Image.open(filepath)
        img = img.rotate(90, expand=True)  # rotate 90 deg right
        img.save(filepath)
        # update db rotation to 0
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('UPDATE media SET rotation = 0 WHERE filepath = ?', (filepath,))
        conn.commit()
        conn.close()
    return '', 204

@app.route('/current_indices')
def current_indices():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return json.dumps(current_image_index)

def run_display():
    global current_image_index, current_hole_to_update, last_cycle_time

    pygame.init()
    screen = pygame.display.set_mode((screen_width_px, screen_height_px), pygame.FULLSCREEN)
    pygame.display.set_caption("80s TV Frame Display")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 36)

    # Generate QR code
    local_ip = get_local_ip()
    url = f"http://{local_ip}:8000"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill='black', back_color='white').convert('RGB')
    qr_surface = pygame.image.fromstring(qr_img.tobytes(), qr_img.size, 'RGB')
    qr_surface = pygame.transform.scale(qr_surface, (100, 100))  # Scale to 100x100

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()

        screen.fill((0, 0, 0))  # Black background

        if display_mode == 'calibrate':
            # Draw grid background
            for x in range(0, screen_width_px, 20):
                pygame.draw.line(screen, (64, 64, 64), (x, 0), (x, screen_height_px))
            for y in range(0, screen_height_px, 20):
                pygame.draw.line(screen, (64, 64, 64), (0, y), (screen_width_px, y))

            # Draw holes
            for hole in holes:
                color = (255, 255, 0)  # Yellow
                x, y, w, h = hole['x_px'], hole['y_px'], hole['w_px'], hole['h_px']
                if hole['type'] == 'rect':
                    pygame.draw.rect(screen, color, (x - w/2, y - h/2, w, h), 2)
                elif hole['type'] == 'circle':
                    pygame.draw.circle(screen, color, (int(x), int(y)), int(w/2), 2)
                else:  # oval
                    pygame.draw.ellipse(screen, color, (x - w/2, y - h/2, w, h), 2)
                # Draw number
                text = font.render(str(hole['id']), True, (255, 0, 0))
                screen.blit(text, (x - w/2 + 5, y - h/2 + 5))

        elif display_mode == 'media':
            # Cycle one frame every 5 seconds, picking random images
            global current_image_index, current_hole_to_update, last_cycle_time
            now = datetime.now()
            if media and (now - last_cycle_time).seconds >= 5:
                hole_id = holes[current_hole_to_update]['id']
                current_image_index[hole_id] = random.randint(0, len(media)-1)
                current_hole_to_update = (current_hole_to_update + 1) % len(holes)
                last_cycle_time = now
            # Draw media
            for hole in holes:
                if media:
                    index = current_image_index[hole['id']]
                    filepath = media[index]
                    try:
                        img = pygame.image.load(filepath)
                        img_w, img_h = img.get_size()
                        hole_w, hole_h = int(hole['w_px']), int(hole['h_px'])
                        # Calculate scale to fit while keeping aspect ratio
                        scale = min(hole_w / img_w, hole_h / img_h)
                        new_w = int(img_w * scale)
                        new_h = int(img_h * scale)
                        img_scaled = pygame.transform.scale(img, (new_w, new_h))
                        # Center in hole
                        x = hole['x_px'] - hole_w / 2 + (hole_w - new_w) / 2
                        y = hole['y_px'] - hole_h / 2 + (hole_h - new_h) / 2
                        screen.blit(img_scaled, (x, y))
                    except:
                        pass  # Skip if can't load

        # Draw QR code at bottom left
        screen.blit(qr_surface, (10, screen_height_px - 110))

        pygame.display.flip()
        clock.tick(30)

if __name__ == '__main__':
    # Start Flask in a thread
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()
    # Run Pygame display
    run_display()