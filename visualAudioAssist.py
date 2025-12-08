import cv2
import numpy as np
import time
import json
import platform
import sys
import glob
import os
from pathlib import Path
from pygame import mixer

mixer.init()

def get_resource_path(relative_path):
    try:
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(__file__).parent
    return base_path / relative_path

def get_exe_directory():
    if hasattr(sys, '_MEIPASS'):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent

ENABLE_HEALTH_MONITORING = True
ENABLE_TRAINING_MENU = True

MEDIA_FOLDER = get_resource_path("media")
TRAINING_MENU_CONFIG_PATH = get_resource_path("training_menu_config.json")

CHECK_INTERVAL = 1
COOLDOWN_PERIOD = 15
CONTROL_SIMILARITY_THRESHOLD = 0.98
MIN_RANK_THRESHOLD = 0.90
MIN_DIVISION_THRESHOLD = 0.83
MIN_MR_THRESHOLD = 0.95
MATCH_CHECK_INTERVAL = 2
HEALTH_CHECK_INTERVAL = 0.3
HEALTH_CONFIRMATION_CHECKS = 3
HEALTH_CONFIRMATION_DELAY = 0.1
MENU_CONFIRMATION_CHECKS = 2
MENU_CONFIRMATION_DELAY = 0.2

CONTROL_REGIONS = [
    {"top": 834, "left": 56, "width": 35, "height": 31, "side": "left"},
    {"top": 834, "left": 1830, "width": 35, "height": 31, "side": "right"}
]

RANK_REGIONS = [
    {"top": 928, "left": 65, "width": 108, "height": 44, "side": "left"},
    {"top": 928, "left": 1740, "width": 108, "height": 44, "side": "right"}
]

NAME_REGIONS = [
    {"top": 912, "left": 334, "width": 82, "height": 26, "side": "left"},
    {"top": 912, "left": 1354, "width": 82, "height": 26, "side": "right"}
]

DIVISION_REGIONS = [
    {"top": 978, "left": 82, "width": 76, "height": 14, "side": "left"},
    {"top": 978, "left": 1757, "width": 76, "height": 14, "side": "right"}
]

HEALTH_REGIONS = [
    {"top": 73, "left": 820, "width": 24, "height": 15, "side": "left"},
    {"top": 73, "left": 1076, "width": 24, "height": 15, "side": "right"}
]

MR_REGIONS = [
    {"top": 993, "left": 38, "width": 14, "height": 23, "side": "left"},
    {"top": 993, "left": 1713, "width": 14, "height": 23, "side": "right"}
]

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

_capture_method = None
_grim_path = None

RANKS = [
    "NewChallenger", "Rookie", "Iron", "Bronze", "Silver", "Gold", 
    "Platinum", "Diamond", "Master", "HighMaster", 
    "GrandMaster", "UltimateMaster", "Legend"
]

RANKS_WITH_DIVISIONS = ["Rookie", "Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond"]
DIVISIONS = ["One", "Two", "Three", "Four", "Five"]
MR_VALUES = ["1000", "1100", "1200", "1300", "1400", "1500"]
CONTROLS = ["Classic", "Modern"]

health_monitoring_active = False
health_alert_states = {"left": {"alert_played": False}, "right": {"alert_played": False}}
last_health_check_time = 0
last_match_check_time = 0
match_end_check_pending = False
match_end_check_time = 0
MATCH_END_CONFIRMATION_DELAY = 5

training_menu_config = None
training_menu_reference_img = None
training_submenu_reference_img = None

def load_training_menu_config():
    global training_menu_config
    if not TRAINING_MENU_CONFIG_PATH.exists():
        return False
    try:
        with open(TRAINING_MENU_CONFIG_PATH, 'r') as f:
            training_menu_config = json.load(f)
        return True
    except Exception as e:
        print(f"Error loading training menu config: {e}")
        return False

def load_image(image_name):
    image_path = MEDIA_FOLDER / image_name
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Failed to load image: {image_path}")
    if len(img.shape) == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img

def load_image_from_path(image_path):
    if not image_path.exists():
        return None
    img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if len(img.shape) == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img

def load_player_name_images():
    exe_dir = get_exe_directory()
    left_path = exe_dir / "MyNameLeft.png"
    right_path = exe_dir / "MyNameRight.png"
    left_img = load_image_from_path(left_path) if left_path.exists() else None
    right_img = load_image_from_path(right_path) if right_path.exists() else None
    return left_img, right_img

def save_player_name_image(img, side):
    exe_dir = get_exe_directory()
    filename = f"MyName{side.capitalize()}.png"
    player_name_path = exe_dir / filename
    try:
        cv2.imwrite(str(player_name_path), img)
        print(f"Player name image saved to: {player_name_path}")
        return True
    except Exception as e:
        print(f"Error saving player name image: {e}")
        return False

