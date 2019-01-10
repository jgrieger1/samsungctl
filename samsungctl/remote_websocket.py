# -*- coding: utf-8 -*-

import base64
import json
import logging
import threading
import ssl
import os
import sys
import websocket
import time
from . import exceptions
from . import application
from . import wake_on_lan


logger = logging.getLogger('samsungctl')


URL_FORMAT = "ws://{}:{}/api/v2/channels/samsung.remote.control?name={}"
SSL_URL_FORMAT = "wss://{}:{}/api/v2/channels/samsung.remote.control?name={}"


class RemoteWebsocket(object):
    """Object for remote control connection."""

    def __init__(self, config):
        if sys.platform.startswith('win'):
            path = os.path.join(os.path.expandvars('%appdata%'), 'samsungctl')
        else:
            path = os.path.join(os.path.expanduser('~'), '.samsungctl')

        if not os.path.exists(path):
            os.mkdir(path)

        token_file = os.path.join(path, "token.txt")

        if not os.path.exists(token_file):
            with open(token_file, 'w') as f:
                f.write('')

        self.token_file = token_file

        self.config = config

        self._loop_event = threading.Event()
        self.receive_lock = threading.Lock()
        self._power_event = threading.Event()
        self._registered_callbacks = []
        self._thread = None
        self._mac_address = None
        self.sock = None
        self._running = False

    @property
    def mac_address(self):
        if self._mac_address is None:
            _mac_address = wake_on_lan.get_mac_address(self.config['host'])
            if _mac_address is None:
                _mac_address = ''

            self._mac_address = _mac_address

        return self._mac_address

    @property
    def power(self):
        return self.sock is not None

    @power.setter
    def power(self, value):
        self._power_event.clear()

        if value and self.sock is None:
            if self.mac_address:
                error_count = 0

                while not self._power_event.isSet() and error_count < 6:
                    wake_on_lan.send_wol(self.mac_address)
                    self._power_event.wait(10)
                    try:
                        self.open()
                    except RuntimeError:
                        error_count += 1

                if error_count == 6:
                    logger.error(
                        'Unable to power on the TV, check network connectivity'
                    )

        elif not value and self.sock is not None:
            self.control('KEY_POWEROFF')
            self._power_event.wait(1.0)

            if not self._power_event.isSet():
                logger.info(
                    'unable to power off TV using command KEY_POWEROFF. '
                    'Trying command KEY_POWER'
                )
                self.control('KEY_POWER')
                self._power_event.wait(1.0)

            if not self._power_event.isSet():
                logger.error('Unable to power off the TV')

    def loop(self):

        while not self._loop_event.isSet():
            try:
                data = self.sock.recv()
                if data:
                    self.on_message(data)
            except:
                self._loop_event.set()

        self._power_event.set()
        self.sock = None
        logger.info('Websocket closed')
        self._loop_event.clear()
        del self._registered_callbacks[:]
        self._thread = None

    def open(self):
        with self.receive_lock:
            token = ''
            all_tokens = []

            with open(self.token_file, 'r') as f:
                tokens = f.read()

            for line in tokens.split('\n'):
                if not line.strip():
                    continue
                if line.startswith(self.config["host"] + ':'):
                    token = line
                else:
                    all_tokens += [line]

            if token:
                all_tokens += [token]
                token = token.replace(self.config["host"] + ':', '')
                logger.debug('using saved token: ' + token)
                token = "&token=" + token

            if all_tokens:
                with open(self.token_file, 'w') as f:
                    f.write('\n'.join(all_tokens) + '\n')

            if self.sock is not None:
                self.close()

            if token or self.config['port'] == 8002:
                self.config['port'] = 8002
                sslopt = {"cert_reqs": ssl.CERT_NONE}
                url = SSL_URL_FORMAT.format(
                    self.config["host"],
                    self.config["port"],
                    self._serialize_string(self.config["name"])
                ) + token

            else:
                self.config['port'] = 8001
                sslopt = {}
                url = URL_FORMAT.format(
                    self.config["host"],
                    self.config["port"],
                    self._serialize_string(self.config["name"])
                )

            try:
                self.sock = websocket.create_connection(url, sslopt=sslopt)
            except:
                raise RuntimeError('Unable to connect to the TV')

            auth_event = threading.Event()

            def unauthorized_callback(_):
                auth_event.set()

                self.unregister_receive_callback(
                    auth_callback,
                    'event',
                    'ms.channel.connect'
                )

                if self.config['port'] == 8001:
                    logger.debug(
                        "Websocket connection failed. Trying ssl connection"
                    )
                    self.config['port'] = 8002
                    self.open()
                else:
                    self.close()
                    raise RuntimeError('Authentication denied')

            def auth_callback(data):
                if 'data' in data and 'token' in data["data"]:
                    with open(self.token_file, "r") as token_file:
                        token_data = token_file.read().split('\n')

                    for lne in token_data[:]:
                        if line.startswith(self.config['host'] + ':'):
                            token_data.remove(lne)

                    token_data += [
                        self.config['host'] + ':' + data['data']["token"]
                    ]

                    logger.debug('new token: ' + token_data[-1])
                    with open(self.token_file, "w") as token_file:
                        token_file.write('\n'.join(token_data) + '\n')

                logger.debug("Access granted.")
                auth_event.set()

                self.unregister_receive_callback(
                    unauthorized_callback,
                    'event',
                    'ms.channel.unauthorized'
                )
                self._power_event.set()

            self.register_receive_callback(
                auth_callback,
                'event',
                'ms.channel.connect'
            )

            self.register_receive_callback(
                unauthorized_callback,
                'event',
                'ms.channel.unauthorized'
            )

            self._thread = threading.Thread(target=self.loop)
            self._thread.start()

            auth_event.wait(30.0)
            if not auth_event.isSet():
                self.close()
                raise RuntimeError('Auth Failure')

            self._running = True

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        """Close the connection."""
        if self.sock is not None:
            self._loop_event.set()
            self.sock.close()

    def send(self, method, **params):
        if self.sock is None:
            logger.info('Is the TV on???')
            return

        payload = dict(
            method=method,
            params=params
        )
        self.sock.send(json.dumps(payload))

    def control(self, key, cmd='Click'):
        """
        Send a control command.
        cmd can be one of the following
        'Click'
        'Press'
        'Release'
        """

        if key == 'KEY_POWERON' and not self.power:
            self.power = True
            return

        if key == 'KEY_POWER' and not self.power:
            self.power = True
            return

        if not self._running:
            self.open()

        with self.receive_lock:
            event = threading.Event()
            params = dict(
                Cmd=cmd,
                DataOfCmd=key,
                Option="false",
                TypeOfRemote="SendRemoteKey"
            )

            logger.info("Sending control command: " + str(params))
            self.send("ms.remote.control", **params)
            event.wait(0.15)

    _key_interval = 0.5

    def get_application(self, pattern):
        for app in self.applications:
            if pattern in (app.app_id, app.name):
                return app

    @property
    def applications(self):
        eden_event = threading.Event()
        installed_event = threading.Event()

        app_data = [[], []]

        def eden_app_get(data):
            if 'data' in data:
                app_data[0] = data['data']['data']
            eden_event.set()

        def installed_app_get(data):
            if 'data' in data:
                app_data[1] = data['data']
            installed_event.set()

        self.register_receive_callback(
            eden_app_get,
            'event',
            'ed.edenApp.get'
        )
        self.register_receive_callback(
            installed_app_get,
            'event',
            'ed.installedApp.get'
        )

        for event in ['ed.edenApp.get', 'ed.installedApp.get']:

            params = dict(
                data='',
                event=event,
                to='host'
            )

            self.send('ms.channel.emit', **params)

        eden_event.wait(2.0)
        installed_event.wait(2.0)

        if not eden_event.isSet():
            self.unregister_receive_callback(
                eden_app_get,
                'event',
                'ed.edenApp.get'
            )

            logger.debug('ed.edenApp.get timed out')

        if not installed_event.isSet():
            self.unregister_receive_callback(
                installed_app_get,
                'data',
                None
            )
            logger.debug('ed.installedApp.get timed out')

        for app_1 in app_data[1]:
            for app_2 in app_data[0]:
                if app_1['appId'] == app_2['appId']:
                    app_1.update(app_2)

        res = []
        for app in app_data[1]:
            res += [application.Application(self, **app)]

        return res

    def register_receive_callback(self, callback, key, data):
        self._registered_callbacks += [[callback, key, data]]

    def unregister_receive_callback(self, callback, key, data):
        if [callback, key, data] in self._registered_callbacks:
            self._registered_callbacks.remove([callback, key, data])

    def on_message(self, message):
        response = json.loads(message)
        logger.debug('incoming message: ' + message)

        for callback, key, data in self._registered_callbacks[:]:
            if key in response and (data is None or response[key] == data):
                callback(response)
                self._registered_callbacks.remove([callback, key, data])

    def start_voice_recognition(self):
        """Activates voice recognition."""
        with self.receive_lock:
            event = threading.Event()

            def voice_callback(_):
                event.set()

            self.register_receive_callback(
                voice_callback,
                'event',
                'ms.voiceApp.standby'
            )

            params = dict(
                Cmd='Press',
                DataOfCmd='KEY_BT_VOICE',
                Option="false",
                TypeOfRemote="SendRemoteKey"
            )

            logger.info("Sending control command: " + str(params))
            self.send("ms.remote.control", **params)

            event.wait(2.0)
            if not event.isSet():
                self.unregister_receive_callback(
                    voice_callback,
                    'event',
                    'ms.voiceApp.standby'
                )
                logger.debug('ms.voiceApp.standby timed out')

    def stop_voice_recognition(self):
        """Activates voice recognition."""

        with self.receive_lock:
            event = threading.Event()

            def voice_callback(_):
                event.set()

            self.register_receive_callback(
                voice_callback,
                'event',
                'ms.voiceApp.hide'
            )

            params = dict(
                Cmd='Release',
                DataOfCmd='KEY_BT_VOICE',
                Option="false",
                TypeOfRemote="SendRemoteKey"
            )

            logger.info("Sending control command: " + str(params))
            self.send("ms.remote.control", **params)

            event.wait(2.0)
            if not event.isSet():
                self.unregister_receive_callback(
                    voice_callback,
                    'event',
                    'ms.voiceApp.hide'
                )
                logger.debug('ms.voiceApp.hide timed out')

    @staticmethod
    def _serialize_string(string):
        if isinstance(string, str):
            string = str.encode(string)

        return base64.b64encode(string).decode("utf-8")

    @property
    def mouse(self):
        return Mouse(self)


