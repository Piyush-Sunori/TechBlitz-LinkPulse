"""Relational models for users, campaigns, links, and click telemetry."""

import enum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    USER = "User"
    ADMIN = "Admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda roles: [role.value for role in roles]),
        default=UserRole.USER,
        nullable=False,
    )
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    links: Mapped[list["Link"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    blocklist_entries: Mapped[list["DomainBlocklist"]] = relationship(back_populates="admin", cascade="all, delete-orphan")


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    owner: Mapped[User] = relationship(back_populates="campaigns")
    links: Mapped[list["Link"]] = relationship(back_populates="campaign")


class Link(Base):
    __tablename__ = "links"
    __table_args__ = (Index("idx_links_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    short_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    long_url: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    click_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    campaign_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    owner: Mapped[User] = relationship(back_populates="links")
    campaign: Mapped[Campaign | None] = relationship(back_populates="links")
    clicks: Mapped[list["Click"]] = relationship(back_populates="link", cascade="all, delete-orphan")


class Click(Base):
    __tablename__ = "clicks"
    __table_args__ = (Index("idx_clicks_link_time", "link_id", "clicked_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    link_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("links.id", ondelete="CASCADE"), nullable=False, index=True)
    clicked_at: Mapped[object] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
    browser: Mapped[str | None] = mapped_column(String(100), nullable=True)
    os: Mapped[str | None] = mapped_column(String(100), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(255), nullable=True)

    link: Mapped[Link] = relationship(back_populates="clicks")


class DomainBlocklist(Base):
    __tablename__ = "domain_blocklist"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    added_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    admin: Mapped[User] = relationship(back_populates="blocklist_entries")