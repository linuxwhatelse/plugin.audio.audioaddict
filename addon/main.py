import json
import os
import sys

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


def list_networks():
    items = []
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

        items.append((utils.build_path('channels', key), item, True))

    utils.list_items(items)


def list_channels(network, style=None, channel=None):
    show_fanart = ADDON.getSettingBool('view.fanart')
    aa = addict.AudioAddict(PROFILE_DIR, network)

    xbmcplugin.setPluginCategory(HANDLE, aa.name)

    items = []
    if not style:
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
            item.setInfo('music', {
                'count': len(style['channels']),
            })
            item.setArt({
                'fanart': os.path.join(ADDON_DIR, 'fanart.jpg'),
            })
            items.append((utils.build_path('channels', network, style['key']),
                          item, True))

    else:
        xbmcplugin.setContent(HANDLE, 'songs')

        if style == 'favorites':
            channels = aa.favorites()
        else:
            channels = aa.channels(style)

        # playing = {}
        # for elem in aa.currently_playing():
        #     playing[elem.get('channel_key')] = elem.get('track')

        for channel in channels:
            item_url = utils.build_path('play', network, channel['key'])

            asset_url = channel.get('asset_url', '')

            item = xbmcgui.ListItem(channel.get('name'))
            item.setPath(item_url)
            item.setArt({
                'thumb': addict.AudioAddict.url(asset_url, width=512),
                'banner': addict.AudioAddict.url(
                    channel.get('banner_url', None), height=512),
            })

            if show_fanart:
                fanart = channel.get('images', {}).get('compact', asset_url)
                item.setArt({
                    'fanart': addict.AudioAddict.url(fanart, height=720),
                })

            # item.addContextMenuItems([
            #     (utils.translate(30317), 'Container.Update({})'.format(
            #         utils.build_path('shows', network, channel['key']))),
            # ], True)

            items.append((item_url, item, False))

    utils.list_items(items)


def list_shows(network, channel, slug=None, page=1):
    def _set_art(item, show, fanart=True):
        compact = show.get('images', {}).get('compact', '')
        item.setArt({
            'thumb': addict.AudioAddict.url(compact, width=512),
        })

        if fanart:
            fanart = show.get('images', {}).get('default', compact)
            item.setArt({
                'fanart': addict.AudioAddict.url(fanart, height=720),
            })
        return item

    show_fanart = ADDON.getSettingBool('view.fanart')
    aa = addict.AudioAddict(PROFILE_DIR, network)

    xbmcplugin.setPluginCategory(HANDLE, aa.name)

    next_page_url = ['shows', network, channel]
    if slug:
        next_page_url.append(slug)

    next_page = (
        utils.build_path(*next_page_url, page=page + 1),
        xbmcgui.ListItem(utils.translate(30318)),
        True,
    )

    items = []
    if not slug:
        xbmcplugin.setContent(HANDLE, 'albums')
        channel_name = None
        for c in aa.channels():
            if c['key'] == channel:
                channel_name = c['name']
                break

        shows = aa.shows(channel_name, page, 100)

        for show in shows.get('results', []):
            item = xbmcgui.ListItem(show['name'])
            item = _set_art(item, show, show_fanart)
            item_url = utils.build_path('shows', network, channel,
                                        show['slug'])
            items.append((item_url, item, True))
        has_next = len(shows.get('results', [])) == 100

    else:
        xbmcplugin.setContent(HANDLE, 'songs')
        for ep in aa.show_episodes(slug, page):
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
            item = _set_art(item, ep.get('show'), show_fanart)

            assets = track.get('content', {}).get('assets', [])
            if not assets:
                continue

            url = addict.AudioAddict.url(assets[0].get('url'))
            items.append((url, item, False))

    if items:
        items.append(next_page)

    utils.list_items(items)


