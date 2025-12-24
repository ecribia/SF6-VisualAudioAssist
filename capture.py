import numpy as np
import cv2
import platform
import subprocess
import glob
import os

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

_capture_method = None
_grim_path = None

def capture_region_windows(region):
    import mss
    with mss.mss() as sct:
        screenshot = sct.grab(region)
        img = np.array(screenshot)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img

def capture_region_linux(region):
    global _capture_method, _grim_path
    
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
        result = subprocess.run([_grim_path, '-g', geometry, '-'], 
                                capture_output=True, check=True, timeout=2)
        img_array = np.frombuffer(result.stdout, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return img
    
    # Try mss first
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
            result = subprocess.run([grim_path, '-g', geometry, '-'], 
                                    capture_output=True, check=True, timeout=2)
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
