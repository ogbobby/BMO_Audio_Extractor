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
        video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.m4v', '.webm']
        
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
                    # Rough estimate: assume 22-minute episode with ~1000 lines
                    # Each line ~1.32 seconds
                    seconds = (i / total_lines) * 22 * 60  # 22-minute episode
                    return seconds  # Return as float seconds instead of timedelta
        except:
            pass
        
        return 0.0
    
    def extract_audio_clip(self, video_path, start_time, duration, output_path):
        """
        Extract audio clip using ffmpeg
        
        Args:
            video_path: Path to video file
            start_time: When to start extraction (seconds as float)
            duration: How long to extract (seconds)
            output_path: Where to save the audio clip
        """
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build ffmpeg command
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-ss', str(start_time),
            '-t', str(duration),
            '-vn',  # No video
            '-acodec', 'libmp3lame',  # Output as MP3
            '-ar', '44100',  # Audio sample rate
            '-ac', '2',  # Stereo
            '-y',  # Overwrite output file
            str(output_path)
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"  FFmpeg error: {e.stderr}")
            return False
        except FileNotFoundError:
            print("  Error: ffmpeg not found. Please install ffmpeg and ensure it's in your PATH")
            return False
    
    def process_all_transcripts(self):
        """
        Main method to process all transcripts and extract BMO dialogues
        """
        # Track all BMO dialogues
        all_bmo_lines = []
        
        # Process each transcript file
        transcript_files = list(self.transcripts_dir.rglob("*.txt"))
        print(f"Found {len(transcript_files)} transcript files")
        
        for transcript_file in sorted(transcript_files):
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
                        safe_dialogue = re.sub(r'\s+', '_', safe_dialogue.strip())
                        output_filename = f"{episode_name}_BMO_{i+1:03d}_{safe_dialogue}.mp3"
                        output_path = self.output_dir / episode_name / output_filename
                        
                        # Estimate timing
                        estimated_time = self.estimate_timestamp(dialogue, full_transcript)
                        
                        # Add dialogue to tracking list
                        dialogue_entry = {
                            'episode': episode_name,
                            'dialogue': dialogue,
                            'estimated_time': estimated_time,
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
    
    def parse_timestamp(self, time_str):
        """
        Parse various timestamp formats to seconds as float
        
        Args:
            time_str: Timestamp string in various formats
                     "HH:MM:SS.ms", "MM:SS.ms", or just seconds as string
        
        Returns:
            float: Time in seconds
        """
        if isinstance(time_str, (int, float)):
            return float(time_str)
        
        time_str = str(time_str).strip()
        
        try:
            # Try to parse as simple float first
            return float(time_str)
        except ValueError:
            pass
        
        try:
            # Handle format like "0:00:52.367491" or "00:52.367491"
            parts = time_str.split(':')
            
            if len(parts) == 3:  # HH:MM:SS.ms
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
            elif len(parts) == 2:  # MM:SS.ms
                m, s = parts
                return int(m) * 60 + float(s)
            else:
                return 0.0
        except (ValueError, IndexError):
            print(f"  Warning: Could not parse timestamp '{time_str}'")
            return 0.0
    
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
            with open(manual_timing_file, 'r', encoding='utf-8') as f:
                for item in json.load(f):
                    key = f"{item['episode']}_{item['dialogue'][:30]}"
                    manual_timings[key] = item['timestamp']
        
        print(f"\n🎬 Extracting audio clips for {len(all_dialogues)} BMO lines...")
        
        successful = 0
        failed = 0
        
        for i, dialogue_data in enumerate(all_dialogues):
            episode = dialogue_data['episode']
            video_path = Path(dialogue_data['video_file'])
            dialogue = dialogue_data['dialogue']
            output_path = Path(dialogue_data['output_file'])
            
            # Create unique key for manual timing lookup
            lookup_key = f"{episode}_{dialogue[:30]}"
            
            # Get timestamp (use manual if available, otherwise estimated)
            if lookup_key in manual_timings:
                start_time = self.parse_timestamp(manual_timings[lookup_key])
                print(f"\n[{i+1}/{len(all_dialogues)}] Using manual timing ({start_time:.2f}s) for: {dialogue[:50]}...")
            else:
                start_time = float(dialogue_data['estimated_time'])
                print(f"\n[{i+1}/{len(all_dialogues)}] Using estimated timing ({start_time:.2f}s) for: {dialogue[:50]}...")
            
            # Estimate duration based on dialogue length
            word_count = len(dialogue.split())
            # Average speaking rate: ~150 words per minute = 2.5 words per second
            # Add 0.5 seconds buffer at start and end
            duration = max(1.5, (word_count / 2.5) + 1.0)
            
            # Check if video file exists
            if not video_path.exists():
                print(f"  ✗ Video file not found: {video_path}")
                failed += 1
                continue
            
            # Extract audio
            print(f"  Extracting {duration:.1f}s clip...")
            success = self.extract_audio_clip(
                video_path,
                start_time,
                duration,
                output_path
            )
            
            if success:
                print(f"  ✓ Saved to: {output_path}")
                successful += 1
            else:
                print(f"  ✗ Failed to extract audio")
                failed += 1
        
        print(f"\n{'='*50}")
        print(f"✅ AUDIO EXTRACTION COMPLETE")
        print(f"{'='*50}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Total: {successful + failed}")
        print(f"\nFiles saved in: {self.output_dir}")

def create_timing_correction_tool(transcripts_dir, output_dir):
    """
    Create a helper tool for manually correcting timestamps
    """
    # First get all dialogues
    extractor = BMOTranscriptExtractor(transcripts_dir, "", output_dir)
    all_dialogues = extractor.process_all_transcripts()
    
    # Format dialogues for the HTML tool
    formatted_dialogues = []
    for d in all_dialogues:
        # Format estimated time as MM:SS.ms
        est_time = float(d['estimated_time'])
        minutes = int(est_time // 60)
        seconds = est_time % 60
        time_str = f"{minutes:02d}:{seconds:06.3f}"
        
        formatted_dialogues.append({
            'episode': d['episode'],
            'dialogue': d['dialogue'],
            'estimated_time': time_str
        })
    
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>BMO Dialogue Timing Corrector</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .controls {
            position: sticky;
            top: 0;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            z-index: 100;
        }
        .dialogue-item { 
            border: 1px solid #ddd; 
            margin: 10px 0; 
            padding: 15px;
            border-radius: 8px;
            background-color: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        .dialogue-text { 
            font-size: 16px; 
            margin-bottom: 10px;
            color: #333;
            font-weight: 500;
        }
        .timestamp-input { 
            padding: 8px;
            font-size: 14px;
            width: 120px;
            border: 2px solid #ddd;
            border-radius: 4px;
            margin-right: 10px;
        }
        .timestamp-input:focus {
            border-color: #4CAF50;
            outline: none;
        }
        .save-btn {
            background-color: #4CAF50;
            color: white;
            padding: 12px 24px;
            margin: 10px 5px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
        }
        .save-btn:hover {
            background-color: #45a049;
        }
        .export-btn {
            background-color: #2196F3;
            color: white;
            padding: 12px 24px;
            margin: 10px 5px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
        }
        .export-btn:hover {
            background-color: #1976D2;
        }
        .episode-header {
            background-color: #e3f2fd;
            padding: 12px;
            margin: 30px 0 15px 0;
            font-weight: bold;
            font-size: 18px;
            border-radius: 6px;
            border-left: 5px solid #2196F3;
        }
        .episode-header:first-of-type {
            margin-top: 0;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            margin-left: 10px;
        }
        .status-corrected {
            background-color: #c8e6c9;
            color: #2e7d32;
        }
        .status-pending {
            background-color: #fff3e0;
            color: #e65100;
        }
        .search-box {
            padding: 10px;
            width: 300px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            margin-right: 10px;
        }
        .stats {
            display: inline-block;
            margin-left: 20px;
            color: #666;
        }
        .copy-btn {
            background-color: #ff9800;
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-left: 10px;
        }
        .copy-btn:hover {
            background-color: #f57c00;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎮 BMO Dialogue Timing Corrector</h1>
        <p>Watch each episode and enter the timestamp (in MM:SS.ms format, e.g., "05:23.5") when BMO starts speaking.</p>
        
        <div class="controls">
            <input type="text" class="search-box" id="search" placeholder="Search episodes or dialogue..." onkeyup="filterDialogues()">
            <button class="save-btn" onclick="saveTimings()">💾 Save All Timings</button>
            <button class="export-btn" onclick="exportJSON()">📤 Export as JSON</button>
            <button class="export-btn" onclick="copyTimingsToClipboard()">📋 Copy to Clipboard</button>
            <span class="stats" id="stats"></span>
        </div>
        
        <div id="content"></div>
    </div>

    <script>
        let dialogues = """ + json.dumps(formatted_dialogues, indent=2) + """;
        let correctedTimings = JSON.parse(localStorage.getItem('bmoTimings') || '{}');
        
        function formatTime(seconds) {
            if (!seconds) return '';
            const minutes = Math.floor(seconds / 60);
            const secs = (seconds % 60).toFixed(3);
            return `${minutes.toString().padStart(2, '0')}:${secs.padStart(6, '0')}`;
        }
        
        function parseTime(timeStr) {
            if (!timeStr) return 0;
            const parts = timeStr.split(':');
            if (parts.length === 2) {
                return parseInt(parts[0]) * 60 + parseFloat(parts[1]);
            }
            return 0;
        }
        
        function loadDialogues() {
            const content = document.getElementById('content');
            let currentEpisode = '';
            let html = '';
            let corrected = 0;
            
            dialogues.forEach((item, index) => {
                const key = `${item.episode}_${item.dialogue.substring(0, 30)}`;
                const correctedTime = correctedTimings[key];
                const displayTime = correctedTime || item.estimated_time;
                const status = correctedTime ? 'corrected' : 'pending';
                if (correctedTime) corrected++;
                
                if (item.episode !== currentEpisode) {
                    currentEpisode = item.episode;
                    html += `<div class="episode-header">${currentEpisode}</div>`;
                }
                
                html += `
                    <div class="dialogue-item" data-episode="${item.episode}" data-dialogue="${item.dialogue.toLowerCase()}">
                        <div class="dialogue-text">
                            ${item.dialogue}
                            <span class="status-badge status-${status}">${status === 'corrected' ? '✓ Corrected' : '⏱️ Pending'}</span>
                        </div>
                        <div>
                            <input type="text" class="timestamp-input" id="time_${index}" 
                                   placeholder="MM:SS.ms" value="${displayTime}">
                            <button onclick="useEstimated(${index})">Use Estimated</button>
                            <button onclick="playTimestamp(${index})">▶️ Preview (copy time)</button>
                        </div>
                    </div>
                `;
            });
            
            content.innerHTML = html;
            document.getElementById('stats').textContent = `📊 Corrected: ${corrected}/${dialogues.length}`;
        }
        
        function useEstimated(index) {
            document.getElementById(`time_${index}`).value = dialogues[index].estimated_time;
        }
        
        function playTimestamp(index) {
            const timeInput = document.getElementById(`time_${index}`).value;
            const timeInSeconds = parseTime(timeInput);
            alert(`Copy this timestamp: ${timeInput} (${timeInSeconds.toFixed(3)} seconds)`);
        }
        
        function saveTimings() {
            correctedTimings = {};
            dialogues.forEach((item, index) => {
                const input = document.getElementById(`time_${index}`);
                if (input.value) {
                    const key = `${item.episode}_${item.dialogue.substring(0, 30)}`;
                    correctedTimings[key] = input.value;
                }
            });
            
            localStorage.setItem('bmoTimings', JSON.stringify(correctedTimings));
            loadDialogues(); // Reload to update status badges
            alert('✅ Timings saved to browser!');
        }
        
        function exportJSON() {
            const exportData = dialogues.map((item, index) => {
                const key = `${item.episode}_${item.dialogue.substring(0, 30)}`;
                return {
                    episode: item.episode,
                    dialogue: item.dialogue,
                    timestamp: correctedTimings[key] || item.estimated_time
                };
            });
            
            const dataStr = JSON.stringify(exportData, null, 2);
            const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
            
            const linkElement = document.createElement('a');
            linkElement.setAttribute('href', dataUri);
            linkElement.setAttribute('download', 'bmo_timings.json');
            linkElement.click();
        }
        
        function copyTimingsToClipboard() {
            const exportData = dialogues.map((item, index) => {
                const key = `${item.episode}_${item.dialogue.substring(0, 30)}`;
                return {
                    episode: item.episode,
                    dialogue: item.dialogue,
                    timestamp: correctedTimings[key] || item.estimated_time
                };
            });
            
            navigator.clipboard.writeText(JSON.stringify(exportData, null, 2)).then(() => {
                alert('✅ Copied to clipboard!');
            });
        }
        
        function filterDialogues() {
            const searchTerm = document.getElementById('search').value.toLowerCase();
            const items = document.querySelectorAll('.dialogue-item');
            
            items.forEach(item => {
                const episode = item.dataset.episode.toLowerCase();
                const dialogue = item.dataset.dialogue;
                if (episode.includes(searchTerm) || dialogue.includes(searchTerm)) {
                    item.style.display = 'block';
                } else {
                    item.style.display = 'none';
                }
            });
        }
        
        // Load dialogues when page loads
        window.onload = loadDialogues;
    </script>
</body>
</html>
    """
    
    # Save HTML file
    html_path = Path(output_dir) / "timing_corrector.html"
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\n✨ Timing correction tool created at: {html_path}")
    print("\n📝 Instructions:")
    print("1. Open the HTML file in your browser")
    print("2. Watch each episode and enter timestamps for BMO's lines")
    print("3. Use 'MM:SS.ms' format (e.g., 05:23.5)")
    print("4. Click 'Save All Timings' to save to browser")
    print("5. Export as JSON when done")
    
    return html_path

# Main execution script
if __name__ == "__main__":
    # Configuration - UPDATE THESE PATHS
    TRANSCRIPTS_DIR = "/home/ogbobby/Documents/git/AdventureTimeTranscriptScrape/adventure_time_transcripts_advanced/Season_1_2010[]"  # Your transcripts folder
    VIDEOS_DIR = "/home/ogbobby/Documents/AdventureTime/Season_1"  # Your video files
    OUTPUT_DIR = "/home/ogbobby/Documents/BMO"  # Where to save BMO clips
    
    # Convert to Path objects
    transcripts_path = Path(TRANSCRIPTS_DIR)
    videos_path = Path(VIDEOS_DIR)
    output_path = Path(OUTPUT_DIR)
    
    print("🎮 BMO Dialogue Extractor")
    print("="*50)
    print(f"Transcripts directory: {transcripts_path}")
    print(f"Videos directory: {videos_path}")
    print(f"Output directory: {output_path}")
    print("="*50)
    print("1. Extract BMO dialogues only (metadata)")
    print("2. Extract BMO dialogues and attempt audio extraction")
    print("3. Create timing correction tool")
    print("4. Full pipeline with manual timing")
    print("5. Test with single episode")
    
    choice = input("\nSelect option (1-5): ").strip()
    
    if choice == "1":
        extractor = BMOTranscriptExtractor(transcripts_path, videos_path, output_path)
        extractor.process_all_transcripts()
        
    elif choice == "2":
        # Check if manual timings file exists
        manual_file = output_path / "bmo_timings.json"
        if manual_file.exists():
            print(f"Found manual timings: {manual_file}")
            use_manual = input("Use manual timings? (y/n): ").strip().lower()
            if use_manual == 'y':
                extractor = BMOAudioExtractor(transcripts_path, videos_path, output_path)
                extractor.extract_all_audio(manual_file)
            else:
                extractor = BMOAudioExtractor(transcripts_path, videos_path, output_path)
                extractor.extract_all_audio()
        else:
            print("No manual timings file found. Using estimated timestamps.")
            extractor = BMOAudioExtractor(transcripts_path, videos_path, output_path)
            extractor.extract_all_audio()
        
    elif choice == "3":
        create_timing_correction_tool(transcripts_path, output_path)
        
    elif choice == "4":
        print("\n📋 Full Pipeline")
        print("Step 1: Extract BMO dialogues")
        extractor = BMOTranscriptExtractor(transcripts_path, videos_path, output_path)
        extractor.process_all_transcripts()
        
        print("\nStep 2: Create timing correction tool")
        html_path = create_timing_correction_tool(transcripts_path, output_path)
        
        print(f"\n📝 Next steps:")
        print("1. Open this file in your browser:")
        print(f"   {html_path}")
        print("2. Watch each episode and enter the timestamps for BMO's lines")
        print("3. Export the timings as 'bmo_timings.json'")
        print("4. Run option 2 again with the exported JSON file")
        
    elif choice == "5":
        # Test with a single episode
        episode = input("Enter episode name (without .txt): ").strip()
        extractor = BMOAudioExtractor(transcripts_path, videos_path, output_path)
        
        # Find the transcript file
        transcript_files = list(transcripts_path.rglob(f"*{episode}*.txt"))
        if transcript_files:
            print(f"Testing with: {transcript_files[0].name}")
            # Process just this episode
            dialogues = extractor.extract_bmo_dialogues_from_transcript(transcript_files[0])
            print(f"Found {len(dialogues)} BMO lines")
            
            video = extractor.find_matching_video(transcript_files[0].stem)
            if video:
                print(f"Found video: {video.name}")
                
                # Create test output directory
                test_output = output_path / "test"
                test_output.mkdir(parents=True, exist_ok=True)
                
                for i, dialogue in enumerate(dialogues[:3]):  # Test first 3 lines
                    print(f"\nTesting line {i+1}: {dialogue['dialogue'][:50]}...")
                    with open(transcript_files[0], 'r', encoding='utf-8') as f:
                        full = f.read()
                    timestamp = extractor.estimate_timestamp(dialogue['dialogue'], full)
                    
                    output_file = test_output / f"test_{i+1}_{episode}.mp3"
                    success = extractor.extract_audio_clip(video, timestamp, 3.0, output_file)
                    if success:
                        print(f"  ✓ Test successful: {output_file}")
                    else:
                        print(f"  ✗ Test failed")
            else:
                print("No matching video found")
        else:
            print(f"No transcript found for episode: {episode}")