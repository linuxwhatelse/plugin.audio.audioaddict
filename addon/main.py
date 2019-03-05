import os
import sys
import time

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from addon import HANDLE, addict, utils

ADDON = xbmcaddon.Addon()

ADDON_DIR = xbmc.translatePath(ADDON.getAddonInfo('path'))
PROFILE_DIR = xbmc.translatePath(os.path.join(ADDON.getAddonInfo('profile')))

TEST_LOGIN_NETWORK = 'difm'

QUALITY_MAP = {
    utils.translate(30200): 'aac_64k',  # Good (64k AAC)
    utils.translate(30201): 'aac_128k',  # Excellent (128k AAC)
    utils.translate(30202): 'mp3_320k',  # Excellent (320k MP3)
}


def list_networks(network=None, do_list=True):
    items = []

    if not network:
        for key, data in addict.NETWORKS.iteritems():
            item = xbmcgui.ListItem(data['name'])
            item.setArt({
                'thumb': os.path.join(ADDON_DIR, 'resources', 'assets',
                                      key + '.png'),
                'fanart': os.path.join(ADDON_DIR, 'fanart.jpg'),
            })

            item.addContextMenuItems([
                (utils.translate(30307), 'RunPlugin({})'.format(
                    utils.build_path('refresh', network=key))),
            ], True)

            items.append((utils.build_path('networks', key), item, True))

    else:
        aa = addict.AudioAddict(PROFILE_DIR, network)
        xbmcplugin.setPluginCategory(HANDLE, aa.name)
        xbmcplugin.setContent(HANDLE, 'files')

        # Channels
        items.append((utils.build_path('channels', network),
                      xbmcgui.ListItem(utils.translate(30321)), True))

        # Shows
        if aa.is_premium and aa.network['has_shows']:
            items.append((utils.build_path('shows', network),
                          xbmcgui.ListItem(utils.translate(30322)), True))

        # Search
        items.append((utils.build_path('search', network),
                      xbmcgui.ListItem(utils.translate(30323)), True))

    if not do_list:
        return items
    utils.list_items(items)


def list_channels(network, style=None, channels=None, do_list=True):
    aa = addict.AudioAddict(PROFILE_DIR, network)
    xbmcplugin.setPluginCategory(HANDLE, aa.name)

    items = []
    if not any((style, channels)):
        xbmcplugin.setContent(HANDLE, 'albums')

        filters = aa.channel_filters()
        favorites = aa.favorites()
        if favorites:
            filters.insert(
                0, {
                    'key': 'favorites',
                    'name': utils.translate(30308),
                    'channels': favorites,
                })

        for style in filters:
            item = xbmcgui.ListItem('{} ({})'.format(style['name'],
                                                     len(style['channels'])))
            item.setArt({
                'fanart': os.path.join(ADDON_DIR, 'fanart.jpg'),
            })
            items.append((utils.build_path('channels', network, style['key']),
                          item, True))

    else:
        xbmcplugin.setContent(HANDLE, 'songs')

        if not channels:
            if style == 'favorites':
                channels = aa.favorites()
            else:
                channels = aa.channels(style)

        show_fanart = ADDON.getSettingBool('view.fanart')
        for channel in channels:
            item_url = utils.build_path('play', network, channel.get('key'))

            item = xbmcgui.ListItem(channel.get('name'))
            item.setPath(item_url)

            item = utils.add_aa_art(item, channel, 'default', 'compact',
                                    set_fanart=show_fanart)
            items.append((item_url, item, False))

    if not do_list:
        return items
    utils.list_items(items)


