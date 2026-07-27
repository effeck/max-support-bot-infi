"""Dataclasses used across core. Pure data, no I/O."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class LinkType(str, Enum):
    POST = "post"
    GROUP = "group"
    OTHER = "other"


class ChatMode(str, Enum):
    LIKE_10 = "like10"      # n1: 10 likes for 10 links
    LIKE_20 = "like20"      # n4: 20 likes for 20 links
    FOLLOW_5 = "follow5"    # n2: 5 subscriptions for 5 groups
    COMMENT_3 = "comment3"  # n3: 3 comments (>=5 words) for 3 posts


class LinkStatus(str, Enum):
    QUEUED = "queued"          # accepted, waiting for others
    WORKED = "worked"          # user did their part
    REJECTED = "rejected"      # admin/blacklisted
    EXPIRED = "expired"        # didn't fulfill in time


@dataclass
class User:
    """A user that has interacted with the bot. Identified by (platform, user_id)."""
    platform: str               # 'vk' | 'telegram' | 'max'
    user_id: int                # native platform id
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_admin: bool = False
    is_vip: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Link:
    """A piece of content (post or group) submitted by a user to a chat."""
    id: int
    user_id: int
    platform: str
    chat_id: int                # conversation/chat where it was posted
    mode: ChatMode
    link_type: LinkType
    url: str
    status: LinkStatus = LinkStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class VipLink:
    """A VIP-boosted link shown first in every work-list."""
    id: int
    user_id: int
    platform: str
    mode: ChatMode
    url: str
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Debt:
    """Tracks how many obligations a user still owes before they can post again."""
    user_id: int
    platform: str
    chat_id: int
    mode: ChatMode
    owed: int                   # how many actions still to perform
    deadline: datetime          # when the debt expires
    given_links: list[int] = field(default_factory=list)  # ids of links we assigned


@dataclass
class Action:
    """A user-action: like, follow, comment. Used for stats and audit."""
    id: int
    user_id: int
    platform: str
    mode: ChatMode
    target_link_id: int         # which link the action was performed on
    action_type: str            # 'like' | 'follow' | 'comment'
    verified: bool = False      # VK API verified it, or self-report
    created_at: datetime = field(default_factory=datetime.utcnow)
