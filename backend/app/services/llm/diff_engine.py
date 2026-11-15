import difflib
import re
from typing import List, Dict, Any


def tokenize_words(text: str) -> List[str]:
    """Splits text into words and whitespace/punctuation preserving tokens."""
    return re.findall(r"\S+|\s+", text)


def compute_word_diff(old_text: str, new_text: str) -> List[Dict[str, str]]:
    """
    Computes fine-grained word/token level diffs between old_text and new_text.
    Returns:
        [{"type": "unchanged" | "added" | "removed", "value": "..."}, ...]
    """
    if old_text == new_text:
        return [{"type": "unchanged", "value": old_text}] if old_text else []

    old_tokens = tokenize_words(old_text)
    new_tokens = tokenize_words(new_text)

    matcher = difflib.SequenceMatcher(None, old_tokens, new_tokens)
    diff_chunks: List[Dict[str, str]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            diff_chunks.append({
                "type": "unchanged",
                "value": "".join(old_tokens[i1:i2]),
            })
        elif tag == "delete":
            diff_chunks.append({
                "type": "removed",
                "value": "".join(old_tokens[i1:i2]),
            })
        elif tag == "insert":
            diff_chunks.append({
                "type": "added",
                "value": "".join(new_tokens[j1:j2]),
            })
        elif tag == "replace":
            diff_chunks.append({
                "type": "removed",
                "value": "".join(old_tokens[i1:i2]),
            })
            diff_chunks.append({
                "type": "added",
                "value": "".join(new_tokens[j1:j2]),
            })

    return diff_chunks


def compute_diff_stats(old_text: str, new_text: str) -> Dict[str, Any]:
    """Computes summary statistics for document diffs."""
    diff = compute_word_diff(old_text, new_text)
    added_words = sum(len(re.findall(r"\S+", chunk["value"])) for chunk in diff if chunk["type"] == "added")
    removed_words = sum(len(re.findall(r"\S+", chunk["value"])) for chunk in diff if chunk["type"] == "removed")
    unchanged_words = sum(len(re.findall(r"\S+", chunk["value"])) for chunk in diff if chunk["type"] == "unchanged")

    return {
        "words_added": added_words,
        "words_removed": removed_words,
        "words_unchanged": unchanged_words,
        "total_changes": added_words + removed_words,
    }
