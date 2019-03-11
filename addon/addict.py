import collections
import json
import os
import time
import urllib
from datetime import datetime
import requests
import dateutil
from dateutil.parser import parse

CACHE_TIME = 1800  # 30 min. cache. Might be tweaked

NETWORKS = collections.OrderedDict([
    ('difm', {
        'name': 'Digitally Imported',
        'has_shows': True,
        'url': 'https://www.di.fm',
        'api_url': 'https://api.audioaddict.com/v1/di',
        'stream': {
            'url': 'http://prem2.di.fm:80/{channel}{quality}?{listen_key}',
            'quality': {
                'aac_64k': '',
                'aac_128k': '_aac',
                'mp3_320k': '_hi',
            },
        },
    }),
    ('radiotunes', {
        'name': 'RadioTunes',
        'has_shows': False,
        'url': 'https://www.radiotunes.com',
        'api_url': 'https://api.audioaddict.com/v1/radiotunes',
        'stream': {
            'url': 'http://prem2.radiotunes.com:80/{channel}{quality}?{listen_key}',
            'quality': {
                'aac_64k': '_aac',
                'aac_128k': '',
                'mp3_320k': '_hi',
            },
        },
    }),
    ('jazzradio', {
        'name': 'JAZZRADIO.com',
        'has_shows': False,
        'url': 'https://www.jazzradio.com',
        'api_url': 'https://api.audioaddict.com/v1/jazzradio',
        'stream': {
            'url': 'http://prem2.jazzradio.com:80/{channel}{quality}?{listen_key}',
            'quality': {
                'aac_64k': '_low',
                'aac_128k': '_aac',
                'mp3_320k': '',
            },
        },
    }),
    ('rockradio', {
        'name': 'ROCKRADIO.com',
        'has_shows': False,
        'url': 'https://www.rockradio.com',
        'api_url': 'https://api.audioaddict.com/v1/rockradio',
        'stream': {
            'url': 'http://prem2.rockradio.com:80/{channel}{quality}?{listen_key}',
            'quality': {
                'aac_64k': '_low',
                'aac_128k': '_aac',
                'mp3_320k': '',
            },
        },
    }),
    ('classicalradio', {
        'name': 'ClassicalRadio.com',
        'has_shows': False,
        'url': 'https://www.classicalradio.com',
        'api_url': 'https://api.audioaddict.com/v1/classicalradio',
        'stream': {
            'url': 'http://prem2.classicalradio.com:80/{channel}{quality}?{listen_key}',
            'quality': {
                'aac_64k': '_low',
                'aac_128k': '_aac',
                'mp3_320k': '',
            },
        },
    }),
])


