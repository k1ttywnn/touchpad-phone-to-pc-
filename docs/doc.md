Touchpad Controller Project Documentation
========================================

Hey bro, welcome to the docs for this cool touchpad controller I built! This thing turns your phone or tablet into a remote mouse for your computer. You can move the cursor, click stuff, scroll, and even do fancy gestures. Here’s everything you need to know to get it running and use it like a pro.

---

What It Does
------------
- Move the mouse cursor by sliding your finger on the screen.
- Left click with a single tap.
- Right click with a two-finger tap.
- Scroll up/down with two fingers.
- Swipe between apps with three fingers.
- Zoom in/out by pinching with two fingers.

It’s like a magic trackpad, but on your phone!

---

Requirements
------------
### On Your Computer (Server Side)
You’ll need Python 3.12 (or close to it) and these libraries. Put this in a `requirements.txt` file and run `pip install -r requirements.txt`:


### On Your Phone/Tablet (Client Side)
- Any modern web browser (Chrome, Safari, Firefox, etc.).
- No apps needed—just open a webpage!

---

Setup Instructions
------------------
1. **Save the Server Code**
   - Copy the Python code (that `server_main.py` thing) into a file on your computer.
   - Make sure it’s got all the fixes we talked about (like clamping mouse coordinates and `global _token_cache`).

2. **Install Python Stuff**
   - Open a terminal where `server_main.py` is.
   - Run: `pip install -r requirements.txt` (after saving the list above).

3. **Start the Server**
   - In the terminal, type: `python server_main.py`.
   - You’ll see it say “Starting touchpad server on 0.0.0.0:2375”. That means it’s running!

4. **Get the Client Ready**
   - Copy the HTML/JavaScript code into a file (like `index.html`).
   - Put it in a `client` folder next to `server_main.py` (or wherever the server can find it).

5. **Connect from Your Phone**
   - On your computer, find your IP address (e.g., `192.168.1.166`). On Windows, type `ipconfig` in Command Prompt and look for “IPv4 Address”.
   - On your phone, open a browser and go to: `http://192.168.1.166:2375/` (swap in your IP).
   - You should see a black touchpad area and a status bar saying “Kimlik doğrulanıyor...” (Authenticating...).

6. **Test It**
   - Tap the screen. The mouse should click on your computer!
   - Slide your finger. The cursor should follow.

---

How to Use It
-------------
### Moving the Mouse
- Slide one finger around the touchpad. The cursor moves smoothly on your screen.

### Clicking
- **Left Click**: Tap once with one finger (quick, under 0.3 seconds).
- **Right Click**: Tap once with two fingers at the same time.

### Scrolling
- Put two fingers down and slide them:
  - Up to scroll up.
  - Down to scroll down.
- Gotta move fast (under 0.2 seconds) and at least a little bit (10 pixels).

### Gestures
- **Three-Finger Swipe**: Swipe three fingers left or right quick (50 pixels in 0.3 seconds):
  - Right: Switches apps forward (like Alt+Tab).
  - Left: Switches apps backward (like Alt+Shift+Tab).
- **Pinch Zoom**: Use two fingers:
  - Spread them apart to zoom in.
  - Pinch them together to zoom out.
  - Needs a decent move (20 pixels or 15% of the starting distance).

---

Troubleshooting
---------------
- **“Kimlik doğrulama başarısız” (Authentication failed)**:
  - Check if the server’s running. Restart it with `python server_main.py`.
  - Make sure your phone’s on the same Wi-Fi as your computer.
  - Look at the server terminal for errors (like missing `pyjwt`).

- **Mouse Won’t Move**:
  - Could be that fail-safe thing. I fixed it by keeping the cursor away from corners, but if it’s still weird, add `pyautogui.FAILSAFE = False` at the top of `server_main.py` (not the best idea though).

- **Clicks Not Working**:
  - Tap faster and don’t slide your finger. If it thinks you’re dragging, it skips the click.

- **Server Crashes**:
  - Look at the terminal logs. If it’s something like `_token_cache` errors, add `global _token_cache` in the `validate_token` function.

---

Techy Details (For Nerds Like Me)
---------------------------------
### Server (Python)
- **Framework**: Uses Quart (like Flask but async) with Hypercorn to serve the app and WebSocket stuff via `python-socketio`.
- **Mouse Control**: `pyautogui` moves the cursor and clicks. I smoothed it out with some math (`numpy`) so it’s not jerky.
- **Auth**: JWT tokens (via `pyjwt`) keep it secure. You get a token from `/auth`, and it’s checked for every move or click.
- **Fixes**:
  - Clamped mouse coords to avoid `(0, 0)` triggering PyAutoGUI’s fail-safe.
  - Added `timedelta` for rate limiting (`quart-rate-limiter`) to fix an old bug.

### Client (JavaScript/HTML)
- **Interface**: A simple HTML page with a touchpad div and status bar.
- **Touch Handling**: Listens for `touchstart`, `touchmove`, and `touchend` to track your fingers.
- **WebSocket**: Talks to the server real-time for smooth moves. Falls back to HTTP if it’s down.
- **Gestures**: Detects taps, swipes, and pinches by tracking finger positions and timing.

### How It Talks
- Client sends stuff like `{x: 500, y: 500}` to `/move` or `{button: "right"}` to `/click`.
- Server scales it to your screen size (default phone res is 1080x2340) and moves the mouse.

---

Tips
----
- **Debug Mode**: Add `?debug` to the URL (e.g., `http://192.168.1.166:2375/?debug`) to see what’s happening on the phone.
- **Custom IP**: If the default IP doesn’t work, add `?server=your.ip.here:2375` to the URL.
- **Keep It Running**: Don’t close the terminal, or the server stops.

---

That’s it, aban! Let me know if it’s not working, and I’ll fix it up for you. Have fun controlling your PC from the couch!