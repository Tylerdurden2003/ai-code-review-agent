import os

SUPPORTED_EXTENSIONS = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.java': 'java',
    '.go': 'go',
    '.rs': 'rust',
    '.cpp': 'cpp',
    '.c': 'c',
}

IGNORE_DIRS = {
    '.git', 'node_modules', '__pycache__',
    'venv', '.venv', 'dist', 'build', '.idea'
}

IGNORE_FILES = {
    'package-lock.json', 'yarn.lock',
    'poetry.lock', 'requirements.txt'
}


def get_code_files(repo_path: str) -> list[dict]:
    """
    Walks the repo and returns a list of code files.
    Each item is a dict with path, language, and raw content.
    """
    code_files = []

    for root, dirs, files in os.walk(repo_path):
        # Remove ignored directories in-place
        # This stops os.walk from descending into them
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for filename in files:
            ext = os.path.splitext(filename)[1].lower()

            if ext not in SUPPORTED_EXTENSIONS:
                continue

            if filename in IGNORE_FILES:
                continue

            full_path = os.path.join(root, filename)

            # Skip very large files — probably generated code
            if os.path.getsize(full_path) > 500_000:  # 500kb
                continue

            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                code_files.append({
                    'path': full_path,
                    'relative_path': os.path.relpath(full_path, repo_path),
                    'language': SUPPORTED_EXTENSIONS[ext],
                    'content': content,
                    'size_bytes': os.path.getsize(full_path)
                })

            except Exception as e:
                print(f"Skipping {full_path}: {e}")
                continue

    print(f"Found {len(code_files)} code files")
    return code_files
