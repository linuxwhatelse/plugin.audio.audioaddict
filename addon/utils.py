import json
import os
import urllib
import urlparse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from addon import HANDLE, addict

DEFAULT_LOG_LEVEL = xbmc.LOGNOTICE

ADDON = xbmcaddon.Addon()
PROFILE_DIR = xbmc.translatePath(os.path.join(ADDON.getAddonInfo('profile')))


def log(*args, **kwargs):
    args = [str(i) for i in args]
    level = kwargs.get('level', DEFAULT_LOG_LEVEL)
    xbmc.log('[{}] {}'.format(ADDON.getAddonInfo('id'), ' '.join(args)),
             level=level)


def notify(title, message, icon=None, display_time=5000):
    if not icon:
        icon = ADDON.getAddonInfo('icon')

    xbmcgui.Dialog().notification(title, message, icon, display_time)


def translate(id_):
    return ADDON.getLocalizedString(id_)


def parse_url(url, base=None):
    url = urlparse.urlparse(url)

    params = dict(urlparse.parse_qsl(url.query))
    for k, v in params.iteritems():
        if v.lower() in ('true', 'false'):
            params[k] = v.lower() == 'true'
        else:
            try:
                params[k] = int(v)
                continue
            except ValueError:
                pass

            try:
                params[k] = float(v)
                continue
            except ValueError:
                pass

    url = url._replace(query=params)
    path_ = filter(
        None, [urllib.unquote_plus(e) for e in url.path.strip('/').split('/')])
    if base and not path_:
        path_ = [base]
    url = url._replace(path=list(path_))

    return url


def build_path(*args, **kwargs):
    args = '/'.join([urllib.quote_plus(str(e)) for e in args])
    url = 'plugin://{}/{}'.format(ADDON.getAddonInfo('id'), args)

    kwargs = urllib.urlencode(kwargs)
    if kwargs:
        url = '{}?{}'.format(url, kwargs)

    return url


def next_track(network, channel, cache=True):
    tracks_file = os.path.join(PROFILE_DIR, 'tracks.json')

    aa = addict.AudioAddict(PROFILE_DIR, network)
    channel_id = aa.get_channel_id(channel)

    track_list = {}
    if cache and os.path.exists(tracks_file):
        with open(tracks_file, 'r') as f:
            track_list = json.loads(f.read())

    if (track_list.get('channel_id') != channel_id
            or len(track_list.get('tracks')) < 1):
        track_list = aa.track_list(channel)

    track = track_list['tracks'].pop(0)

    with open(tracks_file, 'w') as f:
        f.write(json.dumps(track_list, indent=2))

    return track


def add_aa_art(item, elem, thumb_key='compact', fanart_key='default',
               set_fanart=True):
    thumb = elem.get('images', {}).get(thumb_key)
    fanart = elem.get('images', {}).get(fanart_key, thumb)

    item.setArt({
        'thumb': addict.AudioAddict.url(thumb, width=512),
    })

    if set_fanart:
        item.setArt({
            'fanart': addict.AudioAddict.url(fanart, height=720),
        })

    return item


def build_track_item(track, set_offset=False):
    asset = track.get('content', {}).get('assets', [])[0]

    item = xbmcgui.ListItem()
    item.setPath(addict.AudioAddict.url(asset.get('url', '')))
    item.setProperty('IsPlayable', 'true')

    # Even if we "Tune in", we don't get a tracklist which is
    # representative of a live station.
    # As such, setting the offset is more of a nuisance than anything else.
    # Might revisit that sometime later
    if set_offset:
        item.setProperty('StartOffset',
                         str(track.get('content', {}).get('offset', 0.0)))

    item.setInfo(
        'music', {
            'artist': track.get('artist', {}).get('name', ''),
            'title': track.get('title', ''),
            'duration': track.get('length'),
        })
    thumb = addict.AudioAddict.url(track.get('asset_url'), width=512)
    item.setArt({'thumb': thumb, 'fanart': thumb})

    return item


def go_premium(self):
    xbmcgui.Dialog().textviewer(utils.translate(30311), utils.translate(30301))
    ADDON.setSettingInt('addon.last_premium_prompt', int(time.time()))


def list_items(items, sort_methods=None):
    if not sort_methods:
        sort_methods = [
            xbmcplugin.SORT_METHOD_UNSORTED,
            xbmcplugin.SORT_METHOD_LABEL,
        ]

    for method in sort_methods:
        xbmcplugin.addSortMethod(HANDLE, method)

    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.endOfDirectory(HANDLE)
