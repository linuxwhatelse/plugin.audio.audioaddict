import os
import sys
import time

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from addon import HANDLE, addict, utils
from addon.utils import _enc
from mapper import Mapper

MPR = Mapper.get()
ADDON = xbmcaddon.Addon()

ADDON_DIR = xbmc.translatePath(ADDON.getAddonInfo('path'))
PROFILE_DIR = xbmc.translatePath(os.path.join(ADDON.getAddonInfo('profile')))

TEST_LOGIN_NETWORK = 'difm'


@MPR.s_url('/')
@MPR.s_url('/networks/')
def list_networks():
    items = []

    for key, data in addict.NETWORKS.iteritems():
        item = xbmcgui.ListItem(data['name'])
        item.setArt({
            'thumb': os.path.join(ADDON_DIR, 'resources', 'assets',
                                  key + '.png'),
        })

        item.addContextMenuItems([
            (utils.translate(30307), 'RunPlugin({})'.format(
                utils.build_path('refresh', key))),
        ], True)

        items.append((utils.build_path('networks', key), item, True))

    utils.list_items(items)


@MPR.s_url('/networks/<network>/')
def list_network(network):
    items = []

    aa = addict.AudioAddict.get(PROFILE_DIR, network)
    xbmcplugin.setPluginCategory(HANDLE, aa.name)
    xbmcplugin.setContent(HANDLE, 'files')

    # Channels
    items.append((utils.build_path('channels', network),
                  xbmcgui.ListItem(utils.translate(30321)), True))

    # Shows
    if aa.network['has_shows']:
        items.append((utils.build_path('shows', network),
                      xbmcgui.ListItem(utils.translate(30322)), True))

        items.append((utils.build_path('shows', network, 'schedule'),
                      xbmcgui.ListItem(utils.translate(30332)), True))

    # Search
    items.append((utils.build_path('search', network),
                  xbmcgui.ListItem(utils.translate(30323)), True))

    utils.list_items(items)


@MPR.s_url('/channels/<network>/')
def list_styles(network):
    aa = addict.AudioAddict.get(PROFILE_DIR, network)
    xbmcplugin.setPluginCategory(HANDLE, aa.name)
    xbmcplugin.setContent(HANDLE, 'albums')

    items = []

    filters = aa.get_channel_filters()
    favorites = aa.get_favorite_channels()
    if favorites:
        filters.insert(
            0, {
                'key': 'favorites',
                'name': utils.translate(30308),
                'channels': favorites,
            })

    for style in filters:
        item = xbmcgui.ListItem('{} ({})'.format(
            _enc(style.get('name')), len(style.get('channels', []))))
        items.append((utils.build_path('channels', network, style.get('key')),
                      item, True))

    utils.list_items(items)


@MPR.s_url('/channels/<network>/<style>/')
def list_channels(network, style=None, channels=None, do_list=True):
    aa = addict.AudioAddict.get(PROFILE_DIR, network)
    xbmcplugin.setPluginCategory(HANDLE, aa.name)
    xbmcplugin.setContent(HANDLE, 'songs')

    items = []

    if not channels:
        if style == 'favorites':
            channels = aa.get_favorite_channels()
        else:
            channels = aa.get_channels(style)

    favorites = [f['channel_id'] for f in aa.get_favorites()]
    # If I ever manage to get label2 to show, that's what we're going to
    # put there...
    # playing = {
    #     p['channel_id']: p['track']
    #     for p in aa.get_currently_playing()
    # }

    for channel in channels:
        item_url = utils.build_path('play', network, channel.get('key'))

        item = xbmcgui.ListItem(_enc(channel.get('name')))
        item.setPath(item_url)
        item = utils.add_aa_art(item, channel, 'default', 'compact')

        cmenu = []
        if channel.get('id') not in favorites:
            # Add to favorites
            cmenu.append((utils.translate(30326), 'RunPlugin({})'.format(
                utils.build_path('favorite', network, channel.get('key'),
                                 channel_name=_enc(channel.get('name'))))))
        else:
            # Remove from favorites
            cmenu.append((utils.translate(30327), 'RunPlugin({})'.format(
                utils.build_path('unfavorite', network, channel.get('key'),
                                 channel_name=_enc(channel.get('name'))))))

        cmenu.append((utils.translate(30330),
                      'Container.Update({}, return)'.format(
                          utils.build_path('listen_history', network,
                                           channel.get('key')))))

        item.addContextMenuItems(cmenu, True)
        items.append((item_url, item, False))

    if not do_list:
        return items
    utils.list_items(items)


