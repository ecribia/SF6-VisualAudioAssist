import cv2
import numpy as np
import time
import platform
import sys
import glob
import os
import json
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

MEDIA_FOLDER = get_resource_path("media")
CONFIG_FILE = get_resource_path("config.json")
CHECK_INTERVAL = 2
COOLDOWN_PERIOD = 15
CONTROL_SIMILARITY_THRESHOLD = 0.98
RANK_SIMILARITY_THRESHOLD = 0.85
MIN_RANK_THRESHOLD = 0.70

# Control type regions (left and right side of VS screen)
CONTROL_REGIONS = [
    {"top": 834, "left": 56, "width": 35, "height": 31, "side": "left"},
    {"top": 835, "left": 1830, "width": 35, "height": 31, "side": "right"}
]

# Rank regions (left and right side of VS screen)
RANK_REGIONS = [
    {"top": 928, "left": 65, "width": 108, "height": 44, "side": "left"},
    {"top": 928, "left": 1740, "width": 108, "height": 44, "side": "right"}
]

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

# Cache for the working capture method
_capture_method = None
_grim_path = None

# Global flag for reconfiguration
reconfigure_requested = False

RANKS = [
    "NewChallenger", "Rookie", "Iron", "Bronze", "Silver", "Gold", 
    "Platinum", "Diamond", "Master", "HighMaster", 
    "GrandMaster", "UltimateMaster"
]

CONTROLS = ["Modern", "Classic"]

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