def list_shows(network, filter_=None, channel=None, field=None, shows=None,
               page=1, do_list=True):
    aa = addict.AudioAddict(PROFILE_DIR, network)
    xbmcplugin.setPluginCategory(HANDLE, aa.name)

    fanart = ADDON.getSettingBool('view.fanart')
    per_page = ADDON.getSettingInt('aa.shows_per_page')

    if filter_ == 'followed':
        shows = aa.show_followed(page=page, per_page=per_page)

    elif filter_ == 'channels':
        _res = aa.shows(channel, field, page=page, per_page=per_page)
        shows = _res.get('results', [])
        facets = _res.get('metadata', {}).get('facets', [])

    items = []
    if shows:
        for show in shows:
            item_url = utils.build_path('episodes', network, show.get('slug'))

            item = xbmcgui.ListItem(show.get('name'))
            item = utils.add_aa_art(item, show, set_fanart=fanart)

            items.append((item_url, item, True))

        if do_list and len(items) >= per_page:
            items.append((
                utils.build_path('shows', network, channel, field=field,
                                 page=page + 1),
                xbmcgui.ListItem(utils.translate(30318)),
                True,
            ))
    else:
        if not filter_:
            # Followed Shows
            items.append((utils.build_path('shows', network, 'followed'),
                          xbmcgui.ListItem(utils.translate(30324)), True))

            # By Channel
            items.append((utils.build_path('shows', network, 'channels'),
                          xbmcgui.ListItem(utils.translate(30325)), True))

        elif filter_ == 'channels' and not all((channel, field)):
            facets = sorted(facets, key=lambda f: f['name'])

            for facet in facets:
                item_url = utils.build_path('shows', network, 'channels',
                                            facet.get('name'), field=facet.get(
                                                'field', ''))
                items.append((item_url, xbmcgui.ListItem(facet.get('label')),
                              True))

    if not do_list:
        return items
    utils.list_items(items)


def list_episodes(network, slug, page=1, do_list=True):
    aa = addict.AudioAddict(PROFILE_DIR, network)
    xbmcplugin.setPluginCategory(HANDLE, aa.name)

    fanart = ADDON.getSettingBool('view.fanart')
    per_page = ADDON.getSettingInt('aa.shows_per_page')

    xbmcplugin.setContent(HANDLE, 'songs')

    items = []
    for ep in aa.show_episodes(slug, page, per_page):
        tracks = ep.get('tracks', [])
        if not tracks:
            continue

        track = tracks[0]
        item = xbmcgui.ListItem()
        item.setInfo(
            'music', {
                'title': track.get('display_title'),
                'artist': track.get('display_artist'),
                'duration': track.get('length'),
            })
        item = utils.add_aa_art(item, ep.get('show'), set_fanart=fanart)

        assets = track.get('content', {}).get('assets', [])
        if not assets:
            continue

        url = addict.AudioAddict.url(assets[0].get('url'))
        items.append((url, item, False))

    if len(items) >= per_page:
        items.append((
            utils.build_path(['episodes', network, slug], page=page + 1),
            xbmcgui.ListItem(utils.translate(30318)),
            True,
        ))

    if not do_list:
        return items
    utils.list_items(items)


def search(network, query=None, filter_=None, page=1):
    aa = addict.AudioAddict(PROFILE_DIR, network)
    xbmcplugin.setPluginCategory(HANDLE, aa.name)

    per_page = ADDON.getSettingInt('aa.shows_per_page')

    if not query:
        k = xbmc.Keyboard(heading=utils.translate(30323))
        k.doModal()
        if not k.isConfirmed():
            return False
        query = k.getText()

    if not aa.network['has_shows'] or not aa.is_premium:
        filter_ = 'channels'

    if filter_:
        res = aa.search(query, page=page)

    items = []
    if not filter_:
        # Channels
        items.append((utils.build_path('search', network, query, 'channels'),
                      xbmcgui.ListItem(utils.translate(30321)), True))

        # Shows
        items.append((utils.build_path('search', network, query, 'shows'),
                      xbmcgui.ListItem(utils.translate(30322)), True))

    elif filter_ == 'channels':
        channels = res.get('channels', {}).get('items', [])
        if channels:
            items = list_channels(network, channels=channels, do_list=False)

    elif filter_ == 'shows':
        shows = res.get('shows', {}).get('items', [])
        if shows:
            items = list_shows(network, shows=shows, do_list=False)

    if filter_ and len(items) >= per_page:
        items.append((
            utils.build_path('search', network, query, filter_, page=page + 1),
            xbmcgui.ListItem(utils.translate(30318)),
            True,
        ))

    utils.list_items(items)


def play_channel(network, channel):
    valid_handle = HANDLE != -1

    aa = addict.AudioAddict(PROFILE_DIR, network)

    diag = None
    if not valid_handle:
        diag = xbmcgui.DialogProgressBG()
        diag.create(utils.translate(30316))

    track = {}
    for elem in aa.currently_playing():
        if elem.get('channel_key') != channel:
            continue

        track = elem.get('track', {})

    track = aa.track(track.get('id'))
    item_url = utils.build_path('track', network, channel, track.get('id'))

    item = utils.build_track_item(track)
    item.setPath(item_url)

    if diag:
        diag.close()

    playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    playlist.clear()
    playlist.add(item.getPath(), item)

    if valid_handle:
        # Item activated through e.g. Chorus2
        xbmcplugin.setResolvedUrl(HANDLE, True, item)

    else:
        # Item activated through Kodi itself
        xbmc.Player().play()


