def check_safety(text: str):
    unsafe_keywords = ["hurt myself", "kill myself", "suicide", "die"]
    for kw in unsafe_keywords:
        if kw in text.lower():
            return False, "It sounds like you're going through a tough time. If you need help, please contact a trusted adult or a helpline."
    return True, None


def check_nims_runtime_safety(text: str) -> dict:
    """
    Lightweight NIMS runtime safety check.

    Returns:
        {
            "safe": bool,
            "flags": list[str]
        }
    """

    lowered = (text or "").lower()
    flags = []

    blocked_markers = [
        "diagnose you",
        "you definitely have",
        "stop taking",
        "medical advice",
        "keep this secret from",
    ]

    for marker in blocked_markers:
        if marker in lowered:
            flags.append(f"blocked_marker:{marker}")

    return {
        "safe": len(flags) == 0,
        "flags": flags,
    }

