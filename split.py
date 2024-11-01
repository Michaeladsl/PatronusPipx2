import re
import sys
import json
import pyte
import os
import argparse
from tqdm import tqdm
from wcwidth import wcwidth

parser = argparse.ArgumentParser(description='Split CAST files')
parser.add_argument('--debug', action='store_true', help='Enable debug mode')

args = parser.parse_args()

class PatchedScreen(pyte.Screen):
    def select_graphic_rendition(self, *attrs, private=False):
        super().select_graphic_rendition(*attrs)

def generate_filename(command, part_index, timestamp=None):
    cleaned_command_name = clean_filename(command)
    timestamp_part = timestamp.replace(' ', '_') if timestamp else ""
    base_name = f"{cleaned_command_name}_{timestamp_part}.cast"
    if len(base_name) > 255:
        base_name = base_name[:250] + ".cast"
    return f"{base_name}_{part_index}.cast"

def process_with_terminal_emulator(input_file, output_file):
    screen = PatchedScreen(236, 49)
    stream = pyte.Stream(screen)
    screen.reset()

    with open(input_file, 'r') as file:
        lines = file.readlines()
    
    lines = lines[1:]

    for line in lines:
        try:
            data = json.loads(line.strip())
            if isinstance(data, list) and len(data) == 3 and isinstance(data[2], str):
                text_with_escapes = data[2]
            else:
                text_with_escapes = line.strip()
        except json.JSONDecodeError as e:
            text_with_escapes = line.strip()
        
        stream.feed(text_with_escapes)
    
    output_lines = "\n".join(screen.display)

    try:
        with open(output_file, 'w') as file:
            file.write(output_lines)
    except Exception as e:
        print(f"Error writing to text file: {e}")

    return output_lines

def create_text_versions(static_dir):
    text_dir = os.path.join(static_dir, 'text')
    os.makedirs(text_dir, exist_ok=True)

    splits_dir = os.path.join(static_dir, 'splits')
    for root, _, files in os.walk(splits_dir):
        for file in files:
            if file.endswith('.cast'):
                input_file = os.path.join(root, file)
                relative_path = os.path.relpath(input_file, splits_dir)
                output_file = os.path.join(text_dir, os.path.splitext(relative_path)[0] + '.txt')

                os.makedirs(os.path.dirname(output_file), exist_ok=True)

                process_with_terminal_emulator(input_file, output_file)

def write_status(status, static_dir):
    status_file = os.path.join(static_dir, 'status_file.txt')
    with open(status_file, 'w') as file:
        file.write(status)

def split_file(input_dir, output_dir, debug=False):
    mapping_file = os.path.join(output_dir, 'file_timestamp_mapping.json')

    if os.path.exists(mapping_file):
        with open(mapping_file, 'r') as f:
            mapping = json.load(f)
    else:
        mapping = {}

    processed_files = set()
    files_to_process = [file for file in os.listdir(input_dir) if file.endswith('.cast')]
    total_files = len(files_to_process)
    
    write_status("Processing", output_dir)

    try:
        for file in tqdm(files_to_process, desc="Splitting Redacted Files"):
            input_file_path = os.path.join(input_dir, file)
            output_file_path = generate_output_filename(file, output_dir)

            if file in mapping and os.path.getmtime(input_file_path) == mapping[file]:
                if debug:
                    print(f"Skipping file {file} as it hasn't changed since the last run.")
                continue

            if file not in processed_files:
                try:
                    process_cast_file(input_file_path, output_dir, mapping_file)
                    mapping[file] = os.path.getmtime(input_file_path)
                    with open(mapping_file, 'w') as f:
                        json.dump(mapping, f, indent=4)
                except Exception as e:
                    print(f"Error processing section of {input_file_path}: {e}")
                processed_files.add(file)
                if debug:
                    print(f"Processed file: {file}")

            current_progress = round((len(processed_files) / total_files) * 100)
            write_status(f"Processing {current_progress}% complete", output_dir)

        write_status("Complete", output_dir)

    except Exception as e:
        write_status("Failed", output_dir)
        print(f"An error occurred during file splitting: {e}")

