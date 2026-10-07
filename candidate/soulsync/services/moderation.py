def check_safety(text: str):
    unsafe_keywords = ["hurt myself", "kill myself", "suicide", "die"]
    for kw in unsafe_keywords:
        if kw in text.lower():
            return False, "It sounds like you're going through a tough time. If you need help, please contact a trusted adult or a helpline."
    return True, None



