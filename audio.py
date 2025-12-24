import time
from pygame import mixer
from config import MEDIA_FOLDER

mixer.init()

def play_audio(audio_file, subfolder=None, allow_interrupt=False):
    if subfolder:
        audio_path = MEDIA_FOLDER / subfolder / audio_file
    else:
        audio_path = MEDIA_FOLDER / audio_file
    
    if not audio_path.exists():
        print(f"Audio file not found: {audio_file}")
        return
    
    try:
        if allow_interrupt and mixer.music.get_busy():
            mixer.music.stop()
        
        mixer.music.load(str(audio_path))
        mixer.music.play()
        
        if not allow_interrupt:
            while mixer.music.get_busy():
                time.sleep(0.05)
    except Exception as e:
        print(f"Error playing audio {audio_file}: {e}")

def play_audio_sequence(audio_files):
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

def play_health_alert(side):
    audio_path = MEDIA_FOLDER / "CA_health.ogg"
    if not audio_path.exists():
        print(f"Audio file not found: CA_health.ogg")
        return
    
    try:
        sound = mixer.Sound(str(audio_path))
        channel = sound.play()
        if side == "left":
            channel.set_volume(1.0, 0.0)
        else:
            channel.set_volume(0.0, 1.0)
        while channel.get_busy():
            time.sleep(0.05)
    except Exception as e:
        print(f"Error playing health alert: {e}")