class AudioAddict:
    data = None

    name = None

    _cache_file = None
    _ccache_file = None

    _network = None

    _response = None
    __cache = None

    def __init__(self, _cache_dir, network):
        self.__cache = {}

        self.name = NETWORKS[network]['name']

        if not os.path.exists(_cache_dir):
            os.makedirs(_cache_dir)

        self._cache_file = os.path.join(_cache_dir, network + '.json')
        self._ccache_file = os.path.join(_cache_dir, 'common.json')

        self._network = NETWORKS[network]

    @staticmethod
    def url(url, **kwargs):
        if not url:
            return None

        url = url.split('{?')[0]

        query = urllib.urlencode(kwargs)
        if query:
            url += '?{}'.format(query)

        if url.startswith('//'):
            url = 'https:' + url

        return url

    @property
    def network(self):
        return self._network

    @property
    def response(self):
        return self._response

    @property
    def cache_file(self):
        return self._cache_file

    @property
    def _cache(self):
        return (self.__cache.get(self._cache_file)
                or self._read_cache(self._cache_file))

    @property
    def _ccache(self):
        return (self.__cache.get(self._ccache_file)
                or self._read_cache(self._ccache_file))

    def _read_cache(self, cache_file):
        if not os.path.exists(cache_file):
            return {}

        with open(cache_file, 'r') as f:
            data = json.loads(f.read())

        self.__cache[cache_file] = data
        return data

    def _api_call(self, method, *args, **kwargs):
        self._response = None

        args = [str(e) for e in args]

        auth = kwargs.pop('auth', None)
        payload = kwargs.pop('payload', None)
        is_json = kwargs.pop('is_json', True)

        cache = kwargs.pop('cache', self._cache_file)
        cache_key = kwargs.pop('cache_key', '_'.join(args))
        cache_time = kwargs.pop('cache_time', None)
        refresh = kwargs.pop('refresh', False)

        if not refresh and cache and os.path.exists(cache):
            _cache = (self.__cache.get(cache, {}).get(cache_key, {})
                      or self._read_cache(cache).get(cache_key, {}))
            cache_until = _cache.get('cache_until')
            if _cache:
                if not cache_until:
                    return _cache.get('data')
                else:
                    if cache_until > time.time():
                        return _cache.get('data')

        args = '/'.join([urllib.quote_plus(arg) for arg in args])
        url = '/'.join([self._network['api_url'].rstrip('/'), args])

        if 'api_key' not in kwargs and self.api_key:
            kwargs['api_key'] = self.api_key

        query = urllib.urlencode(kwargs)
        if query:
            url += '?{}'.format(query)

        try:
            data = {'data': payload}
            if is_json:
                data = {'json': payload}

            self._response = method(url, auth=auth, **data)

            if cache:
                _cache = self._read_cache(cache)
                _cache[cache_key] = {'data': self._response.json()}
                if cache_time:
                    _cache[cache_key]['cache_until'] = int(time.time() +
                                                           cache_time)

                self.__cache[cache] = _cache

                with open(cache, 'w') as f:
                    f.write(json.dumps(_cache, indent=2))

            return self._response.json()

        except Exception:
            return {}

    def _get(self, *args, **kwargs):
        return self._api_call(requests.get, *args, auth=('mobile', 'apps'),
                              **kwargs)

    def _post(self, *args, **kwargs):
        return self._api_call(requests.post, *args, auth=('mobile', 'apps'),
                              **kwargs)

    def invalidate_cache(self):
        cache = self._read_cache(self._cache_file)
        for key in cache.keys():
            cache_until = cache[key].get('cache_until')
            if cache_until and cache_until < time.time():
                del cache[key]

        with open(self._cache_file, 'w') as f:
            f.write(json.dumps(cache, indent=2))

    @property
    def user(self):
        return self._ccache.get('user', {}).get('data', {})

    @property
    def member_id(self):
        return self.user.get('member_id')

    @property
    def audio_token(self):
        return self.user.get('audio_token')

    @property
    def member(self):
        return self.user.get('member', {})

    @property
    def api_key(self):
        return self.member.get('api_key')

    @property
    def listen_key(self):
        return self.member.get('listen_key')

    @property
    def is_active(self):
        return self.member.get('active', False)

    @property
    def is_premium(self):
        return self.member.get('user_type') == 'premium'

    def get_channel_id(self, channel):
        for c in self.get_channels():
            if c['key'] == channel:
                return c['id']
        return None

    def logout(self):
        if os.path.exists(self._ccache_file):
            os.remove(self._ccache_file)
        if os.path.exists(self._cache_file):
            os.remove(self._cache_file)

    #
    # --- Wrapper ---
    #
    def get_channels(self, styles=None, refresh=False):
        if not styles:
            styles = ['default']

        for s in self.get_channel_filters():
            if s['key'] in styles:
                return s['channels']
        return []

    def get_favorite_channels(self, refresh=False):
        ids = [
            f.get('channel_id') for f in self.get_favorites(refresh=refresh)
        ]
        channels = {c.get('id'): c for c in self.get_channels()}
        return [channels.get(i) for i in ids]

    def add_favorite(self, channel):
        channel_id = self.get_channel_id(channel)
        return self.manage_favorites(add=[channel_id])

    def remove_favorite(self, channel):
        channel_id = self.get_channel_id(channel)
        return self.manage_favorites(remove=[channel_id])

    def get_live_shows(self, refresh=False):
        now = datetime.now(dateutil.tz.UTC)

        shows = []
        for up in self.get_upcoming(refresh=refresh):
            start_at = parse(up.get('start_at'))
            if start_at > now:
                continue

            shows.append(up)

        return shows

    def get_live_show(self, channel, refresh=False):
        for up in self.get_upcoming(refresh=refresh):
            show = up.get('show', {})
            if not show.get('now_playing', False):
                continue

            for chan in show.get('channels', []):
                if chan.get('key') != channel:
                    continue

                return up

        return None

    #
    # --- Get ---
    #
    def get_channel_filters(self, refresh=False):
        return self._get('channel_filters', refresh=refresh)

    def get_favorites(self, refresh=False):
        return self._get('members', self.member_id, 'favorites', 'channels',
                         cache_key='favorites', cache_time=CACHE_TIME,
                         refresh=refresh)

    def get_qualities(self):
        return self._get('qualities', cache=None, refresh=False)

    def get_track_history(self, channel):
        channel_id = self.get_channel_id(channel)
        if channel_id is None:
            return None
        return self._get('track_history', 'channel', channel_id, cache=None)

    def get_currently_playing(self):
        return self._get('currently_playing', cache=None)

    def get_track(self, track_id):
        return self._get('tracks', track_id, cache=None)

    def get_shows(self, channel=None, field=None, page=1, per_page=25,
                  refresh=False):
        if any((channel, field)) and not all((channel, field)):
            raise ValueError('"channel" and "field" are mutually inclusive.')

        cache_key = 'shows_{}'.format(page)
        query = {'page': page, 'per_page': per_page}

        if all((channel, field)):
            query['facets[{}][]'.format(field)] = channel

        return self._get('shows', cache_key=cache_key, cache_time=3600,
                         refresh=refresh, **query)

    def get_shows_followed(self, page=1, per_page=25, refresh=False):
        return self._get('members', self.member_id, 'followed_items', 'show',
                         page=page, per_page=per_page, cache_time=CACHE_TIME,
                         refresh=refresh)

    def get_show_episodes(self, slug, page=1, per_page=25, refresh=False):
        cache_key = 'show_episodes_{}_{}'.format(slug, page)
        return self._get('shows', slug, 'episodes', page=page,
                         per_page=per_page, cache_key=cache_key,
                         cache_time=CACHE_TIME, refresh=refresh)

    def get_upcoming(self, limit=10, start_at=None, end_at=None,
                     refresh=False):
        return self._get('events', 'upcoming', limit=limit, refresh=refresh)

    def get_track_list(self, channel, tune_in=True):
        channel_id = self.get_channel_id(channel)
        if channel_id is None:
            return None

        return self._get('routines', 'channel', channel_id,
                         tune_in=str(tune_in).lower(), cache=None)

    def get_listen_history(self, channel):
        channel_id = self.get_channel_id(channel)
        if channel_id is None:
            return None
        return self._get('listen_history', channel_id=channel_id, cache=None)

    def search(self, query, page=1, per_page=25):
        query = {'q': query, 'page': page, 'per_page': per_page}
        return self._get('search', cache=None, **query)

    def get_premium_stream_url(self, channel, quality='mp3_320k'):
        quality = self._network['stream']['quality'][quality]
        return self._network['stream']['url'].format(
            channel=channel, quality=quality, listen_key=self.listen_key)

    #
    # --- Post ---
    #
    def login(self, username, password):
        payload = {
            'member_session[username]': username,
            'member_session[password]': password,
        }
        self._post('member_sessions', payload=payload, is_json=False,
                   cache=self._ccache_file, cache_key='user')
        return self.is_active

    def add_listen_history(self, channel, track_id):
        channel_id = self.get_channel_id(channel)
        if channel_id is None:
            return None

        return self._post('listen_history', channel_id=channel_id,
                          track_id=track_id, audio_token=self.audio_token)

    def manage_favorites(self, add=None, remove=None):
        if not add:
            add = []

        if not remove:
            remove = []

        favorites = self.get_favorites(refresh=True)

        # Remove favorites
        favorites = [f for f in favorites if f['channel_id'] not in remove]

        # Add new favorites
        favorites.extend([{'channel_id': c, 'position': 0} for c in add])

        # Fix position
        for i, fav in enumerate(favorites):
            fav['position'] = i

        return self._post('members', self.member_id, 'favorites', 'channels',
                          payload={'favorites': favorites}, cache=None)
