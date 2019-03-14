import os
import time

import xbmc
import xbmcaddon
from addon import addict, main, utils

ADDON = xbmcaddon.Addon()

ADDON_ID = os.path.join(ADDON.getAddonInfo('id'))
PROFILE_DIR = xbmc.translatePath(os.path.join(ADDON.getAddonInfo('profile')))


class Monitor(xbmc.Monitor):
    def __init__(self):
        addon = xbmcaddon.Addon()
        self._quality = addon.getSettingInt('aa.quality')

    def onSettingsChanged(self):
        addon = xbmcaddon.Addon()

        if addon.getSettingInt('aa.quality') != self._quality:
            utils.log('Quality setting changed.')
            quality_id = utils.get_quality_id(main.TEST_LOGIN_NETWORK)
            for network in addict.NETWORKS.keys():
                aa = addict.AudioAddict(PROFILE_DIR, network)
                if aa.is_premium:
                    utils.log('Updating preferred quality for:', network)
                    aa.preferred_quality(quality_id)

            self._quality = addon.getSettingInt('aa.quality')


def monitor_live(skip_shows=None):
    if not skip_shows:
        skip_shows = []

    now = addict.datetime_now()
    addon = xbmcaddon.Addon()

    for network in addict.NETWORKS.keys():
        aa = addict.AudioAddict.get(PROFILE_DIR, network)

        if (not aa.is_active or not aa.is_premium
                or not aa.network['has_shows']):
            continue

        followed = [s.get('slug') for s in aa.get_shows_followed()]

        shows = aa.get_live_shows()
        live_show_ids = [s.get('id') for s in shows]

        # Remove shows which are not live anymore
        skip_shows = [i for i in skip_shows if i in live_show_ids]

        for show in shows:
            if show.get('id') in skip_shows:
                continue

            if addict.parse_datetime(show.get('end_at')) < now:
                continue

            skip_shows.append(show.get('id'))

            _show = show.get('show')
            if _show.get('slug') in followed and addon.getSettingBool(
                    'addon.notify_live'):
                utils.notify('[B]{}[/B] is live!'.format(_show.get('name')))

            if addon.getSettingBool('addon.tune_in_live'):
                filename = xbmc.getInfoLabel('Player.Filenameandpath')
                if not filename:
                    continue

                url = utils.parse_url(filename)
                if url.netloc != ADDON_ID:
                    continue

                if len(url.path) < 4:
                    continue

                _, _network, channel, track_id = url.path

                chan = _show.get('channels', [])[0]
                if _network != network or channel != chan.get('key'):
                    utils.log(
                        'Different network/channel playing, not tuning in.')
                    continue

                if url.query.get('is_live') == 'true':
                    utils.log('Live stream already playing.')
                    continue

                utils.log('Tuning in to live stream...')
                xbmc.executebuiltin('RunPlugin({})'.format(
                    utils.build_path('play', network, channel)))

    return skip_shows


def hourly():
    # Clean up cache
    for network in addict.NETWORKS.keys():
        utils.log('Invalidating cache for {}'.format(network))
        aa = addict.AudioAddict.get(PROFILE_DIR, network)
        aa.invalidate_cache()

    # Update user information (like premium status etc.)
    utils.log('Updating user information'.format(network))
    aa = addict.AudioAddict.get(PROFILE_DIR, main.TEST_LOGIN_NETWORK)
    aa.get_member_session()


if __name__ == '__main__':
    monitor = Monitor()

    xbmcaddon.Addon().setSetting('aa.email', 'tadly90@gmail.com')

    skip_shows = []
    hourly_last_run = 0
    while not monitor.abortRequested():
        skip_shows = monitor_live(skip_shows)

        if hourly_last_run + 3600 < time.time():
            hourly_last_run = time.time()
            hourly()

        if monitor.waitForAbort(60):
            break
