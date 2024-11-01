#!/bin/bash

GREEN='\033[92m'
RESET='\033[0m'

undo=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --undo) undo=true ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

if [[ "$undo" = true ]]; then
    echo "Undoing changes made by the script..."
    sed -i '/# Setup asciinema recording/,/#fi/d' "$HOME/.zshrc"
    echo "Changes undone. Please restart your shell."
    exit 0
fi

if ! command -v asciinema &> /dev/null; then
    echo "Asciinema is not found in your PATH. Installing it with pipx..."
    pipx install asciinema
    if ! command -v asciinema &> /dev/null; then
        echo "Asciinema could not be added to your PATH. Please ensure ~/.local/bin is in your PATH."
        echo "Add this line to your ~/.bashrc or ~/.zshrc and source it:"
        echo 'export PATH="$HOME/.local/bin:$PATH"'
        exit 1
    fi
fi

CURRENT_DIR=$(pwd)
FULL_DIR="${CURRENT_DIR}/static/full"
mkdir -p "${FULL_DIR}"
echo "Recording directory set at ${FULL_DIR}"

ZSHRC="$HOME/.zshrc"
RECORD_CMD="asciinema rec \$FULL_DIR/\$(date +%Y-%m-%d_%H-%M-%S).cast"

if ! grep -q "ASC_REC_ACTIVE" "${ZSHRC}"; then
    echo "Adding asciinema setup to ${ZSHRC}"
    cat <<EOF >> "${ZSHRC}"

# Setup asciinema recording
export FULL_DIR=${FULL_DIR}
trap 'echo Shell exited, stopping recording.; asciinema stop' EXIT
if [ -z "\$ASC_REC_ACTIVE" ]; then
    export ASC_REC_ACTIVE=true
    ${RECORD_CMD}
fi
EOF
fi

echo -e "${GREEN}Setup complete. Please open a new terminal to start recording sessions.${RESET}"