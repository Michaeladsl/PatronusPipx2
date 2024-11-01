import argparse
import subprocess
import os
import sys
import shutil

PATRONUS_BASE_DIR = os.path.expanduser('~/.local/.patronus')

def make_script_executable(script_path):
    if not os.access(script_path, os.X_OK):
        os.chmod(script_path, os.stat(script_path).st_mode | 0o111)

def find_script_path(script_name):
    """Finds the path of the script within the pipx environment."""
    venv_root = sys.prefix
    script_path_main = os.path.join(venv_root, '..', script_name)
    script_path_venv_root = os.path.join(venv_root, script_name)
    script_path_site = os.path.join(venv_root, 'lib', 'python3.12', 'site-packages', script_name)

    if os.path.exists(script_path_main):
        return script_path_main
    elif os.path.exists(script_path_venv_root):
        return script_path_venv_root
    elif os.path.exists(script_path_site):
        return script_path_site
    else:
        raise FileNotFoundError(f"Script not found in {script_path_main}, {script_path_venv_root}, or {script_path_site}")

def start_flask_server_in_tmux():
    check_session_command = "tmux has-session -t flask_server 2>/dev/null"
    result = subprocess.run(check_session_command, shell=True)
    if result.returncode == 0:
        print("flask_server session active")
        return 

    flask_script_path = find_script_path('server.py')
    tmux_command = f"tmux new-session -d -s flask_server 'python3 {flask_script_path}'"
    subprocess.run(tmux_command, shell=True, check=True)

def run_script(script_name, args):
    """Runs a script from its original location within the pipx environment."""
    full_script_path = find_script_path(script_name)
    make_script_executable(full_script_path)
    command = [full_script_path] + args if script_name.endswith('.sh') else ['python3', full_script_path] + args
    subprocess.run(command, check=True)

def setup_directories():
    """Sets up the main directory structure in the user's home directory."""
    if not os.path.exists(PATRONUS_BASE_DIR):
        os.makedirs(PATRONUS_BASE_DIR)
        print(f"Created directory: {PATRONUS_BASE_DIR}")

    for subdir in ['full', 'redacted_full', 'splits']:
        subdir_path = os.path.join(PATRONUS_BASE_DIR, 'static', subdir)
        if not os.path.exists(subdir_path):
            os.makedirs(subdir_path)
            print(f"Created directory: {subdir_path}")

    static_src_dir = os.path.join(sys.prefix, 'lib', 'python3.12', 'site-packages', 'static')
    static_dest_dir = os.path.join(PATRONUS_BASE_DIR, 'static')
    if os.path.exists(static_src_dir) and not os.path.exists(static_dest_dir):
        shutil.copytree(static_src_dir, static_dest_dir)
        print(f"Copied static files from {static_src_dir} to {static_dest_dir}")

def remove_gitkeep_files():
    for subdir in ['redacted_full', 'full', 'splits']:
        gitkeep_path = os.path.join(PATRONUS_BASE_DIR, 'static', subdir, '.gitkeep')
        if os.path.exists(gitkeep_path):
            os.remove(gitkeep_path)
            print(f"Removed .gitkeep from {gitkeep_path}")

def nuke_directories():
    for subdir in ['full', 'redacted_full', 'splits']:
        full_path = os.path.join(PATRONUS_BASE_DIR, 'static', subdir)
        for item in os.listdir(full_path):
            item_path = os.path.join(full_path, item)
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        print(f"Nuked all contents from {full_path}")

def main():
    parser = argparse.ArgumentParser(description="Patronus: A central command script for running multiple utility scripts.")
    parser.add_argument('mode', nargs='?', choices=['on', 'off'], help='Mode for running configuration.sh. Use "on" to run configuration.sh or "off" to run configuration.sh --undo.')
    parser.add_argument('--nuke', action='store_true', help='Erase all contents from the static directories')
    args = parser.parse_args()

    setup_directories()

    if args.mode:
        if args.mode == 'on':
            run_script('configure.sh', [])
        elif args.mode == 'off':
            run_script('configure.sh', ['--undo'])
        return

    if args.nuke:
        nuke_directories()
        return 

    remove_gitkeep_files()
    start_flask_server_in_tmux()
    print("Server Started: http://127.0.0.1:8005")
    scripts_to_run = ['redact.py', 'split.py', 'edit.py']
    for script in scripts_to_run:
        run_script(script, [])

if __name__ == "__main__":
    main()
