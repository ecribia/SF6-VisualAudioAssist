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

MEDIA_FOLDER = get_resource_path("media")
CHECK_INTERVAL = 2
COOLDOWN_PERIOD = 15
CONTROL_SIMILARITY_THRESHOLD = 0.98
MIN_RANK_THRESHOLD = 0.70

CONTROL_REGIONS = [
    {"top": 834, "left": 56, "width": 35, "height": 31, "side": "left"},
    {"top": 835, "left": 1830, "width": 35, "height": 31, "side": "right"}
]

RANK_REGIONS = [
    {"top": 928, "left": 65, "width": 108, "height": 44, "side": "left"},
    {"top": 928, "left": 1740, "width": 108, "height": 44, "side": "right"}
]

NAME_REGIONS = [
    {"top": 912, "left": 334, "width": 82, "height": 26, "side": "left"},
    {"top": 912, "left": 1354, "width": 82, "height": 26, "side": "right"}
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

CONTROLS = ["Classic", "Modern"]

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

def name_capture_wizard(control_images):
    """Guide user through capturing their player name from both sides"""
    print("\n" + "="*60)
    print("PLAYER NAME CAPTURE WIZARD")
    print("="*60)
    print("\nNo player name images detected. Running image capture wizard.")
    play_audio("wizard_start.mp3")
    
    print("\nThis wizard will capture your player name from both sides")
    print("of the screen for accurate opponent detection.")
    play_audio("wizard_instructions.mp3")
    
    print("\n" + "-"*60)
    print("STEP 1: LEFT SIDE CAPTURE")
    print("-"*60)
    print("Open a replay where you start on the LEFT side of the screen.")
    print("Your name will be registered from the VS screen.\n")
    play_audio("wizard_left_step.mp3")
    
    while True:
        try:
            left_region = CONTROL_REGIONS[0]
            screen_img = capture_region(left_region)
            
            for control_name, control_img in control_images.items():
                similarity = compare_images(screen_img, control_img)
                
                if similarity >= CONTROL_SIMILARITY_THRESHOLD:
                    print("VS screen detected!")
                    print("Capturing player name from left side...")
                    
                    name_region = NAME_REGIONS[0]
                    name_img = capture_region(name_region)
                    
                    if save_player_name_image(name_img, "left"):
                        print("✓ Left side name captured successfully!\n")
                        play_audio("wizard_left_success.mp3")
                        break
                    else:
                        print("✗ Failed to save left side image.\n")
                        play_audio("wizard_error.mp3")
                        return False
                        
        except Exception as e:
            print(f"Error during left side capture: {e}")
            play_audio("wizard_error.mp3")
            return False
        
        time.sleep(1)
    
    print("\n" + "-"*60)
    print("STEP 2: RIGHT SIDE CAPTURE")
    print("-"*60)
    print("Now open a replay where you start on the RIGHT side of the screen.\n")
    play_audio("wizard_right_step.mp3")
    
    while True:
        try:
            right_region = CONTROL_REGIONS[1]
            screen_img = capture_region(right_region)
            
            for control_name, control_img in control_images.items():
                similarity = compare_images(screen_img, control_img)
                
                if similarity >= CONTROL_SIMILARITY_THRESHOLD:
                    print("VS screen detected!")
                    print("Capturing player name from right side...")
                    
                    name_region = NAME_REGIONS[1]
                    name_img = capture_region(name_region)
                    
                    if save_player_name_image(name_img, "right"):
                        print("✓ Right side name captured successfully!\n")
                        play_audio("wizard_right_success.mp3")
                        print("="*60)
                        print("SETUP COMPLETE")
                        print("="*60)
                        play_audio("wizard_complete.mp3")
                        return True
                    else:
                        print("✗ Failed to save right side image.\n")
                        play_audio("wizard_error.mp3")
                        return False
                        
        except Exception as e:
            print(f"Error during right side capture: {e}")
            play_audio("wizard_error.mp3")
            return False
        
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
    
    print(f"Monitoring VS screen on {platform.system()}...")
    print(f"Check interval: {CHECK_INTERVAL} seconds")
    print(f"Audio cooldown: {COOLDOWN_PERIOD} seconds")
    print(f"Control threshold: {CONTROL_SIMILARITY_THRESHOLD * 100}%")
    print("Press Ctrl+C to stop\n")
    
    last_audio_time = 0
    
    try:
        while True:
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
                
                current_time = time.time()
                
                if current_time - last_audio_time >= COOLDOWN_PERIOD:
                    try:
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
                        
                        print("\nCapturing rank regions...")
                        rank_captures = {}
                        
                        for region in RANK_REGIONS:
                            try:
                                rank_img = capture_region(region)
                                rank_captures[region["side"]] = rank_img
                            except Exception as e:
                                print(f"Error capturing {region['side']} rank: {e}")
                        
                        if len(rank_captures) == 2:
                            left_rank, left_sim = find_best_rank_match(rank_captures["left"], rank_images)
                            right_rank, right_sim = find_best_rank_match(rank_captures["right"], rank_images)
                            
                            print(f"Left rank: {left_rank} ({left_sim * 100:.1f}%)")
                            print(f"Right rank: {right_rank} ({right_sim * 100:.1f}%)")
                            
                            opponent_rank = left_rank if opponent_side == "left" else right_rank
                            print(f"Opponent rank: {opponent_rank}")
                            
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

if __name__ == "__main__":
    main()
