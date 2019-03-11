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

ADDON_DIR = xbmc.translatePath(ADDON.getAddonInfo('path'))
PROFILE_DIR = xbmc.translatePath(os.path.join(ADDON.getAddonInfo('profile')))


def _enc(val):
    return val.encode('utf-8')


def log(*args, **kwargs):
    args = [str(i) for i in args]
    level = kwargs.get('level', DEFAULT_LOG_LEVEL)
    xbmc.log('[{}] {}'.format(ADDON.getAddonInfo('id'), ' '.join(args)),
             level=level)


def notify(title, message='', icon=None, display_time=5000):
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
    args = '/'.join([urllib.quote_plus(_enc(str(e))) for e in args])
    url = 'plugin://{}/{}'.format(ADDON.getAddonInfo('id'), args)

    kwargs = urllib.urlencode(kwargs)
    if kwargs:
        url = '{}?{}'.format(url, kwargs)

    return url


def next_track(network, channel, cache=True, pop=True):
    tracks_file = os.path.join(PROFILE_DIR, 'tracks.json')

    aa = addict.AudioAddict(PROFILE_DIR, network)
    channel_id = aa.get_channel_id(channel)

    track_list = {}
    if cache and os.path.exists(tracks_file):
        with open(tracks_file, 'r') as f:
            track_list = json.loads(f.read())

    if (track_list.get('channel_id') != channel_id
            or len(track_list.get('tracks')) < 1):
        track_list = aa.get_track_list(channel)

    if pop:
        track = track_list['tracks'].pop(0)
    else:
        track = track_list['tracks'][0]

    with open(tracks_file, 'w') as f:
        f.write(json.dumps(track_list, indent=2))

    return track


def add_aa_art(item, elem, thumb_key='compact', fanart_key='default'):
    thumb = elem.get('images', {}).get(thumb_key)
    fanart = elem.get('images', {}).get(fanart_key, thumb)

    item.setArt({
        'icon': addict.AudioAddict.url(thumb, width=512),
        'thumb': addict.AudioAddict.url(thumb, width=512),
    })

    if ADDON.getSettingBool('view.fanart'):
        item.setArt({
            'fanart': addict.AudioAddict.url(fanart, height=720),
        })

    return item


def build_track_item(track, set_offset=False):
    asset = track.get('content', {}).get('assets', {})
    if asset:
        asset = asset[0]

    artist = _enc(
        track.get('artist', {}).get('name', '')
        or track.get('display_arist', ''))
    title = _enc(track.get('title') or track.get('display_title', ''))
    duration = track.get('length')
    offset = track.get('content', {}).get('offset', 0)

    item = xbmcgui.ListItem('{} - {}'.format(artist, title))
    item.setPath(addict.AudioAddict.url(asset.get('url')))
    item.setInfo(
        'music', {
            'mediatype': 'music',
            'artist': artist,
            'title': title,
            'duration': duration,
        })
    item = add_aa_art(item, track, 'default')

    item.setProperty('IsPlayable', 'true')
    item.setProperty('IsInternetStream', 'true')
    item.setProperty('TotalTime', str(duration))
    if set_offset and offset > 0:
        item.setProperty('StartOffset', str(offset))

    return item


def go_premium():
    xbmcgui.Dialog().textviewer(translate(30311), translate(30302))


def clear_cache():
    for network in addict.NETWORKS.keys():
        aa = addict.AudioAddict(PROFILE_DIR, network)
        if os.path.exists(aa.cache_file):
            os.remove(aa.cache_file)

    tracks = os.path.join(PROFILE_DIR, 'tracks.json')
    if os.path.exists(tracks):
        os.remove(tracks)


def list_items(items, sort_methods=None):
    if not sort_methods:
        sort_methods = [
            xbmcplugin.SORT_METHOD_UNSORTED,
            xbmcplugin.SORT_METHOD_LABEL,
        ]

    for method in sort_methods:
        xbmcplugin.addSortMethod(HANDLE, method)

    for url, item, is_folder in items:
        if item.getArt('fanart'):
            continue
        item.setArt({
            'fanart': os.path.join(ADDON_DIR, 'fanart.jpg'),
        })

    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
