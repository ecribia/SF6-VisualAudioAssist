import time
import cv2
from capture import capture_region
from image_processing import apply_binary_threshold, check_for_white_pixels, compare_images_grayscale
from audio import play_audio
from config import MENU_CONFIRMATION_CHECKS, MENU_CONFIRMATION_DELAY
from option_detection import announce_option_value, detect_option_value

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
    is_similar, similarity = compare_images_grayscale(
        submenu_screen, submenu_reference_img, 
        config["detection_settings"]["submenu_match_threshold"]
    )
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
        region = {
            "left": sub_tab_info["left"],
            "top": sub_tab_info["top"],
            "width": sub_tab_info["width"],
            "height": sub_tab_info["height"]
        }
        img = capture_region(region)
        binary = apply_binary_threshold(img, config["detection_settings"]["binary_threshold"])
        if check_for_white_pixels(binary, config["detection_settings"]["white_pixel_threshold"]):
            return sub_tab_info["name"]
    
    return None

def get_item_region(item_y, config, tab_name=None, item_name=None, is_submenu=False):
    check_config = config["item_detection"]["check_region"]
    
    if is_submenu and tab_name == "Record":
        return {
            "top": item_y,
            "left": 738,
            "width": check_config["width"],
            "height": check_config["height"]
        }
    
    if (tab_name == "Environment Settings" and 
        item_name in ["P1 Character Select", "P2 Character Select"]):
        return {
            "top": item_y,
            "left": 449,
            "width": check_config["width"],
            "height": check_config["height"]
        }
    
    return {
        "top": item_y,
        "left": check_config["left"],
        "width": check_config["width"],
        "height": check_config["height"]
    }

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

def check_item_still_selected(item_position_idx, tab_name, item_name, config, is_submenu=False):
    item_positions = config["item_detection"]["positions"]
    if item_position_idx >= len(item_positions):
        return False
    
    item_y = item_positions[item_position_idx]
    region = get_item_region(item_y, config, tab_name, item_name, is_submenu)
    
    img = capture_region(region)
    binary = apply_binary_threshold(img, config["detection_settings"]["binary_threshold"])
    return check_for_white_pixels(binary, config["detection_settings"]["white_pixel_threshold"])

def item_name_to_audio_file(item_name, config):
    audio_name = item_name.lower().replace(" ", "_").replace("-", "_")
    audio_config = config["audio"]
    return f"{audio_name}{audio_config['extension']}"

def tab_name_to_audio_file(tab_name, config):
    audio_name = tab_name.lower().replace(" ", "_").replace("-", "_")
    audio_config = config["audio"]
    return f"{audio_name}{audio_config['extension']}"

