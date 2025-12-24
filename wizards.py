import time
import cv2
from capture import capture_region
from image_processing import compare_images_no_threshold
from audio import play_audio
from config import CONTROL_REGIONS, NAME_REGIONS, CONTROL_SIMILARITY_THRESHOLD, NAME_THRESHOLD, get_exe_directory

def save_player_name_image(img):
    exe_dir = get_exe_directory()
    player_name_path = exe_dir / "MyName.png"
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, NAME_THRESHOLD, 255, cv2.THRESH_BINARY)
        cv2.imwrite(str(player_name_path), binary)
        print(f"Player name image saved to: {player_name_path}")
        return True
    except Exception as e:
        print(f"Error saving player name image: {e}")
        return False

def name_capture_wizard(control_images):
    print("\n" + "="*60)
    print("PLAYER NAME CAPTURE WIZARD")
    print("="*60)
    print("\nNo player name image detected. Running image capture wizard.")
    play_audio("wizard_start.ogg")
    
    print("\n" + "-"*60)
    print("PLAYER NAME CAPTURE")
    print("-"*60)
    print("Open a replay where you start on the LEFT side of the screen.")
    print("Your name will be registered from the VS screen.\n")
    play_audio("wizard_instructions.ogg")
    
    name_captured = False
    while not name_captured:
        try:
            left_region = CONTROL_REGIONS[0]
            screen_img = capture_region(left_region)
            
            best_control = None
            best_similarity = 0
            for control_name, control_img in control_images.items():
                similarity = compare_images_no_threshold(screen_img, control_img)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_control = control_name
            
            if best_similarity >= CONTROL_SIMILARITY_THRESHOLD:
                print("VS screen detected!")
                print("Waiting 1 second to avoid screen blink...")
                time.sleep(1)
                
                screen_img = capture_region(left_region)
                recheck_best_similarity = 0
                for control_name, control_img in control_images.items():
                    similarity = compare_images_no_threshold(screen_img, control_img)
                    if similarity > recheck_best_similarity:
                        recheck_best_similarity = similarity
                
                if recheck_best_similarity >= CONTROL_SIMILARITY_THRESHOLD:
                    print("VS screen still present. Capturing player name...")
                    name_region = NAME_REGIONS[0]
                    name_img = capture_region(name_region)
                    
                    if save_player_name_image(name_img):
                        print("\nThis image will be used to detect your name on both sides.")
                        play_audio("wizard_complete.ogg")
                        print("="*60)
                        print("SETUP COMPLETE")
                        print("="*60)
                        return True
                    else:
                        print("Failed to save player name image.\n")
                        play_audio("wizard_error.ogg")
                        return False
                else:
                    print("VS screen disappeared, retrying...\n")
        except Exception as e:
            print(f"Error during name capture: {e}")
            play_audio("wizard_error.ogg")
            return False
        
        if not name_captured:
            time.sleep(1)
