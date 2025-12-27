import numpy as np
import cv2
from capture import capture_region
from audio import play_audio

def get_value_region_for_item(item_name, tab_name, sub_tab_name, config, is_submenu=False):
    """Calculate the screen region where this item's value appears"""
    
    tabs_dict = config["submenu_tabs"] if is_submenu else config["tabs"]
    
    if tab_name not in tabs_dict:
        return None
    
    tab_data = tabs_dict[tab_name]
    
    if "item_options" in tab_data and item_name in tab_data["item_options"]:
        option_config = tab_data["item_options"][item_name]
        if "value_region_override" in option_config:
            return option_config["value_region_override"]
    
    if not is_submenu and tab_data.get("has_sub_tabs", False) and sub_tab_name:
        items = tab_data["sub_tabs"][sub_tab_name]
    else:
        items = tab_data.get("items", [])
    
    try:
        item_index = items.index(item_name)
    except (ValueError, AttributeError):
        return None
    
    start_position = tab_data["start_position"]
    position_idx = start_position + item_index - 1
    
    positions = config["item_detection"]["positions"]
    if position_idx >= len(positions):
        return None
    
    item_y = positions[position_idx]
    
    value_region_template = config["item_detection"]["value_region"]
    
    return {
        "top": item_y + value_region_template["top_offset"],
        "left": value_region_template["left"],
        "width": value_region_template["width"],
        "height": value_region_template["height"]
    }

def detect_option_value(item_name, tab_name, sub_tab_name, config, is_submenu=False):
    """Detect the current value of a menu item option"""
    tabs_dict = config["submenu_tabs"] if is_submenu else config["tabs"]
    
    if tab_name not in tabs_dict:
        return None
    
    tab_config = tabs_dict[tab_name]
    
    if "item_options" not in tab_config:
        return None
    
    if item_name not in tab_config["item_options"]:
        return None
    
    option_config = tab_config["item_options"][item_name]
    
    region = get_value_region_for_item(item_name, tab_name, sub_tab_name, config, is_submenu)
    
    if not region:
        return None
    
    option_definitions = config["option_definitions"]
    
    if option_config["detection_method"] == "yellow_width":
        tolerance = config["detection_settings"]["yellow_width_tolerance"]
        return detect_by_yellow_width(region, option_config, option_definitions, tolerance)
    elif option_config["detection_method"] == "image_comparison":
        threshold = option_config.get("comparison_threshold", 0.85)
        binary_threshold = option_config.get("binary_threshold", None)
        return detect_by_image_comparison(region, option_config, option_definitions, threshold, binary_threshold)
    
    return None

def detect_by_yellow_width(region, option_config, option_definitions, tolerance):
    """Detect option by measuring yellow text width"""
    img = capture_region(region)
    
    yellow_mask = (
        (img[:,:,0] >= 50) & (img[:,:,0] <= 120) & 
        (img[:,:,1] >= 200) & (img[:,:,1] <= 255) &
        (img[:,:,2] >= 200) & (img[:,:,2] <= 255)
    )
    
    yellow_pixels = np.sum(yellow_mask, axis=0)
    columns_with_yellow = np.where(yellow_pixels > 0)[0]
    
    default_key = option_config.get("default", option_config["options"][0])
    
    if len(columns_with_yellow) == 0:
        return option_definitions[default_key]
    
    measured_width = columns_with_yellow[-1] - columns_with_yellow[0]
    
    print(f"  [Yellow width detected: {measured_width} pixels]")
    
    best_match = None
    best_diff = float('inf')
    best_option_key = None
    
    for option_key in option_config["options"]:
        if option_key == default_key:
            continue
        
        option = option_definitions[option_key]
        diff = abs(option["width"] - measured_width)
        if diff < tolerance and diff < best_diff:
            best_diff = diff
            best_match = option
            best_option_key = option_key
    
    if best_match:
        print(f"  [Matched to '{best_option_key}' (width: {best_match['width']}, diff: {best_diff})]")
        return best_match
    else:
        print(f"  [No match within tolerance, using default]")
        return option_definitions[default_key]

def detect_by_image_comparison(region, option_config, option_definitions, threshold=0.85, binary_threshold=None):
    """Detect option by comparing against reference images"""
    from image_processing import load_image, compare_images_grayscale
    from config import MEDIA_FOLDER
    
    img = capture_region(region)
    
    if binary_threshold is not None:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, img = cv2.threshold(gray, binary_threshold, 255, cv2.THRESH_BINARY)
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    
    best_match = None
    best_similarity = 0
    best_option_key = None
    
    for option_key in option_config["options"]:
        option = option_definitions[option_key]
        
        if "image" not in option:
            continue
        
        ref_img_path = MEDIA_FOLDER / "menu" / option["image"]
        
        try:
            ref_img = load_image(ref_img_path)
            
            if binary_threshold is not None:
                ref_gray = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)
                _, ref_img = cv2.threshold(ref_gray, binary_threshold, 255, cv2.THRESH_BINARY)
                ref_img = cv2.cvtColor(ref_img, cv2.COLOR_GRAY2BGR)
            
            is_match, similarity = compare_images_grayscale(img, ref_img, threshold=threshold)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = option
                best_option_key = option_key
        except Exception as e:
            print(f"  [Error loading reference image {option['image']}: {e}]")
            continue
    
    if best_match:
        print(f"  [Image matched to '{best_option_key}' (similarity: {best_similarity:.2f})]")
        return best_match
    
    first_option_key = option_config["options"][0]
    print(f"  [No good match found, using first option '{first_option_key}']")
    return option_definitions[first_option_key]

def announce_option_value(item_name, tab_name, sub_tab_name, config, is_submenu=False):
    """Detect and announce the current option value for an item"""
    detected_option = detect_option_value(item_name, tab_name, sub_tab_name, config, is_submenu)
    
    if detected_option:
        print(f"Option value: {detected_option['audio'].replace('.ogg', '')}")
        play_audio(detected_option["audio"], "menu", allow_interrupt=True)
        return True
    
    return False
