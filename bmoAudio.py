import os
import re
import json
import subprocess
from pathlib import Path
from datetime import timedelta
import xml.etree.ElementTree as ET

class BMOTranscriptExtractor:
    def __init__(self, transcripts_dir, videos_dir, output_dir):
        """
        Initialize the BMO dialogue extractor
        
        Args:
            transcripts_dir: Directory containing the downloaded transcript text files
            videos_dir: Directory containing your Adventure Time video files
            output_dir: Directory where BMO audio clips will be saved
        """
        self.transcripts_dir = Path(transcripts_dir)
        self.videos_dir = Path(videos_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # BMO's various names/aliases in transcripts
        self.bmo_patterns = [
            r'\bBMO\b',
            r'\bBMO\s*:\s*',
            r'\bBeemo\b',
            r'\(BMO\)',
            r'\[BMO\]',
            r'^BMO[,!?.]?\s+',
        ]
        
        # Compile regex patterns
        self.bmo_regex = re.compile('|'.join(self.bmo_patterns), re.IGNORECASE)
        
        # Dialogue patterns - looking for lines that start with character names
        self.dialogue_pattern = re.compile(r'^([A-Z][A-Za-z\s]+?):\s*(.+)$', re.MULTILINE)
        
    def extract_bmo_dialogues_from_transcript(self, transcript_file):
        """
        Extract all BMO dialogues from a single transcript file
        
        Returns:
            List of dictionaries with dialogue and potential timing info
        """
        with open(transcript_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        bmo_dialogues = []
        lines = content.split('\n')
        
        # Try different parsing strategies
        for i, line in enumerate(lines):
            # Strategy 1: Look for lines starting with BMO:
            if re.match(r'^BMO\s*:', line, re.IGNORECASE):
                dialogue = re.sub(r'^BMO\s*:\s*', '', line, flags=re.IGNORECASE).strip()
                if dialogue:
                    bmo_dialogues.append({
                        'dialogue': dialogue,
                        'line_number': i + 1,
                        'context': lines[max(0, i-2):min(len(lines), i+3)]
                    })
            
            # Strategy 2: Look for BMO's name anywhere in the line followed by dialogue
            elif self.bmo_regex.search(line):
                # Try to extract just the dialogue part
                cleaned_line = self.bmo_regex.sub('', line).strip()
                if cleaned_line and len(cleaned_line) > 5:  # Avoid very short lines
                    bmo_dialogues.append({
                        'dialogue': cleaned_line,
                        'line_number': i + 1,
                        'context': lines[max(0, i-2):min(len(lines), i+3)]
                    })
        
        return bmo_dialogues
    
    def find_matching_video(self, episode_name):
        """
        Find the video file that matches an episode name
        
        Args:
            episode_name: Name of the episode (from transcript filename)
        
        Returns:
            Path to video file or None
        """
        # Clean up episode name for matching
        search_name = re.sub(r'[_\s]+', ' ', episode_name).strip()
        search_name = re.sub(r'\.txt$', '', search_name)
        
        # Common video extensions
        video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.m4v']
        
        # Search in videos directory
        for ext in video_extensions:
            # Try exact match
            video_path = self.videos_dir / f"{search_name}{ext}"
            if video_path.exists():
                return video_path
            
            # Try case-insensitive match
            for video_file in self.videos_dir.glob(f"*{ext}"):
                if search_name.lower() in video_file.stem.lower():
                    return video_file
        
        return None
    
    def estimate_timestamp(self, dialogue, full_transcript):
        """
        Estimate where in the episode this dialogue occurs
        This is a best-guess approach - you may need manual adjustment
        """
        # This is a placeholder - you'll need to implement actual timestamp
        # extraction or use manual alignment
        
        # For now, return a rough estimate based on dialogue position
        transcript_lines = full_transcript.split('\n')
        total_lines = len(transcript_lines)
        
        try:
            # Find approximate position
            for i, line in enumerate(transcript_lines):
                if dialogue in line:
                    # Rough estimate: assume 30-minute episode with ~1000 lines
                    # Each line ~1.8 seconds
                    seconds = (i / total_lines) * 22 * 60  # 22-minute episode
                    return timedelta(seconds=seconds)
        except:
            pass
        
        return None
    
    def extract_audio_clip(self, video_path, start_time, duration, output_path):
        """
        Extract audio clip using ffmpeg
        
        Args:
            video_path: Path to video file
            start_time: When to start extraction (timedelta or seconds)
            duration: How long to extract (seconds)
            output_path: Where to save the audio clip
        """
        # Convert timedelta to seconds if needed
        if isinstance(start_time, timedelta):
            start_seconds = start_time.total_seconds()
        else:
            start_seconds = float(start_time)
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build ffmpeg command
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-ss', str(start_seconds),
            '-t', str(duration),
            '-vn',  # No video
            '-acodec', 'mp3',  # Output as MP3
            '-ar', '44100',  # Audio sample rate
            '-ac', '2',  # Stereo
            '-y',  # Overwrite output file
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e.stderr.decode()}")
            return False
    
    def process_all_transcripts(self):
        """
        Main method to process all transcripts and extract BMO dialogues
        """
        # Track all BMO dialogues
        all_bmo_lines = []
        
        # Process each transcript file
        for transcript_file in sorted(self.transcripts_dir.rglob("*.txt")):
            episode_name = transcript_file.stem
            print(f"\nProcessing: {episode_name}")
            
            # Extract BMO dialogues
            dialogues = self.extract_bmo_dialogues_from_transcript(transcript_file)
            
            if dialogues:
                print(f"  Found {len(dialogues)} BMO lines")
                
                # Find matching video
                video_path = self.find_matching_video(episode_name)
                
                if video_path:
                    print(f"  Found video: {video_path.name}")
                    
                    # Read full transcript for timestamp estimation
                    with open(transcript_file, 'r', encoding='utf-8') as f:
                        full_transcript = f.read()
                    
                    # Process each dialogue
                    for i, dialogue_data in enumerate(dialogues):
                        dialogue = dialogue_data['dialogue']
                        
                        # Create output filename
                        safe_dialogue = re.sub(r'[^\w\s-]', '', dialogue)[:50]
                        output_filename = f"{episode_name}_BMO_{i+1:03d}_{safe_dialogue}.mp3"
                        output_path = self.output_dir / episode_name / output_filename
                        
                        # Estimate timing (you'll need to adjust this)
                        # For now, assume each line takes about 3 seconds
                        estimated_time = self.estimate_timestamp(dialogue, full_transcript)
                        
                        if estimated_time:
                            # Add dialogue to tracking list
                            dialogue_entry = {
                                'episode': episode_name,
                                'dialogue': dialogue,
                                'estimated_time': str(estimated_time),
                                'video_file': str(video_path),
                                'output_file': str(output_path)
                            }
                            all_bmo_lines.append(dialogue_entry)
                            
                            print(f"    Line {i+1}: {dialogue[:50]}...")
                else:
                    print(f"  Warning: No video found for {episode_name}")
            else:
                print(f"  No BMO lines found")
        
        # Save metadata
        metadata_file = self.output_dir / "bmo_dialogues_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(all_bmo_lines, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Found {len(all_bmo_lines)} total BMO lines across all episodes")
        print(f"Metadata saved to: {metadata_file}")
        
        return all_bmo_lines

