from typing import List

CHUNK_SIZE = 40      # lines per chunk
CHUNK_OVERLAP = 5   # lines of overlap between chunks


def chunk_file(file_dict: dict) -> List[dict]:
    """
    Splits a code file into overlapping chunks.
    Returns a list of chunk dicts with metadata.
    """
    lines = file_dict['content'].splitlines()
    chunks = []
    chunk_index = 0

    start = 0
    while start < len(lines):
        end = min(start + CHUNK_SIZE, len(lines))
        chunk_lines = lines[start:end]
        chunk_text = '\n'.join(chunk_lines)

        # Skip chunks that are basically empty
        if len(chunk_text.strip()) < 30:
            start += CHUNK_SIZE - CHUNK_OVERLAP
            continue

        chunks.append({
            'chunk_id': f"{file_dict['relative_path']}::chunk_{chunk_index}",
            'file_path': file_dict['relative_path'],
            'language': file_dict['language'],
            'content': chunk_text,
            'start_line': start + 1,   # 1-indexed for humans
            'end_line': end,
            'chunk_index': chunk_index
        })

        chunk_index += 1
        start += CHUNK_SIZE - CHUNK_OVERLAP  # overlap slides the window back

    return chunks


def chunk_repo(code_files: List[dict]) -> List[dict]:
    """
    Chunks all files in the repo.
    Returns a flat list of all chunks.
    """
    all_chunks = []
    for f in code_files:
        file_chunks = chunk_file(f)
        all_chunks.extend(file_chunks)

    print(f"Created {len(all_chunks)} chunks from {len(code_files)} files")
    return all_chunks
