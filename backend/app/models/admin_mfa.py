from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, JSON, String

from app.database import Base
from app.time_utils import utcnow_naive


class AdminMfaSetting(Base):
    __tablename__ = "admin_mfa_settings"

    admin_username = Column(String(120), primary_key=True)
    secret_encrypted = Column(String, nullable=True)
    pending_secret_encrypted = Column(String, nullable=True)
    recovery_code_hashes = Column(JSON, nullable=True)
    enabled = Column(Boolean, nullable=False, default=False)
    session_version = Column(Integer, nullable=False, default=0)
    enabled_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=utcnow_naive, onupdate=utcnow_naive)


class AdminMfaChallenge(Base):
    __tablename__ = "admin_mfa_challenges"
    __table_args__ = (
        Index("ix_admin_mfa_challenges_expires_at", "expires_at"),
        Index("ix_admin_mfa_challenges_admin_username", "admin_username"),
    )

    challenge_hash = Column(String(64), primary_key=True)
    admin_username = Column(String(120), nullable=False)
    purpose = Column(String(40), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow_naive)