def play_audio(audio_file, subfolder=None, allow_interrupt=False):
    if subfolder:
        audio_path = MEDIA_FOLDER / subfolder / audio_file
    else:
        audio_path = MEDIA_FOLDER / audio_file
    
    if not audio_path.exists():
        print(f"Audio file not found: {audio_file}")
        return
    try:
        if allow_interrupt and mixer.music.get_busy():
            mixer.music.stop()
        
        mixer.music.load(str(audio_path))
        mixer.music.play()
        
        if not allow_interrupt:
            while mixer.music.get_busy():
                time.sleep(0.05)
    except Exception as e:
        print(f"Error playing audio {audio_file}: {e}")

def play_health_alert(side):
    audio_path = MEDIA_FOLDER / "CA_health.ogg"
    if not audio_path.exists():
        print(f"Audio file not found: CA_health.ogg")
        return
    try:
        sound = mixer.Sound(str(audio_path))
        channel = sound.play()
        if side == "left":
            channel.set_volume(1.0, 0.0)
        else:
            channel.set_volume(0.0, 1.0)
        while channel.get_busy():
            time.sleep(0.05)
    except Exception as e:
        print(f"Error playing health alert: {e}")

def capture_region_windows(region):
    import mss
    with mss.mss() as sct:
        screenshot = sct.grab(region)
        img = np.array(screenshot)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img

