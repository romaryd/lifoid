#
# Author:   Romary Dupuis <romary@me.com>
#
# Copyright (C) 2017-2018 Romary Dupuis
"""
Template views system based on Jinja2
"""
from six import add_metaclass
import sys
from os import walk
from os.path import join, dirname, abspath
from importlib import import_module
import yaml
import datetime
import time
from singleton import Singleton
from jinja2 import (Environment, TemplateNotFound, Template,
                    PackageLoader, FileSystemLoader)
from flask_babel import gettext as flask_gettext
from flask import render_template as flask_render_template
from lifoid.data.repository import Repository
from lifoid.data.record import DictRecord
from lifoid.config import settings
from lifoid.plugin import plugator
import lifoid.signals as signals
from lifoid.message import (LifoidMessage, Attachment, ButtonAction, Option,
                            Table, MenuAction, Chat, Edit)
from lifoid.message.message_types import CHAT
from lifoid.logging.mixin import ServiceLogger
logger = ServiceLogger()

MSG_SPLIT = '1234567890ab'


@add_metaclass(Singleton)
class TemplatesLoader(Environment):
    """
    Make a singleton of templates loader
    """
    def __init__(self, module, path):
        super(TemplatesLoader, self).__init__(
            loader=PackageLoader(module, path)
        )


def jinja2_render_template(template_name, **kwargs):
    try:
        app_settings_module = import_module(
            settings.lifoid_settings_module
        )
        path = app_settings_module.TEMPLATES_PATH
    except Exception:
        path = join(abspath(dirname(sys.argv[0])), 'templates')
    templates_loader = FileSystemLoader(path)
    env = Environment(
        loader=templates_loader
    )
    template = env.get_template(template_name)
    if template is None:
        return None
    return template.render(**kwargs)


def load_templates_path(path):
    for (dirpath, dirnames, filenames) in walk(path):
        for _file in filenames:
            logger.debug('load {}'.format(_file))
            with open(join(path, _file)) as file_handler:
                yield {
                    'name': _file,
                    'content': file_handler.read()
                }


class TemplateRecord(dict, DictRecord):
    """
    Generic Lifoid message
    """
    def __init__(self):
        date = datetime.datetime.utcnow().isoformat()[:-3]
        self['ttl'] = int(time.mktime(time.strptime(
            date, "%Y-%m-%dT%H:%M:%S.%f")))
        self['date'] = date


class TemplateRepository(Repository):
    """
    Messages Repository
    """
    klass = TemplateRecord


def get_template(lifoid_id, name, lang):
    template_key = '{}:{}:{}'.format(lifoid_id, name, lang)
    logger.debug('Get template {}'.format(template_key))
    template = TemplateRepository(
        plugator.get_plugin(
            signals.get_backend
        ),
        settings.template_prefix).latest(template_key)
    if template is None:
        logger.error('Get template {}'.format(template_key))
        return None
    return Template(template['content'])


def lifoid_render_template(template_name, **kwargs):
    template = get_template(kwargs['lifoid_id'], template_name, kwargs['lang'])
    if template is None:
        return None
    return template.render(**kwargs)


def template_extension(template_name):
    els = template_name.split('.')
    if len(els) > 1:
        return els[1]
    return False


def render_view(render, template_name, **kwargs):
    content = get_yaml_view(template_name, **kwargs)
    if content is None:
        content = get_text_view(template_name, **kwargs)
    if content is None:
        raise TemplateNotFound
    return render(content)


def get_yaml_view(template_name, **kwargs):
    try:
        rendered_template = render_template(template_name, **kwargs)
        if rendered_template is None:
            return None
        content = yaml.load(rendered_template, Loader=yaml.FullLoader)
        if 'message_type' in content and content['message_type'] == CHAT:
            payload = content['payload']
            attachments = []
            if 'attachments' in payload:
                for attachment in payload['attachments']:
                    if 'image_url' in attachment.keys():
                        attachments.append(Attachment(
                            file_url=attachment['image_url'],
                            text=attachment['text']))
                    if 'file_url' in attachment.keys():
                        attachments.append(Attachment(
                            file_url=attachment['file_url'],
                            text=attachment['text']))
                    if 'buttons' in attachment.keys():
                        actions = []
                        for button in attachment['buttons']:
                            if isinstance(button, dict):
                                actions.append(ButtonAction(name=button['text'],
                                                            value=button['value']))
                            else:
                                actions.append(ButtonAction(name=button))
                        attachments.append(Attachment(actions=actions))
                    if 'select' in attachment.keys():
                        options = []
                        for option in attachment['select']:
                            if isinstance(option, dict):
                                options.append(
                                    Option(text=option['text'],
                                        value=option.get('value',
                                                            option['text']))
                                )
                            else:
                                options.append(Option(text=option, value=option))
                        attachments.append(Attachment(actions=[
                            MenuAction(name='menu_select', options=options)
                        ]))
                    if 'table' in attachment.keys():
                        attachments.append(Attachment(table=Table(
                            title=attachment['table']['title'],
                            name=attachment['table']['name'],
                            columns=attachment['table']['columns'],
                            rows=attachment['table']['rows'],
                            types=attachment['table']['types']
                        )))
                    if 'edit' in attachment.keys():
                        attachments.append(Attachment(
                            edit=[
                                Edit(**item) for item in attachment['edit']
                            ]
                        ))

            return [LifoidMessage(
                message_type=CHAT,
                payload=Chat(
                    text=payload['text'],
                    attachments=attachments))]
        return [LifoidMessage(payload=content)]
    except KeyError:
        logger.error('malformed content in template {}'.format(template_name))
        raise
    except AttributeError:
        logger.error('malformed content in template {}'.format(template_name))
        raise
    except yaml.parser.ParserError:
        logger.error('malformed content in template {}'.format(template_name))
        raise



def get_text_view(template_name, **kwargs):
    """
    Render a template view with a specific context
    """
    content = render_template(template_name, MSG_SPLIT=MSG_SPLIT, **kwargs)
    if content is None:
        return None
    return [LifoidMessage(
        payload=Chat(
            text=text,
            attachments=None)) for text in content.split(MSG_SPLIT)]


gettext = flask_gettext
if settings.templates == 'repository':
    render_template = lifoid_render_template
elif settings.templates == 'flask':
    render_template = flask_render_template
else:
    render_template = jinja2_render_template
