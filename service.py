import os
import time

import xbmc
import xbmcaddon
from addon import addict, utils

CACHE_UPDATE_INTERVAL = 3600
PROFILE_DIR = xbmc.translatePath(
    os.path.join(xbmcaddon.Addon().getAddonInfo('profile')))


def update_cache():
    for i, network in enumerate(addict.NETWORKS):
        aa = addict.AudioAddict(PROFILE_DIR, network)

        if not aa.is_active:
            continue

        utils.log('Updating channels for', network)
        aa.channels(force=True)

        utils.log('Updating favorites for', network)
        aa.favorites(force=True)


if __name__ == '__main__':
    addon = xbmcaddon.Addon()
    monitor = xbmc.Monitor()

    while not monitor.abortRequested():
        try:
            update_cache()
        except Exception as e:
            utils.log(str(e), lvl=xbmc.LOGERROR)


        if monitor.waitForAbort(CACHE_UPDATE_INTERVAL):
            break
