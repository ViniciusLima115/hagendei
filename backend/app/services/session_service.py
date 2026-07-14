from sqlalchemy.orm import Session

from app.models.token_blacklist import TokenBlacklist
from app.time_utils import utcnow_naive


def purge_expired_revoked_tokens(db: Session) -> int:
    deleted = (
        db.query(TokenBlacklist)
        .filter(TokenBlacklist.expires_at <= utcnow_naive())
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(deleted or 0)
