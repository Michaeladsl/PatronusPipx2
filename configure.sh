#!/bin/bash

GREEN='\033[92m'
RESET='\033[0m'

BASE_DIR="$HOME/.local/.patronus"
STATIC_DIR="${BASE_DIR}/static"

mkdir -p "${STATIC_DIR}/full"
mkdir -p "${STATIC_DIR}/redacted_full"
mkdir -p "${STATIC_DIR}/splits"

echo -e "${GREEN}Created the following directories:${RESET}"
echo "${STATIC_DIR}/full"
echo "${STATIC_DIR}/redacted_full"
echo "${STATIC_DIR}/splits"

RECORD_CMD="asciinema rec ${STATIC_DIR}/full/\$(date +%Y-%m-%d_%H-%M-%S).cast"

ZSHRC="$HOME/.zshrc"

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
    sed -i '/# Setup asciinema recording/,/#fi/d' "$ZSHRC"
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

if ! grep -q "ASC_REC_ACTIVE" "${ZSHRC}"; then
    echo "Adding asciinema setup to ${ZSHRC}"
    cat <<EOF >> "${ZSHRC}"

# Setup asciinema recording
export FULL_DIR=${STATIC_DIR}/full
trap 'echo Shell exited, stopping recording.; asciinema stop' EXIT
if [ -z "\$ASC_REC_ACTIVE" ]; then
    export ASC_REC_ACTIVE=true
    ${RECORD_CMD}
fi
EOF
fi

echo -e "${GREEN}Setup complete. Please open a new terminal to start recording sessions.${RESET}"
