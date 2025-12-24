import json
from pathlib import Path
import sys

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
VS_SCREEN_WAIT_TIME = 0.5
COOLDOWN_PERIOD = 15
MATCH_CHECK_INTERVAL = 2
HEALTH_CHECK_INTERVAL = 0.3
HEALTH_CONFIRMATION_CHECKS = 3
HEALTH_CONFIRMATION_DELAY = 0.1
MENU_CONFIRMATION_CHECKS = 3
MENU_CONFIRMATION_DELAY = 0.5
MATCH_END_CONFIRMATION_DELAY = 2

CONTROL_SIMILARITY_THRESHOLD = 0.98
MIN_RANK_THRESHOLD = 0.80
MIN_DIVISION_THRESHOLD = 0.83
MIN_MR_THRESHOLD = 0.93
NAME_THRESHOLD = 190

CONTROL_REGIONS = [
    {"top": 834, "left": 56, "width": 35, "height": 31, "side": "left"},
    {"top": 834, "left": 1830, "width": 35, "height": 31, "side": "right"}
]

CONTROL_COLOR_REGIONS = [
    {"top": 850, "left": 61, "width": 3, "height": 3, "side": "left"},
    {"top": 849, "left": 1834, "width": 3, "height": 3, "side": "right"}
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

RANKS = [
    "NewChallenger", "Rookie", "Iron", "Bronze", "Silver", "Gold", 
    "Platinum", "Diamond", "Master", "HighMaster", 
    "GrandMaster", "UltimateMaster", "Legend"
]

RANKS_WITH_DIVISIONS = ["Rookie", "Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond"]
DIVISIONS = ["One", "Two", "Three", "Four", "Five"]
MR_VALUES = ["1000", "1100", "1200", "1300", "1400", "1500"]
CONTROLS = ["Classic", "Modern"]

training_menu_config = None

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
