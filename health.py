import time
from capture import capture_region
from image_processing import check_health_color
from audio import play_health_alert
from config import (
    HEALTH_REGIONS, HEALTH_CHECK_INTERVAL, MATCH_CHECK_INTERVAL,
    HEALTH_CONFIRMATION_CHECKS, HEALTH_CONFIRMATION_DELAY,
    MATCH_END_CONFIRMATION_DELAY
)

def check_match_started():
    try:
        p1_region = HEALTH_REGIONS[0]
        health_img = capture_region(p1_region)
        color = check_health_color(health_img)
        if color == 'red':
            return True
    except Exception as e:
        print(f"Error checking match start: {e}")
    return False

def check_health_bars(health_alert_states, match_end_check_pending, match_end_check_time):
    left_health_present = False
    right_health_present = False
    
    for region in HEALTH_REGIONS:
        side = region["side"]
        try:
            health_img = capture_region(region)
            color = check_health_color(health_img)
            
            if side == "left":
                if color in ['red', 'yellow']:
                    left_health_present = True
                if color in ['blue', 'yellow']:
                    right_health_present = True
            
            if color == 'yellow':
                confirmed = True
                for i in range(HEALTH_CONFIRMATION_CHECKS - 1):
                    time.sleep(HEALTH_CONFIRMATION_DELAY)
                    health_img_confirm = capture_region(region)
                    color_confirm = check_health_color(health_img_confirm)
                    if color_confirm != 'yellow':
                        confirmed = False
                        print(f"False positive filtered on {side.upper()} side (confirmation {i+1} failed: {color_confirm})")
                        break
                
                if confirmed and not health_alert_states[side]["alert_played"]:
                    print(f"\nCritical health CONFIRMED on {side.upper()} side!")
                    play_health_alert(side)
                    health_alert_states[side]["alert_played"] = True
            else:
                base_color = 'red' if side == 'left' else 'blue'
                if color == base_color:
                    if health_alert_states[side]["alert_played"]:
                        print(f"Health reset detected on {side.upper()} side - ready for next alert")
                        health_alert_states[side]["alert_played"] = False
        except Exception as e:
            print(f"Error checking {side} health bar: {e}")
    
    if left_health_present or right_health_present:
        if match_end_check_pending:
            print("Health bars detected again - match still active")
            match_end_check_pending = False
        return False, match_end_check_pending, match_end_check_time
    
    if not match_end_check_pending:
        match_end_check_pending = True
        match_end_check_time = time.time()
        print(f"Health bars not detected - confirming match end over {MATCH_END_CONFIRMATION_DELAY} seconds...")
    elif time.time() - match_end_check_time >= MATCH_END_CONFIRMATION_DELAY:
        print("\nMatch ended - Health monitoring deactivated\n")
        return True, match_end_check_pending, match_end_check_time
    
    return False, match_end_check_pending, match_end_check_time

def handle_health_monitoring(current_time, health_state):
    if not health_state['active']:
        if current_time - health_state['last_match_check_time'] >= MATCH_CHECK_INTERVAL:
            if check_match_started():
                print("\n" + "="*60)
                print("MATCH STARTED - Health monitoring activated")
                print("="*60 + "\n")
                health_state['active'] = True
                health_state['last_health_check_time'] = current_time
                health_state['last_match_check_time'] = current_time
                return 'vs_screen'
            health_state['last_match_check_time'] = current_time
    else:
        if current_time - health_state['last_health_check_time'] >= HEALTH_CHECK_INTERVAL:
            match_ended, pending, end_time = check_health_bars(
                health_state['alert_states'],
                health_state['match_end_check_pending'],
                health_state['match_end_check_time']
            )
            health_state['match_end_check_pending'] = pending
            health_state['match_end_check_time'] = end_time
            
            if match_ended:
                health_state['active'] = False
                health_state['alert_states']["left"]["alert_played"] = False
                health_state['alert_states']["right"]["alert_played"] = False
                health_state['match_end_check_pending'] = False
                return 'idle'
            health_state['last_health_check_time'] = current_time
    
    return None
