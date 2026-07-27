"""Core package: platform-agnostic business logic for the mutual-promo bot.

Modules:
    models    — dataclasses for User, Link, VipLink, Action
    storage   — SQLite persistence (users, links, vip, blacklist, whitelist, debts)
    logic     — VP rules: like 10/10, like 20/20, follow 5/5, comment 3/3 (>=5 words)
    vip       — VIP queue management
    text_utils— comment-word counting, link validation
"""

__version__ = "0.1.0"
