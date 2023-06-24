import os
from urllib.parse import urlparse, parse_qsl, unquote_plus, urlencode
from contextlib import contextmanager

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from addon import HANDLE, addict

DEFAULT_LOG_LEVEL = xbmc.LOGINFO

ADDON = xbmcaddon.Addon()
ADDON_ID = os.path.join(ADDON.getAddonInfo('id'))
ADDON_DIR = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
PROFILE_DIR = xbmcvfs.translatePath(os.path.join(
    ADDON.getAddonInfo('profile')))


def _enc(val):
    '''Legacy from python2'''
    return val


def log(*args, **kwargs):
    args = [str(i) for i in args]
    level = kwargs.get('level', DEFAULT_LOG_LEVEL)
    xbmc.log('[{}] {}'.format(ADDON.getAddonInfo('id'), ' '.join(args)),
             level=level)


def logd(*args, **kwargs):
    log(*args, level=xbmc.LOGDEBUG)


def logw(*args, **kwargs):
    log(*args, level=xbmc.LOGWARNING)


def notify(title, message='', icon=None, display_time=5000):
    if not icon:
        icon = ADDON.getAddonInfo('icon')

    xbmcgui.Dialog().notification(title, message, icon, display_time)


def translate(id_):
    return ADDON.getLocalizedString(id_)


@contextmanager
def busy_dialog():
    try:
        xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
        yield

    finally:
        xbmc.executebuiltin('Dialog.Close(busydialognocancel)')


def seek_offset(offset, timeout=5, interval=0.1):
    player = xbmc.Player()
    monitor = xbmc.Monitor()

    waited = 0
    while not monitor.abortRequested():
        if player.isPlayingAudio():
            # Initially we get times from the previous playback or something
            if player.getTime() > 0 and player.getTime() < 1:
                break

        if monitor.waitForAbort(interval):
            return False

        if waited >= timeout:
            return False

        waited += interval

    player.seekTime(offset)
    return True


def parse_url(url, base=None):
    url = urlparse(url)

    params = dict(parse_qsl(url.query))
    url = url._replace(query=params)

    path_ = filter(None,
                   [unquote_plus(e) for e in url.path.strip('/').split('/')])
    if base and not path_:
        path_ = [base]
    url = url._replace(path=list(path_))

    return url


def get_playing():
    filename = xbmc.getInfoLabel('Player.Filenameandpath')
    if not filename:
        return None

    url = parse_url(filename)
    if url.netloc != ADDON_ID:
        return None

    network, channel, track_id, playlist_id = (None, None, None, None)

    if url.path[0] == 'channel':
        _, __, network, channel, track_id = url.path
        track_id = int(track_id)

    elif url.path[0] == 'playlist':
        _, __, network, playlist_id, track_id = url.path
        playlist_id, track_id = int(playlist_id), int(track_id)

    else:
        return None

    return {
        'network': network,
        'channel': channel,
        'track_id': track_id,
        'playlist_id': playlist_id,
        'is_live': url.query.get('is_live', 'false').lower() == 'true'
    }


def build_path(*args, **kwargs):
    args = '/'.join([_enc(str(e)) for e in args])
    url = 'plugin://{}/{}'.format(ADDON.getAddonInfo('id'), args)

    kwargs = urlencode(kwargs)
    if kwargs:
        url = '{}?{}'.format(url, kwargs)

    return url


def get_quality_id(network):
    quality_map = {0: 'medium', 1: 'high', 2: 'ultra'}
    quality_key = quality_map[ADDON.getSettingInt('aa.quality')]

    aa = addict.AudioAddict.get(PROFILE_DIR, network)

    quality_id = None
    for quality in aa.get_qualities():
        # In case the requested quality does not exist we make sure
        # at least something is returned
        quality_id = quality.get('id')
        if quality.get('key') == quality_key:
            break

    return quality_id


def add_aa_art(item, elem, thumb_key='compact', fanart_key='default'):
    thumb = elem.get('images', {}).get(thumb_key)
    fanart = elem.get('images', {}).get(fanart_key, thumb)

    item.setArt({
        'icon': addict.convert_url(thumb, width=512),
        'thumb': addict.convert_url(thumb, width=512),
    })

    art = os.path.join(ADDON_DIR, 'fanart.jpg')
    if ADDON.getSettingBool('view.fanart') and fanart:
        art = addict.convert_url(fanart, height=720)

    item.setArt({'fanart': art})

    return item