class BMOAudioExtractor(BMOTranscriptExtractor):
    """
    Extended class that actually extracts the audio clips
    """
    
    def extract_all_audio(self, manual_timing_file=None):
        """
        Extract audio for all BMO dialogues
        
        Args:
            manual_timing_file: Optional JSON file with manually corrected timestamps
        """
        # First get all dialogues
        all_dialogues = self.process_all_transcripts()
        
        # Load manual timings if provided
        manual_timings = {}
        if manual_timing_file and os.path.exists(manual_timing_file):
            with open(manual_timing_file, 'r') as f:
                for item in json.load(f):
                    key = f"{item['episode']}_{item['dialogue'][:30]}"
                    manual_timings[key] = item['timestamp']
        
        print("\n🎬 Extracting audio clips...")
        
        for i, dialogue_data in enumerate(all_dialogues):
            episode = dialogue_data['episode']
            video_path = Path(dialogue_data['video_file'])
            dialogue = dialogue_data['dialogue']
            output_path = Path(dialogue_data['output_file'])
            
            # Create unique key for manual timing lookup
            lookup_key = f"{episode}_{dialogue[:30]}"
            
            # Get timestamp (use manual if available, otherwise estimated)
            if lookup_key in manual_timings:
                start_time = manual_timings[lookup_key]
                print(f"\n[{i+1}/{len(all_dialogues)}] Using manual timing for: {dialogue[:50]}...")
            else:
                # Parse estimated time from string back to seconds
                time_str = dialogue_data['estimated_time']
                h, m, s = map(int, time_str.split(':'))
                start_time = timedelta(hours=h, minutes=m, seconds=s)
                print(f"\n[{i+1}/{len(all_dialogues)}] Using estimated timing for: {dialogue[:50]}...")
            
            # Estimate duration (average speaking rate: ~150 words per minute)
            word_count = len(dialogue.split())
            duration = max(2, word_count * 0.4)  # Rough estimate: 0.4 seconds per word
            
            # Extract audio
            success = self.extract_audio_clip(
                video_path,
                start_time,
                duration + 0.5,  # Add small buffer
                output_path
            )
            
            if success:
                print(f"  ✓ Saved to: {output_path}")
            else:
                print(f"  ✗ Failed to extract audio")
        
        print(f"\n✅ Audio extraction complete! Files saved in: {self.output_dir}")

