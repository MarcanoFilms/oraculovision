"""Safe embedding of user/node text inside Textual markup."""


def safe_markup_text(text: str) -> str:
    """Escape arbitrary text so square brackets are not parsed as markup tags.

    Textual's built-in ``escape()`` only handles tags that look like
    ``[word...]``. Miner tags often start with ``[8j...`` (digit after bracket)
    and still break the markup parser.
    """
    return text.replace("\\", "\\\\").replace("[", "\\[")


def format_pool_badge(miner_tag: str) -> str:
    """Format miner tag into a stylized pool badge with custom colors."""
    tag_lower = miner_tag.lower()
    if "ocean" in tag_lower:
        return "[bold white on #00bcd4] OCEAN [/]"
    if "foundry" in tag_lower:
        return "[bold white on #2980b9] FOUNDRY [/]"
    if "antpool" in tag_lower:
        return "[bold black on #f1c40f] ANTPOOL [/]"
    if "f2pool" in tag_lower:
        return "[bold white on #3498db] F2POOL [/]"
    if "viabtc" in tag_lower:
        return "[bold white on #9b59b6] VIABTC [/]"
    if "binance" in tag_lower:
        return "[bold black on #f39c12] BINANCE [/]"
    if "mara" in tag_lower or "marapool" in tag_lower:
        return "[bold white on #2ecc71] MARA [/]"
    if "luxor" in tag_lower:
        return "[bold white on #d35400] LUXOR [/]"
    if "braiins" in tag_lower or "slush" in tag_lower:
        return "[bold white on #e74c3c] BRAIINS [/]"
    if miner_tag == "unknown" or not miner_tag or miner_tag == "?":
        return "[dim]unknown[/]"
    # Fallback: display tag in a simple box
    return f"[bold white on #7f8c8d] {miner_tag.upper()[:10]} [/]"