def resolve_track(network, channel, track_id, cache=False):
    aa = addict.AudioAddict(PROFILE_DIR, network)

    track = aa.track(track_id)
    item = utils.build_track_item(track)

    xbmcplugin.setResolvedUrl(HANDLE, True, item)

    add_track(network, channel, track, cache)


def add_track(network, channel, current_track=None, cache=False):
    if not current_track:
        current_track = {}

    playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    if playlist.getposition() + 2 >= playlist.size():
        utils.log('Adding another track to the playlist...')

        next_track = utils.next_track(network, channel, cache)
        if current_track.get('id') == next_track.get('id'):
            # Was the same track as is already playing, get a new one
            next_track = utils.next_track(network, channel)

        next_item = utils.build_track_item(next_track)
        next_item.setPath(
            utils.build_path('track', network, channel, next_track.get('id'),
                             cache=True))

        playlist.add(next_item.getPath(), next_item)


def update_networks(networks=None):
    if not networks:
        networks = addict.NETWORKS.keys()

    diag = xbmcgui.DialogProgress()
    diag.create(utils.translate(30312))

    utils.log('Updating network', networks)
    for i, network in enumerate(networks):
        progress = i * 100 / len(networks)
        aa = addict.AudioAddict(PROFILE_DIR, network)

        diag.update(progress, utils.translate(30313).format(aa.name))
        aa.channels(refresh=True)
        aa.favorites(refresh=True)

    diag.update(100, utils.translate(30314))
    diag.close()


def setup(notice=True, update_cache=False):
    aa = addict.AudioAddict(PROFILE_DIR, TEST_LOGIN_NETWORK)
    aa.logout()

    ADDON.setSetting('aa.email', '')

    if notice:
        xbmcgui.Dialog().ok(utils.translate(30300), utils.translate(30302))

    k = xbmc.Keyboard(aa.member.get('email', ''), utils.translate(30319))
    k.doModal()
    if not k.isConfirmed():
        return False
    username = k.getText()

    k = xbmc.Keyboard('', utils.translate(30320), True)
    k.doModal()
    if not k.isConfirmed():
        return False
    password = k.getText()

    if not aa.login(username, password, refresh=True):
        if xbmcgui.Dialog().yesno(
                utils.translate(30309), utils.translate(30310)):
            return setup(False, update_cache)
        return False

    ADDON.setSetting('aa.email', username)

    utils.notify(utils.translate(30304), utils.translate(30305))
    if not aa.is_premium:
        utils.go_premium()

    if update_cache:
        update_networks()

    return True


def run():
    utils.log(sys.argv[0] + sys.argv[2])
    url = utils.parse_url(sys.argv[0] + sys.argv[2], 'networks')

    aa = addict.AudioAddict(PROFILE_DIR, TEST_LOGIN_NETWORK)
    if not aa.is_active and url.path[0] not in ['setup', 'logout']:
        if not setup(True, True):
            sys.exit(0)

    # Routing
    if url.path[0] == 'setup':
        setup(False, True)

    elif url.path[0] == 'logout':
        aa.logout()
        utils.notify(utils.translate(30306), '')
        sys.exit(0)

    elif url.path[0] == 'refresh':
        network = url.query.get('network')
        update_networks(filter([network]))

    elif url.path[0] == 'search':
        search(*url.path[1:], **url.query)

    elif url.path[0] == 'networks':
        last_prompt = ADDON.getSettingInt('addon.last_premium_prompt')
        if not aa.is_premium and last_prompt + (3600 * 1) < time.time():
            utils.go_premium()

        list_networks(*url.path[1:], **url.query)

    elif url.path[0] == 'play':
        utils.log('calling play channel')
        play_channel(*url.path[1:], **url.query)

    elif url.path[0] == 'channels':
        list_channels(*url.path[1:], **url.query)

    elif url.path[0] == 'track':
        resolve_track(*url.path[1:], **url.query)

    elif url.path[0] == 'shows':
        list_shows(*url.path[1:], **url.query)

    elif url.path[0] == 'episodes':
        list_episodes(*url.path[1:], **url.query)
