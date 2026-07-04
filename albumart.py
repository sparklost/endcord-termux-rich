import http.client
import json
import logging
import socket
import ssl
import sys
import urllib.parse

import socks

logger = logging.getLogger(__name__)


def get_connection(host, port=443, timeout=2, proxy=None):
    """Get connection object and handle proxying"""
    if sys.platform == "darwin":
        import certifi
        ssl_context = ssl.create_default_context(cafile=certifi.where())
    else:
        ssl_context = ssl.create_default_context()
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

    if not proxy:
        proxy = ""
    proxy = urllib.parse.urlsplit(proxy)
    if proxy.scheme:
        if proxy.scheme.lower() == "http":
            connection = http.client.HTTPSConnection(proxy.hostname, proxy.port, timeout=timeout, context=ssl_context)
            connection.set_tunnel(host, port=port)
        elif "socks" in proxy.scheme.lower():
            proxy_sock = socks.socksocket()
            proxy_sock.set_proxy(socks.SOCKS5, proxy.hostname, proxy.port)
            proxy_sock.settimeout(timeout)
            proxy_sock.connect((host, port))
            proxy_sock = ssl_context.wrap_socket(proxy_sock, server_hostname=host)
            connection = http.client.HTTPSConnection(host, port, timeout=timeout + 5)   # extra time for tor
            connection.sock = proxy_sock
        else:
            connection = http.client.HTTPSConnection(host, port, timeout=timeout, context=ssl_context)
    else:
        connection = http.client.HTTPSConnection(host, port, timeout=timeout, context=ssl_context)
    return connection


def get_lastfm_albumart(artist, title, proxy, headers, api_key, thumb=None):
    """Query musicbrainz for release id"""
    q_artist = urllib.parse.quote(artist)
    q_title = urllib.parse.quote(title)
    url = f"/2.0/?method=album.getInfo&api_key={api_key}&artist={q_artist}&album={q_title}&autocorrect=0&format=json"
    try:
        connection = get_connection("ws.audioscrobbler.com", timeout=10, proxy=proxy)
        connection.request("GET", url, headers=headers)
        response = connection.getresponse()
    except (socket.gaierror, TimeoutError):
        connection.close()
        return None, None
    if response.status == 200:
        data = json.loads(response.read())
        connection.close()
        album_name = data.get("album", {}).get("name")
        images = data.get("album", {}).get("image", [])
        if not images:
            return None, album_name
        image_dict = {img["size"]: img["#text"] for img in images if img["#text"]}
        if thumb in image_dict:
            return image_dict[thumb], album_name
        return image_dict.get("large") or list(image_dict.values())[0], album_name
    connection.close()
    print(f"Lastf lookup failed for {artist} - {title}, http error code: {response.status}")
    return None, None


def get_musicbrainz_release_ids(artist, title, proxy, headers):
    """Query musicbrainz for release id"""
    query = f'artist:"{artist}" AND recording:"{title}"'
    url = f"/ws/2/recording/?query={urllib.parse.quote(query)}&fmt=json&limit=5"
    try:
        connection = get_connection("musicbrainz.org", timeout=10, proxy=proxy)
        connection.request("GET", url, headers=headers)
        response = connection.getresponse()
    except (socket.gaierror, TimeoutError):
        connection.close()
        return None
    if response.status == 200:
        data = json.loads(response.read())
        albums = []
        cds = 0
        if data.get("recordings"):
            for recording in data["recordings"]:
                if "live" in recording.get("disambiguation", "").lower():
                    continue
                releases = recording.get("releases", [])
                if releases:
                    for release in releases:
                        if release["status"] != "Official" or release["title"].lower() == "greatest hits":
                            continue
                        if release.get("media", [{}])[0].get("format", "").lower() == "cd":
                            albums.insert(cds, (release["id"], release["title"]))
                            cds += 1
                        albums.append((release["id"], release["title"]))
        connection.close()
        return albums
    connection.close()
    logger.info(f"MusicBrainz lookup failed for {artist} - {title}, http error code: {response.status}")
    return None


def get_coverartarchive_image(release_id, proxy, headers, thumb=None):
    """Get album art from coverartarchive"""
    host = "archive.org"   # going direct to IA to skip one redirect
    url = f"/download/mbid-{release_id}/index.json"
    redirects = 0

    while redirects < 5:
        try:
            connection = get_connection(host, timeout=10, proxy=proxy)
            connection.request("GET", url, headers=headers)
            response = connection.getresponse()
        except (socket.gaierror, TimeoutError):
            connection.close()
            return None

        if response.status == 200:
            data = json.loads(response.read())
            images = data.get("images", [])
            if images:
                if thumb:
                    return images[0]["thumbnails"][thumb]
                return images[0]["image"]
            connection.close()
            return None

        if response.status in (301, 302, 303, 307, 308):
            location = response.getheader("Location")
            if not location:
                logger.error("Redirect without lcation")
                return None
            redirects += 1
            connection.close()
            parsed = urllib.parse.urlparse(location)
            if parsed.netloc:
                host = parsed.netloc
            if parsed.path:
                url = parsed.path
            continue

        connection.close()
        logger.error(f"Coverartarchive lookup failed for {release_id}, http error code: {response.status}")
        return None
    connection.close()
    return None