@MPR.s_url('/listen_history/<network>/<channel>/')
def list_listen_history(network, channel):
    aa = addict.AudioAddict.get(PROFILE_DIR, network)
    xbmcplugin.setPluginCategory(HANDLE, aa.name)
    xbmcplugin.setContent(HANDLE, 'songs')

    items = []
    for track in aa.get_listen_history(channel):
        item = utils.build_track_item(track.get('track'))
        item.setProperty('IsPlayable', 'false')
        item.setPath(None)
        items.append((None, item, False))

    utils.list_items(items)


@MPR.s_url('/shows/<network>/')
def list_shows_menu(network):
    aa = addict.AudioAddict.get(PROFILE_DIR, network)
    xbmcplugin.setPluginCategory(HANDLE, aa.name)

    items = []

    # Followed Shows
    items.append((utils.build_path('shows', network, 'followed'),
                  xbmcgui.ListItem(utils.translate(30324)), True))

    # By Style
    items.append((utils.build_path('shows', network, 'fields',
                                   'channel_filter_name'),
                  xbmcgui.ListItem(utils.translate(30325)), True))

    # By Channel
    items.append((utils.build_path('shows', network, 'fields', 'channel_name'),
                  xbmcgui.ListItem(utils.translate(30316)), True))

    # Schedule
    items.append((utils.build_path('shows', network, 'schedule'),
                  xbmcgui.ListItem(utils.translate(30332)), True))

    utils.list_items(items)


@MPR.s_url('/shows/<network>/followed/')
def list_shows_followed(network, page=1):
    aa = addict.AudioAddict.get(PROFILE_DIR, network)
    xbmcplugin.setPluginCategory(HANDLE, aa.name)

    per_page = ADDON.getSettingInt('aa.shows_per_page')

    shows = aa.get_shows_followed(page=page, per_page=per_page)

    items = []
    for show in shows:
        item = utils.build_show_item(network, show)
        items.append((item.getPath(), item, True))

    if len(items) >= per_page:
        items.append((
            utils.build_path('shows', network, 'followed', page=page + 1),
            xbmcgui.ListItem(utils.translate(30318)),
            True,
        ))

    utils.list_items(items)


@MPR.s_url('/shows/<network>/fields/<field>/')
def list_shows_styles(network, field):
    aa = addict.AudioAddict.get(PROFILE_DIR, network)
    xbmcplugin.setPluginCategory(HANDLE, aa.name)

    facets = aa.get_show_facets()
    facets = sorted(facets, key=lambda f: f['name'])

    items = []
    for facet in facets:
        if facet.get('field') != field:
            continue

        item_url = utils.build_path('shows', network, 'facets',
                                    facet.get('name'))
        items.append((item_url, xbmcgui.ListItem(_enc(facet.get('label'))),
                      True))

    utils.list_items(items)


@MPR.s_url('/shows/<network>/facets/<facet>/')
def list_shows(network, facet='All', page=1):
    aa = addict.AudioAddict.get(PROFILE_DIR, network)
    xbmcplugin.setPluginCategory(HANDLE, aa.name)

    per_page = ADDON.getSettingInt('aa.shows_per_page')
    shows = aa.get_shows(facet, page=page, per_page=per_page)

    items = []
    for show in shows:
        item = utils.build_show_item(network, show)
        items.append((item.getPath(), item, True))

    if len(items) >= per_page:
        items.append((
            utils.build_path('shows', network, 'followed', page=page + 1),
            xbmcgui.ListItem(utils.translate(30318)),
            True,
        ))

    utils.list_items(items)


@MPR.s_url('/shows/<network>/schedule/')
def list_shows_schedule(network, page=1):
    aa = addict.AudioAddict.get(PROFILE_DIR, network)
    xbmcplugin.setPluginCategory(HANDLE, aa.name)

    shows = aa.get_upcoming()
    shows = sorted(shows, key=lambda s: s['start_at'])

    # Shows for "get_upcoming" have "following" always set to False
    # Have to work around this for now :/
    followed_shows = aa.get_shows_followed()
    followed_slugs = [s.get('slug') for s in followed_shows]

    now = addict.datetime_now()

    items = []
    for show in shows:
        end_at = addict.parse_datetime(show.get('end_at'))

        if end_at < now:
            continue

        start_at = addict.parse_datetime(show.get('start_at'))

        show = show.get('show', {})
        channel = show.get('channels', [])[0]

        item = utils.build_show_item(network, show, followed_slugs)
        item.setPath(utils.build_path('play', network, channel.get('key')))

        if start_at < now or show.get('now_playing', False):
            label_prefix = utils.translate(30333)  # Live now
        else:
            label_prefix = '{} - {}'.format(
                start_at.strftime('%H:%M'), end_at.strftime('%H:%M'))

        item.setLabel('[B]{}[/B] - {} [I]({})[/I]'.format(
            label_prefix, _enc(show.get('name')), _enc(channel.get('name'))))

        items.append((item.getPath(), item, False))

    utils.list_items(items)


