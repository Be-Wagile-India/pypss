import os
import linecache


def extract_function_code(filename: str, start_line: int) -> str:
    """
    Reads the source code of a function starting at start_line from filename.
    It tries to be smart about where the function ends (by indentation).
    """
    if filename == "unknown" or not os.path.exists(filename):
        return "Source code not available."

    # Clear cache to ensure fresh read
    linecache.checkcache(filename)

    lines = linecache.getlines(filename)
    if not lines or start_line > len(lines):
        return "Source code not found in file."

    # Python lines are 1-indexed
    start_idx = start_line - 1

    # Extract the function body based on indentation
    # The first line (def ...) sets the base indentation
    first_line = lines[start_idx]
    base_indent = len(first_line) - len(first_line.lstrip())

    code_block = [first_line]

    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines inside the function
        if not stripped:
            code_block.append(line)
            continue

        current_indent = len(line) - len(line.lstrip())

        # If indentation drops back to base level (or less), function ended
        if current_indent <= base_indent:
            break

        code_block.append(line)

    return "".join(code_block)