def capture_region_linux(region):
    global _capture_method, _grim_path
    import subprocess
    left = region["left"]
    top = region["top"]
    width = region["width"]
    height = region["height"]
    
    if _capture_method == 'mss':
        import mss
        with mss.mss() as sct:
            screenshot = sct.grab(region)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img
    
    if _capture_method == 'grim' and _grim_path:
        geometry = f"{left},{top} {width}x{height}"
        result = subprocess.run([_grim_path, '-g', geometry, '-'], capture_output=True, check=True, timeout=2)
        img_array = np.frombuffer(result.stdout, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return img
    
    try:
        import mss
        with mss.mss() as sct:
            screenshot = sct.grab(region)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        _capture_method = 'mss'
        return img
    except Exception:
        pass
    
    grim_paths = ['/run/current-system/sw/bin/grim']
    user_home = os.path.expanduser('~')
    grim_paths.append(f'{user_home}/.nix-profile/bin/grim')
    user_profiles = glob.glob('/home/*/.nix-profile/bin/grim')
    grim_paths.extend(user_profiles)
    
    try:
        which_result = subprocess.run(['which', 'grim'], capture_output=True, text=True)
        if which_result.returncode == 0:
            grim_paths.insert(0, which_result.stdout.strip())
    except:
        pass
    
    grim_paths.append('grim')
    geometry = f"{left},{top} {width}x{height}"
    for grim_path in grim_paths:
        try:
            result = subprocess.run([grim_path, '-g', geometry, '-'], capture_output=True, check=True, timeout=2)
            img_array = np.frombuffer(result.stdout, dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            _capture_method = 'grim'
            _grim_path = grim_path
            return img
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    
    raise RuntimeError("Could not capture screen. mss failed and grim not found.")

def capture_region(region):
    if IS_WINDOWS:
        return capture_region_windows(region)
    elif IS_LINUX:
        return capture_region_linux(region)
    else:
        raise NotImplementedError(f"Unsupported OS: {platform.system()}")

def compare_images(img1, img2):
    if img1.shape != img2.shape:
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    _, gray1 = cv2.threshold(gray1, 150, 255, cv2.THRESH_BINARY)
    _, gray2 = cv2.threshold(gray2, 150, 255, cv2.THRESH_BINARY)
    mse = np.mean((gray1.astype(float) - gray2.astype(float)) ** 2)
    max_mse = 255 ** 2
    similarity = 1 - (mse / max_mse)
    return similarity

def compare_images_no_threshold(img1, img2):
    if img1.shape != img2.shape:
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    mse = np.mean((gray1.astype(float) - gray2.astype(float)) ** 2)
    max_mse = 255 ** 2
    similarity = 1 - (mse / max_mse)
    return similarity

def compare_images_grayscale(img1, img2, threshold=0.90):
    if img1.shape != img2.shape:
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    mse = np.mean((gray1.astype(float) - gray2.astype(float)) ** 2)
    max_mse = 255 ** 2
    similarity = 1 - (mse / max_mse)
    return similarity >= threshold, similarity

def apply_binary_threshold(img, threshold=230):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    return binary

def check_for_white_pixels(img, threshold=200):
    return np.any(img > threshold)

def check_health_color(img):
    h, w = img.shape[:2]
    center = img[h//2-3:h//2+4, w//2-3:w//2+4]
    total_pixels = center.shape[0] * center.shape[1]
    
    red_mask = ((center[:,:,2] >= 215) & (center[:,:,2] <= 220) & (center[:,:,1] >= 26) & (center[:,:,1] <= 30) & (center[:,:,0] >= 93) & (center[:,:,0] <= 97))
    red_matches = np.sum(red_mask)
    yellow_mask = ((center[:,:,2] >= 250) & (center[:,:,2] <= 253) & (center[:,:,1] >= 246) & (center[:,:,1] <= 250) & (center[:,:,0] >= 105) & (center[:,:,0] <= 110))
    yellow_matches = np.sum(yellow_mask)
    blue_mask = ((center[:,:,2] >= 12) & (center[:,:,2] <= 15) & (center[:,:,1] >= 105) & (center[:,:,1] <= 110) & (center[:,:,0] >= 184) & (center[:,:,0] <= 188))
    blue_matches = np.sum(blue_mask)
    threshold = total_pixels * 0.8
    
    if red_matches >= threshold:
        return 'red'
    elif yellow_matches >= threshold:
        return 'yellow'
    elif blue_matches >= threshold:
        return 'blue'
    return None

def check_match_started():
    try:
        p1_region = HEALTH_REGIONS[0]
        health_img = capture_region(p1_region)
        color = check_health_color(health_img)
        if color == 'red':
            return True
    except Exception as e:
        print(f"Error checking match start: {e}")
    return False

def check_health_bars():
    global health_alert_states, match_end_check_pending, match_end_check_time
    left_health_present = False
    right_health_present = False
    
    for region in HEALTH_REGIONS:
        side = region["side"]
        try:
            health_img = capture_region(region)
            color = check_health_color(health_img)
            
            if side == "left":
                if color in ['red', 'yellow']:
                    left_health_present = True
                if color in ['blue', 'yellow']:
                    right_health_present = True
            
            if color == 'yellow':
                confirmed = True
                for i in range(HEALTH_CONFIRMATION_CHECKS - 1):
                    time.sleep(HEALTH_CONFIRMATION_DELAY)
                    health_img_confirm = capture_region(region)
                    color_confirm = check_health_color(health_img_confirm)
                    if color_confirm != 'yellow':
                        confirmed = False
                        print(f"False positive filtered on {side.upper()} side (confirmation {i+1} failed: {color_confirm})")
                        break
                
                if confirmed and not health_alert_states[side]["alert_played"]:
                    print(f"\nCritical health CONFIRMED on {side.upper()} side!")
                    play_health_alert(side)
                    health_alert_states[side]["alert_played"] = True
            else:
                base_color = 'red' if side == 'left' else 'blue'
                if color == base_color:
                    if health_alert_states[side]["alert_played"]:
                        print(f"Health reset detected on {side.upper()} side - ready for next alert")
                        health_alert_states[side]["alert_played"] = False
        except Exception as e:
            print(f"Error checking {side} health bar: {e}")
    
    if left_health_present or right_health_present:
        if match_end_check_pending:
            print("Health bars detected again - match still active")
            match_end_check_pending = False
        return False
    
    if not match_end_check_pending:
        match_end_check_pending = True
        match_end_check_time = time.time()
        print("Health bars not detected - confirming match end over 5 seconds...")
    elif time.time() - match_end_check_time >= MATCH_END_CONFIRMATION_DELAY:
        print("\nMatch ended - Health monitoring deactivated\n")
        return True
    return False

def name_capture_wizard(control_images):
    print("\n" + "="*60)
    print("PLAYER NAME CAPTURE WIZARD")
    print("="*60)
    print("\nNo player name images detected. Running image capture wizard.")
    play_audio("wizard_start.ogg")
    
    print("\nThis wizard will capture your player name from both sides")
    print("of the screen for accurate opponent detection.")
    play_audio("wizard_instructions.ogg")
    
    print("\n" + "-"*60)
    print("STEP 1: LEFT SIDE CAPTURE")
    print("-"*60)
    print("Open a replay where you start on the LEFT side of the screen.")
    print("Your name will be registered from the VS screen.\n")
    play_audio("wizard_left_step.ogg")
    
    left_captured = False
    while not left_captured:
        try:
            left_region = CONTROL_REGIONS[0]
            screen_img = capture_region(left_region)
            for control_name, control_img in control_images.items():
                similarity = compare_images_no_threshold(screen_img, control_img)
                if similarity >= CONTROL_SIMILARITY_THRESHOLD:
                    print("VS screen detected!")
                    print("Waiting 1 second to avoid screen blink...")
                    time.sleep(1)
                    screen_img = capture_region(left_region)
                    similarity = compare_images(screen_img, control_img)
                    if similarity >= CONTROL_SIMILARITY_THRESHOLD:
                        print("VS screen still present. Capturing player name from left side...")
                        name_region = NAME_REGIONS[0]
                        name_img = capture_region(name_region)
                        if save_player_name_image(name_img, "left"):
                            print("Left side name captured successfully!\n")
                            play_audio("wizard_left_success.ogg")
                            left_captured = True
                            break
                        else:
                            print("Failed to save left side image.\n")
                            play_audio("wizard_error.ogg")
                            return False
                    else:
                        print("VS screen disappeared, retrying...\n")
        except Exception as e:
            print(f"Error during left side capture: {e}")
            play_audio("wizard_error.ogg")
            return False
        if not left_captured:
            time.sleep(1)
    
    print("\n" + "-"*60)
    print("STEP 2: RIGHT SIDE CAPTURE")
    print("-"*60)
    print("Now open a replay where you start on the RIGHT side of the screen.\n")
    play_audio("wizard_right_step.ogg")
    
    right_captured = False
    while not right_captured:
        try:
            right_region = CONTROL_REGIONS[1]
            screen_img = capture_region(right_region)
            for control_name, control_img in control_images.items():
                similarity = compare_images_no_threshold(screen_img, control_img)
                if similarity >= CONTROL_SIMILARITY_THRESHOLD:
                    print("VS screen detected!")
                    print("Waiting 1 second to avoid screen blink...")
                    time.sleep(1)
                    screen_img = capture_region(right_region)
                    similarity = compare_images_no_threshold(screen_img, control_img)
                    if similarity >= CONTROL_SIMILARITY_THRESHOLD:
                        print("VS screen still present. Capturing player name from right side...")
                        name_region = NAME_REGIONS[1]
                        name_img = capture_region(name_region)
                        if save_player_name_image(name_img, "right"):
                            print("Right side name captured successfully!\n")
                            play_audio("wizard_right_success.ogg")
                            print("="*60)
                            print("SETUP COMPLETE")
                            print("="*60)
                            play_audio("wizard_complete.ogg")
                            return True
                        else:
                            print("Failed to save right side image.\n")
                            play_audio("wizard_error.ogg")
                            return False
                    else:
                        print("VS screen disappeared, retrying...\n")
        except Exception as e:
            print(f"Error during right side capture: {e}")
            play_audio("wizard_error.ogg")
            return False
        if not right_captured:
            time.sleep(1)

def find_best_rank_match(captured_img, rank_images):
    best_match = None
    best_similarity = 0
    for rank_name, rank_img in rank_images.items():
        similarity = compare_images(captured_img, rank_img)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = rank_name
    if best_similarity < MIN_RANK_THRESHOLD:
        return "Unknown", best_similarity
    return best_match, best_similarity

def find_best_division_match(captured_img, division_images):
    best_match = None
    best_similarity = 0
    for division_name, division_img in division_images.items():
        similarity = compare_images_no_threshold(captured_img, division_img)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = division_name
    if best_similarity < MIN_DIVISION_THRESHOLD:
        return None, best_similarity
    return best_match, best_similarity

def find_best_mr_match(captured_img, mr_images):
    best_match = None
    best_similarity = 0
    for mr_value, mr_img in mr_images.items():
        similarity = compare_images(captured_img, mr_img)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = mr_value
    if best_similarity < MIN_MR_THRESHOLD:
        return None, best_similarity
    return best_match, best_similarity

def play_audio_sequence(audio_files):
    for audio_file in audio_files:
        audio_path = MEDIA_FOLDER / audio_file
        if not audio_path.exists():
            print(f"Audio file not found: {audio_file}")
            continue
        try:
            mixer.music.load(str(audio_path))
            mixer.music.play()
            while mixer.music.get_busy():
                time.sleep(0.1)
        except Exception as e:
            print(f"Error playing audio {audio_file}: {e}")

def check_if_in_submenu(config, submenu_reference_img):
    indicator_region = {"top": 35, "left": 877, "width": 13, "height": 14}
    img = capture_region(indicator_region)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)
    has_white = check_for_white_pixels(binary, 7)
    if has_white:
        return False
    submenu_region = config["submenu_detection"]["tab_region"]
    submenu_screen = capture_region(submenu_region)
    is_similar, similarity = compare_images_grayscale(submenu_screen, submenu_reference_img, config["detection_settings"]["submenu_match_threshold"])
    return is_similar

def get_tab_name_by_number(tab_number, config, is_submenu=False):
    tabs_dict = config["submenu_tabs"] if is_submenu else config["tabs"]
    for tab_name, tab_data in tabs_dict.items():
        if tab_data["tab_number"] == tab_number:
            return tab_name
    return None

def detect_active_tab(config, is_submenu=False):
    if is_submenu:
        tab_region = config["submenu_detection"]["tab_region"]
        num_tabs = config["submenu_detection"]["num_tabs"]
    else:
        tab_region = config["tab_detection"]["region"]
        num_tabs = config["tab_detection"]["num_tabs"]
    img = capture_region(tab_region)
    binary = apply_binary_threshold(img, config["detection_settings"]["binary_threshold"])
    width = tab_region["width"]
    segment_width = width / num_tabs
    for i in range(num_tabs):
        x_start = int(i * segment_width + segment_width * 0.3)
        x_end = int(i * segment_width + segment_width * 0.7)
        segment = binary[:, x_start:x_end]
        if check_for_white_pixels(segment, config["detection_settings"]["white_pixel_threshold"]):
            tab_number = i + 1
            return tab_number, get_tab_name_by_number(tab_number, config, is_submenu)
    return None, None

def detect_active_sub_tab(tab_name, config):
    if tab_name not in config["tabs"]:
        return None
    tab_config = config["tabs"][tab_name]
    if not tab_config.get("has_sub_tabs", False):
        return None
    if "sub_tab_detection" not in tab_config:
        return None
    sub_tab_positions = tab_config["sub_tab_detection"]["positions"]
    for sub_tab_info in sub_tab_positions:
        region = {"left": sub_tab_info["left"], "top": sub_tab_info["top"], "width": sub_tab_info["width"], "height": sub_tab_info["height"]}
        img = capture_region(region)
        binary = apply_binary_threshold(img, config["detection_settings"]["binary_threshold"])
        if check_for_white_pixels(binary, config["detection_settings"]["white_pixel_threshold"]):
            return sub_tab_info["name"]
    return None

def get_item_region(item_y, config, tab_name=None, item_name=None, is_submenu=False):
    check_config = config["item_detection"]["check_region"]
    if is_submenu and tab_name == "Record":
        return {"top": item_y, "left": 738, "width": check_config["width"], "height": check_config["height"]}
    if (tab_name == "Environment Settings" and item_name in ["P1 Character Select", "P2 Character Select"]):
        return {"top": item_y, "left": 449, "width": check_config["width"], "height": check_config["height"]}
    return {"top": item_y, "left": check_config["left"], "width": check_config["width"], "height": check_config["height"]}

def detect_selected_item(tab_name, sub_tab_name, config, is_submenu=False):
    tabs_dict = config["submenu_tabs"] if is_submenu else config["tabs"]
    if tab_name not in tabs_dict:
        return None, None
    tab_config = tabs_dict[tab_name]
    if not is_submenu and tab_config.get("has_sub_tabs", False):
        if not sub_tab_name:
            return None, None
        if "sub_tabs" not in tab_config or sub_tab_name not in tab_config["sub_tabs"]:
            return None, None
        items = tab_config["sub_tabs"][sub_tab_name]
    else:
        if "items" not in tab_config:
            return None, None
        items = tab_config["items"]
    if not items:
        return None, None
    start_position = tab_config["start_position"]
    item_positions = config["item_detection"]["positions"]
    for idx, item_name in enumerate(items):
        if item_name is None:
            continue
        position_idx = start_position + idx - 1
        if position_idx >= len(item_positions):
            break
        item_y = item_positions[position_idx]
        region = get_item_region(item_y, config, tab_name, item_name, is_submenu)
        img = capture_region(region)
        binary = apply_binary_threshold(img, config["detection_settings"]["binary_threshold"])
        if check_for_white_pixels(binary, config["detection_settings"]["white_pixel_threshold"]):
            return item_name, position_idx
    return None, None

def item_name_to_audio_file(item_name, config):
    audio_name = item_name.lower().replace(" ", "_").replace("-", "_")
    audio_config = config["audio"]
    return f"{audio_name}{audio_config['extension']}"

def tab_name_to_audio_file(tab_name, config):
    audio_name = tab_name.lower().replace(" ", "_").replace("-", "_")
    audio_config = config["audio"]
    return f"{audio_name}{audio_config['extension']}"

def check_item_still_selected(item_position_idx, tab_name, item_name, config, is_submenu=False):
    item_positions = config["item_detection"]["positions"]
    if item_position_idx >= len(item_positions):
        return False
    item_y = item_positions[item_position_idx]
    region = get_item_region(item_y, config, tab_name, item_name, is_submenu)
    img = capture_region(region)
    binary = apply_binary_threshold(img, config["detection_settings"]["binary_threshold"])
    return check_for_white_pixels(binary, config["detection_settings"]["white_pixel_threshold"])

def main():
    global health_monitoring_active, last_health_check_time, last_match_check_time, match_end_check_pending
    global training_menu_reference_img, training_submenu_reference_img
    
    print("\n" + "="*60)
    print("VISUAL AUDIO ASSIST - Street Fighter 6")
    print("="*60 + "\n")
    
    print("Loading control images...")
    control_images = {}
    try:
        for control in CONTROLS:
            control_images[control] = load_image(f"{control}.png")
        print(f"Loaded {len(control_images)} control images\n")
    except Exception as e:
        print(f"Error loading control images: {e}")
        return
    
    player_name_left, player_name_right = load_player_name_images()
    
    if player_name_left is None or player_name_right is None:
        if not name_capture_wizard(control_images):
            print("Setup failed. Exiting.")
            return
        player_name_left, player_name_right = load_player_name_images()
    else:
        print("Player name images found: MyNameLeft.png, MyNameRight.png")
    
    print("\nLoading rank images...")
    rank_images = {}
    try:
        for rank in RANKS:
            rank_images[rank] = load_image(f"{rank}.png")
        print(f"Loaded {len(rank_images)} rank images\n")
    except Exception as e:
        print(f"Error loading rank images: {e}")
        return
    
    print("Loading division images...")
    division_images = {}
    try:
        for division in DIVISIONS:
            division_images[division] = load_image(f"{division.lower()}.png")
        print(f"Loaded {len(division_images)} division images\n")
    except Exception as e:
        print(f"Error loading division images: {e}")
        return
    
    print("Loading MR images...")
    mr_images = {}
    try:
        for mr_value in MR_VALUES:
            mr_images[mr_value] = load_image(f"{mr_value}.png")
        print(f"Loaded {len(mr_images)} MR images\n")
    except Exception as e:
        print(f"Error loading MR images: {e}")
        return
    
    training_menu_enabled = False
    if ENABLE_TRAINING_MENU:
        if load_training_menu_config():
            try:
                training_menu_reference_img = load_image(training_menu_config["tab_detection"]["reference_image"])
                training_submenu_reference_img = load_image(training_menu_config["submenu_detection"]["reference_image"])
                training_menu_enabled = True
                print("Training menu monitoring enabled\n")
            except Exception as e:
                print(f"Error loading training menu images: {e}")
                print("Training menu monitoring disabled\n")
    
    print(f"Monitoring on {platform.system()}...")
    print(f"Check interval: {CHECK_INTERVAL} seconds")
    print(f"Audio cooldown: {COOLDOWN_PERIOD} seconds")
    if ENABLE_HEALTH_MONITORING:
        print(f"Health monitoring: Enabled")
    if training_menu_enabled:
        print(f"Training menu: Enabled")
    print("Press Ctrl+C to stop\n")
    
    last_audio_time = 0
    current_mode = "idle"
    
    menu_last_selected_item = None
    menu_last_item_position = None
    menu_last_active_tab = None
    menu_last_active_sub_tab = None
    menu_was_open = False
    menu_initial_check_done = False
    menu_sub_tab_announced = False
    menu_in_submenu = False
    
    try:
        while True:
            current_time = time.time()
            
            if current_mode == "vs_screen" or current_mode == "idle":
                if ENABLE_HEALTH_MONITORING:
                    if not health_monitoring_active:
                        if current_time - last_match_check_time >= MATCH_CHECK_INTERVAL:
                            if check_match_started():
                                print("\n" + "="*60)
                                print("MATCH STARTED - Health monitoring activated")
                                print("="*60 + "\n")
                                health_monitoring_active = True
                                last_health_check_time = current_time
                                current_mode = "vs_screen"
                            last_match_check_time = current_time
                    else:
                        if current_time - last_health_check_time >= HEALTH_CHECK_INTERVAL:
                            match_ended = check_health_bars()
                            if match_ended:
                                health_monitoring_active = False
                                health_alert_states["left"]["alert_played"] = False
                                health_alert_states["right"]["alert_played"] = False
                                match_end_check_pending = False
                                current_mode = "idle"
                            last_health_check_time = current_time
            
            if current_mode == "vs_screen" or current_mode == "idle":
                left_region = CONTROL_REGIONS[0]
                right_region = CONTROL_REGIONS[1]
                left_control = None
                left_similarity = 0
                
                try:
                    screen_img = capture_region(left_region)
                    for control_name, control_img in control_images.items():
                        similarity = compare_images_no_threshold(screen_img, control_img)
                        if similarity >= CONTROL_SIMILARITY_THRESHOLD:
                            left_control = control_name
                            left_similarity = similarity
                            break
                except Exception as e:
                    print(f"Error checking left control region: {e}")
                
                if left_control:
                    current_mode = "vs_screen"
                    right_control = None
                    right_similarity = 0
                    
                    try:
                        screen_img = capture_region(right_region)
                        for control_name, control_img in control_images.items():
                            similarity = compare_images(screen_img, control_img)
                            if similarity >= CONTROL_SIMILARITY_THRESHOLD:
                                right_control = control_name
                                right_similarity = similarity
                                break
                    except Exception as e:
                        print(f"Error checking right control region: {e}")
                    
                    print(f"\n{'='*60}")
                    print(f"VS SCREEN DETECTED")
                    print(f"  Left: {left_control} ({left_similarity * 100:.1f}%)")
                    if right_control:
                        print(f"  Right: {right_control} ({right_similarity * 100:.1f}%)")
                    else:
                        print(f"  Right: No match detected")
                    print(f"{'='*60}")
                    print("Ctrl+C to stop")
                    
                    if current_time - last_audio_time >= COOLDOWN_PERIOD:
                        try:
                            print("Waiting 1 second to avoid screen blink...")
                            time.sleep(1)
                            
                            try:
                                left_screen_img = capture_region(left_region)
                                left_still_present = False
                                for control_name, control_img in control_images.items():
                                    similarity = compare_images_no_threshold(left_screen_img, control_img)
                                    if similarity >= CONTROL_SIMILARITY_THRESHOLD:
                                        left_still_present = True
                                        break
                                
                                if not left_still_present:
                                    print("VS screen disappeared during wait, skipping...")
                                    print(f"{'='*60}\n")
                                    time.sleep(CHECK_INTERVAL)
                                    continue
                            except Exception as e:
                                print(f"Error re-verifying left control region: {e}")
                                time.sleep(CHECK_INTERVAL)
                                continue
                            
                            opponent_side = None
                            opponent_control = None
                            
                            print("\nUsing name detection...")
                            try:
                                left_name_img = capture_region(NAME_REGIONS[0])
                                right_name_img = capture_region(NAME_REGIONS[1])
                                
                                left_vs_left = compare_images_no_threshold(player_name_left, left_name_img)
                                left_vs_right = compare_images_no_threshold(player_name_left, right_name_img)
                                right_vs_left = compare_images_no_threshold(player_name_right, left_name_img)
                                right_vs_right = compare_images_no_threshold(player_name_right, right_name_img)
                                
                                left_side_max = max(left_vs_left, right_vs_left)
                                right_side_max = max(left_vs_right, right_vs_right)
                                
                                print(f"Name similarity - Left side: {left_side_max * 100:.1f}% | Right side: {right_side_max * 100:.1f}%")
                                
                                if left_side_max > right_side_max:
                                    opponent_side = "right"
                                    opponent_control = right_control if right_control else left_control
                                    print(f"Player detected on LEFT, opponent on RIGHT")
                                else:
                                    opponent_side = "left"
                                    opponent_control = left_control
                                    print(f"Player detected on RIGHT, opponent on LEFT")
                            except Exception as e:
                                print(f"Error in name detection: {e}")
                                continue
                            
                            print("\nCapturing opponent rank region...")
                            opponent_rank_region = RANK_REGIONS[0] if opponent_side == "left" else RANK_REGIONS[1]
                            
                            try:
                                opponent_rank_img = capture_region(opponent_rank_region)
                                opponent_rank, opponent_sim = find_best_rank_match(opponent_rank_img, rank_images)
                                print(f"Opponent rank: {opponent_rank} ({opponent_sim * 100:.1f}%)")
                                
                                division = None
                                mr_value = None
                                
                                if opponent_rank == "Master":
                                    print(f"\nMaster rank detected, checking MR region...")
                                    try:
                                        mr_region = MR_REGIONS[0] if opponent_side == "left" else MR_REGIONS[1]
                                        mr_img = capture_region(mr_region)
                                        mr_value, mr_sim = find_best_mr_match(mr_img, mr_images)
                                        if mr_value:
                                            print(f"MR detected: {mr_value} ({mr_sim * 100:.1f}%)")
                                        else:
                                            print(f"No MR match found (best: {mr_sim * 100:.1f}%), using base Master")
                                    except Exception as e:
                                        print(f"Error capturing MR: {e}, using base Master")
                                elif opponent_rank in RANKS_WITH_DIVISIONS and opponent_rank != "Unknown":
                                    print(f"\nRank requires division check, capturing division region...")
                                    try:
                                        division_region = DIVISION_REGIONS[0] if opponent_side == "left" else DIVISION_REGIONS[1]
                                        division_img = capture_region(division_region)
                                        division, div_sim = find_best_division_match(division_img, division_images)
                                        if division:
                                            print(f"Division detected: {division} ({div_sim * 100:.1f}%)")
                                        else:
                                            print(f"No division match found (best: {div_sim * 100:.1f}%), using base rank")
                                    except Exception as e:
                                        print(f"Error capturing division: {e}, using base rank")
                                
                                if opponent_control:
                                    if opponent_rank == "Unknown":
                                        audio_files = [f"{opponent_control}.ogg", "Unknown.ogg"]
                                        print(f"\nRank unknown, playing control + Unknown")
                                    elif opponent_rank == "Master" and mr_value:
                                        audio_files = [f"{opponent_control}.ogg", f"{mr_value}.ogg"]
                                    elif opponent_rank in RANKS_WITH_DIVISIONS and division:
                                        audio_files = [f"{opponent_control}.ogg", f"{opponent_rank}{division}.ogg"]
                                    else:
                                        audio_files = [f"{opponent_control}.ogg", f"{opponent_rank}.ogg"]
                                    
                                    print(f"\nPlaying audio sequence: {' -> '.join(audio_files)}")
                                    play_audio_sequence(audio_files)
                                    last_audio_time = current_time
                                    
                                    if ENABLE_HEALTH_MONITORING:
                                        health_monitoring_active = False
                                        health_alert_states["left"]["alert_played"] = False
                                        health_alert_states["right"]["alert_played"] = False
                                        print("Health monitoring reset for next match")
                                    print(f"{'='*60}\n")
                                else:
                                    print(f"\nSkipping audio - opponent control not detected")
                                    print(f"{'='*60}\n")
                            except Exception as e:
                                print(f"Error capturing opponent rank: {e}")
                                print(f"{'='*60}\n")
                        except Exception as e:
                            print(f"Error processing ranks: {e}")
                            print(f"{'='*60}\n")
                    else:
                        remaining = int(COOLDOWN_PERIOD - (current_time - last_audio_time))
                        print(f"Cooldown active ({remaining}s remaining)")
                        print(f"{'='*60}\n")
                elif current_mode == "vs_screen":
                    current_mode = "idle"
            
            if training_menu_enabled and (current_mode == "training_menu" or current_mode == "idle"):
                if not menu_initial_check_done:
                    tab_region = training_menu_config["tab_detection"]["region"]
                    screen_img = capture_region(tab_region)
                    menu_open, similarity = compare_images_grayscale(screen_img, training_menu_reference_img, training_menu_config["detection_settings"]["menu_match_threshold"])
                    
                    if menu_open:
                        confirmed = True
                        for i in range(MENU_CONFIRMATION_CHECKS - 1):
                            time.sleep(MENU_CONFIRMATION_DELAY)
                            screen_img_confirm = capture_region(tab_region)
                            menu_still_open, similarity_confirm = compare_images_grayscale(screen_img_confirm, training_menu_reference_img, training_menu_config["detection_settings"]["menu_match_threshold"])
                            if not menu_still_open:
                                confirmed = False
                                print(f"False positive filtered - menu closed during confirmation check {i+1}")
                                break
                        
                        if confirmed:
                            print(f"\n{'='*60}")
                            print(f"TRAINING MENU DETECTED (similarity: {similarity*100:.1f}%)")
                            print(f"{'='*60}\n")
                            menu_initial_check_done = True
                            menu_was_open = True
                            current_mode = "training_menu"
                else:
                    should_check_submenu = (menu_last_active_tab == "Reversal Settings" or menu_in_submenu)
                    
                    if should_check_submenu:
                        was_in_submenu = menu_in_submenu
                        menu_in_submenu = check_if_in_submenu(training_menu_config, training_submenu_reference_img)
                        
                        if menu_in_submenu != was_in_submenu:
                            if menu_in_submenu:
                                print(f"\n{'─'*60}")
                                print("SUBMENU OPENED")
                                print(f"{'─'*60}\n")
                                menu_last_selected_item = None
                                menu_last_item_position = None
                                menu_last_active_tab = None
                                menu_last_active_sub_tab = None
                            else:
                                print(f"\n{'─'*60}")
                                print("RETURNED TO MAIN MENU")
                                print(f"{'─'*60}\n")
                                menu_last_selected_item = None
                                menu_last_item_position = None
                                menu_last_active_tab = "Reversal Settings"
                                menu_sub_tab_announced = False
                    else:
                        menu_in_submenu = False
                    
                    tab_number, tab_name = detect_active_tab(training_menu_config, is_submenu=menu_in_submenu)
                    
                    if tab_name:
                        current_mode = "training_menu"
                        if not menu_was_open:
                            print(f"\n{'='*60}")
                            print(f"TRAINING MENU RE-OPENED")
                            print(f"{'='*60}\n")
                            menu_was_open = True
                        
                        if menu_last_active_tab and menu_last_active_tab != tab_name:
                            if menu_in_submenu:
                                print(f"Submenu tab changed: {menu_last_active_tab} -> {tab_name}")
                            else:
                                print(f"Tab changed: {menu_last_active_tab} -> {tab_name}")
                            
                            audio_file = tab_name_to_audio_file(tab_name, training_menu_config)
                            print(f"Playing: {audio_file}")
                            play_audio(audio_file, "menu")
                            
                            menu_last_selected_item = None
                            menu_last_item_position = None
                            menu_last_active_sub_tab = None
                            menu_sub_tab_announced = False
                        
                        menu_last_active_tab = tab_name
                        
                        sub_tab_name = None
                        if not menu_in_submenu:
                            sub_tab_name = detect_active_sub_tab(tab_name, training_menu_config)
                            
                            if sub_tab_name and not menu_sub_tab_announced:
                                audio_file = tab_name_to_audio_file(sub_tab_name, training_menu_config)
                                print(f"Sub-tab: {sub_tab_name}")
                                print(f"Playing: {audio_file}")
                                play_audio(audio_file, "menu")
                                menu_sub_tab_announced = True
                            
                            if sub_tab_name and menu_last_active_sub_tab and menu_last_active_sub_tab != sub_tab_name:
                                print(f"Sub-tab changed: {menu_last_active_sub_tab} -> {sub_tab_name}")
                                audio_file = tab_name_to_audio_file(sub_tab_name, training_menu_config)
                                print(f"Playing: {audio_file}")
                                play_audio(audio_file, "menu")
                                menu_last_selected_item = None
                                menu_last_item_position = None
                            
                            menu_last_active_sub_tab = sub_tab_name
                        
                        if menu_last_selected_item and menu_last_item_position is not None:
                            still_selected = check_item_still_selected(menu_last_item_position, tab_name, menu_last_selected_item, training_menu_config, menu_in_submenu)
                            if not still_selected:
                                print(f"'{menu_last_selected_item}' deselected - resuming scan\n")
                                menu_last_selected_item = None
                                menu_last_item_position = None
                        
                        if menu_last_selected_item is None:
                            selected_item, item_position = detect_selected_item(tab_name, sub_tab_name, training_menu_config, is_submenu=menu_in_submenu)
                            if selected_item:
                                if menu_in_submenu:
                                    print(f"Submenu Tab: {tab_name}")
                                elif sub_tab_name:
                                    print(f"Tab: {tab_name} > {sub_tab_name}")
                                else:
                                    print(f"Tab: {tab_name}")
                                print(f"Selected: {selected_item}")
                                
                                audio_file = item_name_to_audio_file(selected_item, training_menu_config)
                                print(f"Playing: {audio_file}")
                                play_audio(audio_file, "menu", allow_interrupt=True)
                                
                                menu_last_selected_item = selected_item
                                menu_last_item_position = item_position
                                print(f"Locked onto '{selected_item}' - waiting for deselection\n")
                    else:
                        if menu_was_open:
                            print(f"\n{'='*60}")
                            print("TRAINING MENU CLOSED")
                            print(f"{'='*60}\n")
                            menu_was_open = False
                            menu_initial_check_done = False
                            menu_last_selected_item = None
                            menu_last_item_position = None
                            menu_last_active_tab = None
                            menu_last_active_sub_tab = None
                            menu_sub_tab_announced = False
                            menu_in_submenu = False
                            current_mode = "idle"
            
            time.sleep(CHECK_INTERVAL)
    
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")

if __name__ == "__main__":
    main()
