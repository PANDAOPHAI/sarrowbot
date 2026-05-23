import re
import os
import asyncio
import requests
from difflib import SequenceMatcher

from PIL import Image, ImageDraw, ImageFont

from telethon import TelegramClient, events
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from flask import Flask
from threading import Thread

# =========================================
# CONFIG
# =========================================

API_ID = 21836257
API_HASH = "817ab8acbb95ae9ad02b74bd83ccbea2"

SESSION_NAME = "tghehe"

SOURCE_CHANNEL = -1003908794495
TARGET_CHANNEL = -1003913101784

BYPASS_BOT = "@Nick_Bypass_Bot"

THUMB_BOT = "@VideosThumb_hgbot"

TMDB_API_KEY = "f1e46d83ecce5dc29c90d9d2ed41f2ed"

processed_posts = set()

# =========================================
# CLIENT
# =========================================

client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH
)

# =========================================
# FLASK WEB SERVER
# =========================================

app = Flask(__name__)

@app.route("/")
def home():
    return "TG Anime Bot Running!"

def run_web():
    app.run(
        host="0.0.0.0",
        port=10000
    )

def keep_alive():

    t = Thread(target=run_web)

    t.start()
    
# =========================================
# HELPERS
# =========================================

def extract_anime_name(text):

    first_line = text.split("\n")[0]

    return (
        first_line
        .replace(":", "")
        .strip()
    )


