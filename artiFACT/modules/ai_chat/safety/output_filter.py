"""Layer 3: Response filtering — bulk dump detection and fact fingerprinting."""


def check_output(response: str, fact_sentences: list[str]) -> tuple[bool, str]:
    """Check if AI response is a bulk dump of facts.

    Uses full-sentence fingerprint matching (not 40-char prefix).
    Returns (is_safe, filtered_response).
    """
    if not fact_sentences:
        return True, response

    # Count how many corpus facts appear verbatim in the response
    verbatim_count = 0
    for sentence in fact_sentences:
        if sentence.lower().strip() in response.lower():
            verbatim_count += 1

    # Bulk dump: more than 5 verbatim facts or >60% of loaded facts
    threshold = max(5, int(len(fact_sentences) * 0.6))
    if verbatim_count >= threshold:
        return False, (
            "I can help answer specific questions about this topic, "
            "but I can't output the full corpus. What would you like to know?"
        )

    return True, response
