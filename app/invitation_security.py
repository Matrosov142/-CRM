import hashlib

ALLOWED_ROLES = {
    "tender_specialist", "procurement_manager", "warehouse", "logistics", "accounting"
}
INVITE_TTL_HOURS = 72


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
