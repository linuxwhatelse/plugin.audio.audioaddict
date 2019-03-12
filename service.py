import os
import time
from datetime import datetime

import dateutil
import xbmc
import xbmcaddon
from addon import addict, utils
from dateutil.parser import parse

ADDON = xbmcaddon.Addon()

ADDON_ID = os.path.join(ADDON.getAddonInfo('id'))
PROFILE_DIR = xbmc.translatePath(os.path.join(ADDON.getAddonInfo('profile')))

CACHE_UPDATE_INTERVAL = 600


def update_cache():
    for network in addict.NETWORKS.keys():
        aa = addict.AudioAddict(PROFILE_DIR, network)

        aa.invalidate_cache()

        if not aa.is_active:
            continue

        utils.log('Updating "{}"'.format(aa.name))

        utils.log('Updating channels/favorites')
        aa.get_channel_filters(refresh=True)
        aa.get_favorites(refresh=True)

        if aa.network['has_shows']:
            utils.log('Updating upcoming/followed shows')
            aa.get_shows_followed(refresh=True)
            aa.get_upcoming(refresh=True)


def monitor_live(skip_shows=None):
    if not skip_shows:
        skip_shows = []

    now = datetime.now(dateutil.tz.UTC)

    for network in addict.NETWORKS.keys():
        aa = addict.AudioAddict(PROFILE_DIR, network)

        if not aa.network['has_shows']:
            continue

        followed = [s.get('slug') for s in aa.get_shows_followed()]

        shows = aa.get_live_shows()
        live_show_ids = [s.get('id') for s in shows]

        # Remove shows which are not live anymore
        skip_shows = [i for i in skip_shows if i in live_show_ids]

        for show in shows:
            if show.get('id') in skip_shows:
                utils.log('Already notified for show:', show.get('name'))
                continue

            if parse(show.get('end_at')) < now:
                continue

            skip_shows.append(show.get('id'))

            _show = show.get('show')
            if _show.get('slug') in followed and ADDON.getSettingBool(
                    'addon.notify_live'):
                utils.notify('[B]{}[/B] is live!'.format(_show.get('name')))

            if ADDON.getSettingBool('addon.tune_in_live'):
                url = xbmc.getInfoLabel('Player.Filenameandpath')
                if not url:
                    continue

                url = utils.parse_url(url)
                if url.netloc != ADDON_ID:
                    continue

                if len(url.path) < 4:
                    continue

                chan = _show.get('channels', [])[0]
                sub, _network, channel, track_id = url.path

                if _network != network or channel != chan.get('key'):
                    utils.log('Different network/channel playing, skipping...')
                    continue

                if url.query.get('is_live', False):
                    utils.log('Live stream already playing...')
                    continue

                is_live, track = utils.next_track(
                    _network, channel, cache=True, pop=False, live=True)

                xbmc.executebuiltin('RunPlugin({})'.format(
                    utils.build_path('play', network, channel, cache=True)))

    return skip_shows


if __name__ == '__main__':
    monitor = xbmc.Monitor()

    last_cache_update = 0
    skip_shows = []
    while not monitor.abortRequested():
        if last_cache_update + CACHE_UPDATE_INTERVAL < time.time():
            last_cache_update = time.time()
            # update_cache()

        skip_shows = monitor_live(skip_shows)

        if monitor.waitForAbort(30):
            break
