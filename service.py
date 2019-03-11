import time
import os

import xbmc
import xbmcaddon
from addon import addict, utils, main
from datetime import datetime

import dateutil
from dateutil.parser import parse

ADDON = xbmcaddon.Addon()

ADDON_ID = os.path.join(ADDON.getAddonInfo('id'))
CACHE_UPDATE_INTERVAL = 3600
PROFILE_DIR = xbmc.translatePath(os.path.join(ADDON.getAddonInfo('profile')))


def update_cache():
    for network in addict.NETWORKS.keys():
        aa = addict.AudioAddict(PROFILE_DIR, network)

        aa.invalidate_cache()

        if not aa.is_active:
            continue

        utils.log('Updating channels for "{}"'.format(aa.name))

        aa.get_channel_filters(refresh=True)
        aa.get_favorites(refresh=True)
        aa.get_shows_followed(refresh=True)

        if aa.network['has_shows']:
            aa.get_upcoming(refresh=True)


def monitor_live(skip_shows=None):
    if not skip_shows:
        skip_shows = {}

    # Clean up old shows
    now = datetime.now(dateutil.tz.UTC)
    for show_id in skip_shows.keys():
        if skip_shows[show_id]['end_at'] < now:
            del skip_shows[show_id]

    for network in addict.NETWORKS.keys():
        aa = addict.AudioAddict(PROFILE_DIR, network)

        if not aa.network['has_shows']:
            continue

        followed = [s.get('slug') for s in aa.get_shows_followed()]
        for show in aa.get_live_shows():
            if show.get('id') in skip_shows.keys():
                utils.log('Already notified for show:', show.get('id'))
                continue

            sshow = show.get('show')
            if sshow.get('slug') not in followed:
                continue

            skip_shows[show.get('id')] = {
                'end_at': parse(show.get('end_at')),
            }

            if ADDON.getSettingBool('addon.notify_live'):
                utils.notify('[B]{}[/B] is live!'.format(sshow.get('name')))

            if ADDON.getSettingBool('addon.tune_in_live'):
                url = xbmc.getInfoLabel('Player.Filenameandpath')
                if not url:
                    continue

                url = utils.parse_url(url)
                if url.netloc != ADDON_ID:
                    continue

                if len(url.path) < 4:
                    continue

                chan = sshow.get('channels', [])[0]
                sub, _network, channel, track_id = url.path
                if _network != network or channel != chan.get('key'):
                    continue

                track = utils.next_track(_network, channel, True, False, True)
                if track_id == track.get('id'):
                    utils.log('Live stream already playing...')
                    continue

                utils.log('Tuning in to live channel...')
                xbmc.executebuiltin('RunPlugin({})'.format(
                    utils.build_path('play', network, channel, cache=True)))

    return skip_shows


if __name__ == '__main__':
    monitor = xbmc.Monitor()

    last_cache_update = 0
    skip_shows = {}
    while not monitor.abortRequested():
        try:
            if last_cache_update + CACHE_UPDATE_INTERVAL < time.time():
                last_cache_update = time.time()
                update_cache()
        except Exception as e:
            utils.log('Error while updating cache:', str(e), lvl=xbmc.LOGERROR)

        try:
            skip_shows = monitor_live(skip_shows)
        except Exception as e:
            utils.log('Error while monitoring channel:', str(e),
                      lvl=xbmc.LOGERROR)

        if monitor.waitForAbort(60):
            break