def build_show_item(network, show, followed_slugs=None):
    if not followed_slugs:
        followed_slugs = []

    item = xbmcgui.ListItem(_enc(show.get('name')))
    item.setPath(build_path('episodes', network, show.get('slug')))
    item = add_aa_art(item, show)

    # Add context menu item(s)
    cmenu = []
    if (show.get('following', False) or show.get('slug') in followed_slugs):
        # Unfollow show
        cmenu.append((translate(30335), 'RunPlugin({})'.format(
            build_path('unfollow', network, show.get('slug'),
                       show_name=_enc(show.get('name'))))))
    else:
        # Follow show
        cmenu.append((translate(30334), 'RunPlugin({})'.format(
            build_path('follow', network, show.get('slug'),
                       show_name=_enc(show.get('name'))))))

    item.addContextMenuItems(cmenu)
    return item


def build_playlist_item(network, playlist, followed_slugs=None):
    if not followed_slugs:
        followed_slugs = []

    item = xbmcgui.ListItem(_enc(playlist.get('name')))
    item.setPath(
        build_path('play', 'playlist', network, playlist.get('id'),
                   playlist_name=playlist.get('name')))
    item = add_aa_art(item, playlist, 'default')

    # Add context menu item(s)
    cmenu = []
    if (playlist.get('following', False)
            or playlist.get('slug') in followed_slugs):
        # Unfollow playlist
        cmenu.append((translate(30335), 'RunPlugin({})'.format(
            build_path('unfollow', network, playlist.get('slug'),
                       show_name=_enc(playlist.get('name'))))))
    else:
        # Follow playlist
        cmenu.append((translate(30334), 'RunPlugin({})'.format(
            build_path('follow', network, playlist.get('slug'),
                       show_name=_enc(playlist.get('name'))))))

    # Convert strings like "6h 11m"
    duration = 0
    for u in playlist.get('duration', '').split(' '):
        if u.endswith('d'):
            duration += int(u[:1]) * 24 * 60 * 60

        if u.endswith('h'):
            duration += int(u[:1]) * 60 * 60

        if u.endswith('m'):
            duration += int(u[:1]) * 60

    # tag = item.getMusicInfoTag()
    # tag.setMediaType('music')
    # tag.setArtist(playlist.get('curator', {}).get('name'))
    # tag.setDuration(duration)
    item.setInfo('music', {
        'artist': playlist.get('curator', {}).get('name'),
        'duration': duration,
    })

    item.addContextMenuItems(cmenu)
    return item


def build_track_item(track, item_path=None, album=None):
    asset = track.get('content', {}).get('assets', {})
    if asset:
        asset = asset[0]

    artist = _enc(
        track.get('artist', {}).get('name', '')
        or track.get('display_arist', ''))
    title = _enc(track.get('title') or track.get('display_title', ''))
    duration = track.get('length')

    item = xbmcgui.ListItem('{} - {}'.format(artist, title))
    item.setInfo('music', {
        'artist': artist,
        'album': album,
        'title': title,
        'duration': duration,
    })
    if item_path:
        item.setPath(item_path)
    else:
        item.setPath(addict.convert_url(asset.get('url')))

    item = add_aa_art(item, track, 'default')

    # tag = item.getMusicInfoTag()
    # tag.setMediaType('music')
    # tag.setArtist(artist)
    # tag.setTitle(title)
    # tag.setAlbum(album)
    # tag.setDuration(duration)

    return item


def go_premium():
    xbmcgui.Dialog().textviewer(translate(30311), translate(30302))


def clear_cache():
    for network in addict.NETWORKS.keys():
        aa = addict.AudioAddict.get(PROFILE_DIR, network)
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

    fanart = os.path.join(ADDON_DIR, 'fanart.jpg')
    for url, item, is_folder in items:
        if item.getArt('fanart'):
            continue
        item.setArt({'fanart': fanart})

    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