def extract_episode(text):

    match = re.search(
        r"EPISODE\s*(\d+)",
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(1).zfill(2)

    return None


def extract_text_link(message):

    blocked_domains = [
        "play.google.com",
        "youtube.com",
        "youtu.be",
        "instagram.com",
        "facebook.com",
        "t.me"
    ]

    shortener_keywords = [
        "arolinks",
        "lksfy",
        "gplinks",
        "droplink",
        "short",
        "link"
    ]

    if message.entities:

        for entity in message.entities:

            if hasattr(entity, "url"):

                url = entity.url.lower()

                if any(x in url for x in blocked_domains):
                    continue

                if any(x in url for x in shortener_keywords):
                    return entity.url

        for entity in message.entities:

            if hasattr(entity, "url"):

                url = entity.url.lower()

                if any(x in url for x in blocked_domains):
                    continue

                return entity.url

    return None


async def bypass_link(link):

    bot = await client.get_entity(
        BYPASS_BOT
    )

    async with client.conversation(
        bot,
        timeout=120
    ) as conv:

        await conv.send_message(link)

        for _ in range(10):

            response = await conv.get_response()

            text = response.text

            print("\nBOT REPLY:")
            print(text)

            match = re.search(
                r"https://t\.me/[A-Za-z0-9_+/-]+",
                text
            )

            if match:

                clean = (
                    match.group(0)
                    .replace("*", "")
                    .strip()
                )

                return clean

    return None


async def join_channel(link):

    try:

        # =========================
        # PRIVATE INVITE LINK
        # =========================

        if "t.me/+" in link:

            invite_hash = (
                link.split("+")[1]
                .replace("*", "")
                .strip("/")
            )

            try:

                result = await client(
                    ImportChatInviteRequest(
                        invite_hash
                    )
                )

                if result.chats:
                    return result.chats[0]

            except Exception as e:

                print(f"\nJOIN INFO: {e}")

                # already joined fix
                if (
                    "already a participant"
                    in str(e).lower()
                ):

                    dialogs = await client.get_dialogs()

                    for dialog in dialogs:

                        if (
                            hasattr(dialog.entity, "title")
                        ):

                            return dialog.entity

        # =========================
        # PUBLIC USERNAME LINK
        # =========================

        else:

            username = (
                link
                .replace(
                    "https://t.me/",
                    ""
                )
                .replace("@", "")
                .replace("*", "")
                .strip("/")
            )

            entity = await client.get_entity(
                username
            )

            try:

                await client(
                    JoinChannelRequest(entity)
                )

            except Exception as e:

                print(f"\nJOIN INFO: {e}")

            return entity

    except Exception as e:

        print(f"\nJOIN FAILED: {e}")

    return None

async def find_latest_video_post(
    channel,
    episode_number
):

    async for msg in client.iter_messages(
        channel,
        limit=150
    ):

        if not msg.message:
            continue

        text = msg.message

        if (
            f"Episode :- {episode_number}" in text
            or f"EPISODE {episode_number}" in text.upper()
        ):

            if msg.video or msg.document:

                unique_id = (
                    f"{channel.id}_{msg.id}"
                )

                if unique_id in processed_posts:
                    return None

                processed_posts.add(unique_id)

                return msg

    return None


def clean_caption(text):

    episode = re.search(
        r"💠\s*Episode\s*:-\s*.*",
        text
    )

    language = re.search(
        r"➠\s*Language\s*:-\s*.*",
        text
    )

    quality = re.search(
        r"➳\s*Quality\s*:-\s*.*",
        text
    )

    final = []

    if episode:
        final.append(episode.group())

    if language:
        final.append(language.group())

    if quality:
        final.append(quality.group())

    return "\n".join(final)


# =========================================
# TMDB POSTER
# =========================================

def similarity(a, b):

    return SequenceMatcher(
        None,
        a.lower(),
        b.lower()
    ).ratio()


def fetch_tmdb_poster(anime_name):

    try:

        url = (
            "https://api.themoviedb.org/3/search/tv"
        )

        params = {
            "api_key": TMDB_API_KEY,
            "query": anime_name
        }

        r = requests.get(
            url,
            params=params
        ).json()

        results = r.get("results", [])

        if not results:
            return None

        best = None
        best_score = 0

        for item in results:

            name = item.get(
                "name",
                ""
            )

            score = similarity(
                anime_name,
                name
            )

            if score > best_score:

                best = item
                best_score = score

        if not best:
            return None

        backdrop = best.get(
            "backdrop_path"
        )

        if not backdrop:
            return None

        poster_url = (
            f"https://image.tmdb.org/t/p/original{backdrop}"
        )

        img = requests.get(
            poster_url
        ).content

        with open(
            "poster.jpg",
            "wb"
        ) as f:

            f.write(img)

        return "poster.jpg"

    except Exception as e:

        print(e)

        return None


# =========================================
# CUSTOM THUMBNAIL
# =========================================

def create_anime_thumbnail(
    poster_path,
    anime_name,
    episode_number,
    season_number
):

    try:

        img = Image.open(
            poster_path
        ).convert("RGB")

        img = img.resize(
            (1280, 720)
        )

        # =========================
        # CINEMATIC OVERLAY
        # =========================

        overlay = Image.new(
            "RGBA",
            img.size,
            (0, 0, 0, 55)
        )

        img = Image.alpha_composite(
            img.convert("RGBA"),
            overlay
        )

        draw = ImageDraw.Draw(img)

      
        # =========================
        # FONTS
        # =========================

        try:

            title_font = ImageFont.truetype(
                "BebasNeue-Regular.ttf",
                120
            )

            logo_font = ImageFont.truetype(
                "BebasNeue-Regular.ttf",
                70
            )

            small_font = ImageFont.truetype(
                "BebasNeue-Regular.ttf",
                50
            )

        except:

            title_font = ImageFont.load_default()
            logo_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # =========================
        # TOP LEFT LOGO
        # =========================

        draw.text(
            (35, 25),
            "TGFLIX",
            font=logo_font,
            fill=(255, 40, 40),
            stroke_width=2,
            stroke_fill="black"
        )

        # =========================
        # TOP RIGHT S01E01
        # =========================

        se_text = (
            f"S{season_number}"
            f"E{episode_number}"
        )

        bbox = draw.textbbox(
            (0, 0),
            se_text,
            font=small_font
        )

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        padding_x = 22
        padding_y = 12

        box_x1 = 1280 - text_width - 80
        box_y1 = 15
        box_x2 = 1250
        box_y2 = (
            box_y1
            + text_height
            + padding_y * 2
        )

        draw.rounded_rectangle(
            (
                box_x1,
                box_y1,
                box_x2,
                box_y2
            ),
            radius=18,
            fill=(15, 15, 15)
        )

        draw.text(
            (
                box_x1 + padding_x,
                box_y1 + 8
            ),
            se_text,
            font=small_font,
            fill="white"
        )

        # =========================
        # BOTTOM SHADOW AREA
        # =========================

        shadow = Image.new(
            "RGBA",
            (1280, 220),
            (0, 0, 0, 150)
        )

        img.paste(
            shadow,
            (0, 500),
            shadow
        )

        draw = ImageDraw.Draw(img)

                # =========================
        # HINDI DUB BADGE
        # =========================

        badge_x = 70
        badge_y = 470

        draw.rounded_rectangle(
            (
                badge_x,
                badge_y,
                badge_x + 240,
                badge_y + 55
            ),
            radius=14,
            fill=(225, 35, 35)
        )

        draw.text(
            (
                badge_x + 22,
                badge_y + 4
            ),
            "HINDI DUB",
            font=small_font,
            fill="white"
        )

                # =========================
        # ANIME TITLE
        # =========================

        anime_name = anime_name.upper()

        # BIGGER PROFESSIONAL SIZE

        dynamic_size = 160

        if len(anime_name) > 22:
            dynamic_size = 130

        if len(anime_name) > 30:
            dynamic_size = 105

        try:

            title_font = ImageFont.truetype(
                "BebasNeue-Regular.ttf",
                dynamic_size
            )

        except:

            title_font = ImageFont.load_default()

        bbox = draw.textbbox(
            (0, 0),
            anime_name,
            font=title_font
        )

        text_width = bbox[2] - bbox[0]

        x = (1280 - text_width) // 2

        # TITLE POSITION
        y = 575

        # SHADOW

        draw.text(
            (
                x + 5,
                y + 5
            ),
            anime_name,
            font=title_font,
            fill=(0, 0, 0)
        )

        # MAIN TITLE

        draw.text(
            (
                x,
                y
            ),
            anime_name,
            font=title_font,
            fill="white"
        )

        # =========================
        # SAVE
        # =========================

        output = "final_thumb.jpg"

        img.convert("RGB").save(
            output,
            quality=95
        )

        return output

    except Exception as e:

        print(e)

        return poster_path
def extract_season_from_caption(text):

    # remove telegram markdown
    clean_text = re.sub(
        r"[*_`\[\]]",
        "",
        text
    )

    print("\nCLEAN TEXT:")
    print(clean_text)

    match = re.search(
        r"SEASON\s*:\-\s*(\d+)",
        clean_text,
        re.IGNORECASE
    )

    if match:

        return match.group(1).zfill(2)

    return "01"

# =========================================
# THUMBNAIL BOT
# =========================================

async def process_thumbnail_bot(
    poster_path,
    video_post,
    caption
):

    bot = await client.get_entity(
        THUMB_BOT
    )

    async with client.conversation(
        bot,
        timeout=600
    ) as conv:

        print(
            "\nSENDING POSTER..."
        )

        await conv.send_file(
            poster_path
        )

        for _ in range(10):

            r = await conv.get_response()

            print(r.text)

            if (
                "thumb saved"
                in r.text.lower()
            ):

                break

        print(
            "\nSENDING VIDEO..."
        )

        await conv.send_file(
            file=video_post.media
        )

        for _ in range(20):

            msg = await conv.get_response()

            if msg.video or msg.document:

                print(
                    "\nTHUMB VIDEO RECEIVED"
                )

                await client.send_file(
                    TARGET_CHANNEL,
                    file=msg.media,
                    caption=caption,
                    supports_streaming=True
                )

                return True

    return False


# =========================================
# MAIN EVENT
# =========================================

@client.on(
    events.NewMessage(
        chats=SOURCE_CHANNEL
    )
)
async def handler(event):

    global CURRENT_TEXT

    try:

        print("\n==========================")
        print("NEW SOURCE POST")
        print("==========================")

        text = event.raw_text

        CURRENT_TEXT = text

        print(text)

        # =================================
        # ANIME NAME
        # =================================

        anime_name = extract_anime_name(
            text
        )

        print(
            f"\nANIME: {anime_name}"
        )

        # =================================
        # EPISODE
        # =================================

        episode_number = extract_episode(
            text
        )

        if not episode_number:

            print(
                "\nEPISODE NOT FOUND"
            )

            return

        print(
            f"\nEPISODE: "
            f"{episode_number}"
        )

        # =================================
        # SHORTLINK
        # =================================

        shortlink = extract_text_link(
            event.message
        )

        if not shortlink:

            print(
                "\nSHORTLINK NOT FOUND"
            )

            return

        print(
            f"\nSHORTLINK: "
            f"{shortlink}"
        )

        # =================================
        # BYPASS
        # =================================

        bypassed = await bypass_link(
            shortlink
        )

        if not bypassed:

            print(
                "\nBYPASS FAILED"
            )

            return

        print(
            f"\nBYPASSED: "
            f"{bypassed}"
        )

        # =================================
        # JOIN CHANNEL
        # =================================

        joined_channel = await join_channel(
            bypassed
        )

        if not joined_channel:

            print(
                "\nJOIN FAILED"
            )

            return

        print(
            f"\nJOINED: "
            f"{getattr(joined_channel, 'title', 'Unknown')}"
        )

        # =================================
        # WAIT TELEGRAM SYNC
        # =================================

        await asyncio.sleep(25)

        # =================================
        # FIND VIDEO
        # =================================

        post = await find_latest_video_post(
            joined_channel,
            episode_number
        )

        if not post:

            print(
                "\nVIDEO NOT FOUND"
            )

            return

        print("\nVIDEO FOUND")

                # =================================
        # CAPTION
        # =================================

        caption = clean_caption(
            post.message
        )

        season_number = extract_season_from_caption(
            post.text or ""
        )

        print("\nVIDEO CAPTION:")
        print(post.text)

        print(
            f"\nSEASON: {season_number}"
        )

        # =================================
        # TMDB POSTER
        # =================================

        print("\nFETCHING TMDB POSTER...")

        poster = fetch_tmdb_poster(
            anime_name
        )

        if not poster:

            print(
                "\nPOSTER NOT FOUND"
            )

            return

        print(
            "\nPOSTER DOWNLOADED"
        )

        # =================================
        # CUSTOM THUMBNAIL
        # =================================

        poster = create_anime_thumbnail(
            poster,
            anime_name,
            episode_number,
            season_number
        )

        print(
            "\nCUSTOM THUMB CREATED"
        )

        # =================================
        # PROCESS THUMB BOT
        # =================================

        done = await process_thumbnail_bot(
            poster,
            post,
            caption
        )

        if done:

            print("\n======================")
            print("DONE SUCCESSFULLY")
            print("======================")

        else:

            print(
                "\nTHUMB BOT FAILED"
            )

    except Exception as e:

        print(
            f"\nMAIN ERROR: {e}"
        )
# =========================================
# START
# =========================================

print("==============================")
print(" TG AUTO FORWARDER STARTED")
print("==============================")

keep_alive()

client.start()

print("\nBOT RUNNING...\n")

client.run_until_disconnected()
