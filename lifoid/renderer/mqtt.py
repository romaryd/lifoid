import json
from lifoid.logging.mixin import LoggingMixin
from paho.mqtt.publish import multiple
from lifoid.utils.asdict import namedtuple_asdict
from lifoid.renderer import Renderer
from lifoid.config import settings


class MQTTRenderer(Renderer, LoggingMixin):
    """
    Prototype of Lifoid renderer
    """
    api = 'mqtt'

    def convert(self, messages):
        return messages

    def render(self, messages, receiver_id):
        msgs = []
        for msg in self.convert(messages):
            self.logger.info(
                'Response {}'.format(json.dumps(namedtuple_asdict(msg))))
            msgs.append(
                {
                    'topic': receiver_id,
                    'payload': json.dumps(namedtuple_asdict(msg))
                }
            )
        multiple(msgs, hostname=settings.mqtt.host, port=settings.mqtt.port)
