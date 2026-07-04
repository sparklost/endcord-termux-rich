import json
import logging
import shutil
import subprocess
import threading
import time

from endcord import utils

import albumart

EXT_NAME = "Termux Rich Presence"
EXT_VERSION = "0.1.0"
EXT_ENDCORD_VERSION = "1.5.0"
EXT_DESCRIPTION = "An extension that uses termux api to send rich presence when playing a media on android"
EXT_SOURCE = "https://github.com/sparklost/endcord-termux-rich"
logger = logging.getLogger(__name__)

COVER_NAMES = ("cover.jpg", "cover.png", "album.jpg", "folder.jpg")
USER_AGENT = "endcord/1.5.0 ( https://github.com/sparklost/endcord-termux-rich )"


class Extension:
    """Main extension class"""

    def __init__(self, app):
        if not shutil.which("termux-notification-list"):
            logger.error("termux-notification-list command not found")
            return

        self.app = app
        self.run = True
        self.whitelist = app.config.get("ext_termux_rich_whitelist", [])
        self.query_interval = app.config.get("ext_termux_rich_query_interval", 10)
        self.app_id = app.config.get("ext_termux_rich_app_id")
        self.latfm_api_key = app.config.get("ext_termux_rich_lastm_api_key")
        self.proxy = app.config["proxy"]
        self.headers = {"Accept": "*/*", "User-Agent": USER_AGENT}
        self.headers_ia = self.app.downloader.headers
        try:
            self.query_interval = int(self.query_interval)
        except ValueError:
            self.query_interval = 10

        self.start_time = None
        self.last_title = None
        self.last_artist = None
        self.image_cache = utils.load_json("termux_rich_img_cache.json", default={})
        threading.Thread(target=self.worker, daemon=True).start()


    def worker(self):
        """A thread that queries termux-notification-list every 10s and updates rich presence"""
        while self.run:
            while self.app.my_status["client_state"] != "online":
                time.sleep(0.2)
                self.last_title = None

            # query termux-notification-list
            try:
                result = subprocess.run(["termux-notification-list"], capture_output=True, text=True, check=True)
                notifications = json.loads(result.stdout)
            except Exception as e:
                logger.error(f"Failed to query termux-notification-list: {e}")
                break

            # search for whitelisted player
            for notification in notifications:
                pkg_name = notification.get("packageName")
                if pkg_name in self.whitelist:
                    break
            else:
                notification = None

            # clear activity status if no whitelisted player
            if not notification:
                if self.last_title or self.last_artist:
                    self.app.my_activities = []
                    self.last_title, self.last_artist = None, None
                    self.app.gateway.update_presence(
                        self.app.my_status["status"],
                        custom_status=self.app.my_status["custom_status"],
                        custom_status_emoji=self.app.my_status["custom_status_emoji"],
                        activities=self.app.my_activities,
                        afk=self.app.my_status["afk"],
                    )
                time.sleep(self.query_interval)
                continue

            # extract data
            title = notification.get("title")
            content = notification.get("content")
            if not content:
                time.sleep(self.query_interval)
                continue
            artist = content.split(" - ")[0] if " - " in content else content
            if not title and " - " in content:
                title = content.split(" - ")[1]
            if not title:
                time.sleep(self.query_interval)
                continue

            # skip if no change
            if title == self.last_title and artist == self.last_artist:
                time.sleep(self.query_interval)
                continue
            self.last_title = title
            self.last_artist = artist
            self.start_time = int(time.time())
            logger.info((title, artist))

            # get album art
            image_url, album = self.image_cache.get(f"{artist} - {title}", (None, None))
            album_name = None
            if not image_url:
                if self.latfm_api_key:
                    image_url, album_name = albumart.get_lastfm_albumart(artist, title, self.proxy, self.headers, self.lastfm_api_key, thumb="small")
                if not image_url:
                    albums = albumart.get_musicbrainz_release_ids(artist, title, self.proxy, self.headers)
                    for album in albums:
                        image_url = albumart.get_coverartarchive_image(album[0], None, self.headers_ia, thumb="small")
                        album_name = album[1]
                        if image_url:
                            break
                if image_url:
                    self.image_cache[f"{artist} - {title}"] = [image_url, album_name]
                    utils.save_json(self.image_cache, "termux_rich_img_cache.json")

            # get external asset url
            if image_url:
                asset = self.app.discord.get_rpc_app_external(self.app_id, image_url)
                if asset:
                    if isinstance(asset, float):
                        time.sleep(asset + 0.2)
                        self.last_title = None
                        continue
                    asset_url = asset[0]["external_asset_path"]
                else:
                    asset_url = None
            else:
                asset_url = None

            # build activity
            payload = {
                "name": "Music",
                "type": 2,  # listening
                "details": title,
                "state": artist,
                "timestamps": {
                    "start": self.start_time * 1000,
                },
                "assets": {},
            }
            if self.app_id:
                payload["application_id"] = self.app_id
            if asset_url:
                payload["assets"]["large_image"] = f"mp:{asset_url}"
                if album_name:
                    payload["assets"]["large_text"] = f"album: {album_name}"
            else:
                payload["assets"]["large_image"] = "default_music"
            logger.info(payload)
            self.app.my_activities = [payload]
            logger.debug(f"Sending activity payload: \n{json.dumps(payload, indent=2)}")

            # update presence
            self.app.gateway.update_presence(
                self.app.my_status["status"],
                custom_status=self.app.my_status["custom_status"],
                custom_status_emoji=self.app.my_status["custom_status_emoji"],
                activities=self.app.my_activities,
                afk=self.app.my_status["afk"],
            )

            time.sleep(self.query_interval)
