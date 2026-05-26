"""
selectors.py — Centralized, language-agnostic CSS & XPath selectors for Instagram.
Allows fast adjustments when Instagram changes its DOM structure.
"""

# Navigation & Login Checking
NAV_HOME_SVG = "svg[aria-label='Home']"
NAV_BAR = "nav"
MOBILE_LOGGED_IN = "[data-testid='mobile-nav-logged-in']"

# Feed Extraction
FEED_ARTICLE = "article"
FEED_HEADER_USER = "header a"
FEED_POST_URL = "a[href*='/p/'], a[href*='/reel/']"
FEED_CAPTIONS = [
    "div[data-testid='post-comment-root'] span",
    "._a9zs span",
    ".C4VMK span",
]
FEED_LIKES = [
    "button span:has-text('like')",
    "section span",
]

# Comments
EXPAND_COMMENTS_TEXT = "text=View all comments"
COMMENT_ITEM = "ul > li"
COMMENT_TEXT = "ul > li div > span"
COMMENT_AUTHOR = "ul > li a"

# Interactions
COMMENT_INPUTS = [
    "textarea[placeholder*='comment' i]",
    "textarea[aria-label*='comment' i]",
    "form textarea",
]
COMMENT_POST_BUTTONS = [
    "button[type='submit']",
    "button:has-text('Post')",
    "div[role='button']:has-text('Post')",
]
LIKE_BUTTONS = [
    "svg[aria-label='Like']",
    "button[aria-label*='Like' i]",
    "span[aria-label*='Like' i]",
]

# Notifications
NOTIF_TRIGGER = [
    "svg[aria-label='Notifications']",
    "a[href='/accounts/activity/']",
]
NOTIF_CONTAINER_ITEMS = "div[role='dialog'] > div > div, main div > ul > li"

# Profile
PROFILE_NAME = "h1, header h2, header span._aa_c"
PROFILE_BIO = [
    "div[data-testid='user-description']",
    "header div span",
    "div.-vDIg",
]
PROFILE_STATS = "header ul li"
PROFILE_PRIVATE = "span[aria-label='Private'], h2:has-text('private'), svg[aria-label='Private']"
PROFILE_RECENT_POSTS = "a[href*='/p/']"
