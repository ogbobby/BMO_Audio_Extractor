import os
import re
import json
import subprocess
import whisper
import numpy as np
from pathlib import Path
from datetime import timedelta
import torch
from difflib import SequenceMatcher
#import Levenshtein

class BMOAutoExtractor:
    def __init__(self, transcripts_dir, videos_dir, output_dir):
        """
        Initialize the automatic BMO dialogue extractor
        
        Args:
            transcripts_dir: Directory containing the transcript text files
            videos_dir: Directory containing your Adventure Time video files
            output_dir: Directory where BMO audio clips will be saved
        """
        self.transcripts_dir = Path(transcripts_dir)
        self.videos_dir = Path(videos_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load Whisper model (choose size based on your GPU/CPU)
        print("Loading Whisper model...")
        self.model = whisper.load_model("base")
        print("Model loaded!")
        
    def extract_bmo_dialogues_from_transcript(self, transcript_file):
        """
        Extract all BMO dialogues from a transcript file with better pattern matching
        """
        with open(transcript_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        bmo_dialogues = []
        i = 0
        
        print(f"\n  Debug - Reading {transcript_file.name}")
        print(f"  Total lines: {len(lines)}")
        
        while i < len(lines):
            current_line = lines[i].strip()
            
            # Pattern 1: "BMO" on its own line followed by colon line
            if current_line == "BMO" and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith(':'):
                    dialogue = next_line[1:].strip()
                    if dialogue:
                        bmo_dialogues.append({
                            'dialogue': dialogue,
                            'line_number': i + 1,
                            'speaker': 'BMO',
                            'cleaned_dialogue': self.clean_dialogue_for_matching(dialogue)
                        })
                        print(f"    ✅ Found BMO line {len(bmo_dialogues)}: '{dialogue[:50]}...'")
                    i += 2
                    continue
            
            i += 1
        
        print(f"  Total found in this transcript: {len(bmo_dialogues)} BMO lines")
        return bmo_dialogues
    
    def clean_dialogue_for_matching(self, text):
        """
        Clean dialogue text for better matching by pip install python-levenshteinremoving:
        - Stage directions in brackets
        - Extra punctuation
        - Repeated characters (like multiple dots)
        - Convert to lowercase
        """
        # Remove stage directions in brackets
        text = re.sub(r'\[.*?\]', '', text)
        # Replace multiple dots with space
        text = re.sub(r'\.{2,}', ' ', text)
        # Remove special characters but keep letters, numbers, and basic punctuation
        text = re.sub(r'[^\w\s\'\.,!?]', '', text)
        # Normalize whitespace
        text = ' '.join(text.split())
        # Convert to lowercase
        return text.lower().strip()
    
    def find_matching_video(self, episode_name):
        """
        Find the video file that matches an episode name
        """
        search_name = re.sub(r'[_\s]+', ' ', episode_name).strip()
        search_name = re.sub(r'\.txt$', '', search_name)
        
        video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.m4v', '.webm', '.mpg', '.mpeg']
        
        print(f"  Looking for video matching: '{search_name}'")
        
        for ext in video_extensions:
            # Try exact match
            video_path = self.videos_dir / f"{search_name}{ext}"
            if video_path.exists():
                print(f"  ✅ Found video: {video_path.name}")
                return video_path
            
            # Try without special characters
            clean_name = re.sub(r'[^\w\s]', '', search_name)
            video_path = self.videos_dir / f"{clean_name}{ext}"
            if video_path.exists():
                print(f"  ✅ Found video: {video_path.name}")
                return video_path
            
            # Try case-insensitive match
            for video_file in self.videos_dir.glob(f"*{ext}"):
                if search_name.lower() in video_file.stem.lower():
                    print(f"  ✅ Found video: {video_file.name}")
                    return video_file
        
        print(f"  ❌ No video found for {episode_name}")
        return None
    
    def transcribe_episode(self, video_path):
        """
        Transcribe the entire episode using Whisper with word-level timestamps
        """
        print(f"  Transcribing {video_path.name}...")
        
        # Transcribe with word-level timestamps
        result = self.model.transcribe(
            str(video_path),
            word_timestamps=True,
            language='en',
            verbose=False,
            fp16=False  # Disable FP16 for CPU
        )
        
        return result
    
    def find_dialogue_advanced(self, target_dialogue, transcription_segments):
        """
        Advanced dialogue finding using multiple matching strategies
        """
        # Clean the target dialogue
        target_clean = self.clean_dialogue_for_matching(target_dialogue)
        target_words = target_clean.split()
        
        if len(target_words) < 3:
            return None
        
        best_match = None
        best_score = 0
        
        for segment_idx, segment in enumerate(transcription_segments):
            segment_clean = self.clean_dialogue_for_matching(segment['text'])
            
            # Strategy 1: Full segment similarity
            full_similarity = SequenceMatcher(None, target_clean, segment_clean).ratio()
            
            if full_similarity > best_score and full_similarity > 0.5:
                best_score = full_similarity
                best_match = {
                    'text': segment['text'],
                    'start': segment['start'],
                    'end': segment['end'],
                    'similarity': full_similarity,
                    'method': 'full_segment'
                }
            
            # Strategy 2: Look for key phrases
            # Split target into key phrases (by punctuation or length)
            key_phrases = re.split(r'[.!?]', target_clean)
            key_phrases = [p.strip() for p in key_phrases if len(p.split()) > 2]
            
            for phrase in key_phrases:
                if phrase in segment_clean:
                    score = len(phrase) / len(segment_clean)
                    if score > best_score:
                        best_score = score
                        best_match = {
                            'text': segment['text'],
                            'start': segment['start'],
                            'end': segment['end'],
                            'similarity': score,
                            'method': 'key_phrase'
                        }
            
            # Strategy 3: Word-by-word matching with context
            segment_words = segment_clean.split()
            for i in range(len(segment_words) - len(target_words) + 1):
                window = ' '.join(segment_words[i:i+len(target_words)])
                similarity = SequenceMatcher(None, target_clean, window).ratio()
                
                if similarity > best_score and similarity > 0.4:
                    best_score = similarity
                    
                    # Try to get word-level timestamps if available
                    if 'words' in segment and i < len(segment['words']):
                        start_word = segment['words'][i]
                        end_word = segment['words'][min(i+len(target_words)-1, len(segment['words'])-1)]
                        best_match = {
                            'text': window,
                            'start': start_word['start'],
                            'end': end_word['end'],
                            'similarity': similarity,
                            'method': 'word_window'
                        }
                    else:
                        # Estimate based on position in segment
                        segment_duration = segment['end'] - segment['start']
                        start_offset = (i / len(segment_words)) * segment_duration
                        end_offset = ((i + len(target_words)) / len(segment_words)) * segment_duration
                        best_match = {
                            'text': window,
                            'start': segment['start'] + start_offset,
                            'end': segment['start'] + end_offset,
                            'similarity': similarity,
                            'method': 'estimated_window'
                        }
        
        return best_match
    
    def extract_audio_clip(self, video_path, start_time, end_time, output_path):
        """
        Extract audio clip using ffmpeg
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
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
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"  FFmpeg error: {e.stderr}")
            return False
    
    def process_episode(self, transcript_file):
        """
        Process a single episode: find BMO lines and extract audio
        """
        episode_name = transcript_file.stem
        print(f"\n📺 Processing: {episode_name}")
        
        # Find matching video
        video_path = self.find_matching_video(episode_name)
        if not video_path:
            print(f"  ❌ No video found for {episode_name}")
            return []
        
        # Extract BMO dialogues from transcript
        bmo_lines = self.extract_bmo_dialogues_from_transcript(transcript_file)
        if not bmo_lines:
            print(f"  No BMO lines found")
            return []
        
        print(f"  Found {len(bmo_lines)} BMO lines in transcript")
        
        # Transcribe the episode
        try:
            transcription = self.transcribe_episode(video_path)
        except Exception as e:
            print(f"  ❌ Transcription failed: {e}")
            return []
        
        # Find each BMO line in the transcription
        successful = 0
        results = []
        
        for i, bmo_line in enumerate(bmo_lines):
            dialogue = bmo_line['dialogue']
            print(f"\n  🔍 Looking for line {i+1}:")
            print(f"     Original: {dialogue}")
            print(f"     Cleaned: {self.clean_dialogue_for_matching(dialogue)}")
            
            # Find this dialogue in the transcription
            match = self.find_dialogue_advanced(dialogue, transcription['segments'])
            
            if match:
                print(f"    ✅ Found at {match['start']:.2f}s - {match['end']:.2f}s")
                print(f"       Method: {match['method']}")
                print(f"       Similarity: {match['similarity']:.2f}")
                print(f"       Matched text: {match['text'][:100]}...")
                
                # Create output filename
                safe_dialogue = re.sub(r'[^\w\s-]', '', dialogue)[:50]
                safe_dialogue = re.sub(r'\s+', '_', safe_dialogue.strip())
                output_filename = f"{episode_name}_BMO_{i+1:03d}_{safe_dialogue}.mp3"
                output_path = self.output_dir / episode_name / output_filename
                
                # Add a small buffer
                start_time = max(0, match['start'] - 0.3)
                end_time = match['end'] + 0.3
                
                # Extract audio
                success = self.extract_audio_clip(video_path, start_time, end_time, output_path)
                
                if success:
                    successful += 1
                    results.append({
                        'episode': episode_name,
                        'dialogue': dialogue,
                        'start_time': start_time,
                        'end_time': end_time,
                        'similarity': match['similarity'],
                        'method': match['method'],
                        'matched_text': match['text'],
                        'output_file': str(output_path)
                    })
                    print(f"    💾 Saved to: {output_path.name}")
            else:
                print(f"    ❌ Could not find this line in the audio")
                
                # Show nearby segments for debugging
                print(f"       First few transcription segments:")
                for j, seg in enumerate(transcription['segments'][:5]):
                    print(f"       {j+1}: {seg['text'][:100]}...")
        
        print(f"\n  Episode complete: {successful}/{len(bmo_lines)} lines found")
        return results
    
    def process_all_episodes(self):
        """
        Process all episodes automatically
        """
        transcript_files = sorted(list(self.transcripts_dir.rglob("*.txt")))
        print(f"Found {len(transcript_files)} transcript files")
        
        all_results = []
        total_bmo_lines = 0
        total_found = 0
        
        for transcript_file in transcript_files:
            results = self.process_episode(transcript_file)
            
            if results:
                all_results.extend(results)
                total_found += len(results)
            
            # Get total BMO lines for this episode
            bmo_lines = self.extract_bmo_dialogues_from_transcript(transcript_file)
            total_bmo_lines += len(bmo_lines)
        
        # Save results
        results_file = self.output_dir / "bmo_extraction_results.json"
        
        summary = {
            'total_bmo_lines': total_bmo_lines,
            'successfully_extracted': total_found,
            'results': all_results
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*60}")
        print(f"✅ AUTOMATIC EXTRACTION COMPLETE")
        print(f"{'='*60}")
        print(f"Total BMO lines found in transcripts: {total_bmo_lines}")
        print(f"Successfully extracted: {total_found}")
        if total_bmo_lines > 0:
            print(f"Success rate: {(total_found/total_bmo_lines)*100:.1f}%")
        print(f"\nResults saved to: {results_file}")
        print(f"Audio files saved in: {self.output_dir}")
        
        return all_results

# Main execution
if __name__ == "__main__":
    # Configuration - UPDATE THESE PATHS
    TRANSCRIPTS_DIR = "/home/ogbobby/Documents/git/AdventureTimeTranscriptScrape/adventure_time_transcripts_advanced/Season_1_2010[]"  # Your transcripts folder
    VIDEOS_DIR = "/home/ogbobby/Documents/AdventureTime/Season_1"  # Your video files
    OUTPUT_DIR = "/home/ogbobby/Documents/BMO"  # Where to save BMO clips
    
    transcripts_path = Path(TRANSCRIPTS_DIR)
    videos_path = Path(VIDEOS_DIR)
    output_path = Path(OUTPUT_DIR)
    
    print("🎮 BMO Automatic Audio Extractor")
    print("="*60)
    print(f"Transcripts directory: {transcripts_path}")
    print(f"Videos directory: {videos_path}")
    print(f"Output directory: {output_path}")
    print("="*60)
    
    # Check if directories exist
    if not transcripts_path.exists():
        print(f"❌ Transcripts directory not found: {transcripts_path}")
        print("Please update the TRANSCRIPTS_DIR path")
        exit(1)
        
    if not videos_path.exists():
        print(f"❌ Videos directory not found: {videos_path}")
        print("Please update the VIDEOS_DIR path")
        exit(1)
    
    # Get all transcript files
    all_episodes = sorted(list(transcripts_path.glob("*.txt")))
    print(f"\nFound {len(all_episodes)} transcript files")
    
    # Ask which episodes to process
    print("\nOptions:")
    print("1. Process all episodes")
    print("2. Test with single episode")
    
    choice = input("\nSelect option (1 or 2): ").strip()
    
    if choice == "2":
        # Show all episodes with pagination
        page_size = 20
        total_pages = (len(all_episodes) + page_size - 1) // page_size
        current_page = 1
        
        while True:
            start_idx = (current_page - 1) * page_size
            end_idx = min(start_idx + page_size, len(all_episodes))
            
            print(f"\n--- Page {current_page}/{total_pages} ---")
            for i in range(start_idx, end_idx):
                print(f"  {i+1:3d}. {all_episodes[i].stem}")
            
            print(f"\nOptions:")
            print(f"  n - next page")
            print(f"  p - previous page")
            print(f"  # - episode number to test")
            print(f"  q - back to main menu")
            
            nav = input("\nEnter choice: ").strip().lower()
            
            if nav == 'n' and current_page < total_pages:
                current_page += 1
            elif nav == 'p' and current_page > 1:
                current_page -= 1
            elif nav == 'q':
                break
            elif nav.isdigit():
                idx = int(nav) - 1
                if 0 <= idx < len(all_episodes):
                    extractor = BMOAutoExtractor(transcripts_path, videos_path, output_path)
                    extractor.process_episode(all_episodes[idx])
                    break
                else:
                    print("❌ Invalid episode number")
            else:
                print("❌ Invalid input")
    
    else:
        # Process all episodes
        response = input(f"\nProcess all {len(all_episodes)} episodes? (y/n): ").strip().lower()
        
        if response == 'y':
            extractor = BMOAutoExtractor(transcripts_path, videos_path, output_path)
            results = extractor.process_all_episodes()
            print(f"\n✨ Done! Check {output_path} for your BMO audio clips")
        else:
            print("Extraction cancelled")