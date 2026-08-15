def find_repetition_loop(text: str, min_repeats: int = 6, max_period: int = 200) -> int | None:
    """
    Detects a degenerate repetition loop at the CHARACTER level: a
    substring of length `period` (1..max_period) that repeats
    immediately after itself at least `min_repeats` times in a row,
    anywhere in the text. This single check covers every pattern seen
    in practice:
      - a single repeated line (period ~= length of that line)
      - a repeating multi-line cycle, e.g. "# pyright\npyrightconfig.json\n..."
        or longer cycles like "# Poetry\npoetry.lock\n\n# Poetry virtualenv\n.venv/\n\n"
        (period ~50 chars)
      - a repeating token WITHIN a single growing line, e.g.
        "pydantic-orm-orm-orm-orm-orm-mapping" (period = len("-orm"))

    This happens occasionally with small models on low-entropy, list-like
    content (e.g. .gitignore, requirements.txt) especially at low
    temperature. Increasing max_tokens does NOT fix this -- the model
    will just keep repeating/growing until it hits whatever limit you
    give it.

    Returns the character offset where the repeated run STARTS, or
    None if no such loop is found.
    """
    n = len(text)
    if n == 0:
        return None

    for period in range(1, max_period + 1):
        run_len = period * min_repeats
        if run_len > n:
            break  # periods only grow from here; no point continuing

        i = 0
        while i + run_len <= n:
            pattern = text[i:i + period]

            if not pattern.strip():
                i += 1
                continue

            j = i + period
            repeats = 1
            while j + period <= n and text[j:j + period] == pattern:
                repeats += 1
                j += period

            if repeats >= min_repeats:
                return i

            i += 1

    return None