def create_timing_correction_tool(transcripts_dir, output_dir):
    """
    Create a helper tool for manually correcting timestamps
    """
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>BMO Dialogue Timing Corrector</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .dialogue-item { 
            border: 1px solid #ccc; 
            margin: 10px 0; 
            padding: 15px;
            border-radius: 5px;
        }
        .dialogue-text { font-size: 16px; margin-bottom: 10px; }
        .timestamp-input { 
            padding: 5px;
            font-size: 14px;
            width: 200px;
        }
        .save-btn {
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            margin: 20px 0;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        .episode-header {
            background-color: #f0f0f0;
            padding: 10px;
            margin: 20px 0 10px 0;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <h1>BMO Dialogue Timing Corrector</h1>
    <p>Watch each episode and enter the timestamp (in MM:SS format) when BMO starts speaking each line.</p>
    
    <button class="save-btn" onclick="saveTimings()">Save All Timings</button>
    <button class="save-btn" onclick="exportJSON()">Export as JSON</button>
    
    <div id="content"></div>
    
    <script>
        let dialogues = [];
        
        function loadDialogues() {
            // This will be populated by the Python script
            const dialogueData = DIALOGUE_PLACEHOLDER;
            
            const content = document.getElementById('content');
            let currentEpisode = '';
            
            dialogueData.forEach((item, index) => {
                if (item.episode !== currentEpisode) {
                    currentEpisode = item.episode;
                    const header = document.createElement('div');
                    header.className = 'episode-header';
                    header.textContent = currentEpisode;
                    content.appendChild(header);
                }
                
                const div = document.createElement('div');
                div.className = 'dialogue-item';
                div.innerHTML = `
                    <div class="dialogue-text">${item.dialogue}</div>
                    <input type="text" class="timestamp-input" id="time_${index}" 
                           placeholder="MM:SS" value="${item.estimated_time || ''}">
                    <button onclick="playPreview(${index})">Preview</button>
                `;
                content.appendChild(div);
            });
        }
        
        function saveTimings() {
            const timings = [];
            dialogues.forEach((item, index) => {
                const input = document.getElementById(`time_${index}`);
                if (input.value) {
                    timings.push({
                        episode: item.episode,
                        dialogue: item.dialogue,
                        timestamp: input.value
                    });
                }
            });
            
            localStorage.setItem('bmoTimings', JSON.stringify(timings));
            alert('Timings saved to browser!');
        }
        
        function exportJSON() {
            const timings = JSON.parse(localStorage.getItem('bmoTimings') || '[]');
            const dataStr = JSON.stringify(timings, null, 2);
            const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
            
            const exportFileDefaultName = 'bmo_timings.json';
            const linkElement = document.createElement('a');
            linkElement.setAttribute('href', dataUri);
            linkElement.setAttribute('download', exportFileDefaultName);
            linkElement.click();
        }
        
        // Load dialogues when page loads
        window.onload = loadDialogues;
    </script>
</body>
</html>
    """
    
    # Get all dialogues first
    extractor = BMOTranscriptExtractor(transcripts_dir, "", output_dir)
    all_dialogues = extractor.process_all_transcripts()
    
    # Replace placeholder with actual dialogue data
    html_content = html_content.replace(
        'DIALOGUE_PLACEHOLDER',
        json.dumps(all_dialogues, indent=2)
    )
    
    # Save HTML file
    html_path = Path(output_dir) / "timing_corrector.html"
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Timing correction tool created at: {html_path}")
    return html_path

# Main execution script
if __name__ == "__main__":
    # Configuration - UPDATE THESE PATHS
    TRANSCRIPTS_DIR = "adventure_time_transcripts"  # Your transcripts folder
    VIDEOS_DIR = "/path/to/your/adventure/time/episodes"  # Your video files
    OUTPUT_DIR = "bmo_audio_clips"  # Where to save BMO clips
    
    print("🎮 BMO Dialogue Extractor")
    print("="*50)
    print("1. Extract BMO dialogues only (metadata)")
    print("2. Extract BMO dialogues and attempt audio extraction")
    print("3. Create timing correction tool")
    print("4. Full pipeline with manual timing")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    if choice == "1":
        extractor = BMOTranscriptExtractor(TRANSCRIPTS_DIR, VIDEOS_DIR, OUTPUT_DIR)
        extractor.process_all_transcripts()
        
    elif choice == "2":
        extractor = BMOAudioExtractor(TRANSCRIPTS_DIR, VIDEOS_DIR, OUTPUT_DIR)
        extractor.extract_all_audio()
        
    elif choice == "3":
        create_timing_correction_tool(TRANSCRIPTS_DIR, OUTPUT_DIR)
        
    elif choice == "4":
        print("\nStep 1: Extract BMO dialogues")
        extractor = BMOTranscriptExtractor(TRANSCRIPTS_DIR, VIDEOS_DIR, OUTPUT_DIR)
        extractor.process_all_transcripts()
        
        print("\nStep 2: Create timing correction tool")
        create_timing_correction_tool(TRANSCRIPTS_DIR, OUTPUT_DIR)
        
        print("\n📝 Next steps:")
        print("1. Open the timing_corrector.html file in your browser")
        print("2. Watch each episode and enter the timestamps for BMO's lines")
        print("3. Export the timings as JSON")
        print("4. Run option 2 with the exported JSON file")