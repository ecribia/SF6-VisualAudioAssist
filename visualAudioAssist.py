import cv2
import numpy as np
import time
import platform
import sys
import glob
import os
from pathlib import Path
from pygame import mixer
import threading

mixer.init()

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(__file__).parent
    return base_path / relative_path

def get_exe_directory():
    """ Get the directory where the executable is located """
    if hasattr(sys, '_MEIPASS'):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent

ENABLE_HEALTH_MONITORING = True

MEDIA_FOLDER = get_resource_path("media")
CHECK_INTERVAL = 1
COOLDOWN_PERIOD = 15
CONTROL_SIMILARITY_THRESHOLD = 0.98
MIN_RANK_THRESHOLD = 0.70
MIN_DIVISION_THRESHOLD = 0.70
HEALTH_SIMILARITY_THRESHOLD = 0.995
MATCH_CHECK_INTERVAL = 2
HEALTH_CHECK_INTERVAL = 0.5
HEALTH_CONFIRMATION_CHECKS = 2
HEALTH_CONFIRMATION_DELAY = 0.1

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
    {"top": 65, "left": 820, "width": 24, "height": 31, "side": "left"},
    {"top": 65, "left": 1076, "width": 24, "height": 31, "side": "right"}
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

CONTROLS = ["Classic", "Modern"]

health_monitoring_active = False
health_alert_states = {
    "left": {"alert_played": False},
    "right": {"alert_played": False}
}
last_health_check_time = 0
last_match_check_time = 0
match_end_check_pending = False
match_end_check_time = 0
MATCH_END_CONFIRMATION_DELAY = 5

def load_image(image_name):
    """Load an image from the media folder"""
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
    """Load an image from a specific path"""
    if not image_path.exists():
        return None
    img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if len(img.shape) == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img

def load_player_name_images():
    """Load player name images from exe directory if they exist"""
    exe_dir = get_exe_directory()
    left_path = exe_dir / "MyNameLeft.png"
    right_path = exe_dir / "MyNameRight.png"
    
    left_img = load_image_from_path(left_path) if left_path.exists() else None
    right_img = load_image_from_path(right_path) if right_path.exists() else None
    
    return left_img, right_img

def save_player_name_image(img, side):
    """Save player name image to exe directory"""
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

def play_audio(audio_file):
    """Play a single audio file"""
    audio_path = MEDIA_FOLDER / audio_file
    if not audio_path.exists():
        print(f"Audio file not found: {audio_file}")
        return
    try:
        mixer.music.load(str(audio_path))
        mixer.music.play()
        while mixer.music.get_busy():
            time.sleep(0.1)
    except Exception as e:
        print(f"Error playing audio {audio_file}: {e}")

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
        result = subprocess.run(
            [_grim_path, '-g', geometry, '-'],
            capture_output=True,
            check=True,
            timeout=2
        )
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
            result = subprocess.run(
                [grim_path, '-g', geometry, '-'],
                capture_output=True,
                check=True,
                timeout=2
            )
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
    """Compare two images and return similarity score"""
    if img1.shape != img2.shape:
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    mse = np.mean((gray1.astype(float) - gray2.astype(float)) ** 2)
    max_mse = 255 ** 2
    similarity = 1 - (mse / max_mse)
    return similarity

def check_match_started(health_images):
    """Check if match has started by detecting red health bar on P1 side (left)"""
    try:
        p1_region = HEALTH_REGIONS[0]
        health_img = capture_region(p1_region)
        
        similarity = compare_images(health_img, health_images["red"])
        
        if similarity >= HEALTH_SIMILARITY_THRESHOLD:
            return True
    except Exception as e:
        print(f"Error checking match start: {e}")
    
    return False

