import time
from capture import capture_region
from image_processing import (
    compare_images_no_threshold, compare_names, compare_images, 
    compare_characters, check_control_color
)
from audio import play_audio_sequence
from config import (
    CONTROL_REGIONS, CONTROL_COLOR_REGIONS, RANK_REGIONS, NAME_REGIONS,
    DIVISION_REGIONS, MR_REGIONS, CHARACTER_REGIONS, CONTROL_SIMILARITY_THRESHOLD,
    MIN_RANK_THRESHOLD, MIN_DIVISION_THRESHOLD, MIN_MR_THRESHOLD, 
    MIN_CHARACTER_THRESHOLD, RANKS_WITH_DIVISIONS, COOLDOWN_PERIOD, VS_SCREEN_WAIT_TIME
)

def find_best_rank_match(captured_img, rank_images):
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
    best_match = None
    best_similarity = 0
    for division_name, division_img in division_images.items():
        similarity = compare_images_no_threshold(captured_img, division_img)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = division_name
    if best_similarity < MIN_DIVISION_THRESHOLD:
        return None, best_similarity
    return best_match, best_similarity

def find_best_mr_match(captured_img, mr_images):
    best_match = None
    best_similarity = 0
    for mr_value, mr_img in mr_images.items():
        similarity = compare_images(captured_img, mr_img)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = mr_value
    if best_similarity < MIN_MR_THRESHOLD:
        return None, best_similarity
    return best_match, best_similarity

def find_best_character_match(captured_img, character_images):
    best_match = None
    best_similarity = 0
    for character_name, character_img in character_images.items():
        similarity = compare_characters(captured_img, character_img)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = character_name
    if best_similarity < MIN_CHARACTER_THRESHOLD:
        return None, best_similarity
    return best_match, best_similarity

def detect_control_via_image(region, control_images):
    try:
        screen_img = capture_region(region)
        best_control = None
        best_similarity = 0
        for control_name, control_img in control_images.items():
            similarity = compare_images(screen_img, control_img)
            if similarity > best_similarity:
                best_similarity = similarity
                best_control = control_name
        
        if best_similarity >= 0.85:
            return best_control, best_similarity
        return None, best_similarity
    except Exception as e:
        print(f"  Error in image fallback detection: {e}")
        return None, 0.0