def load_config():
    """Load player configuration from config.json"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get("player_control"), config.get("player_rank")
        except Exception as e:
            print(f"Error loading config: {e}")
    return None, None

def save_config(control, rank):
    """Save player configuration to config.json"""
    try:
        config = {"player_control": control, "player_rank": rank}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Configuration saved!\n")
    except Exception as e:
        print(f"Error saving config: {e}")

def setup_wizard():
    """Interactive setup to choose player control and rank"""
    print("\n" + "="*50)
    print("VISUAL AUDIO ASSIST - SETUP")
    print("="*50 + "\n")
    
    # Choose control type
    print("Select your control type:")
    for i, control in enumerate(CONTROLS, 1):
        print(f"  {i}. {control}")
    
    while True:
        try:
            choice = input("\nEnter number (1-2): ").strip()
            choice_num = int(choice)
            if 1 <= choice_num <= len(CONTROLS):
                player_control = CONTROLS[choice_num - 1]
                break
            else:
                print("Invalid choice. Please enter 1 or 2.")
        except (ValueError, KeyboardInterrupt):
            print("\nSetup cancelled.")
            sys.exit(0)
    
    # Choose rank
    print(f"\nYou selected: {player_control}")
    print("\nSelect your rank:")
    for i, rank in enumerate(RANKS, 1):
        print(f"  {i:2d}. {rank}")
    
    while True:
        try:
            choice = input(f"\nEnter number (1-{len(RANKS)}): ").strip()
            choice_num = int(choice)
            if 1 <= choice_num <= len(RANKS):
                player_rank = RANKS[choice_num - 1]
                break
            else:
                print(f"Invalid choice. Please enter a number between 1 and {len(RANKS)}.")
        except (ValueError, KeyboardInterrupt):
            print("\nSetup cancelled.")
            sys.exit(0)
    
    print(f"\nYou selected: {player_rank}")
    print("\n" + "="*50)
    print(f"Configuration: {player_control} / {player_rank}")
    print("="*50 + "\n")
    
    save_config(player_control, player_rank)
    return player_control, player_rank

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
            # Wait for audio to finish
            while mixer.music.get_busy():
                time.sleep(0.1)
        except Exception as e:
            print(f"Error playing audio {audio_file}: {e}")

def keyboard_listener():
    """Listen for keyboard input in a separate thread"""
    global reconfigure_requested
    try:
        if IS_WINDOWS:
            import msvcrt
            while True:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8').lower()
                    if key == 'r':
                        reconfigure_requested = True
        else:
            import sys
            import tty
            import termios
            old_settings = termios.tcgetattr(sys.stdin)
            try:
                tty.setcbreak(sys.stdin.fileno())
                while True:
                    key = sys.stdin.read(1).lower()
                    if key == 'r':
                        reconfigure_requested = True
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    except Exception:
        pass

def main():
    global reconfigure_requested
    
    print("\n" + "="*60)
    print("VISUAL AUDIO ASSIST - Street Fighter 6 Rank Announcer")
    print("="*60 + "\n")
    
    # Load or create configuration
    player_control, player_rank = load_config()
    
    if player_control and player_rank:
        print(f"Loaded configuration: {player_control} / {player_rank}")
        print("Press 'R' during monitoring to reconfigure\n")
    else:
        player_control, player_rank = setup_wizard()
    
    # Load all control images
    print("Loading control images...")
    control_images = {}
    try:
        for control in CONTROLS:
            control_images[control] = load_image(f"{control}.png")
        print(f"Loaded {len(control_images)} control images\n")
    except Exception as e:
        print(f"Error loading control images: {e}")
        return
    
    # Load all rank images
    print("Loading rank images...")
    rank_images = {}
    try:
        for rank in RANKS:
            rank_images[rank] = load_image(f"{rank}.png")
        print(f"Loaded {len(rank_images)} rank images\n")
    except Exception as e:
        print(f"Error loading rank images: {e}")
        return
    
    print(f"Monitoring VS screen on {platform.system()}...")
    print(f"Check interval: {CHECK_INTERVAL} seconds")
    print(f"Audio cooldown: {COOLDOWN_PERIOD} seconds")
    print(f"Control threshold: {CONTROL_SIMILARITY_THRESHOLD * 100}%")
    print(f"Rank threshold: {RANK_SIMILARITY_THRESHOLD * 100}%")
    print("Press Ctrl+C to stop")
    print("Press 'R' to reconfigure\n")
    
    # Start keyboard listener thread
    listener_thread = threading.Thread(target=keyboard_listener, daemon=True)
    listener_thread.start()
    
    last_audio_time = 0
    
    try:
        while True:
            # Check for reconfiguration request
            if reconfigure_requested:
                reconfigure_requested = False
                print("\n" + "="*60)
                print("RECONFIGURATION REQUESTED")
                print("="*60)
                player_control, player_rank = setup_wizard()
                print("\nResuming monitoring...\n")
                continue
            
            # Step 1: Check LEFT side first
            left_region = CONTROL_REGIONS[0]  # Left side
            right_region = CONTROL_REGIONS[1]  # Right side
            
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
            
            # Step 2: If left side has match, check RIGHT side
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
                
                # Step 3: VS Screen detected - determine opponent
                print(f"\n{'='*60}")
                print(f"VS SCREEN DETECTED")
                print(f"  Left: {left_control} ({left_similarity * 100:.1f}%)")
                if right_control:
                    print(f"  Right: {right_control} ({right_similarity * 100:.1f}%)")
                else:
                    print(f"  Right: No match detected")
                print(f"{'='*60}")
                
                current_time = time.time()
                
                if current_time - last_audio_time >= COOLDOWN_PERIOD:
                    try:
                        # Determine opponent side and control
                        opponent_side = None
                        opponent_control = None
                        
                        if right_control:
                            # Both sides detected
                            if left_control != player_control and right_control == player_control:
                                opponent_side = "left"
                                opponent_control = left_control
                                print(f"\nOpponent identified: {opponent_control} on LEFT side")
                            elif right_control != player_control and left_control == player_control:
                                opponent_side = "right"
                                opponent_control = right_control
                                print(f"\nOpponent identified: {opponent_control} on RIGHT side")
                            elif left_control == player_control and right_control == player_control:
                                # Both same as player - determine by rank later
                                opponent_control = player_control
                                print(f"\nBoth players use {player_control} - will determine opponent by rank")
                            else:
                                # Both different from player (shouldn't happen)
                                opponent_side = "left"
                                opponent_control = left_control
                                print(f"\nWarning: Unexpected control combination, assuming left is opponent")
                        else:
                            # Only left side detected
                            if left_control != player_control:
                                opponent_side = "left"
                                opponent_control = left_control
                                print(f"\nOnly left side detected: {opponent_control}")
                            else:
                                # Only player's control on left, opponent must be on right (but not detected)
                                opponent_control = player_control
                                print(f"\nOnly your control detected on left - opponent on right (undetected)")
                        
                        # Capture both rank regions
                        print("\nCapturing rank regions...")
                        rank_captures = {}
                        
                        for region in RANK_REGIONS:
                            try:
                                rank_img = capture_region(region)
                                rank_captures[region["side"]] = rank_img
                            except Exception as e:
                                print(f"Error capturing {region['side']} rank: {e}")
                        
                        if len(rank_captures) == 2:
                            # Find best match for both ranks
                            left_rank, left_sim = find_best_rank_match(rank_captures["left"], rank_images)
                            right_rank, right_sim = find_best_rank_match(rank_captures["right"], rank_images)
                            
                            print(f"Left rank: {left_rank} ({left_sim * 100:.1f}%)")
                            print(f"Right rank: {right_rank} ({right_sim * 100:.1f}%)")
                            
                            # Determine opponent's rank
                            opponent_rank = None
                            
                            if opponent_side:
                                # We already know which side is opponent
                                opponent_rank = left_rank if opponent_side == "left" else right_rank
                                print(f"Opponent rank (based on side): {opponent_rank}")
                            else:
                                # Same control type - determine by rank
                                if left_rank == player_rank and right_rank == player_rank:
                                    opponent_rank = player_rank
                                    print(f"Both ranks are {player_rank} - opponent has same rank")
                                elif left_rank == player_rank:
                                    opponent_rank = right_rank
                                    print(f"Your rank on left ({player_rank}), opponent on right: {opponent_rank}")
                                elif right_rank == player_rank:
                                    opponent_rank = left_rank
                                    print(f"Your rank on right ({player_rank}), opponent on left: {opponent_rank}")
                                else:
                                    # Neither matches player rank
                                    # Default to left if we detected left control, otherwise right
                                    if opponent_side is None:
                                        # Fallback: pick the higher confidence rank
                                        if left_sim >= right_sim:
                                            opponent_rank = left_rank
                                            print(f"Warning: Your rank ({player_rank}) not detected. Using left rank: {opponent_rank}")
                                        else:
                                            opponent_rank = right_rank
                                            print(f"Warning: Your rank ({player_rank}) not detected. Using right rank: {opponent_rank}")
                                    else:
                                        opponent_rank = left_rank if opponent_side == "left" else right_rank
                                        print(f"Warning: Your rank ({player_rank}) not detected. Using {opponent_side} rank: {opponent_rank}")
                            
                            # Play audio sequence
                            if opponent_control and opponent_rank and opponent_rank != "Unknown":
                                audio_files = [f"{opponent_control}.mp3", f"{opponent_rank}.mp3"]
                                print(f"\nPlaying audio sequence: {' -> '.join(audio_files)}")
                                play_audio_sequence(audio_files)
                                last_audio_time = current_time
                                print(f"{'='*60}\n")
                            else:
                                print(f"\nSkipping audio - opponent info incomplete")
                                if not opponent_control:
                                    print("  Missing: opponent control")
                                if not opponent_rank or opponent_rank == "Unknown":
                                    print("  Missing: opponent rank")
                                print(f"{'='*60}\n")
                        else:
                            print("Failed to capture both rank regions")
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
        print("Configuration saved. Run again to resume with same settings.")

if __name__ == "__main__":
    main()