@MPR.s_url('/episodes/<network>/<slug>/', type_cast={'page': int})
def list_episodes(network, slug, page=1):
    aa = addict.AudioAddict.get(PROFILE_DIR, network)
    xbmcplugin.setContent(HANDLE, 'songs')
    xbmcplugin.setPluginCategory(HANDLE, aa.name)

    per_page = ADDON.getSettingInt('aa.shows_per_page')

    items = []
    for ep in aa.get_show_episodes(slug, page, per_page):
        tracks = ep.get('tracks', [])
        if not tracks:
            continue

        item = utils.build_track_item(tracks[0])
        item = utils.add_aa_art(item, ep.get('show'))

        items.append((item.getPath(), item, False))

    if len(items) >= per_page:
        items.append((
            utils.build_path('episodes', network, slug, page=page + 1),
            xbmcgui.ListItem(utils.translate(30318)),
            True,
        ))

    utils.list_items(items)


@MPR.s_url('/favorite/<network>/<channel>/')
def favorite(network, channel, channel_name=''):
    aa = addict.AudioAddict.get(PROFILE_DIR, network)

    with utils.busy_dialog():
        aa.add_favorite(channel)
        utils.notify(utils.translate(30328).format(channel_name))

    xbmc.executebuiltin('Container.Refresh')


@MPR.s_url('/unfavorite/<network>/<channel>/')
def favorite(network, channel, channel_name=''):
    aa = addict.AudioAddict.get(PROFILE_DIR, network)

    with utils.busy_dialog():
        aa.remove_favorite(channel)
        utils.notify(utils.translate(30329).format(channel_name))

    xbmc.executebuiltin('Container.Refresh')


@MPR.s_url('/follow/<network>/<slug>/')
def follow(network, slug, show_name=''):
    aa = addict.AudioAddict.get(PROFILE_DIR, network)

    with utils.busy_dialog():
        aa.follow_show(slug)
        utils.notify(utils.translate(30336).format(show_name))

    xbmc.executebuiltin('Container.Refresh')


@MPR.s_url('/unfollow/<network>/<slug>/')
def unfollow(network, slug, show_name=''):
    aa = addict.AudioAddict.get(PROFILE_DIR, network)

    with utils.busy_dialog():
        aa.unfollow_show(slug)
        utils.notify(utils.translate(30337).format(show_name))

    xbmc.executebuiltin('Container.Refresh')


@MPR.s_url('/search/<network>/')
@MPR.s_url('/search/<network>/<filter_>/<query>/', type_cast={'page': int})
def search(network, filter_=None, query=None, page=1):
    aa = addict.AudioAddict.get(PROFILE_DIR, network)
    xbmcplugin.setPluginCategory(HANDLE, aa.name)

    per_page = ADDON.getSettingInt('aa.shows_per_page')

    if not query:
        k = xbmc.Keyboard(heading=utils.translate(30323))
        k.doModal()
        if not k.isConfirmed():
            return False
        query = k.getText()

    if not aa.network['has_shows']:
        filter_ = 'channels'

    items = []
    if not filter_:
        # Channels
        items.append((utils.build_path('search', network, 'channels', query),
                      xbmcgui.ListItem(utils.translate(30321)), True))

        # Shows
        items.append((utils.build_path('search', network, 'shows', query),
                      xbmcgui.ListItem(utils.translate(30322)), True))

    else:
        if filter_ == 'channels':
            channels = aa.search_channels(query, page=page)
            if channels:
                items = list_channels(network, channels=channels,
                                      do_list=False)

        elif filter_ == 'shows':
            for show in aa.search_shows(query, page).get('results', []):
                item = utils.build_show_item(network, show)
                items.append((item.getPath(), item, True))

        if filter_ and len(items) >= per_page:
            items.append((
                utils.build_path('search', network, query, filter_,
                                 page=page + 1),
                xbmcgui.ListItem(utils.translate(30318)),
                True,
            ))

    utils.list_items(items)


@MPR.s_url('/play/<network>/<channel>/')
def play_channel(network, channel):
    # Item activated through e.g. Chorus2
    # If we'd call "play" within this "session", kodi would crash.
    if HANDLE != -1:
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        xbmc.executebuiltin('RunPlugin({})'.format(
            utils.build_path('play', network, channel)))
        return

    utils.logd('Fetching tracklist from server...')
    aa = addict.AudioAddict.get(PROFILE_DIR, network)
    with utils.busy_dialog():
        is_live, track = aa.next_track(channel, cache=False, pop=False,
                                       live=True)

        utils.logd('Activating first track: {}, is-live: {}'.format(
            track.get('id'), is_live))
        item_url = utils.build_path('track', network, channel, track.get('id'),
                                    is_live=is_live)

        item = utils.build_track_item(track, item_url)

        playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        playlist.clear()
        playlist.add(item.getPath(), item)

        xbmc.Player().play()