def handle_vs_screen_detection(current_time, last_audio_time, control_images, 
                               player_name_img, rank_images, division_images, mr_images, character_images):
    left_region = CONTROL_REGIONS[0]
    right_region = CONTROL_REGIONS[1]
    left_color_region = CONTROL_COLOR_REGIONS[0]
    right_color_region = CONTROL_COLOR_REGIONS[1]
    
    try:
        screen_img = capture_region(left_region)
        best_control = None
        best_similarity = 0
        for control_name, control_img in control_images.items():
            similarity = compare_images_no_threshold(screen_img, control_img)
            if similarity > best_similarity:
                best_similarity = similarity
                best_control = control_name
        
        if best_similarity < CONTROL_SIMILARITY_THRESHOLD:
            return False, None, last_audio_time
    except Exception as e:
        print(f"Error checking left control region: {e}")
        return False, None, last_audio_time
    
    vs_detected_right = False
    try:
        screen_img = capture_region(right_region)
        best_control = None
        best_similarity = 0
        for control_name, control_img in control_images.items():
            similarity = compare_images_no_threshold(screen_img, control_img)
            if similarity > best_similarity:
                best_similarity = similarity
                best_control = control_name
        
        if best_similarity >= CONTROL_SIMILARITY_THRESHOLD:
            vs_detected_right = True
    except Exception as e:
        print(f"Error checking right control region: {e}")
    
    print(f"\n{'='*60}")
    print(f"VS SCREEN DETECTED")
    if vs_detected_right:
        print(f"  Both sides detected")
    else:
        print(f"  Left side only")
    print(f"{'='*60}")
    print("Ctrl+C to stop")
    
    if current_time - last_audio_time < COOLDOWN_PERIOD:
        remaining = int(COOLDOWN_PERIOD - (current_time - last_audio_time))
        print(f"Cooldown active ({remaining}s remaining)")
        print(f"{'='*60}\n")
        return True, 'vs_screen', last_audio_time
    
    try:
        print(f"Waiting {VS_SCREEN_WAIT_TIME} second(s) to avoid screen blink...")
        time.sleep(VS_SCREEN_WAIT_TIME)
        
        try:
            left_screen_img = capture_region(left_region)
            best_similarity = 0
            for control_name, control_img in control_images.items():
                similarity = compare_images_no_threshold(left_screen_img, control_img)
                if similarity > best_similarity:
                    best_similarity = similarity
            
            if best_similarity < CONTROL_SIMILARITY_THRESHOLD:
                print("VS screen disappeared during wait, skipping...")
                print(f"{'='*60}\n")
                return True, 'vs_screen', last_audio_time
        except Exception as e:
            print(f"Error re-verifying left control region: {e}")
            return True, 'vs_screen', last_audio_time
        
        print("\nDetecting control schemes via color...")
        left_control = None
        right_control = None
        
        try:
            color_img = capture_region(left_color_region)
            left_control = check_control_color(color_img)
            if left_control:
                print(f"  Left: {left_control} [via color]")
            else:
                print(f"  Left: Color detection failed, trying image comparison...")
                left_control, sim = detect_control_via_image(left_region, control_images)
                if left_control:
                    print(f"  Left: {left_control} [via image, {sim*100:.1f}%]")
                else:
                    print(f"  Left: Image detection also failed, defaulting to Classic")
                    left_control = "Classic"
        except Exception as e:
            print(f"  Left: Color detection error: {e}")
            print(f"  Left: Trying image comparison fallback...")
            left_control, sim = detect_control_via_image(left_region, control_images)
            if left_control:
                print(f"  Left: {left_control} [via image, {sim*100:.1f}%]")
            else:
                print(f"  Left: All detection methods failed, defaulting to Classic")
                left_control = "Classic"
        
        if vs_detected_right:
            try:
                color_img = capture_region(right_color_region)
                right_control = check_control_color(color_img)
                if right_control:
                    print(f"  Right: {right_control} [via color]")
                else:
                    print(f"  Right: Color detection failed, trying image comparison...")
                    right_control, sim = detect_control_via_image(right_region, control_images)
                    if right_control:
                        print(f"  Right: {right_control} [via image, {sim*100:.1f}%]")
                    else:
                        print(f"  Right: Image detection also failed, using left side")
                        right_control = left_control
            except Exception as e:
                print(f"  Right: Color detection error: {e}")
                print(f"  Right: Trying image comparison fallback...")
                right_control, sim = detect_control_via_image(right_region, control_images)
                if right_control:
                    print(f"  Right: {right_control} [via image, {sim*100:.1f}%]")
                else:
                    print(f"  Right: All detection methods failed, using left side")
                    right_control = left_control
        
        print("\nUsing name detection...")
        opponent_side = None
        opponent_control = None
        
        try:
            left_name_img = capture_region(NAME_REGIONS[0])
            right_name_img = capture_region(NAME_REGIONS[1])
            
            left_name_similarity = compare_names(player_name_img, left_name_img)
            right_name_similarity = compare_names(player_name_img, right_name_img)
            
            print(f"Name similarity - Left side: {left_name_similarity * 100:.1f}% | Right side: {right_name_similarity * 100:.1f}%")
            
            if left_name_similarity > right_name_similarity:
                opponent_side = "right"
                opponent_control = right_control if right_control else left_control
                print(f"Player detected on LEFT, opponent on RIGHT")
                print(f"Opponent control: {opponent_control}")
            else:
                opponent_side = "left"
                opponent_control = left_control
                print(f"Player detected on RIGHT, opponent on LEFT")
                print(f"Opponent control: {opponent_control}")
        except Exception as e:
            print(f"Error in name detection: {e}")
            print(f"{'='*60}\n")
            return True, 'vs_screen', last_audio_time
        
        print("\nCapturing opponent character region...")
        opponent_character_region = CHARACTER_REGIONS[0] if opponent_side == "left" else CHARACTER_REGIONS[1]
        
        opponent_character = None
        try:
            opponent_character_img = capture_region(opponent_character_region)
            opponent_character, char_sim = find_best_character_match(opponent_character_img, character_images[opponent_side])
            if opponent_character:
                print(f"Opponent character: {opponent_character} ({char_sim * 100:.1f}%)")
            else:
                print(f"No character match found (best: {char_sim * 100:.1f}%)")
        except Exception as e:
            print(f"Error capturing character: {e}")
        
        print("\nCapturing opponent rank region...")
        opponent_rank_region = RANK_REGIONS[0] if opponent_side == "left" else RANK_REGIONS[1]
        
        try:
            opponent_rank_img = capture_region(opponent_rank_region)
            opponent_rank, opponent_sim = find_best_rank_match(opponent_rank_img, rank_images)
            print(f"Opponent rank: {opponent_rank} ({opponent_sim * 100:.1f}%)")
            
            division = None
            mr_value = None
            
            if opponent_rank == "Master":
                print(f"\nMaster rank detected, checking MR region...")
                try:
                    mr_region = MR_REGIONS[0] if opponent_side == "left" else MR_REGIONS[1]
                    mr_img = capture_region(mr_region)
                    mr_value, mr_sim = find_best_mr_match(mr_img, mr_images)
                    if mr_value:
                        print(f"MR detected: {mr_value} ({mr_sim * 100:.1f}%)")
                    else:
                        print(f"No MR match found (best: {mr_sim * 100:.1f}%), using base Master")
                except Exception as e:
                    print(f"Error capturing MR: {e}, using base Master")
            elif opponent_rank in RANKS_WITH_DIVISIONS and opponent_rank != "Unknown":
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
                audio_files = [f"{opponent_control}.ogg"]
                
                if opponent_character:
                    audio_files.append(f"characters/{opponent_character}.ogg")
                
                if opponent_rank == "Unknown":
                    audio_files.append("Unknown.ogg")
                    print(f"\nRank unknown, playing control + character + Unknown")
                elif opponent_rank == "Master" and mr_value:
                    audio_files.append(f"{mr_value}.ogg")
                elif opponent_rank in RANKS_WITH_DIVISIONS and division:
                    audio_files.append(f"{opponent_rank}{division}.ogg")
                else:
                    audio_files.append(f"{opponent_rank}.ogg")
                
                print(f"\nPlaying audio sequence: {' -> '.join(audio_files)}")
                play_audio_sequence(audio_files)
                new_last_audio_time = current_time
                
                print("Health monitoring reset for next match")
                print(f"{'='*60}\n")
                return True, 'vs_screen', new_last_audio_time
            else:
                print(f"\nSkipping audio - opponent control not detected")
                print(f"{'='*60}\n")
        except Exception as e:
            print(f"Error capturing opponent rank: {e}")
            print(f"{'='*60}\n")
    except Exception as e:
        print(f"Error processing ranks: {e}")
        print(f"{'='*60}\n")
    
    return True, 'vs_screen', last_audio_time
