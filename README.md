How to Use This System
Step 1: Install Dependencies

pip install beautifulsoup4 requests

You'll also need ffmpeg installed on your system.

    sudo apt-get install ffmpeg

Step 2: Configure Paths

Update these variables in the script:
python

TRANSCRIPTS_DIR = "adventure_time_transcripts"  # Where your transcripts are
VIDEOS_DIR = "/path/to/your/adventure/time/episodes"  # Your video files
OUTPUT_DIR = "bmo_audio_clips"  # Where BMO clips will be saved

Step 3: Run the Script
bash

python3 bmo_extractor.py

Features
1. Dialogue Extraction

    Identifies BMO's dialogue using multiple patterns

    Handles different transcript formats

    Saves metadata in JSON format

2. Video Matching

    Automatically matches transcript files to video files

    Supports multiple video formats (mp4, mkv, avi, etc.)

    Fuzzy matching for filename variations

3. Audio Extraction

    Uses ffmpeg to extract precise audio clips

    Estimates timing based on dialogue position

    Adds buffer to ensure complete sentences

4. Timing Correction Tool

    Creates an HTML tool for manually correcting timestamps

    Watch episodes and enter exact timestamps

    Export corrected timings as JSON

5. Output Structure
text

bmo_audio_clips/
├── bmo_dialogues_metadata.json
├── timing_corrector.html
├── Season_1_(2010)/
│   ├── Slumber_Party_Panic_BMO_001_Hello_everyone.mp3
│   ├── Slumber_Party_Panic_BMO_002_Im_so_excited.mp3
│   └── ...
├── Season_2_(2010-2011)/
│   └── ...
└── Season_3_(2011-2012)/
    └── ...

Tips for Best Results

    Name your video files consistently with the episode titles from the transcripts

    Use the timing correction tool for accurate timestamps - the automatic timing is just an estimate

    Start with a few episodes to test the system before running on all episodes

    Check the metadata JSON to verify BMO's dialogue was correctly identified

    Consider creating a spreadsheet to track which episodes you've processed
