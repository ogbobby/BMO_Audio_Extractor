import os
import re
import json
import subprocess
from pathlib import Path
from datetime import timedelta

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
        
    def extract_bmo_dialogues_from_transcript(self, transcript_file):
        """
        Extract all BMO dialogues from a single transcript file
        Handles the format where character name is on its own line
        followed by dialogue on the next line(s)
        """
        with open(transcript_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        bmo_dialogues = []
        i = 0
        
        while i < len(lines):
            current_line = lines[i].strip()
            
            # Check if this line is a character name (all caps or capitalized, no colon)
            # BMO might appear as "BMO" or "BMO:" in some formats
            if current_line in ['BMO', 'BMO:'] or current_line.startswith('BMO '):
                # Found BMO speaking
                dialogue_lines = []
                i += 1  # Move to next line for dialogue
                
                # Collect all dialogue lines until we hit another character name or empty line
                while i < len(lines):
                    next_line = lines[i].strip()
                    
                    # Stop if we hit another character name (all caps word)
                    if next_line and next_line.isupper() and len(next_line) < 30:
                        break
                    # Also stop if we hit a line with a colon (alternative format)
                    if ':' in next_line and next_line.split(':')[0].strip().isupper():
                        break
                    # Stop if we hit an empty line after collecting dialogue
                    if not next_line and dialogue_lines:
                        break
                    
                    if next_line:  # Only add non-empty lines
                        dialogue_lines.append(next_line)
                    i += 1
                
                # Join all dialogue lines
                if dialogue_lines:
                    full_dialogue = ' '.join(dialogue_lines)
                    bmo_dialogues.append({
                        'dialogue': full_dialogue,
                        'line_number': i - len(dialogue_lines),
                        'speaker': 'BMO'
                    })
            else:
                i += 1
        
        return bmo_dialogues
    
    def extract_all_dialogues_by_character(self, transcript_file, character):
        """
        Extract all dialogues for a specific character
        Useful for verification or other characters
        """
        with open(transcript_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        dialogues = []
        i = 0
        
        while i < len(lines):
            current_line = lines[i].strip()
            
            # Check if this line is the target character
            if current_line in [character, f'{character}:'] or current_line.startswith(f'{character} '):
                dialogue_lines = []
                i += 1
                
                while i < len(lines):
                    next_line = lines[i].strip()
                    
                    # Stop if we hit another character name
                    if next_line and next_line.isupper() and len(next_line) < 30:
                        break
                    if ':' in next_line and next_line.split(':')[0].strip().isupper():
                        break
                    if not next_line and dialogue_lines:
                        break
                    
                    if next_line:
                        dialogue_lines.append(next_line)
                    i += 1
                
                if dialogue_lines:
                    full_dialogue = ' '.join(dialogue_lines)
                    dialogues.append({
                        'dialogue': full_dialogue,
                        'line_number': i - len(dialogue_lines),
                        'speaker': character
                    })
            else:
                i += 1
        
        return dialogues
    
    def verify_bmo_dialogues(self, transcript_file):
        """
        Verify that we're correctly identifying BMO dialogues
        by showing context around each found dialogue
        """
        with open(transcript_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"\nVerifying BMO dialogues in: {transcript_file.name}")
        print("="*60)
        
        bmo_lines = self.extract_bmo_dialogues_from_transcript(transcript_file)
        
        for i, dialogue in enumerate(bmo_lines):
            print(f"\nBMO Line {i+1}:")
            print(f"Dialogue: {dialogue['dialogue']}")
            
            # Show context (2 lines before and after)
            start = max(0, dialogue['line_number'] - 4)
            end = min(len(lines), dialogue['line_number'] + 4)
            
            print("Context:")
            for j in range(start, end):
                prefix = "→ " if j >= dialogue['line_number'] - 2 else "  "
                print(f"{prefix}{j+1}: {lines[j].strip()}")
            print("-"*40)
        
        return bmo_lines
    
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
    
    def estimate_timestamp(self, dialogue_index, total_dialogues):
        """
        Estimate timestamp based on dialogue position in episode
        This is a rough estimate - manual timing is recommended
        """
        # Assume 22-minute episode (1320 seconds)
        # Distribute dialogues evenly
        if total_dialogues > 0:
            return (dialogue_index / total_dialogues) * 1320
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
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-ss', str(start_time),
            '-t', str(duration),
            '-vn',
            '-acodec', 'libmp3lame',
            '-ar', '44100',
            '-ac', '2',
            '-y',
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
        all_bmo_lines = []
        
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
                    
                    # Process each dialogue
                    for i, dialogue_data in enumerate(dialogues):
                        dialogue = dialogue_data['dialogue']
                        
                        # Create safe filename
                        safe_dialogue = re.sub(r'[^\w\s-]', '', dialogue)[:50]
                        safe_dialogue = re.sub(r'\s+', '_', safe_dialogue.strip())
                        output_filename = f"{episode_name}_BMO_{i+1:03d}_{safe_dialogue}.mp3"
                        output_path = self.output_dir / episode_name / output_filename
                        
                        # Estimate timing (rough)
                        estimated_time = self.estimate_timestamp(i, len(dialogues))
                        
                        dialogue_entry = {
                            'episode': episode_name,
                            'dialogue': dialogue,
                            'estimated_time': estimated_time,
                            'dialogue_index': i,
                            'total_dialogues': len(dialogues),
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
        """
        if isinstance(time_str, (int, float)):
            return float(time_str)
        
        time_str = str(time_str).strip()
        
        try:
            return float(time_str)
        except ValueError:
            pass
        
        try:
            parts = time_str.split(':')
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
            elif len(parts) == 2:
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
        """
        all_dialogues = self.process_all_transcripts()
        
        # Load manual timings if provided
        manual_timings = {}
        if manual_timing_file and Path(manual_timing_file).exists():
            with open(manual_timing_file, 'r', encoding='utf-8') as f:
                for item in json.load(f):
                    key = f"{item['episode']}_{item['dialogue_index']}"
                    manual_timings[key] = item['timestamp']
        
        print(f"\n🎬 Extracting audio clips for {len(all_dialogues)} BMO lines...")
        
        successful = 0
        failed = 0
        
        for i, dialogue_data in enumerate(all_dialogues):
            episode = dialogue_data['episode']
            video_path = Path(dialogue_data['video_file'])
            dialogue = dialogue_data['dialogue']
            output_path = Path(dialogue_data['output_file'])
            dialogue_index = dialogue_data['dialogue_index']
            
            # Create key for manual timing lookup
            key = f"{episode}_{dialogue_index}"
            
            if key in manual_timings:
                start_time = self.parse_timestamp(manual_timings[key])
                print(f"\n[{i+1}/{len(all_dialogues)}] Using manual timing ({start_time:.2f}s) for line {dialogue_index+1}")
            else:
                start_time = float(dialogue_data['estimated_time'])
                print(f"\n[{i+1}/{len(all_dialogues)}] Using estimated timing ({start_time:.2f}s) for line {dialogue_index+1}")
            
            # Estimate duration based on dialogue length
            word_count = len(dialogue.split())
            duration = max(1.5, (word_count / 2.5) + 1.0)
            
            if not video_path.exists():
                print(f"  ✗ Video file not found: {video_path}")
                failed += 1
                continue
            
            print(f"  Dialogue: {dialogue[:100]}...")
            print(f"  Extracting {duration:.1f}s clip...")
            
            success = self.extract_audio_clip(video_path, start_time, duration, output_path)
            
            if success:
                print(f"  ✓ Saved to: {output_path.name}")
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
    print("3. Verify BMO extraction on a single episode")
    print("4. Create timing correction tool")
    print("5. Full pipeline with manual timing")
    print("6. Test with single episode")
    
    choice = input("\nSelect option (1-6): ").strip()
    
    if choice == "1":
        extractor = BMOTranscriptExtractor(transcripts_path, videos_path, output_path)
        extractor.process_all_transcripts()
        
    elif choice == "2":
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
        # Verify extraction on a single episode
        episode = input("Enter episode name to verify (without .txt): ").strip()
        extractor = BMOTranscriptExtractor(transcripts_path, videos_path, output_path)
        
        transcript_files = list(transcripts_path.rglob(f"*{episode}*.txt"))
        if transcript_files:
            extractor.verify_bmo_dialogues(transcript_files[0])
        else:
            print(f"No transcript found for episode: {episode}")
    
    elif choice == "4":
        # Create timing correction tool (simplified version)
        print("Timing correction tool creation - coming soon!")
        
    elif choice == "5":
        print("\n📋 Full Pipeline")
        print("Step 1: Extract BMO dialogues")
        extractor = BMOTranscriptExtractor(transcripts_path, videos_path, output_path)
        extractor.process_all_transcripts()
        
        print("\n⚠️  Manual timing required for accurate extraction")
        print("For now, use option 3 to verify extraction, then option 2 for audio")
        
    elif choice == "6":
        episode = input("Enter episode name (without .txt): ").strip()
        extractor = BMOAudioExtractor(transcripts_path, videos_path, output_path)
        
        transcript_files = list(transcripts_path.rglob(f"*{episode}*.txt"))
        if transcript_files:
            print(f"Testing with: {transcript_files[0].name}")
            dialogues = extractor.extract_bmo_dialogues_from_transcript(transcript_files[0])
            print(f"Found {len(dialogues)} BMO lines")
            
            # Print first few dialogues to verify
            for i, dialogue in enumerate(dialogues[:5]):
                print(f"\nBMO Line {i+1}: {dialogue['dialogue']}")
            
            video = extractor.find_matching_video(transcript_files[0].stem)
            if video:
                print(f"\nFound video: {video.name}")
                
                test_output = output_path / "test"
                test_output.mkdir(parents=True, exist_ok=True)
                
                # Test first 2 lines
                for i, dialogue in enumerate(dialogues[:2]):
                    print(f"\nExtracting line {i+1}...")
                    timestamp = extractor.estimate_timestamp(i, len(dialogues))
                    output_file = test_output / f"test_{i+1}_{episode}.mp3"
                    success = extractor.extract_audio_clip(video, timestamp, 3.0, output_file)
                    if success:
                        print(f"  ✓ Saved to: {output_file}")
                    else:
                        print(f"  ✗ Failed")
            else:
                print("No matching video found")
        else:
            print(f"No transcript found for episode: {episode}")