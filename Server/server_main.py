import asyncio
import time
import os
import logging
from pathlib import Path
from functools import wraps
from typing import Tuple, Dict, Callable, Any, Optional
from datetime import timedelta

import jwt
import numpy as np
import pyautogui
from quart import Quart, request, jsonify, send_from_directory
from quart_cors import cors
from quart_rate_limiter import RateLimiter, rate_limit
import socketio

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("touchpad_server")

# Load environment variables
# SECRET_KEY = os.getenv("SECRET_KEY")
SECRET_KEY = "bc9a602817a22d8886ee8f4862fc2cd7f4c239c773f64745e9392d16a44fca56"
if not SECRET_KEY:
    logger.warning("No SECRET_KEY found in environment! Using insecure default.")
    SECRET_KEY = "DEVELOPER_SECRET_KEY"

# Initialize async server components
app = Quart(__name__, static_folder="client")
app = cors(app, allow_origin=["http://localhost:*", "http://192.168.*.*:*", "*"])
rate_limiter = RateLimiter(app)
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=[])
socket_app = socketio.ASGIApp(sio, app)


# Thread-safe calibration with dataclass for type safety
class CalibrationData:
    def __init__(self):
        self.phone_resolution = (1080, 2340)  # Default values
        self.screen_resolution = pyautogui.size()
        self._lock = asyncio.Lock()

    async def scale_coordinates(self, x: float, y: float) -> Tuple[float, float]:
        """Scale phone coordinates to computer screen coordinates"""
        async with self._lock:
            return (
                (x * self.screen_resolution[0]) / self.phone_resolution[0],
                (y * self.screen_resolution[1]) / self.phone_resolution[1],
            )


# Initialize calibration
calibration = CalibrationData()

# Token cache with TTL
_token_cache: Dict[str, float] = {}
_token_cache_lock = asyncio.Lock()


async def smooth_move(
    x: float, y: float, smoothness: float = 0.5
) -> Tuple[float, float]:
    current_x, current_y = pyautogui.position()
    smooth_factor = 1 - np.exp(-smoothness)
    target_x = current_x + (x - current_x) * smooth_factor
    target_y = current_y + (y - current_y) * smooth_factor

    screen_width, screen_height = pyautogui.size()
    target_x = max(1, min(target_x, screen_width - 1))
    target_y = max(1, min(target_y, screen_height - 1))
    logger.info(f"Moving to: ({target_x}, {target_y}) from ({current_x}, {current_y})")

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, lambda: pyautogui.moveTo(target_x, target_y, _pause=False)
    )
    return target_x, target_y


def require_auth(func: Callable) -> Callable:
    """Authorization decorator for Quart routes"""

    @wraps(func)
    async def decorated(*args: Any, **kwargs: Any) -> Any:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Invalid token format"}), 401

        token = auth_header.split(" ")[1]
        if not await validate_token(token):
            return jsonify({"error": "Unauthorized"}), 401

        return await func(*args, **kwargs)

    return decorated


async def generate_token(expiry_seconds: int = 3600) -> str:
    """Generate JWT token with configurable expiry"""
    payload = {
        "exp": int(time.time()) + expiry_seconds,
        "iat": int(time.time()),
        "jti": os.urandom(8).hex(),  # Unique token identifier
    }

    try:
        return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    except Exception as e:
        logger.error(f"Token generation error: {e}")
        raise


async def validate_token(token: str) -> bool:
    """Validate JWT token with caching and TTL"""
    global _token_cache
    async with _token_cache_lock:
        current_time = time.time()
        if token in _token_cache:
            if _token_cache[token] > current_time:
                return True
            else:
                del _token_cache[token]
                return False

        try:
            decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            _token_cache[token] = decoded["exp"]
            # Cleanup expired tokens
            if len(_token_cache) > 100:
                _token_cache = {
                    k: v for k, v in _token_cache.items() if v > current_time
                }
            return True
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return False
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return False
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return False


# Gesture action executor to run in separate thread
async def execute_gesture_action(action_func: Callable) -> None:
    """Execute PyAutoGUI actions in a thread pool"""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, action_func)


