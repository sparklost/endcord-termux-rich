# endcord-termux-rich
An extension for [endcord](https://github.com/sparklost/endcord) discord TUI client, that uses termux api to send rich presence when playing a media on android.
This extension requires Termux:API installed alongside Termux.

## Installing
See [official extensions documentation](https://github.com/sparklost/endcord/blob/main/docs/extensions.md#installing-extensions) for installing instructions.
Available options:
- Git clone into `Extensions` directory located in endcord config directory.
- Run `endcord -i https://github.com/sparklost/endcord-termux-rich`
- Or use endcord client-side command `install_extension sparklost/endcord-termux-rich`

## Configuration
All extension options are under `[main]` section in endcord config. This extension options are always prepended with `ext_termux_rich_`.  
Verify that Termux:API is working by running `termux-notification-list` and see if there are results.

### Settings options
- `ext_termux_rich_whitelist = []`  
    List of android packages whose notifications will be scanned for playing media. You can get package name using `termux-notification-list` command in termux while notification is present. Put package name in quotes like: `ext_termux_rich_whitelist = ["com.myapp", "org.someapp"]`
- `ext_termux_rich_query_interval = 10`  
    How often to query termux-notification-list command for notifications.
- `ext_termux_rich_app_id = None`  
    Discord app id is required to show album art. Put it in quotes.
- `ext_termux_rich_lastm_api_key = None`  
    Your lastfm api key is required to fetch album art. As a fallback musicbrainz will be used (no api key required), but results might be wrong (sometimes will use album art from not-original release, like collections, live recordings...).


## Disclaimer
> [!WARNING]
> Using third-party client is against Discord's Terms of Service and may cause your account to be banned!  
> **Use endcord and/or this extension at your own risk!**  
> If this extension is modified, it may be used for harmful or unintended purposes.  
> **The developer is not responsible for any misuse or for actions taken by users.**  