def check_health_bars(health_images):
    """Check both health bars for yellow (critical health) with confirmation"""
    global health_alert_states, match_end_check_pending, match_end_check_time
    
    left_health_present = False
    right_health_present = False
    
    for region in HEALTH_REGIONS:
        side = region["side"]
        
        try:
            health_img = capture_region(region)
            
            yellow_similarity = compare_images(health_img, health_images["yellow"])
            
            if side == "left":
                red_similarity = compare_images(health_img, health_images["red"])
                if yellow_similarity >= HEALTH_SIMILARITY_THRESHOLD or red_similarity >= HEALTH_SIMILARITY_THRESHOLD:
                    left_health_present = True
                blue_similarity = compare_images(health_img, health_images["blue"])
                if yellow_similarity >= HEALTH_SIMILARITY_THRESHOLD or blue_similarity >= HEALTH_SIMILARITY_THRESHOLD:
                    right_health_present = True
            
            if yellow_similarity >= HEALTH_SIMILARITY_THRESHOLD:
                confirmed = True
                for i in range(HEALTH_CONFIRMATION_CHECKS - 1):
                    time.sleep(HEALTH_CONFIRMATION_DELAY)
                    health_img_confirm = capture_region(region)
                    yellow_similarity_confirm = compare_images(health_img_confirm, health_images["yellow"])
                    
                    if yellow_similarity_confirm < HEALTH_SIMILARITY_THRESHOLD:
                        confirmed = False
                        print(f"False positive filtered on {side.upper()} side (confirmation {i+1} failed: {yellow_similarity_confirm * 100:.1f}%)")
                        break
                
                if confirmed and not health_alert_states[side]["alert_played"]:
                    print(f"\n⚠ Critical health CONFIRMED on {side.upper()} side! ({yellow_similarity * 100:.1f}%)")
                    play_audio("CA_health.ogg")
                    health_alert_states[side]["alert_played"] = True
            else:
                if side == "left":
                    base_color_similarity = red_similarity
                else:
                    base_color_similarity = blue_similarity
                
                if base_color_similarity >= HEALTH_SIMILARITY_THRESHOLD:
                    if health_alert_states[side]["alert_played"]:
                        print(f"Health reset detected on {side.upper()} side - ready for next alert")
                        health_alert_states[side]["alert_played"] = False
                        
        except Exception as e:
            print(f"Error checking {side} health bar: {e}")
    
    if not left_health_present and not right_health_present:
        if not match_end_check_pending:
            match_end_check_pending = True
            match_end_check_time = time.time()
            print("Health bars not detected - checking again in 5 seconds...")
        elif time.time() - match_end_check_time >= MATCH_END_CONFIRMATION_DELAY:
            print("\nMatch ended - Health monitoring deactivated\n")
            return True
    else:
        match_end_check_pending = False
    
    return False 

def name_capture_wizard(control_images):
    """Guide user through capturing their player name from both sides"""
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
                similarity = compare_images(screen_img, control_img)
                
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
                            print("✓ Left side name captured successfully!\n")
                            play_audio("wizard_left_success.ogg")
                            left_captured = True
                            break
                        else:
                            print("✗ Failed to save left side image.\n")
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
                similarity = compare_images(screen_img, control_img)
                
                if similarity >= CONTROL_SIMILARITY_THRESHOLD:
                    print("VS screen detected!")
                    print("Waiting 1 second to avoid screen blink...")
                    time.sleep(1)
                    
                    screen_img = capture_region(right_region)
                    similarity = compare_images(screen_img, control_img)
                    
                    if similarity >= CONTROL_SIMILARITY_THRESHOLD:
                        print("VS screen still present. Capturing player name from right side...")
                        
                        name_region = NAME_REGIONS[1]
                        name_img = capture_region(name_region)
                        
                        if save_player_name_image(name_img, "right"):
                            print("✓ Right side name captured successfully!\n")
                            play_audio("wizard_right_success.ogg")
                            print("="*60)
                            print("SETUP COMPLETE")
                            print("="*60)
                            play_audio("wizard_complete.ogg")
                            return True
                        else:
                            print("✗ Failed to save right side image.\n")
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
    """Find the best matching rank from all rank images"""
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
    """Find the best matching division from all division images"""
    best_match = None
    best_similarity = 0
    
    for division_name, division_img in division_images.items():
        similarity = compare_images(captured_img, division_img)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = division_name
    
    if best_similarity < MIN_DIVISION_THRESHOLD:
        return None, best_similarity
    
    return best_match, best_similarity

def play_audio_sequence(audio_files):
    """Play multiple audio files in sequence"""
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

