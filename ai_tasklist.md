# AI Task List

- [x] Add support for oval and circle cut-outs in config_creator.py.
- [x] Update SVG export to include outer frame as a cut shape.
- [x] Add config loading on app start.
- [x] Create creator.sh runner script in the top folder.
- [x] Create config creator app: Developed program/config_creator.py, a Tkinter-based GUI for designing the 80s TV frame layout. Features include input for frame dimensions, interactive canvas for adding and dragging cut-out rectangles, saving to config.cfg, and exporting SVG templates for cutting.

- [x] Modify config_creator.py: Revert to all yellow cut-outs, black background, wood-colored frame, add edge resizing for cut-outs.

- [x] Build Flask app for media playback: Created program/app.py with authentication, calibration mode with adjustable offset for alignment, and media mode for uploading and displaying photos/videos in cut-out positions, stored in organized directory structure.

- [x] Initialize git repository and push initial commit to GitHub repo.

- [x] Implement user management system: Add JSON-based user storage, admin user creation, disable default config login after adding users, use session username for uploads.

- [x] Add calibration commit functionality: Allow committing calibration to switch to media mode, save mode to config, redirect login to media mode by default with option to reconfigure layout.

- [x] Create run.sh script to start the Flask app and Pygame display.

- [x] Implement random image cycling: Initialize with random images and cycle to random images every 5 seconds instead of sequential.

- [x] Add current frames display in media page with Bin and Rotate 90 Deg buttons for each hole.

- [x] Add auto-update to media page: Poll server every 5 seconds to update thumbnails without refresh.

- [x] Improve media page for phone use: Hide upload form behind button, use landscape orientation, display TV layout with holes positioned, add touch gestures for long press + drag to delete (up), rotate left (left), rotate right (right), further options (down).

- [x] Fix login by setting default password hash and removing conflicting users.json.
