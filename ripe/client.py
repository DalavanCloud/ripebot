#
#
#

from requests import Session
from logging import getLogger
from uuid import uuid4


class RipeClient(object):
    log = getLogger('RipeClient')

    BASE_URL = 'https://atlas.ripe.net/api/v2'
    PAGE_SIZE = 40

    def __init__(self, name, api_key, timeout=10):
        self.name = name
        self.timeout = timeout

        sess = Session()
        sess.headers.update({
            'Authorization': 'Key {}'.format(api_key),
            'User-Agent': 'ripe.RipeClient 0.1/{}'.format(name),
        })
        self._sess = sess

    def _request(self, method, url, params, data=None, headers={}):
        self.log.debug('_request: method=%s, url=%s, params=%s', method, url,
                       params)
        resp = self._sess.request(method, url, params=params, json=data,
                                  headers=headers, timeout=self.timeout)
        if resp.status_code < 200 or resp.status_code > 299:
            self.log.error('_get: resp.content=%s', resp.content)
        resp.raise_for_status()
        return resp.json()

    def _get(self, url, params={}, headers={}):
        return self._request('GET', url, params, headers=headers)

    def _post(self, url, params={}, data=None):
        return self._request('POST', url, params, data=data)

    def _validate_probe_filters(self, filters):
        # TODO:
        pass

    def probes_by_id(self, ids):
        '''
        Note: ids will be consumed
        '''
        self.log.debug('probes_by_id:')

        url = '{}/probes/'.format(self.BASE_URL)
        params = {
            'page_size': self.PAGE_SIZE,
            'sort': 'id',
        }

        while ids:
            batch = ids[:self.PAGE_SIZE]
            ids = ids[self.PAGE_SIZE:]
            params['id__in'] = ','.join([str(id) for id in batch])
            data = self._get(url, params)
            for probe in data['results']:
                yield probe

    def _probe_query(self, params):
        url = '{}/probes/'.format(self.BASE_URL)

        # TODO: LRU cache probes for use in responses? Maybe in client...
        while True:
            data = self._get(url, params)
            results = data['results']
            for probe in results:
                yield probe
            if data['next'] is None:
                return
            params['id__gt'] = results[-1]['id']

    def probes_by_geo(self, lat, lon, radius, **filters):
        self.log.debug('probes_by_geo: lat=%f, lon=%f, radius=%f', lat, lon,
                       radius)

        self._validate_probe_filters(filters)

        params = {
            'id__gt': -1,
            'page_size': self.PAGE_SIZE,
            'radius': '{},{}:{}'.format(lat, lon, radius),
            # Would be nice to sort by radius, but that doesn't appear to be
            # supported
            'sort': 'id',
        }
        params.update(filters)

        return self._probe_query(params)

    def probes_by_country(self, country_code, **filters):
        self.log.debug('probes_by_country: country_code=%s', country_code)

        self._validate_probe_filters(filters)

        params = {
            'id__gt': -1,
            'page_size': self.PAGE_SIZE,
            'country_code': country_code,
            'sort': 'id',
        }
        params.update(filters)

        return self._probe_query(params)

    def _description(self, _type):
        return '{} - {} - {}'.format(self.name, _type, uuid4().hex)

    def ping(self, target, probe_ids, packets=4, packet_interval=100,
             address_family=4, resolve_on_probe=True):
        self.log.debug('sslcert: target=%s, probe_ids=%s, address_family=%d, '
                       'resolve_on_probe=%s', target, probe_ids,
                       address_family, resolve_on_probe)

        data = {
            'definitions': [{
                'af': address_family,
                'description': self._description('ping'),
                'is_oneoff': True,
                'packets': packets,
                'packet_interval': packet_interval,
                'resolve_on_probe': resolve_on_probe,
                'target': target,
                'type': 'ping',
            }],
            'probes': [{
                'requested': len(probe_ids),
                'type': 'probes',
                'value': ','.join([str(id) for id in probe_ids]),
            }],
        }
        url = '{}/measurements/'.format(self.BASE_URL)
        resp = self._post(url, data=data)

        return resp['measurements'][0]

    def sslcert(self, target, probe_ids, address_family=4,
                resolve_on_probe=True):
        self.log.debug('sslcert: target=%s, probe_ids=%s, address_family=%d, '
                       'resolve_on_probe=%s', target, probe_ids,
                       address_family, resolve_on_probe)

        data = {
            'definitions': [{
                'af': address_family,
                'description': self._description('sslcert'),
                'is_oneoff': True,
                'resolve_on_probe': resolve_on_probe,
                'target': target,
                'type': 'sslcert',
            }],
            'probes': [{
                'requested': len(probe_ids),
                'type': 'probes',
                'value': ','.join([str(id) for id in probe_ids]),
            }],
        }
        url = '{}/measurements/'.format(self.BASE_URL)
        resp = self._post(url, data=data)

        return resp['measurements'][0]

    def measurement(self, measurement_id):
        self.log.debug('measurement: measurement_id=%d', measurement_id)

        url = '{}/measurements/{}/'.format(self.BASE_URL, measurement_id)
        return self._get(url)

    def results(self, measurement_id, start=0, stop=9999999999):
        self.log.debug('results: measurement_id=%d', measurement_id)

        url = '{}/measurements/{}/results/'.format(self.BASE_URL,
                                                   measurement_id)
        # The only way to paginate here would be to walk times?
        params = {
            'start': start,
            'stop': stop,
        }

        return self._get(url, params, headers={'Authorization': ''})