def main():
    global health_monitoring_active, last_health_check_time, last_match_check_time, match_end_check_pending
    
    print("\n" + "="*60)
    print("VISUAL AUDIO ASSIST - Street Fighter 6 Rank Announcer")
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
    
    health_images = {}
    if ENABLE_HEALTH_MONITORING:
        print("Loading health bar images...")
        try:
            health_images["red"] = load_image("red_health.png")
            health_images["blue"] = load_image("blue_health.png")
            health_images["yellow"] = load_image("yellow_health.png")
            print(f"Loaded {len(health_images)} health bar images\n")
        except Exception as e:
            print(f"Error loading health bar images: {e}")
            print("Continuing without health monitoring...\n")
            health_images = None
    
    print(f"Monitoring VS screen on {platform.system()}...")
    print(f"Check interval: {CHECK_INTERVAL} seconds")
    print(f"Audio cooldown: {COOLDOWN_PERIOD} seconds")
    print(f"Control threshold: {CONTROL_SIMILARITY_THRESHOLD * 100}%")
    if ENABLE_HEALTH_MONITORING and health_images:
        print(f"Health monitoring: Enabled")
    else:
        print(f"Health monitoring: Disabled")
    print("Press Ctrl+C to stop\n")
    
    last_audio_time = 0
    
    try:
        while True:
            current_time = time.time()
            
            if ENABLE_HEALTH_MONITORING and health_images:
                if not health_monitoring_active:
                    if current_time - last_match_check_time >= MATCH_CHECK_INTERVAL:
                        if check_match_started(health_images):
                            print("\n" + "="*60)
                            print("MATCH STARTED - Health monitoring activated")
                            print("="*60 + "\n")
                            health_monitoring_active = True
                            last_health_check_time = current_time
                        last_match_check_time = current_time
                else:
                    if current_time - last_health_check_time >= HEALTH_CHECK_INTERVAL:
                        match_ended = check_health_bars(health_images)
                        
                        if match_ended:
                            health_monitoring_active = False
                            health_alert_states["left"]["alert_played"] = False
                            health_alert_states["right"]["alert_played"] = False
                            match_end_check_pending = False
                        
                        last_health_check_time = current_time
            
            left_region = CONTROL_REGIONS[0] 
            right_region = CONTROL_REGIONS[1]
            
            left_control = None
            left_similarity = 0
            
            try:
                screen_img = capture_region(left_region)
                
                for control_name, control_img in control_images.items():
                    similarity = compare_images(screen_img, control_img)
                    
                    if similarity >= CONTROL_SIMILARITY_THRESHOLD:
                        left_control = control_name
                        left_similarity = similarity
                        break
                        
            except Exception as e:
                print(f"Error checking left control region: {e}")
            
            if left_control:
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
                                similarity = compare_images(left_screen_img, control_img)
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
                            
                            left_vs_left = compare_images(player_name_left, left_name_img)
                            left_vs_right = compare_images(player_name_left, right_name_img)
                            right_vs_left = compare_images(player_name_right, left_name_img)
                            right_vs_right = compare_images(player_name_right, right_name_img)
                            
                            left_side_max = max(left_vs_left, right_vs_left)
                            right_side_max = max(left_vs_right, right_vs_right)
                            
                            print(f"Name similarity - Left side: {left_side_max * 100:.1f}% | Right side: {right_side_max * 100:.1f}%")
                            
                            if left_side_max > right_side_max:
                                opponent_side = "right"
                                opponent_control = right_control if right_control else left_control
                                print(f"✓ Player detected on LEFT, opponent on RIGHT")
                            else:
                                opponent_side = "left"
                                opponent_control = left_control
                                print(f"✓ Player detected on RIGHT, opponent on LEFT")
                                
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
                            if opponent_rank in RANKS_WITH_DIVISIONS and opponent_rank != "Unknown":
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
                                elif opponent_rank in RANKS_WITH_DIVISIONS and division:
                                    audio_files = [f"{opponent_control}.ogg", f"{opponent_rank}{division}.ogg"]
                                else:
                                    audio_files = [f"{opponent_control}.ogg", f"{opponent_rank}.ogg"]
                                
                                print(f"\nPlaying audio sequence: {' -> '.join(audio_files)}")
                                play_audio_sequence(audio_files)
                                last_audio_time = current_time
                                
                                if ENABLE_HEALTH_MONITORING and health_images:
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
            
            time.sleep(CHECK_INTERVAL)
    
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")

if __name__ == "__main__":
    main()
