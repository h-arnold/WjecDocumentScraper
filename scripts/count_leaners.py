#!/usr/bin/env python3
"""
Script to count occurrences of a word in tracked files and generate an SVG badge.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def is_binary(file_path):
    """Check if a file is binary by looking for null bytes."""
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(8192)
            return b'\x00' in chunk
    except (IOError, OSError):
        return True


def count_word_in_file(file_path, word):
    """Count whole-word occurrences of word in file (case-insensitive)."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Use word boundaries for whole-word matching, case-insensitive
            pattern = r'\b' + re.escape(word) + r'\b'
            matches = re.findall(pattern, content, re.IGNORECASE)
            return len(matches)
    except (IOError, OSError, UnicodeDecodeError):
        return 0


def get_tracked_files():
    """Get list of tracked files using git ls-files."""
    try:
        result = subprocess.run(
            ['git', 'ls-files'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip().split('\n')
    except subprocess.CalledProcessError:
        print("Error: Failed to get tracked files from git", file=sys.stderr)
        sys.exit(1)


def generate_svg_badge(label, count, output_path):
    """Generate an SVG badge with label and count."""
    # Calculate widths based on text length
    # Approximate character width: 6 pixels per character
    label_width = len(label) * 6.5 + 10
    count_str = str(count)
    count_width = len(count_str) * 7 + 10
    total_width = label_width + count_width
    
    # SVG template
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20">
  <defs>
    <linearGradient id="gradient" x2="0" y2="100%">
      <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
      <stop offset="1" stop-opacity=".1"/>
    </linearGradient>
  </defs>
  <g>
    <rect width="{label_width}" height="20" fill="#555"/>
    <rect x="{label_width}" width="{count_width}" height="20" fill="#007ec6"/>
    <rect width="{total_width}" height="20" fill="url(#gradient)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="{label_width/2}" y="14" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{label_width/2}" y="13">{label}</text>
    <text x="{label_width + count_width/2}" y="14" fill="#010101" fill-opacity=".3">{count_str}</text>
    <text x="{label_width + count_width/2}" y="13">{count_str}</text>
  </g>
</svg>'''
    
    # Create parent directory if needed
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write SVG file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(svg)


def main():
    parser = argparse.ArgumentParser(
        description='Count word occurrences in tracked files and generate SVG badge'
    )
    parser.add_argument('--word', required=True, help='Word to count')
    parser.add_argument('--output', required=True, help='Output SVG file path')
    
    args = parser.parse_args()
    
    # Get all tracked files
    files = get_tracked_files()
    
    # Count occurrences
    total_count = 0
    for file_path in files:
        # Only count files in the Documents folder
        if not file_path.startswith('Documents/'):
            continue
        
        # Skip badges directory
        if file_path.startswith('badges/'):
            continue
        
        # Skip if file doesn't exist or is binary
        if not os.path.isfile(file_path) or is_binary(file_path):
            continue
        
        count = count_word_in_file(file_path, args.word)
        total_count += count
    
    # Generate badge
    label = "Leaner count so far:"
    generate_svg_badge(label, total_count, args.output)
    
    print(f"Badge generated: {total_count} occurrences of '{args.word}' found")
    return 0


if __name__ == '__main__':
    sys.exit(main())
