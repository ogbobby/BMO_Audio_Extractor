import os
import re
import json
import subprocess
from pathlib import Path
from datetime import timedelta
import sys

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
        """
        with open(transcript_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        bmo_dialogues = []
        i = 0
        
        while i < len(lines):
            current_line = lines[i].strip()
            
            # Look for "BMO" on its own line
            if current_line == "BMO":
                # Next line should be the colon with dialogue
                if i + 1 < len(lines):
                    dialogue_line = lines[i + 1].strip()
                    
                    # Check if it starts with ":" and has dialogue
                    if dialogue_line.startswith(':'):
                        # Extract everything after the colon and space
                        dialogue = dialogue_line[1:].strip()
                        if dialogue:
                            bmo_dialogues.append({
                                'dialogue': dialogue,
                                'line_number': i + 1,
                                'speaker': 'BMO',
                                'transcript_file': str(transcript_file)
                            })
                i += 2
            else:
                i += 1
        
        return bmo_dialogues
    
    def find_matching_video(self, episode_name):
        """
        Find the video file that matches an episode name
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
    
    def extract_audio_clip(self, video_path, start_time, end_time, output_path):
        """
        Extract audio clip using ffmpeg with precise start and end times
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Calculate duration
        duration = end_time - start_time
        
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
    
    def get_video_duration(self, video_path):
        """
        Get the duration of a video file using ffprobe
        """
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(video_path)
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return float(result.stdout.strip())
        except:
            return None
    
    def create_timing_template(self, output_file=None):
        """
        Create a JSON template for manual timing entry
        """
        all_bmo_lines = []
        transcript_files = list(self.transcripts_dir.rglob("*.txt"))
        
        for transcript_file in sorted(transcript_files):
            episode_name = transcript_file.stem
            dialogues = self.extract_bmo_dialogues_from_transcript(transcript_file)
            
            # Find matching video
            video_path = self.find_matching_video(episode_name)
            video_duration = self.get_video_duration(video_path) if video_path else None
            
            for i, dialogue in enumerate(dialogues):
                all_bmo_lines.append({
                    'id': f"{episode_name}_{i+1:03d}",
                    'episode': episode_name,
                    'dialogue': dialogue['dialogue'],
                    'video_file': str(video_path) if video_path else "MISSING",
                    'video_duration': video_duration,
                    'timestamp': '',  # To be filled by user
                    'duration': '',   # To be filled by user
                    'notes': ''
                })
        
        if output_file is None:
            output_file = self.output_dir / "bmo_timing_template.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_bmo_lines, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Created timing template with {len(all_bmo_lines)} BMO lines")
        print(f"📄 Template saved to: {output_file}")
        print("\n📝 Instructions:")
        print("1. Open this JSON file in a text editor or spreadsheet")
        print("2. For each line, watch the episode and note the timestamp (in seconds)")
        print("3. Format: timestamp = seconds when BMO starts speaking")
        print("4. Optional: duration = length of the dialogue in seconds")
        print("5. Save the file and run the extraction with it")
        
        return output_file
    
    def extract_with_timing_file(self, timing_file):
        """
        Extract audio using a manually created timing file
        """
        with open(timing_file, 'r', encoding='utf-8') as f:
            timing_data = json.load(f)
        
        print(f"\n🎬 Extracting {len(timing_data)} BMO audio clips with manual timings...")
        
        successful = 0
        failed = 0
        missing_video = 0
        missing_timestamp = 0
        
        for item in timing_data:
            episode = item['episode']
            dialogue = item['dialogue']
            timestamp = item.get('timestamp', '')
            duration = item.get('duration', '')
            
            # Skip if no timestamp
            if not timestamp:
                print(f"\n⏭️  Skipping {item['id']}: No timestamp provided")
                missing_timestamp += 1
                continue
            
            # Convert timestamp to float
            try:
                start_time = float(timestamp)
            except ValueError:
                print(f"\n❌ Invalid timestamp for {item['id']}: {timestamp}")
                failed += 1
                continue
            
            # Use provided duration or estimate
            if duration:
                try:
                    clip_duration = float(duration)
                except ValueError:
                    word_count = len(dialogue.split())
                    clip_duration = max(1.5, (word_count / 2.5) + 1.0)
            else:
                word_count = len(dialogue.split())
                clip_duration = max(1.5, (word_count / 2.5) + 1.0)
            
            # Check if video exists
            video_path = Path(item['video_file'])
            if not video_path.exists():
                print(f"\n❌ Video not found for {episode}: {video_path}")
                missing_video += 1
                continue
            
            # Create output path
            safe_dialogue = re.sub(r'[^\w\s-]', '', dialogue)[:50]
            safe_dialogue = re.sub(r'\s+', '_', safe_dialogue.strip())
            output_filename = f"{item['id']}_{safe_dialogue}.mp3"
            output_path = self.output_dir / episode / output_filename
            
            print(f"\n📢 {item['id']}:")
            print(f"   Dialogue: {dialogue[:75]}...")
            print(f"   Time: {start_time:.2f}s - {start_time + clip_duration:.2f}s ({clip_duration:.1f}s)")
            
            # Extract audio
            end_time = start_time + clip_duration
            success = self.extract_audio_clip(video_path, start_time, end_time, output_path)
            
            if success:
                print(f"   ✓ Saved to: {output_path}")
                successful += 1
            else:
                print(f"   ✗ Failed to extract")
                failed += 1
        
        print(f"\n{'='*50}")
        print(f"✅ EXTRACTION COMPLETE")
        print(f"{'='*50}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Missing video: {missing_video}")
        print(f"Missing timestamp: {missing_timestamp}")
        print(f"Total processed: {len(timing_data)}")
        print(f"\nFiles saved in: {self.output_dir}")

class BMOInteractiveExtractor(BMOTranscriptExtractor):
    """
    Interactive version that asks for timestamps while playing videos
    """
    
    def interactive_extract(self):
        """
        Interactive mode: for each BMO line, play the video and ask for timestamp
        """
        all_bmo_lines = []
        transcript_files = list(self.transcripts_dir.rglob("*.txt"))
        
        # First, collect all BMO lines
        for transcript_file in sorted(transcript_files):
            episode_name = transcript_file.stem
            dialogues = self.extract_bmo_dialogues_from_transcript(transcript_file)
            
            video_path = self.find_matching_video(episode_name)
            if not video_path:
                print(f"⚠️  Warning: No video found for {episode_name}")
                continue
            
            for i, dialogue in enumerate(dialogues):
                all_bmo_lines.append({
                    'id': f"{episode_name}_{i+1:03d}",
                    'episode': episode_name,
                    'dialogue': dialogue['dialogue'],
                    'video_file': str(video_path),
                    'timestamp': None
                })
        
        print(f"\n🎮 Interactive BMO Audio Extractor")
        print(f"Found {len(all_bmo_lines)} BMO lines across all episodes")
        print("="*60)
        
        successful = 0
        skipped = 0
        
        for idx, item in enumerate(all_bmo_lines):
            print(f"\n[{idx+1}/{len(all_bmo_lines)}] {item['id']}")
            print(f"📝 Dialogue: {item['dialogue']}")
            print(f"🎬 Video: {Path(item['video_file']).name}")
            
            # Ask for timestamp
            print("\nOptions:")
            print("  [timestamp] - Enter timestamp in seconds (e.g., 125.5)")
            print("  [MM:SS] - Enter timestamp in minutes:seconds (e.g., 2:05)")
            print("  s - Skip this line")
            print("  q - Quit and save progress")
            
            response = input("⏱️  When does BMO start speaking? ").strip().lower()
            
            if response == 'q':
                break
            elif response == 's':
                skipped += 1
                continue
            
            # Parse timestamp
            timestamp = self.parse_timestamp_input(response)
            if timestamp is None:
                print("❌ Invalid timestamp format. Skipping...")
                skipped += 1
                continue
            
            # Calculate duration based on dialogue length
            word_count = len(item['dialogue'].split())
            duration = max(1.5, (word_count / 2.5) + 1.0)
            
            # Create output path
            safe_dialogue = re.sub(r'[^\w\s-]', '', item['dialogue'])[:50]
            safe_dialogue = re.sub(r'\s+', '_', safe_dialogue.strip())
            output_filename = f"{item['id']}_{safe_dialogue}.mp3"
            output_path = self.output_dir / item['episode'] / output_filename
            
            # Extract audio
            print(f"   Extracting {duration:.1f}s clip...")
            success = self.extract_audio_clip(
                Path(item['video_file']),
                timestamp,
                timestamp + duration,
                output_path
            )
            
            if success:
                print(f"   ✓ Saved to: {output_path}")
                successful += 1
                item['timestamp'] = timestamp
                item['duration'] = duration
            else:
                print(f"   ✗ Failed to extract")
        
        # Save progress
        progress_file = self.output_dir / "interactive_progress.json"
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(all_bmo_lines, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*50}")
        print(f"✅ INTERACTIVE SESSION COMPLETE")
        print(f"{'='*50}")
        print(f"Successful: {successful}")
        print(f"Skipped: {skipped}")
        print(f"Progress saved to: {progress_file}")
    
    def parse_timestamp_input(self, input_str):
        """
        Parse various timestamp formats:
        - Seconds as number: 125.5
        - MM:SS: 2:05 -> 125 seconds
        - MM:SS.ms: 2:05.5 -> 125.5 seconds
        """
        input_str = input_str.strip()
        
        # Try as simple float first
        try:
            return float(input_str)
        except ValueError:
            pass
        
        # Try MM:SS format
        try:
            if ':' in input_str:
                parts = input_str.split(':')
                if len(parts) == 2:
                    minutes = int(parts[0])
                    seconds = float(parts[1])
                    return minutes * 60 + seconds
        except (ValueError, IndexError):
            pass
        
        return None

# Main execution script
if __name__ == "__main__":
    # Configuration - UPDATE THESE PATHS
    TRANSCRIPTS_DIR = "adventure_time_transcripts"  # Your transcripts folder
    VIDEOS_DIR = "/path/to/your/adventure/time/episodes"  # Your video files
    OUTPUT_DIR = "bmo_audio_clips"  # Where to save BMO clips
    
    # Convert to Path objects
    transcripts_path = Path(TRANSCRIPTS_DIR)
    videos_path = Path(VIDEOS_DIR)
    output_path = Path(OUTPUT_DIR)
    
    print("🎮 BMO Dialogue Extractor")
    print("="*60)
    print(f"Transcripts directory: {transcripts_path}")
    print(f"Videos directory: {videos_path}")
    print(f"Output directory: {output_path}")
    print("="*60)
    print("1. Extract BMO dialogues only (metadata)")
    print("2. Create timing template (JSON for manual entry)")
    print("3. Extract with timing file (use your JSON)")
    print("4. Interactive mode (enter timestamps while watching)")
    print("5. Verify BMO extraction on a single episode")
    print("6. Test with single episode (extract audio)")
    
    choice = input("\nSelect option (1-6): ").strip()
    
    if choice == "1":
        extractor = BMOTranscriptExtractor(transcripts_path, videos_path, output_path)
        extractor.process_all_transcripts()
        
    elif choice == "2":
        extractor = BMOTranscriptExtractor(transcripts_path, videos_path, output_path)
        template_file = extractor.create_timing_template()
        print(f"\n📝 Next steps:")
        print(f"1. Open {template_file} in a spreadsheet or text editor")
        print("2. For each line, watch the episode and fill in the 'timestamp' field")
        print("3. Save the file and run option 3 with it")
        
    elif choice == "3":
        timing_file = input("Enter path to timing JSON file: ").strip()
        timing_path = Path(timing_file)
        if not timing_path.exists():
            timing_path = output_path / "bmo_timing_template.json"
        
        if timing_path.exists():
            extractor = BMOTranscriptExtractor(transcripts_path, videos_path, output_path)
            extractor.extract_with_timing_file(timing_path)
        else:
            print(f"❌ Timing file not found: {timing_path}")
            print("Create one first with option 2")
    
    elif choice == "4":
        extractor = BMOInteractiveExtractor(transcripts_path, videos_path, output_path)
        extractor.interactive_extract()
    
    elif choice == "5":
        episode = input("Enter episode name to verify (without .txt): ").strip()
        extractor = BMOTranscriptExtractor(transcripts_path, videos_path, output_path)
        
        transcript_files = list(transcripts_path.rglob(f"*{episode}*.txt"))
        if transcript_files:
            dialogues = extractor.extract_bmo_dialogues_from_transcript(transcript_files[0])
            print(f"\nFound {len(dialogues)} BMO lines in {episode}:")
            for i, d in enumerate(dialogues):
                print(f"\n{i+1}. \"{d['dialogue']}\"")
        else:
            print(f"No transcript found for episode: {episode}")
    
    elif choice == "6":
        episode = input("Enter episode name (without .txt): ").strip()
        extractor = BMOInteractiveExtractor(transcripts_path, videos_path, output_path)
        
        transcript_files = list(transcripts_path.rglob(f"*{episode}*.txt"))
        if transcript_files:
            dialogues = extractor.extract_bmo_dialogues_from_transcript(transcript_files[0])
            print(f"\nFound {len(dialogues)} BMO lines in {episode}")
            
            for i, dialogue in enumerate(dialogues):
                print(f"\n{i+1}. \"{dialogue['dialogue']}\"")
            
            # Ask for timestamp
            print("\nEnter timestamp for each line (or 's' to skip, 'q' to quit)")
            
            video = extractor.find_matching_video(episode)
            if not video:
                print("No matching video found")
                sys.exit(1)
            
            test_output = output_path / "test"
            test_output.mkdir(parents=True, exist_ok=True)
            
            for i, dialogue in enumerate(dialogues[:3]):  # Test first 3
                print(f"\nLine {i+1}: \"{dialogue['dialogue']}\"")
                ts_input = input("Timestamp (seconds or MM:SS): ").strip()
                
                if ts_input.lower() == 'q':
                    break
                if ts_input.lower() == 's':
                    continue
                
                timestamp = extractor.parse_timestamp_input(ts_input)
                if timestamp is None:
                    print("Invalid timestamp, skipping")
                    continue
                
                word_count = len(dialogue['dialogue'].split())
                duration = max(2.0, (word_count / 2.5) + 1.0)
                
                output_file = test_output / f"test_{i+1}_{episode}.mp3"
                success = extractor.extract_audio_clip(video, timestamp, timestamp + duration, output_file)
                
                if success:
                    print(f"  ✓ Saved to: {output_file}")
                else:
                    print(f"  ✗ Failed")