# Route handlers
@app.route("/")
async def home():
    """Serve index.html from client directory"""
    return await send_from_directory("client", "index.html")


@app.route("/auth", methods=["GET"])
@rate_limit(10, timedelta(seconds=60))
async def authenticate():
    try:
        token = await generate_token()
        return jsonify({"token": token})
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return jsonify({"error": "Authentication failed"}), 500


@app.route("/move", methods=["POST"])
@require_auth
async def handle_move():
    """Process mouse movement request"""
    data = await request.get_json()
    x, y = await calibration.scale_coordinates(data["x"], data["y"])
    target_x, target_y = await smooth_move(x, y)

    return jsonify({"status": "ok", "x": target_x, "y": target_y})


@app.route("/click", methods=["POST"])
@require_auth
async def handle_click():
    """Process mouse click request"""
    data = await request.get_json()
    button = data.get("button", "left")  # Default to left click if not specified
    loop = asyncio.get_running_loop()
    if button == "right":
        await loop.run_in_executor(None, lambda: pyautogui.click(button="right"))
    else:
        await loop.run_in_executor(None, pyautogui.click)  # Default is left click
    return jsonify({"status": "click_processed"})


@app.route("/gesture", methods=["POST"])
@require_auth
async def handle_gesture():
    """Process gesture request with improved actions"""
    data = await request.get_json()
    gesture_type = data.get("type")

    gesture_actions = {
        "three_finger_swipe_right": lambda: pyautogui.hotkey("alt", "tab"),
        "three_finger_swipe_left": lambda: pyautogui.hotkey("alt", "shift", "tab"),
        "two_finger_scroll_up": lambda: pyautogui.scroll(300),
        "two_finger_scroll_down": lambda: pyautogui.scroll(-300),
        "pinch_in": lambda: (
            pyautogui.keyDown("ctrl"),
            pyautogui.scroll(-120),
            pyautogui.keyUp("ctrl"),
        ),
        "pinch_out": lambda: (
            pyautogui.keyDown("ctrl"),
            pyautogui.scroll(120),
            pyautogui.keyUp("ctrl"),
        ),
        "double_tap": lambda: pyautogui.doubleClick(),
    }

    action = gesture_actions.get(gesture_type)
    if action:
        await execute_gesture_action(action)
        return jsonify({"status": "gesture_processed"})

    return jsonify({"error": "Unknown gesture"}), 400


# Socket.IO event handlers
@sio.event
async def connect(sid, environ):
    """Handle WebSocket connection"""
    # Extract and validate token from query params
    query = environ.get("QUERY_STRING", "")
    token = None
    for param in query.split("&"):
        if param.startswith("token="):
            token = param[6:]

    if not token or not await validate_token(token):
        await sio.disconnect(sid)
        return

    logger.info(f"Client connected: {sid}")
    await sio.emit("connection_success", {"status": "connected"}, to=sid)


@sio.event
async def disconnect(sid):
    """Handle WebSocket disconnection"""
    logger.info(f"Client disconnected: {sid}")


@sio.event
async def move(sid, data):
    """Real-time mouse movement via WebSocket"""
    x, y = await calibration.scale_coordinates(data["x"], data["y"])
    target_x, target_y = await smooth_move(x, y)
    await sio.emit("update_position", {"x": target_x, "y": target_y}, to=sid)


if __name__ == "__main__":
    import hypercorn.asyncio
    import platform

    # Set event loop policy based on platform
    if platform.system() != "Windows":
        try:
            logger.info("Using uvloop for improved performance")
        except ImportError:
            logger.info("uvloop not available, using default asyncio event loop")
    else:
        # Use optimized Windows event loop
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        logger.info("Using Windows ProactorEventLoop")

    # Server configuration
    config = hypercorn.Config()
    config.bind = ["0.0.0.0:2375"]
    config.use_reloader = True if os.getenv("ENVIRONMENT") == "development" else False

    # Start server
    logger.info("Starting touchpad server on 0.0.0.0:2375")
    asyncio.run(hypercorn.asyncio.serve(socket_app, config))
