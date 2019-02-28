import os
import urllib
import urlparse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from addon import HANDLE

DEFAULT_LOG_LEVEL = xbmc.LOGNOTICE

ADDON = xbmcaddon.Addon()


def log(*args, **kwargs):
    args = [str(i) for i in args]
    level = kwargs.get('level', DEFAULT_LOG_LEVEL)
    xbmc.log('[{}] {}'.format(ADDON.getAddonInfo('id'), ' '.join(args)),
             level=level)


def notify(title, message, icon=None, display_time=5000):
    if not icon:
        icon = ADDON.getAddonInfo('icon')

    xbmcgui.Dialog().notification(title, message, icon, display_time)


def translate(id_):
    return ADDON.getLocalizedString(id_)


def parse_url(url):
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
    path_ = [urllib.unquote_plus(e) for e in url.path.strip('/').split('/')]
    url = url._replace(path=list(filter(None, path_)))

    return url


def build_path(*args, **kwargs):
    args = '/'.join([urllib.quote_plus(str(e)) for e in args])
    url = 'plugin://{}/{}'.format(ADDON.getAddonInfo('id'), args)

    kwargs = urllib.urlencode(kwargs)
    if kwargs:
        url = '{}?{}'.format(url, kwargs)

    return url


def list_items(items, sort_methods=None):
    if not sort_methods:
        sort_methods = [
            xbmcplugin.SORT_METHOD_UNSORTED, xbmcplugin.SORT_METHOD_LABEL
        ]

    for method in sort_methods:
        xbmcplugin.addSortMethod(HANDLE, method)

    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    xbmcplugin.endOfDirectory(HANDLE)