def play_channel(network, channel):
    valid_handle = HANDLE != -1

    diag = None
    if not valid_handle:
        diag = xbmcgui.DialogProgressBG()
        diag.create(utils.translate(30316))

    aa = addict.AudioAddict(PROFILE_DIR, network)

    track = {}
    for elem in aa.currently_playing():
        if elem.get('channel_key') != channel:
            continue

        track = elem.get('track', {})

    track = aa.track(str(track.get('id')))
    item_url = utils.build_path('track', network, channel, track.get('id'))

    item = utils.build_track_item(track)
    item.setPath(item_url)

    if diag:
        diag.close()

    if valid_handle:
        # Item activated through e.g. Chrous2
        xbmcplugin.setResolvedUrl(HANDLE, True, item)

        # Wait up to 5 sec. for playback to start
        utils.log('Waiting for player to play something.')
        player = xbmc.Player()
        for i in range(10):
            if player.isPlayingAudio():
                break
            xbmc.sleep(250)

        if player.isPlayingAudio():
            utils.log('Updating infotag')
            item.setPath(utils.build_path('play', network, channel))
            player.updateInfoTag(item)

    else:
        # Item activated through Kodi itself
        utils.log('Manually starting playback')
        playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        playlist.clear()
        playlist.add(item_url, item)

        xbmc.Player().play()


def resolve_track(network, channel, track_id, cache=False):
    aa = addict.AudioAddict(PROFILE_DIR, network)

    track = aa.track(track_id)
    item = utils.build_track_item(track)

    xbmcplugin.setResolvedUrl(HANDLE, True, item)

    playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    if playlist.getposition() + 2 >= playlist.size():
        utils.log('Adding another track to the playlist...')
        next_track = utils.next_track(network, channel, cache)

        if track.get('id') == next_track.get('id'):
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

    for i, network in enumerate(networks):
        progress = i * 100 / len(networks)
        aa = addict.AudioAddict(PROFILE_DIR, network)

        diag.update(progress, utils.translate(30313).format(aa.name))
        aa.channels(force=True)
        aa.favorites(force=True)

    diag.update(100, utils.translate(30314))
    diag.close()


def setup(notice=True, update_cache=False):
    addon = xbmcaddon.Addon()

    aa = addict.AudioAddict(PROFILE_DIR, TEST_LOGIN_NETWORK)
    aa.logout()

    addon.setSetting('aa.email', '')

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

    if not aa.login(username, password, force=True):
        if xbmcgui.Dialog().yesno(
                utils.translate(30309), utils.translate(30310)):
            return setup(False, update_cache)
        return False

    addon.setSetting('aa.email', username)

    utils.notify(utils.translate(30304), utils.translate(30305))
    if not aa.is_premium:
        xbmcgui.Dialog().textviewer(
            utils.translate(30311), utils.translate(30301))

    if update_cache:
        update_networks(None)

    return True


def run():
    url = utils.parse_url(sys.argv[0] + sys.argv[2])
    utils.log(sys.argv[0] + sys.argv[2])

    aa = addict.AudioAddict(PROFILE_DIR, TEST_LOGIN_NETWORK)
    if not aa.is_active and url.path[0] not in ['setup', 'logout']:
        if not setup(True, True):
            sys.exit(0)

    # Routing
    if url.path == []:
        list_networks()

    elif url.path[0] == 'setup':
        setup(False, True)

    elif url.path[0] == 'logout':
        aa.logout()
        utils.notify(utils.translate(30306), '')
        sys.exit(0)

    elif url.path[0] == 'refresh':
        network = url.query.get('network', [])
        update_networks(network)

    elif url.path[0] == 'channels':
        list_channels(*url.path[1:], **url.query)

    elif url.path[0] == 'play':
        play_channel(*url.path[1:], **url.query)

    elif url.path[0] == 'track':
        resolve_track(*url.path[1:], **url.query)

    elif url.path[0] == 'shows':
        list_shows(*url.path[1:], **url.query)
