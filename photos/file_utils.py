def format_file_size(size_bytes):
    if size_bytes is None:
        return "—"

    try:
        size_bytes = int(size_bytes)
    except (TypeError, ValueError):
        return "—"

    if size_bytes < 0:
        return "—"

    if size_bytes < 1024 * 1024:
        size_kb = (size_bytes + 1023) // 1024
        return f"{size_kb} КБ"

    size_mb = size_bytes / (1024 * 1024)
    return f"{size_mb:.1f} МБ"
