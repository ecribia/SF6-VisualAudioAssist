import cv2
import numpy as np
from config import NAME_THRESHOLD

def load_image_from_path(image_path):
    if not image_path.exists():
        return None
    img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if len(img.shape) == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img

def load_image(image_path):
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Failed to load image: {image_path}")
    if len(img.shape) == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img

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

def compare_names(img1, img2):
    if img1.shape != img2.shape:
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
    
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    _, binary2 = cv2.threshold(gray2, NAME_THRESHOLD, 255, cv2.THRESH_BINARY)
    
    mse = np.mean((img1.astype(float) - binary2.astype(float)) ** 2)
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

def check_control_color(img):
    h, w = img.shape[:2]
    center_y = h // 2
    center_x = w // 2
    center = img[center_y-1:center_y+2, center_x-1:center_x+2]
    
    if center.size == 0:
        print("  [Color detection: center region is empty]")
        return None
    
    total_pixels = center.shape[0] * center.shape[1]
    
    modern_mask = (
        (center[:,:,0] >= 0) & (center[:,:,0] <= 35) &
        (center[:,:,1] >= 25) & (center[:,:,1] <= 70) &
        (center[:,:,2] >= 90) & (center[:,:,2] <= 165)
    )
    modern_matches = np.sum(modern_mask)
    
    classic_mask = (
        (center[:,:,0] >= 100) & (center[:,:,0] <= 140) &
        (center[:,:,1] >= 0) & (center[:,:,1] <= 12) &
        (center[:,:,2] >= 45) & (center[:,:,2] <= 95)
    )
    classic_matches = np.sum(classic_mask)
    
    center_pixel = center[1, 1]
    print(f"  [Color check: BGR={center_pixel}, Modern={modern_matches}/{total_pixels}, Classic={classic_matches}/{total_pixels}]")
    
    threshold = 3
    
    if modern_matches >= threshold:
        return 'Modern'
    elif classic_matches >= threshold:
        return 'Classic'
    
    print(f"  [Color detection failed: neither threshold met (need {threshold:.1f})]")
    return None

def check_health_color(img):
    h, w = img.shape[:2]
    center = img[h//2-3:h//2+4, w//2-3:w//2+4]
    total_pixels = center.shape[0] * center.shape[1]
    
    red_mask = (
        (center[:,:,2] >= 215) & (center[:,:,2] <= 220) & 
        (center[:,:,1] >= 26) & (center[:,:,1] <= 30) & 
        (center[:,:,0] >= 93) & (center[:,:,0] <= 97)
    )
    red_matches = np.sum(red_mask)
    
    yellow_mask = (
        (center[:,:,2] >= 250) & (center[:,:,2] <= 253) & 
        (center[:,:,1] >= 246) & (center[:,:,1] <= 250) & 
        (center[:,:,0] >= 105) & (center[:,:,0] <= 110)
    )
    yellow_matches = np.sum(yellow_mask)
    
    blue_mask = (
        (center[:,:,2] >= 12) & (center[:,:,2] <= 15) & 
        (center[:,:,1] >= 105) & (center[:,:,1] <= 110) & 
        (center[:,:,0] >= 184) & (center[:,:,0] <= 188)
    )
    blue_matches = np.sum(blue_mask)
    
    threshold = total_pixels * 0.8
    
    if red_matches >= threshold:
        return 'red'
    elif yellow_matches >= threshold:
        return 'yellow'
    elif blue_matches >= threshold:
        return 'blue'
    return None