def process_cast_file(input_file_path, output_dir, mapping_file):
    trivial_commands = {'cd', 'ls', 'ls -la', 'nano', 'vi', }
    try:
        with open(input_file_path, 'r') as file:
            lines = file.readlines()
    except IOError as e:
        print(f"Error: Could not read file '{input_file_path}'. {e}")
        return

    screen = PatchedScreen(236, 49)
    stream = pyte.Stream(screen)
    json_line = lines[0].strip()
    try:
        json_data = json.loads(json_line)
    except json.JSONDecodeError:
        print(f"Error: The first line is not valid JSON in file '{input_file_path}'")
        return

    part_index = 0
    current_file_content = []
    start_time = None
    command_name = None
    timestamp = None

    if check_file_modification(input_file_path, mapping_file):
        for line in lines[1:]:
            try:
                data = json.loads(line.strip())
                try:
                    stream.feed(data[2])
                except Exception as e:
                    print(f"Error processing stream data in file '{input_file_path}'")
                    continue

                current_display = "\n".join(screen.display)
                plain_text_content = extract_plain_text(screen.display)

                if re.search(r';[\w,\d,-,_,\.]+@[\w,-.\d]+:', line):
                    if current_file_content and command_name:
                        if not is_trivial_command(command_name, trivial_commands):
                            filename = os.path.join(output_dir, generate_filename(clean_filename(command_name), part_index))
                            write_segment(filename, [json_line] + current_file_content, timestamp)
                            part_index += 1
                        current_file_content = []
                        command_name = None
                        timestamp = None
                    start_time = None
                
                adjusted_line = adjust_time(line, start_time)
                if adjusted_line:
                    if start_time is None:
                        start_time = adjusted_line[0]
                    current_file_content.append(json.dumps([adjusted_line[0] - start_time, data[1], data[2]]))
                    if timestamp is None and re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [A-Z]{3}', data[2]):
                        timestamp_match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [A-Z]{3}', data[2])
                        timestamp = timestamp_match.group()
                
                if re.search(r'└─\$|➜', current_display):
                    command_name = extract_command(current_display)
            except Exception as e:
                print(f"Error processing section of '{input_file_path}'")
                continue

        if current_file_content and command_name and not is_trivial_command(command_name, trivial_commands):
            filename = os.path.join(output_dir, generate_filename(clean_filename(command_name), part_index))
            write_segment(filename, [json_line] + current_file_content, timestamp)
            update_mapping_file(input_file_path, mapping_file)

def check_file_modification(file_path, mapping_file):
    try:
        with open(mapping_file, 'r') as f:
            mapping = json.load(f)
    except FileNotFoundError:
        mapping = {}

    current_timestamp = os.path.getmtime(file_path)

    stored_timestamp = mapping.get(file_path)

    if stored_timestamp is None or stored_timestamp != current_timestamp:
        return True
    else:
        return False

def update_mapping_file(file_path, mapping_file):
    try:
        with open(mapping_file, 'r') as f:
            mapping = json.load(f)
    except FileNotFoundError:
        mapping = {}

    mapping[file_path] = os.path.getmtime(file_path)

    with open(mapping_file, 'w') as f:
        json.dump(mapping, f, indent=4)

def extract_plain_text(display):
    return "\n".join(line.rstrip() for line in display)

def adjust_time(line, start_time):
    parts = json.loads(line.strip())
    original_time = float(parts[0])
    return original_time, parts[1], parts[2]

def write_segment(filename, content, timestamp):
    with open(filename, 'w') as new_file:
        new_file.write('\n'.join(content))
    if args.debug:
        print(f"Created file: {filename}")

    mapping_file = os.path.join(os.path.dirname(filename), 'file_timestamp_mapping.json')
    try:
        with open(mapping_file, 'r') as f:
            mapping = json.load(f)
    except FileNotFoundError:
        mapping = {}

    mapping[filename] = timestamp

    with open(mapping_file, 'w') as f:
        json.dump(mapping, f, indent=4)

def write_plain_text(filename, content):
    with open(filename, 'w') as text_file:
        text_file.write('\n'.join(content))
    print(f"Created plain text file: {filename}")

def extract_command(display):
    lines = display.split('\n')
    for line in reversed(lines):
        if '➜' in line:
            command = line.split('➜')[-1].strip()
            parts = command.split()
            if parts:
                if parts[0].startswith(('python3', 'sudo')):
                    full_command = " ".join(parts[1:])
                    return full_command.replace(' ', '_')
            return command.replace(' ', '_')
        elif '└─$' in line:
            command = line.split('└─$')[-1].strip()
            parts = command.split()
            if parts:
                if parts[0].startswith(('python3', 'sudo')):
                    full_command = " ".join(parts[1:])
                    return full_command.replace(' ', '_')
            return command.replace(' ', '_')
    return "initial"

def clean_filename(command_name):
    command_name = re.sub(r'(-p\s+\S+)', '-p', command_name)
    command_name = re.sub(r'(-H\s+\S+)', '-H', command_name)
    command_name = re.sub(r'[^a-zA-Z0-9_]', '_', command_name)
    command_name = command_name.lstrip('_')
    if not command_name:
        command_name = "command"
    return command_name

def generate_output_filename(command, output_dir):
    cleaned_command_name = clean_filename(command)
    output_filename = os.path.join(output_dir, f"{cleaned_command_name}.cast")
    if os.path.exists(output_filename):
        index = 1
        while True:
            new_output_filename = os.path.join(output_dir, f"{cleaned_command_name}_{index}.cast")
            if not os.path.exists(new_output_filename):
                return new_output_filename
            index += 1
    return output_filename

def is_trivial_command(command, trivial_commands):
    return command.split('_')[0] in trivial_commands

def main():
    parser = argparse.ArgumentParser(description='Split and process Asciinema cast files.')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    args = parser.parse_args()

    home_dir = os.path.expanduser("~")
    static_dir = os.path.join(home_dir, ".local", ".patronus", "static")
    input_dir = os.path.join(static_dir, 'redacted_full')
    output_dir = os.path.join(static_dir, 'splits')

    try:
        split_file(input_dir, output_dir, args.debug)
        create_text_versions(static_dir)
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()