class Mouse(object):

    def __init__(self, remote):
        self._remote = remote
        self._is_running = False
        self._commands = []
        self._ime_start_event = threading.Event()
        self._ime_update_event = threading.Event()
        self._touch_enable_event = threading.Event()
        self._send_event = threading.Event()

    @property
    def is_running(self):
        return self._is_running

    def clear(self):
        if not self.is_running:
            del self._commands[:]

    def _send(self, cmd, **kwargs):
        """Send a control command."""

        if not self._remote.connection:
            raise exceptions.ConnectionClosed()

        if not self.is_running:
            params = {
                "Cmd":          cmd,
                "TypeOfRemote": "ProcessMouseDevice"
            }
            params.update(kwargs)

            payload = json.dumps({
                "method": "ms.remote.control",
                "params": params
            })

            self._commands += [payload]

    def left_click(self):
        self._send('LeftClick')

    def right_click(self):
        self._send('RightClick')

    def move(self, x, y):
        position = dict(
            x=x,
            y=y,
            Time=str(time.time())
        )

        self._send('Move', Position=position)

    def add_wait(self, wait):
        if self._is_running:
            self._commands += [wait]

    def stop(self):
        if self.is_running:
            self._send_event.set()
            self._ime_start_event.set()
            self._ime_update_event.set()
            self._touch_enable_event.set()

    def run(self):
        if self._remote.sock is None:
            logger.error('Is the TV on??')
            return

        if not self.is_running:
            self._send_event.clear()
            self._ime_start_event.clear()
            self._ime_update_event.clear()
            self._touch_enable_event.clear()

            self._is_running = True

            with self._remote.receive_lock:

                def imeStart(_):
                    self._ime_start_event.set()

                def imeUpdate(_):
                    self._ime_update_event.set()

                def touchEnable(_):
                    self._touch_enable_event.set()

                self._remote.register_receive_callback(
                    imeStart,
                    'event',
                    'ms.remote.imeStart'
                )

                self._remote.register_receive_callback(
                    imeUpdate,
                    'event',
                    'ms.remote.imeUpdate'
                )

                self._remote.register_receive_callback(
                    touchEnable,
                    'event',
                    'ms.remote.touchEnable'
                )

                for payload in self._commands:
                    if isinstance(payload, (float, int)):
                        self._send_event.wait(payload)
                        if self._send_event.isSet():
                            self._is_running = False
                            return
                    else:
                        logger.info(
                            "Sending mouse control command: " + str(payload)
                        )
                        self._remote.sock.send(payload)

                self._ime_start_event.wait(len(self._commands))
                self._ime_update_event.wait(len(self._commands))
                self._touch_enable_event.wait(len(self._commands))

                self._is_running = False
