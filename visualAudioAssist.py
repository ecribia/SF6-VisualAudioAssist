import time
import platform

from config import (
    MEDIA_FOLDER, ENABLE_HEALTH_MONITORING, ENABLE_TRAINING_MENU,
    CHECK_INTERVAL, COOLDOWN_PERIOD, CONTROLS, RANKS, DIVISIONS, MR_VALUES,
    load_training_menu_config, training_menu_config, get_exe_directory
)
from image_processing import load_image, load_image_from_path
from vs_screen import handle_vs_screen_detection
from health import handle_health_monitoring
from training_menu import handle_training_menu
from wizards import name_capture_wizard

def load_player_name_image():
    exe_dir = get_exe_directory()
    name_path = exe_dir / "MyName.png"
    return load_image_from_path(name_path) if name_path.exists() else None

def load_game_images():
    print("Loading control images...")
    control_images = {}
    for control in CONTROLS:
        control_images[control] = load_image(MEDIA_FOLDER / f"{control}.png")
    print(f"Loaded {len(control_images)} control images\n")
    
    print("Loading rank images...")
    rank_images = {}
    for rank in RANKS:
        rank_images[rank] = load_image(MEDIA_FOLDER / f"{rank}.png")
    print(f"Loaded {len(rank_images)} rank images\n")
    
    print("Loading division images...")
    division_images = {}
    for division in DIVISIONS:
        division_images[division] = load_image(MEDIA_FOLDER / f"{division.lower()}.png")
    print(f"Loaded {len(division_images)} division images\n")
    
    print("Loading MR images...")
    mr_images = {}
    for mr_value in MR_VALUES:
        mr_images[mr_value] = load_image(MEDIA_FOLDER / f"{mr_value}.png")
    print(f"Loaded {len(mr_images)} MR images\n")
    
    return control_images, rank_images, division_images, mr_images

def setup_training_menu():
    if not ENABLE_TRAINING_MENU:
        return False, None, None
    
    if not load_training_menu_config():
        return False, None, None
    
    try:
        menu_ref_img = load_image(
            MEDIA_FOLDER / training_menu_config["tab_detection"]["reference_image"]
        )
        submenu_ref_img = load_image(
            MEDIA_FOLDER / training_menu_config["submenu_detection"]["reference_image"]
        )
        print("Training menu monitoring enabled\n")
        return True, menu_ref_img, submenu_ref_img
    except Exception as e:
        print(f"Error loading training menu images: {e}")
        print("Training menu monitoring disabled\n")
        return False, None, None

def main():
    print("\n" + "="*60)
    print("VISUAL AUDIO ASSIST - Street Fighter 6")
    print("="*60 + "\n")
    
    try:
        control_images, rank_images, division_images, mr_images = load_game_images()
    except Exception as e:
        print(f"Error loading images: {e}")
        return
    
    player_name_img = load_player_name_image()
    if player_name_img is None:
        if not name_capture_wizard(control_images):
            print("Setup failed. Exiting.")
            return
        player_name_img = load_player_name_image()
    else:
        print("Player name image found: MyName.png\n")
    
    training_menu_enabled, menu_ref_img, submenu_ref_img = setup_training_menu()
    
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
    
    health_state = {
        'active': False,
        'alert_states': {
            "left": {"alert_played": False},
            "right": {"alert_played": False}
        },
        'last_health_check_time': 0,
        'last_match_check_time': 0,
        'match_end_check_pending': False,
        'match_end_check_time': 0
    }
    
    menu_state = {
        'last_selected_item': None,
        'last_item_position': None,
        'last_active_tab': None,
        'last_active_sub_tab': None,
        'was_open': False,
        'initial_check_done': False,
        'sub_tab_announced': False,
        'in_submenu': False
    }
    
    try:
        while True:
            current_time = time.time()
            
            if ENABLE_HEALTH_MONITORING:
                new_mode = handle_health_monitoring(current_time, health_state)
                if new_mode:
                    current_mode = new_mode
                    # If match just ended, immediately check for VS screen
                    if new_mode == 'idle':
                        vs_detected, vs_mode, last_audio_time = handle_vs_screen_detection(
                            current_time, last_audio_time, control_images, player_name_img,
                            rank_images, division_images, mr_images
                        )
                        if vs_detected:
                            current_mode = 'vs_screen'
            
            # Only check VS screen when health monitoring is NOT active
            # Use elif to avoid double-checking in same iteration
            elif not health_state['active'] and current_mode in ["vs_screen", "idle"]:
                vs_detected, new_mode, last_audio_time = handle_vs_screen_detection(
                    current_time, last_audio_time, control_images, player_name_img,
                    rank_images, division_images, mr_images
                )
                
                if vs_detected:
                    current_mode = 'vs_screen'
                    if ENABLE_HEALTH_MONITORING:
                        health_state['active'] = False
                        health_state['alert_states']["left"]["alert_played"] = False
                        health_state['alert_states']["right"]["alert_played"] = False
                elif current_mode == "vs_screen":
                    current_mode = "idle"
            
            if training_menu_enabled and current_mode in ["training_menu", "idle"]:
                menu_open = handle_training_menu(
                    menu_state, training_menu_config, 
                    menu_ref_img, submenu_ref_img
                )
                
                if menu_open:
                    current_mode = "training_menu"
                elif current_mode == "training_menu":
                    current_mode = "idle"
            
            time.sleep(CHECK_INTERVAL)
    
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")

if __name__ == "__main__":
    main()