def handle_training_menu(menu_state, config, menu_reference_img, submenu_reference_img):
    if not menu_state['initial_check_done']:
        tab_region = config["tab_detection"]["region"]
        screen_img = capture_region(tab_region)
        menu_open, similarity = compare_images_grayscale(
            screen_img, menu_reference_img, 
            config["detection_settings"]["menu_match_threshold"]
        )
        
        if not menu_open:
            return False
        
        confirmed = True
        for i in range(MENU_CONFIRMATION_CHECKS - 1):
            time.sleep(MENU_CONFIRMATION_DELAY)
            screen_img_confirm = capture_region(tab_region)
            menu_still_open, similarity_confirm = compare_images_grayscale(
                screen_img_confirm, menu_reference_img, 
                config["detection_settings"]["menu_match_threshold"]
            )
            if not menu_still_open:
                confirmed = False
                print(f"False positive filtered - menu closed during confirmation check {i+1}")
                break
        
        if confirmed:
            print(f"\n{'='*60}")
            print(f"TRAINING MENU DETECTED (similarity: {similarity*100:.1f}%)")
            print(f"{'='*60}\n")
            menu_state['initial_check_done'] = True
            menu_state['was_open'] = True
            return True
        return False
    
    should_check_submenu = (
        menu_state['last_active_tab'] == "Reversal Settings" or 
        menu_state['in_submenu']
    )
    
    if should_check_submenu:
        was_in_submenu = menu_state['in_submenu']
        menu_state['in_submenu'] = check_if_in_submenu(config, submenu_reference_img)
        
        if menu_state['in_submenu'] != was_in_submenu:
            if menu_state['in_submenu']:
                print(f"\n{'-'*60}")
                print("SUBMENU OPENED")
                print(f"{'-'*60}\n")
                menu_state['last_selected_item'] = None
                menu_state['last_item_position'] = None
                menu_state['last_active_tab'] = None
                menu_state['last_active_sub_tab'] = None
                menu_state['last_announced_option'] = None
            else:
                print(f"\n{'-'*60}")
                print("RETURNED TO MAIN MENU")
                print(f"{'-'*60}\n")
                menu_state['last_selected_item'] = None
                menu_state['last_item_position'] = None
                menu_state['last_active_tab'] = "Reversal Settings"
                menu_state['sub_tab_announced'] = False
                menu_state['last_announced_option'] = None
    else:
        menu_state['in_submenu'] = False
    
    tab_number, tab_name = detect_active_tab(config, is_submenu=menu_state['in_submenu'])
    
    if not tab_name:
        if menu_state['was_open']:
            print(f"\n{'='*60}")
            print("TRAINING MENU CLOSED")
            print(f"{'='*60}\n")
            menu_state['was_open'] = False
            menu_state['initial_check_done'] = False
            menu_state['last_selected_item'] = None
            menu_state['last_item_position'] = None
            menu_state['last_active_tab'] = None
            menu_state['last_active_sub_tab'] = None
            menu_state['sub_tab_announced'] = False
            menu_state['in_submenu'] = False
            menu_state['last_announced_option'] = None
        return False
    
    if not menu_state['was_open']:
        print(f"\n{'='*60}")
        print(f"TRAINING MENU RE-OPENED")
        print(f"{'='*60}\n")
        menu_state['was_open'] = True
    
    if menu_state['last_active_tab'] and menu_state['last_active_tab'] != tab_name:
        if menu_state['in_submenu']:
            print(f"Submenu tab changed: {menu_state['last_active_tab']} -> {tab_name}")
        else:
            print(f"Tab changed: {menu_state['last_active_tab']} -> {tab_name}")
        
        audio_file = tab_name_to_audio_file(tab_name, config)
        print(f"Playing: {audio_file}")
        play_audio(audio_file, "menu")
        
        menu_state['last_selected_item'] = None
        menu_state['last_item_position'] = None
        menu_state['last_active_sub_tab'] = None
        menu_state['sub_tab_announced'] = False
        menu_state['last_announced_option'] = None
    
    menu_state['last_active_tab'] = tab_name
    
    sub_tab_name = None
    if not menu_state['in_submenu']:
        sub_tab_name = detect_active_sub_tab(tab_name, config)
        
        if sub_tab_name and not menu_state['sub_tab_announced']:
            audio_file = tab_name_to_audio_file(sub_tab_name, config)
            print(f"Sub-tab: {sub_tab_name}")
            print(f"Playing: {audio_file}")
            play_audio(audio_file, "menu")
            menu_state['sub_tab_announced'] = True
        
        if (sub_tab_name and menu_state['last_active_sub_tab'] and 
            menu_state['last_active_sub_tab'] != sub_tab_name):
            print(f"Sub-tab changed: {menu_state['last_active_sub_tab']} -> {sub_tab_name}")
            audio_file = tab_name_to_audio_file(sub_tab_name, config)
            print(f"Playing: {audio_file}")
            play_audio(audio_file, "menu")
            menu_state['last_selected_item'] = None
            menu_state['last_item_position'] = None
            menu_state['last_announced_option'] = None
        
        menu_state['last_active_sub_tab'] = sub_tab_name
    
    if menu_state['last_selected_item'] and menu_state['last_item_position'] is not None:
        still_selected = check_item_still_selected(
            menu_state['last_item_position'], tab_name, 
            menu_state['last_selected_item'], config, menu_state['in_submenu']
        )
        if not still_selected:
            print(f"'{menu_state['last_selected_item']}' deselected - resuming scan\n")
            menu_state['last_selected_item'] = None
            menu_state['last_item_position'] = None
            menu_state['last_announced_option'] = None
    
    if menu_state['last_selected_item'] is None:
        selected_item, item_position = detect_selected_item(
            tab_name, sub_tab_name, config, is_submenu=menu_state['in_submenu']
        )
        if selected_item:
            if menu_state['in_submenu']:
                print(f"Submenu Tab: {tab_name}")
            elif sub_tab_name:
                print(f"Tab: {tab_name} > {sub_tab_name}")
            else:
                print(f"Tab: {tab_name}")
            print(f"Selected: {selected_item}")
            
            audio_file = item_name_to_audio_file(selected_item, config)
            print(f"Playing: {audio_file}")
            play_audio(audio_file, "menu", allow_interrupt=False)
            
            menu_state['last_selected_item'] = selected_item
            menu_state['last_item_position'] = item_position
            menu_state['last_announced_option'] = None
            print(f"Locked onto '{selected_item}' - waiting for deselection\n")
    else:
        current_option = detect_option_value(
            menu_state['last_selected_item'], 
            tab_name, 
            sub_tab_name, 
            config, 
            menu_state['in_submenu']
        )
        
        if current_option:
            current_option_id = current_option.get("audio", "")
            
            if menu_state['last_announced_option'] != current_option_id:
                print(f"Option value: {current_option['audio'].replace('.ogg', '')}")
                play_audio(current_option["audio"], "menu", allow_interrupt=True)
                menu_state['last_announced_option'] = current_option_id
    
    return True