@MPR.s_url('/track/<network>/<channel>/<track_id>/',
           type_cast={'is_live': bool})
def resolve_track(network, channel, track_id, is_live=False):
    utils.logd('Resolving track:', track_id)
    aa = addict.AudioAddict.get(PROFILE_DIR, network)

    current_is_live, track = aa.next_track(channel, cache=True, pop=True,
                                           live=is_live)

    utils.logd('Resolved track: {}, is-live: {}'.format(
        track.get('id'), current_is_live))
    if int(track_id) != track.get('id'):
        utils.logw('Got unexpected track from cache!'
                   'Expected {} but got {}'.format(track_id, track.get('id')))

    item = utils.build_track_item(track)

    xbmcplugin.setResolvedUrl(HANDLE, True, item)

    offset = track.get('content', {}).get('offset', 0)
    if ADDON.getSettingBool('addon.seek_offset') and offset:
        playing = utils.get_playing()
        if (not playing or playing['live'] or
            (playing['network'] != network and playing['channel'] != channel)):
            # Have at least 30 sec. left to prevent the track ending before
            # the next one has been queued
            length = track.get('length')
            offset = min(length - 30, offset)

            utils.logd('Seeking to:', offset)
            if not utils.seek_offset(offset):
                utils.logd('Seeking failed!')

    aa.add_listen_history(channel, track_id)

    # Queue another track if it's the last one playing
    playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
    if playlist.getposition() + 2 < playlist.size():
        return

    utils.logd('Adding another track to the playlist...')
    is_live, track = aa.next_track(channel, cache=True, pop=False,
                                   live=not current_is_live)

    item = utils.build_track_item(track)
    item.setPath(
        utils.build_path('track', network, channel, track.get('id'),
                         is_live=is_live))

    utils.logd('Queuing track: {}, is-live: {}'.format(
        track.get('id'), is_live))
    playlist.add(item.getPath(), item)


@MPR.s_url('/refresh/')
@MPR.s_url('/refresh/<network>/')
def update_networks(network=None):
    networks = None
    if network:
        networks = [network]
    else:
        networks = addict.NETWORKS.keys()

    diag = xbmcgui.DialogProgress()
    diag.create(utils.translate(30312))

    quality_id = utils.get_quality_id(TEST_LOGIN_NETWORK)
    utils.logd('Got quality-id:', quality_id)

    for i, network in enumerate(networks):
        utils.logd('Updating network', network)
        aa = addict.AudioAddict.get(PROFILE_DIR, network)

        progress = i * 100 / len(networks)
        diag.update(progress, utils.translate(30313).format(aa.name))

        aa.get_channels(refresh=True)
        aa.get_favorite_channels(refresh=True)

        if aa.is_premium:
            utils.logd('Setting preferred quality')
            aa.preferred_quality(quality_id)

    diag.update(100, utils.translate(30314))
    diag.close()


@MPR.s_url('/setup/', type_cast={'notice': bool, 'update_cache': bool})
def setup(notice=True, update_cache=False):
    for network in addict.NETWORKS.keys():
        addict.AudioAddict.get(PROFILE_DIR, network).logout()

    aa = addict.AudioAddict.get(PROFILE_DIR, TEST_LOGIN_NETWORK)

    ADDON.setSetting('aa.email', '')

    if notice:
        xbmcgui.Dialog().textviewer(
            utils.translate(30300), utils.translate(30301))

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

    if not aa.login(username, password):
        if xbmcgui.Dialog().yesno(
                utils.translate(30309), utils.translate(30310)):
            return setup(False, update_cache)
        return False

    ADDON.setSetting('aa.email', username)

    utils.notify(utils.translate(30304), utils.translate(30305))
    if not aa.is_premium:
        utils.go_premium()
        ADDON.setSettingInt('addon.last_premium_prompt', int(time.time()))

    if update_cache:
        update_networks()

    return True


@MPR.s_url('/logout/')
def logout():
    for network in addict.NETWORKS.keys():
        addict.AudioAddict.get(PROFILE_DIR, network).logout()

    utils.clear_cache()

    ADDON.setSetting('aa.email', '')
    utils.notify(utils.translate(30306))
    sys.exit(0)


@MPR.s_url('/clear_cache/')
def clear_cache():
    utils.clear_cache()
    utils.notify(utils.translate(30315))
    sys.exit(0)


def run():
    url = sys.argv[0] + sys.argv[2]
    utils.logd(HANDLE, url)

    aa = addict.AudioAddict.get(PROFILE_DIR, TEST_LOGIN_NETWORK)

    url_parsed = utils.parse_url(url)
    path_ = next(iter(url_parsed.path), '')

    if not aa.is_active and path_ not in ['setup', 'logout', 'clear_cache']:
        if not setup(True, True):
            sys.exit(0)

    MPR.call(url)
