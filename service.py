import os

import xbmc
import xbmcaddon
from addon import addict, utils

CACHE_UPDATE_INTERVAL = 3600 * 3
PROFILE_DIR = xbmc.translatePath(
    os.path.join(xbmcaddon.Addon().getAddonInfo('profile')))


def update_cache():
    for i, network in enumerate(addict.NETWORKS):
        aa = addict.AudioAddict(PROFILE_DIR, network)

        if not aa.is_active:
            continue

        utils.log('Updating channels for "{}"'.format(aa.name))
        aa.get_channel_filters(refresh=True)

        if aa.network['has_shows']:
            # TODO
            break


if __name__ == '__main__':
    monitor = xbmc.Monitor()

    while not monitor.abortRequested():
        try:
            update_cache()
        except Exception as e:
            utils.log('Error while updating cache:', str(e), lvl=xbmc.LOGERROR)

        if monitor.waitForAbort(CACHE_UPDATE_INTERVAL):
            break
