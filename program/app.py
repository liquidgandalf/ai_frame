# Flask app for 80s TV Frame media display
# Depends on config.cfg for settings

import os
import configparser
from flask import Flask, request, render_template_string, redirect, url_for, session, flash, send_file
from werkzeug.utils import secure_filename
from datetime import datetime
import hashlib
import threading
import pygame
import sys
import json

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Change in production

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

# Video settings
video_loop = config['video'].getboolean('loop')
video_mute = config['video'].getboolean('mute')

# Media storage: dict of hole_id to file_path
media = {}

# Display mode
display_mode = 'calibrate'  # 'calibrate' or 'media'

def load_media():
    # Load existing media from uploads_dir
    # Scan recursively for files, parse hole_id from filename
    media_temp = {}
    for root, dirs, files in os.walk(uploads_dir):
        for file in files:
            if '_' in file:
                try:
                    hole_id = int(file.split('_')[0])
                    filepath = os.path.join(root, file)
                    if hole_id not in media_temp or os.path.getmtime(filepath) > os.path.getmtime(media_temp[hole_id]):
                        media_temp[hole_id] = filepath
                except ValueError:
                    pass
    global media
    media = media_temp

load_media()

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
    <br><a href="/switch_mode/media">Switch to Media Mode</a> | <a href="/media">Admin Media Upload</a>
    <script>
    function adjust(dx, dy, reset=false) {
        if (reset) {
            fetch('/adjust_offset?reset=1').then(() => location.reload());
        } else {
            fetch(`/adjust_offset?dx=${dx}&dy=${dy}`).then(() => location.reload());
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
    return redirect(request.referrer or url_for('calibrate'))

@app.route('/media', methods=['GET', 'POST'])
def media_page():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        hole_id = int(request.form['hole_id'])
        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            # Create directory structure: uploads_dir/user/year/month/day/fileid_filename
            now = datetime.now()
            user = session['username']
            path = os.path.join(uploads_dir, user, str(now.year), f"{now.month:02d}", f"{now.day:02d}")
            os.makedirs(path, exist_ok=True)
            fileid = f"{hole_id}_{filename}"
            filepath = os.path.join(path, fileid)
            file.save(filepath)
            media[hole_id] = filepath
    # Display page
    html = '''
    <!DOCTYPE html>
    <html>
    <head><title>Media Mode</title><style>
    body { margin: 0; background: black; }
    .media { position: absolute; }
    video { width: 100%; height: 100%; object-fit: cover; }
    img { width: 100%; height: 100%; object-fit: cover; }
    </style></head>
    <body>
    <h1>Media Mode</h1>
    <form method="post" enctype="multipart/form-data">
        Hole ID: <select name="hole_id">
    '''
    for hole in holes:
        html += f'<option value="{hole["id"]}">{hole["id"]}</option>'
    html += '''
        </select>
        File: <input type="file" name="file">
        <input type="submit" value="Upload">
    </form>
    '''
    for hole in holes:
        if hole['id'] in media:
            filepath = media[hole['id']]
            ext = os.path.splitext(filepath)[1].lower()
            if ext in ['.mp4', '.webm', '.ogg']:
                html += f'<video class="media" style="left: {hole["x_px"] - hole["w_px"]/2}px; top: {hole["y_px"] - hole["h_px"]/2}px; width: {hole["w_px"]}px; height: {hole["h_px"]}px;" {"loop" if video_loop else ""} {"muted" if video_mute else ""} autoplay><source src="/media_file/{hole["id"]}" type="video/{ext[1:]}"></video>'
            else:
                html += f'<img class="media" style="left: {hole["x_px"] - hole["w_px"]/2}px; top: {hole["y_px"] - hole["h_px"]/2}px; width: {hole["w_px"]}px; height: {hole["h_px"]}px;" src="/media_file/{hole["id"]}">'
    html += '<br><a href="/switch_mode/calibrate">Switch to Calibration Mode</a></body></html>'
    return html

@app.route('/media_file/<int:hole_id>')
def media_file(hole_id):
    if hole_id in media:
        return send_file(media[hole_id])
    return '', 404

def run_display():
    pygame.init()
    screen = pygame.display.set_mode((screen_width_px, screen_height_px), pygame.FULLSCREEN)
    pygame.display.set_caption("80s TV Frame Display")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 36)

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
            # Draw media
            for hole in holes:
                if hole['id'] in media:
                    filepath = media[hole['id']]
                    try:
                        img = pygame.image.load(filepath)
                        img = pygame.transform.scale(img, (int(hole['w_px']), int(hole['h_px'])))
                        screen.blit(img, (hole['x_px'] - hole['w_px']/2, hole['y_px'] - hole['h_px']/2))
                    except:
                        pass  # Skip if can't load

        pygame.display.flip()
        clock.tick(30)

if __name__ == '__main__':
    # Start Flask in a thread
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()
    # Run Pygame display
    run_display()