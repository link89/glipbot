from boltons.cacheutils import cachedproperty

from ringcentral.platform.platform import Platform


class RcPlatformHelper(object):
    def __init__(self, platform: Platform):
        self.platform = platform

    @cachedproperty
    def me(self):
        res = self.platform.get('/glip/persons/~')
        return res.json_dict()

    def create_or_get_private_group(self, person_id):
        members = [str(person_id), self.me['id']]
        data = {
            'members': members,
            'type': 'PrivateChat'
        }
        res = self.platform.post('/glip/groups', body=data)
        return res.json_dict()

    def post_to_group(self, group_id, data):
        if isinstance(data, str):
            data = {'text': data}
        res = self.platform.post('/glip/groups/{}/posts'.format(group_id), body=data)
        return res.json_dict()

    def post_to_person(self, person_id, data):
        group = self.create_or_get_private_group(person_id)
        return self.post_to_group(group['id'], data)

    def subscribe_webhook(self, address, event_filters=None, expires_in=500000000):
        if event_filters is None:
            event_filters = [
                "/restapi/v1.0/glip/posts",
                "/restapi/v1.0/glip/groups",
            ]
        data = {
            "eventFilters": event_filters,
            "deliveryMode": {
                "transportType": "WebHook",
                "address": address,
            },
            "expiresIn": expires_in,
        }

        res = self.platform.post('/subscription', body=data)
        return res.json_dict()
