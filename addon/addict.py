import collections
import json
import os
import time
from datetime import datetime
from urllib.parse import quote_plus, urlencode

import requests

from dateutil.parser import parse
from dateutil.tz import tzlocal

NETWORKS = collections.OrderedDict([
    ('difm', {
        'name': 'Digitally Imported',
        'has_shows': True,
        'has_playlists': True,
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
        'has_playlists': False,
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
        'has_playlists': False,
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
        'has_playlists': False,
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
        'has_playlists': False,
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
    ('zenradio', {
        'name': 'ZenRadio',
        'has_shows': False,
        'has_playlists': False,
        'url': 'https://www.zenradio.com',
        'api_url': 'https://api.audioaddict.com/v1/zenradio',
        'stream': {
            'url': 'http://prem2.zenradio.com:80/{channel}{quality}?{listen_key}',
            'quality': {
                'aac_64k': '_low',
                'aac_128k': '_aac',
                'mp3_320k': '',
            },
        },
    }),
])


def datetime_now():
    return datetime.now(tzlocal())


def parse_datetime(val):
    return parse(val).astimezone(tzlocal())


def convert_url(url, **kwargs):
    if not url:
        return None

    url = url.split('{?')[0]

    query = urlencode(kwargs)
    if query:
        url += '?{}'.format(query)

    if url.startswith('//'):
        url = 'https:' + url

    return url


def log(*args):
    print('[plugin.audio.audioaddict]', [str(a) for a in args])


class AudioAddict:
    __instances = {}

    data = None

    name = None

    _cache_dir = None
    _cache_file = None
    _ccache_file = None

    _network = None

    _response = None
    __cache = None

    def __init__(self, cache_dir, network):
        self.__cache = {}

        self.name = NETWORKS[network]['name']

        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        self._cache_dir = cache_dir
        self._cache_file = os.path.join(cache_dir, network + '.json')
        self._ccache_file = os.path.join(cache_dir, 'common.json')

        self._network = NETWORKS[network]

    @classmethod
    def get(cls, cache_dir, network):
        key = cache_dir + network
        if key not in cls.__instances:
            cls.__instances[key] = cls(cache_dir, network)
        return cls.__instances[key]

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
        cls_cache = self.__cache.get(cache_file, {})
        if cls_cache:
            return cls_cache

        if not os.path.exists(cache_file):
            return {}

        with open(cache_file, 'r') as f:
            try:
                self.__cache[cache_file] = json.loads(f.read())
            except ValueError:
                return {}

        return self.__cache[cache_file]

    def _write_cache(self, cache_file, cache):
        self.__cache[cache_file] = cache
        with open(cache_file, 'w') as f:
            f.write(json.dumps(cache, indent=2))

    def _update_cache(self, cache_file, key, data=None, cache_time=None):
        cache = self.__cache.get(cache_file, {})
        cache.setdefault(key, {})

        if data is not None:
            cache[key]['data'] = data

        if cache_time:
            cache[key]['expires_on'] = int(time.time() + (cache_time * 60))

        self._write_cache(cache_file, cache)

    def _api_call(self, method, paths, auth=None, payload=None, is_json=True,
                  cache='default', cache_key=None, cache_time=0, refresh=False,
                  **query):

        self._response = None
        paths = [str(p) for p in paths]

        if cache == 'default':
            cache = self._cache_file

        if not cache_key:
            cache_key = '_'.join(paths)

        if not refresh and cache and os.path.exists(cache):
            _cache = self._read_cache(cache).get(cache_key, {})
            expires_on = _cache.get('expires_on')
            if _cache and (not expires_on or expires_on > time.time()):
                return _cache.get('data')

        paths = '/'.join([quote_plus(p) for p in paths])
        url = '/'.join([self._network['api_url'].rstrip('/'), paths])

        if 'api_key' not in query and self.api_key:
            query['api_key'] = self.api_key

        query = urlencode(query)
        if query:
            url += '?{}'.format(query)

        try:
            data = {'data': payload}
            if is_json:
                data = {'json': payload}

            self._response = method(url, auth=auth, **data)

            cache_data = self._response.json()
            if cache:
                self._update_cache(cache, cache_key, cache_data, cache_time)

            return cache_data

        except Exception:
            return {}

    def _get(self, *paths, **kwargs):
        return self._api_call(requests.get, paths, auth=('mobile', 'apps'),
                              **kwargs)

    def _post(self, *paths, **kwargs):
        cache = kwargs.get('cache', None)
        if 'cache' in kwargs:
            kwargs.pop('cache')
        return self._api_call(requests.post, paths, auth=('mobile', 'apps'),
                              cache=cache, **kwargs)

    def _delete(self, *paths, **kwargs):
        cache = kwargs.get('cache', None)
        if cache:
            kwargs.pop('cache')
        return self._api_call(requests.delete, paths, auth=('mobile', 'apps'),
                              cache=cache, **kwargs)

    def invalidate_cache(self):
        cache = self._read_cache(self._cache_file)
        for key, val in list(cache.items()):
            expires_on = val.get('expires_on')
            if expires_on and expires_on < time.time():
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

    def get_channel_name(self, channel):
        for c in self.get_channels():
            if c['key'] == channel:
                return c['name']
        return None

    def logout(self):
        if os.path.exists(self._ccache_file):
            os.remove(self._ccache_file)
        if os.path.exists(self._cache_file):
            os.remove(self._cache_file)

    def next_channel_track(self, channel, tune_in=True, refresh=False,
                           pop=False, live=True):
        is_live = False
        track = None

        if live:
            now = datetime_now()
            for show in self.get_live_shows():
                channels = [
                    c for c in show.get('show', {}).get('channels', [])
                    if c.get('key') == channel
                ]

                if len(channels) == 0:
                    continue

                end_at = parse_datetime(show.get('end_at'))
                if end_at < now:
                    continue

                track = show.get('tracks')[0]
                if not track.get('content', {}).get('assets', {}):
                    track = self.get_track(track.get('id'))

                time_left = (end_at - now).seconds
                if time_left < 2:
                    break

                track['content']['offset'] = track.get('length') - time_left

                is_live = True
                break

        if not track:
            cache_file = os.path.join(self._cache_dir, 'channel_tracks.json')

            channel_id = self.get_channel_id(channel)
            track_list = self.get_track_list(channel, refresh=refresh,
                                             cache=cache_file)

            is_new = False
            if (track_list.get('channel_id') != channel_id
                    or len(track_list.get('tracks', [])) < 1):
                is_new = True
                track_list = self.get_track_list(channel, tune_in,
                                                 refresh=True,
                                                 cache=cache_file)

            track = (track_list['tracks'].pop(0)
                     if pop else track_list['tracks'][0])

            if is_new or pop:
                self._update_cache(cache_file, 'channel_tracks', track_list)

        return (is_live, track)

    def next_playlist_track(self, playlist_id, refresh=False, pop=True):
        cache_file = os.path.join(self._cache_dir, 'playlist_tracks.json')

        track_list = self.get_playlist_tracks(playlist_id, refresh=refresh,
                                              cache=cache_file)

        is_new = False

        if (track_list.get('id') != playlist_id
                or len(track_list.get('tracks', [])) == 0):
            is_new = True
            track_list = self.get_playlist_tracks(playlist_id, refresh=True)

        track = track_list['tracks'].pop(0) if pop else track_list['tracks'][0]

        if is_new or refresh or pop:
            self._update_cache(cache_file, 'playlist_tracks', track_list)

        return track

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
        return self.favorites(add=[channel_id])

    def remove_favorite(self, channel):
        channel_id = self.get_channel_id(channel)
        return self.favorites(remove=[channel_id])

    def get_live_shows(self, refresh=False):
        now = datetime_now()

        shows = []
        for up in self.get_upcoming(refresh=refresh):
            start_at = parse(up.get('start_at'))
            if start_at > now:
                continue

            shows.append(up)

        return shows

    #
    # --- Get ---
    #
    def get_member_session(self):
        return self._get('member_sessions', self.user.get('key'),
                         cache=self._ccache_file, cache_key='user',
                         refresh=True)

    def get_subscriptions(self):
        return self._get('members', self.member_id, 'subscriptions', 'active',
                         cache=None)

    def get_channel_filters(self, refresh=False):
        return self._get('channel_filters', cache_time=24 * 60,
                         refresh=refresh)

    def get_favorites(self, refresh=False):
        return self._get('members', self.member_id, 'favorites', 'channels',
                         cache_key='favorites', cache_time=10, refresh=refresh)

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

    def get_show_facets(self, refresh=False):
        res = self._get('shows', cache_key='show_facets', cache_time=24 * 60,
                        refresh=refresh, page=1, per_page=0)
        return res.get('metadata', {}).get('facets', [])

    def get_shows(self, channel, page=1, per_page=25, refresh=False):
        for facet in self.get_show_facets():
            if facet.get('name') == channel:
                field = facet.get('field')
                break

        if not field:
            raise ValueError(
                'Unable to determin a valid field for channel "{}"'.format(
                    channel))

        cache_key = 'shows_{}_{}'.format(channel, page)
        query = {
            'facets[{}][]'.format(field): channel,
            'page': page,
            'per_page': per_page,
        }
        return self._get('shows', cache_key=cache_key, cache_time=60,
                         refresh=refresh, **query).get('results', [])

    def get_shows_followed(self, page=1, per_page=25, refresh=False):
        return self._get('members', self.member_id, 'followed_items', 'show',
                         page=page, per_page=per_page,
                         cache_key='shows_followed', cache_time=10,
                         refresh=refresh)

    def get_show_episodes(self, slug, page=1, per_page=25, refresh=False):
        cache_key = 'show_episodes_{}_{}'.format(slug, page)
        return self._get('shows', slug, 'episodes', page=page,
                         per_page=per_page, cache_key=cache_key, cache_time=10,
                         refresh=refresh)

    def get_upcoming(self, limit=24, refresh=False):
        return self._get('events', 'upcoming', limit=limit,
                         cache_key='shows_upcoming', cache_time=10,
                         refresh=refresh)

    def get_track_list(self, channel, tune_in=True, refresh=True, cache=None):
        channel_id = self.get_channel_id(channel)
        if channel_id is None:
            return None

        return self._get('routines', 'channel', channel_id,
                         cache_key='channel_tracks',
                         tune_in=str(tune_in).lower(), cache=cache,
                         refresh=refresh)

    def get_listen_history(self, channel):
        channel_id = self.get_channel_id(channel)
        if channel_id is None:
            return None
        return self._get('listen_history', channel_id=channel_id, cache=None)

    def search(self, query, page=1, per_page=25):
        cache_key = 'search_{}'.format(query.lower())
        query = {'q': query, 'page': page, 'per_page': per_page}

        return self._get('search', cache_key=cache_key, cache_time=10, **query)

    def search_shows(self, query, page=1, per_page=25):
        cache_key = 'search_shows_{}'.format(query.lower())
        query = {'q': query, 'page': page, 'per_page': per_page}

        return self._get('shows', cache_key=cache_key, cache_time=10, **query)

    def search_channels(self, query, page=1, per_page=25):
        cache_key = 'search_channels_{}'.format(query.lower())
        query = {'q': query, 'page': page, 'per_page': per_page}

        return self._get('channels', cache_key=cache_key, cache_time=10,
                         **query)

    def get_playlists(self, order_by, page=1, per_page=25):
        cache_key = 'search_playlists_{}'.format(order_by.lower())
        query = {'order_by': order_by, 'page': page, 'per_page': per_page}

        return self._get('playlists', cache_key=cache_key, cache_time=10,
                         **query)

    def get_playlists_popular(self, page=1, per_page=25):
        return self.get_playlists('popularity_sort desc', page, per_page)

    def get_playlists_newest(self, page=1, per_page=25):
        return self.get_playlists('newest_sort desc', page, per_page)

    def get_playlists_followed(self, page=1, per_page=25):
        query = {'order_by': 'follow_date', 'page': page, 'per_page': per_page}
        return {
            'results': self._get('members', self.member_id, 'followed_items',
                                 'playlist', cache_key='followed_playlists',
                                 cache_time=10, **query)
        }

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
                   cache=self._ccache_file, cache_key='user', refresh=True)
        return self.is_active

    def add_listen_history(self, channel, track_id):
        channel_id = self.get_channel_id(channel)
        if channel_id is None:
            return None

        payload = {'channel_id': channel_id, 'track_id': track_id}
        return self._post('listen_history', payload=payload)

    def follow_show(self, show):
        resp = self._post('members', self.member_id, 'followed_items', 'show',
                          show)

        # Invalidate all show cache
        cache = self._cache
        for key, val in self._cache.items():
            if key.startswith('shows_'):
                del cache[key]

        self._write_cache(self._cache_file, cache)
        return resp

    def favorites(self, add=None, remove=None):
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

        resp = self._post('members', self.member_id, 'favorites', 'channels',
                          payload={'favorites': favorites})

        self._update_cache(self._cache_file, 'favorites', favorites)
        return resp

    def preferred_quality(self, quality_id):
        return self._post('members', self.member_id, 'preferred_quality',
                          quality_id=quality_id)

    def get_playlist_tracks(self, playlist_id, refresh=True, cache=None):
        return self._post('playlists', playlist_id, 'play',
                          cache_key='playlist_tracks', cache=cache,
                          refresh=refresh)

    #
    # --- Delete ---
    #
    def unfollow_show(self, show):
        resp = self._delete('members', self.member_id, 'followed_items',
                            'show', show)

        # Invalidate all show cache
        cache = self._cache
        for key, val in self._cache.items():
            if key.startswith('shows_'):
                del cache[key]

        self._write_cache(self._cache_file, cache)
        return resp
