import collections
import json
import os
import urllib

import requests

NETWORKS = collections.OrderedDict([
    ('difm', {
        'name': 'Digitally Imported',
        'url': 'https://www.di.fm',
        'api': '/_papi/v1/di',
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
        'url': 'https://www.radiotunes.com',
        'api': '/_papi/v1/radiotunes',
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
        'url': 'https://www.jazzradio.com',
        'api': '/_papi/v1/jazzradio',
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
        'url': 'https://www.rockradio.com',
        'api': '/_papi/v1/rockradio',
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
        'url': 'https://www.classicalradio.com',
        'api': '/_papi/v1/classicalradio',
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
    session = None
    data = None

    name = None

    _cache_file = None
    _ccache_file = None

    _network = None

    __cache = None

    def __init__(self, _cache_dir, network):
        self.__cache = {}
        self.session = requests.Session()

        self.name = NETWORKS[network]['name']

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
    def _cache(self):
        cache = self.__cache.get(self._cache_file, {})
        if not cache:
            cache = self._read_cache(self._cache_file)
            self.__cache[self._cache_file] = cache
        return cache

    @property
    def _ccache(self):
        cache = self.__cache.get(self._ccache_file, {})
        if not cache:
            cache = self._read_cache(self._ccache_file)
            self.__cache[self._ccache_file] = cache
        return cache

    def _read_cache(self, cache_file):
        if not os.path.exists(cache_file):
            return {}

        with open(cache_file, 'r') as f:
            return json.loads(f.read())

    def _api_call(self, method, *args, **kwargs):
        auth = kwargs.pop('auth', None)
        payload = kwargs.pop('payload', None)

        cache = kwargs.pop('cache', self._cache_file)
        cache_key = kwargs.pop('cache_key', '_'.join(args))
        force = kwargs.pop('force', False)

        if not force and cache and os.path.exists(cache):
            _cache = self._read_cache(cache)
            if _cache.get(cache_key):
                return _cache.get(cache_key)

        args = '/'.join([urllib.quote_plus(str(arg)) for arg in args])
        url = '/'.join([
            self._network['url'].rstrip('/'),
            self._network['api'].lstrip('/'),
            args,
        ])

        if 'api_key' not in kwargs and self.api_key:
            kwargs['api_key'] = self.api_key

        query = urllib.urlencode(kwargs)
        if query:
            url += '?{}'.format(query)

        print url
        try:
            res = method(url, auth=auth, data=payload).json()
            if cache:
                _cache = self._read_cache(cache)
                _cache[cache_key] = res

                self.__cache[cache] = _cache

                with open(cache, 'w') as f:
                    f.write(json.dumps(_cache, indent=2))

            return res

        except Exception:
            return {}

    def _channel_id(self, channel):
        for c in self.channels():
            if c['key'] == channel:
                return c['id']
        return None

    def _get(self, *args, **kwargs):
        return self._api_call(self.session.get, *args, **kwargs)

    def _post(self, *args, **kwargs):
        return self._api_call(self.session.post, *args, **kwargs)

    @property
    def member(self):
        return self._ccache.get('user', {}).get('member', {})

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

    @property
    def audio_token(self):
        return self._ccache.get('user', {}).get('audio_token')

    def logout(self):
        if os.path.exists(self._ccache_file):
            os.remove(self._ccache_file)

    def login(self, username, password, **kwargs):
        payload = {
            'member_session[username]': username,
            'member_session[password]': password,
        }
        self._post('member_sessions', auth=('mobile', 'apps'), payload=payload,
                   cache_key='user', cache=self._ccache_file, **kwargs)
        return self.is_active

    def channel_filters(self, **kwargs):
        return self._get('channel_filters', **kwargs)

    def channels(self, styles=None, **kwargs):
        if not styles:
            styles = ['default']

        for s in self.channel_filters(**kwargs):
            if s['key'] in styles:
                return s['channels']

    def favorites(self, **kwargs):
        favorites = self._get('members', 'id', 'favorites', 'channels',
                              cache_key='favorites', **kwargs)
        ids = [f['channel_id'] for f in favorites]
        return [c for c in self.channels() if c['id'] in ids]

    def qualities(self):
        return self._get('qualities', cache=None)

    def listen_history(self, channel, track_id):
        channel_id = self._channel_id(channel)
        if channel_id is None:
            return None

        payload = {
            'track_id': int(track_id),
            'channel_id': int(channel_id),
        }

        return self._post('listen_history', payload=payload)

    def track_history(self, channel):
        channel_id = self._channel_id(channel)
        if channel_id is None:
            return None
        return self._get('track_history', 'channel', channel_id, cache=None)

    def currently_playing(self):
        return self._get('currently_playing', cache=None)

    def shows(self, channel_name, page=1, per_page=25):
        query = {
            'facets[channel_name][]': channel_name,
            'page': page,
            'per_page': per_page,
        }

        return self._get('shows', cache=None, **query)

    def show_episodes(self, slug, page=1, per_page=25):
        return self._get('shows', slug, 'episodes', page=page,
                         per_page=per_page)

    def upcoming(self, limit=10, start_at=None, end_at=None, **kwargs):
        return self._get('events', 'upcoming', limit=limit, **kwargs)

    def track_list(self, channel, tune_in=True):
        channel_id = self._channel_id(channel)
        if channel_id is None:
            return None

        return self._get('routines', 'channel', str(channel_id),
                         tune_in=str(tune_in).lower(),
                         audio_token=self.audio_token, cache=None)

    def premium_stream_url(self, channel, quality='mp3_320k'):
        quality = self._network['stream']['quality'][quality]
        return self._network['stream']['url'].format(
            channel=channel, quality=quality, listen_key=self.listen_key)
