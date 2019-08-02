# -*- coding: utf-8 -*-
import requests
import six
from xml.sax import saxutils
from lxml import etree
from .UPNP_Device.upnp_class import UPNPObject
from .UPNP_Device.instance_singleton import InstanceSingleton
from .UPNP_Device.xmlns import strip_xmlns

import logging
logger = logging.getLogger('samsungctl')


class UPNPTV(UPNPObject):

    def __init__(self, ip, locations):
        self._dtv_information = None
        self._tv_options = None
        self.name = self.__class__.__name__
        self.ip_address = ip
        self._connected = False
        self._locations = locations
        self._connect_upnp()

    @property
    def connected(self):
        if self.power:
            self._connect_upnp()
            return True
        else:
            logger.info('UPNP suspended')
            return False

    def _connect_upnp(self):
        if not self._connected and self.power:
            UPNPObject.__init__(self, self.ip_address, self._locations)
            self._connected = True

    @property
    def tv_options(self):
        if not self.connected:
            return

        if self._tv_options is None:
            try:
                url = 'http://{0}:8001/api/v2'.format(self.ip_address)
                response = requests.get(url)
                response = response.json()

                if 'device' in response:
                    response = response['device']
                    if 'isSupport' in response:
                        import json
                        response['isSupport'] = json.loads(
                            response['isSupport']
                        )
                else:
                    response = None
            except (
                requests.HTTPError,
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ConnectionError
            ):
                response = None

            if response is None:
                return {}

            self._tv_options = response
        return self._tv_options

    @property
    def is_support(self):
        if not self.connected:
            return

        return self.tv_options.get('isSupport', {})

    @property
    def power(self):
        raise NotImplementedError

    def get_audio_selection(self):
        if not self.connected:
            return

        audio_pid, audio_encoding = self.RenderingControl.X_GetAudioSelection(0)
        return audio_pid, audio_encoding

    def set_audio_selection(self, audio_encoding, audio_pid=0):
        if not self.connected:
            return

        self.RenderingControl.X_UpdateAudioSelection(
            0,
            audio_pid,
            audio_encoding
        )

    def get_channel_mute(self, channel):
        if not self.connected:
            return

        return self.RenderingControl.GetMute(0, channel)[0]

    def set_channel_mute(self, channel, desired_mute):
        if not self.connected:
            return

        self.RenderingControl.SetMute(0, channel, desired_mute)

    def get_channel_volume(self, channel):
        if not self.connected:
            return

        return self.RenderingControl.GetVolume(0, channel)[0]

    def set_channel_volume(self, channel, desired_volume):
        if not self.connected:
            return

        self.RenderingControl.SetVolume(0, channel, desired_volume)
    # ===============================

    def add_schedule(self, reservation_type, remind_info):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.AddSchedule(
                reservation_type,
                remind_info
            )[1]

    @property
    def antenna_mode(self):
        raise NotImplementedError

    @antenna_mode.setter
    def antenna_mode(self, value):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            self.MainTVAgent2.SetAntennaMode(value)

    @property
    def aspect_ratio(self):
        if not self.connected:
            return

        return self.RenderingControl.X_GetAspectRatio(0)[0]

    @aspect_ratio.setter
    def aspect_ratio(self, aspect_ratio='Default'):
        if not self.connected:
            return

        self.RenderingControl.X_SetAspectRatio(0, aspect_ratio)

    @property
    def av_off(self):
        raise NotImplementedError

    @av_off.setter
    def av_off(self, value):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            self.MainTVAgent2.SetAVOff(value)

    @property
    def banner_information(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.GetBannerInformation()[1]

    @property
    def brightness(self):
        if not self.connected:
            return

        return self.RenderingControl.GetBrightness(0)[0]

    @brightness.setter
    def brightness(self, desired_brightness):
        if not self.connected:
            return

        self.RenderingControl.SetBrightness(0, desired_brightness)

    @property
    def byte_position_info(self):
        if not self.connected:
            return

        (
            track_size,
            relative_byte,
            absolute_byte
        ) = self.AVTransport.X_DLNA_GetBytePositionInfo(0)

        return track_size, relative_byte, absolute_byte

    @property
    def caption_state(self):
        if not self.connected:
            return

        captions, enabled_captions = self.RenderingControl.X_GetCaptionState(0)
        return captions, enabled_captions

    def change_schedule(self, reservation_type, remind_info):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.ChangeSchedule(
                reservation_type,
                remind_info
            )[0]

    @property
    def channels(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            supported_channels = (
                self.MainTVAgent2.GetChannelListURL()[2]
            )

            channels = saxutils.unescape(supported_channels)
            channels = etree.fromstring(channels)

            supported_channels = []

            for channel in channels:
                channel_num = (
                    channel.find('MajorCh').text,
                    channel.find('MinorCh').text
                )

                supported_channels += [Channel(channel_num, channel, self)]

            return supported_channels

    @property
    def channel(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            channel = self.MainTVAgent2.GetCurrentMainTVChannel()[1]
            channel = saxutils.unescape(channel)
            channel = etree.fromstring(channel)
            channel_num = (
                channel.find('MajorCh').text,
                channel.find('MinorCh').text
            )

            return Channel(channel_num, channel, self)

    @channel.setter
    def channel(self, channel):
        """
        can be a string with '.'s separating the
        major/minor/micro for digital. or it can be a tuple of numbers.
        or a Channel instance gotten from instance.channels.
        """
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):

            for chnl in self.channels:
                if chnl == channel:
                    chnl.activate()
                    break
            else:
                raise ValueError(
                    'Channel not found ({0})'.format(channel)
                )

    def check_pin(self, pin):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.CheckPIN(pin)[0]

    @property
    def color_temperature(self):
        if not self.connected:
            return

        return self.RenderingControl.GetColorTemperature(0)[0]

    @color_temperature.setter
    def color_temperature(self, desired_color_temperature):
        if not self.connected:
            return

        self.RenderingControl.SetColorTemperature(
            0,
            desired_color_temperature
        )

    def connection_complete(self, connection_id=0):
        if not self.connected:
            return

        self.ConnectionManager.ConnectionComplete(connection_id)

    @property
    def contrast(self):
        if not self.connected:
            return

        return self.RenderingControl.GetContrast(0)[0]

    @contrast.setter
    def contrast(self, desired_contrast):
        if not self.connected:
            return

        self.RenderingControl.SetContrast(0, desired_contrast)

    def control_caption(
        self,
        operation,
        name,
        resource_uri,
        caption_uri,
        caption_type,
        language,
        encoding
    ):
        if not self.connected:
            return

        self.RenderingControl.X_ControlCaption(
            0,
            operation,
            name,
            resource_uri,
            caption_uri,
            caption_type,
            language,
            encoding
        )

    @property
    def current_connection_ids(self):
        if not self.connected:
            return

        connection_ids = self.ConnectionManager.GetCurrentConnectionIDs()
        return connection_ids

    def current_connection_info(self, connection_id):
        if not self.connected:
            return

        (
            rcs_id,
            av_transport_id,
            protocol_info,
            peer_connection_manager,
            peer_connection_id,
            direction,
            status
        ) = self.ConnectionManager.GetCurrentConnectionInfo(connection_id)

        return (
            rcs_id,
            av_transport_id,
            protocol_info,
            peer_connection_manager,
            peer_connection_id,
            direction,
            status
        )

    @property
    def current_time(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.GetCurrentTime()[1]

    @property
    def current_transport_actions(self):
        if not self.connected:
            return

        actions = self.AVTransport.GetCurrentTransportActions(0)
        return actions

    def delete_channel_list(self, antenna_mode, channel_list):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.DeleteChannelList(
                antenna_mode,
                channel_list
            )[0]

    def delete_channel_list_pin(self, antenna_mode, channel_list, pin):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.DeleteChannelListPIN(
                antenna_mode,
                channel_list,
                pin
            )[0]

    def delete_recorded_item(self, uid):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.DeleteRecordedItem(uid)[0]

    def delete_schedule(self, uid):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.DeleteSchedule(uid)[0]

    @property
    def device_capabilities(self):
        if not self.connected:
            return

        play_media, rec_media, rec_quality_modes = (
            self.AVTransport.GetDeviceCapabilities(0)
        )

        return play_media, rec_media, rec_quality_modes

    @property
    def dtv_information(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            if self._dtv_information is None:
                response, data = self.MainTVAgent2.GetDTVInformation()
                data = saxutils.unescape(data)
                self._dtv_information = etree.fromstring(data.encode('utf-8'))
            return self._dtv_information

    def enforce_ake(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent22.EnforceAKE()[0]

    def get_all_program_information_url(self, antenna_mode, channel):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.GetAllProgramInformationURL(
                antenna_mode,
                channel
            )[1]


    def get_channel_lock_information(self, channel, antenna_mode):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            lock, start_time, end_time = (
                self.MainTVAgent2.GetChannelLockInformation(
                    channel,
                    antenna_mode
                )[1:]
            )

            return lock, start_time, end_time

    def get_detail_channel_information(self, channel, antenna_mode):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.GetDetailChannelInformation(
                channel,
                antenna_mode
            )[1]

    def get_detail_program_information(
        self,
        antenna_mode,
        channel,
        start_time
    ):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.GetDetailProgramInformation(
                antenna_mode,
                channel,
                start_time
            )[1]

    def list_presets(self):
        if not self.connected:
            return

        current_preset_list = self.RenderingControl.ListPresets(0)
        return current_preset_list

    @property
    def media_info(self):
        (
            num_tracks,
            media_duration,
            current_uri,
            current_uri_metadata,
            next_uri,
            next_uri_metadata,
            play_medium,
            record_medium,
            write_status
        ) = self.AVTransport.GetMediaInfo(0)

        return (
            num_tracks,
            media_duration,
            current_uri,
            current_uri_metadata,
            next_uri,
            next_uri_metadata,
            play_medium,
            record_medium,
            write_status
        )

    def modify_favorite_channel(self, antenna_mode, favorite_ch_list):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.ModifyFavoriteChannel(
                antenna_mode,
                favorite_ch_list
            )[0]

    def move_360_view(self, latitude_offset=0.0, longitude_offset=0.0):
        if not self.connected:
            return

        self.RenderingControl.X_Move360View(0, latitude_offset, longitude_offset)

    @property
    def mute(self):
        if not self.connected:
            return

        try:
            status = self.MainTVAgent2.GetMuteStatus()[1]
        except AttributeError:
            status = self.get_channel_mute('Master')

        return status

    @mute.setter
    def mute(self, desired_mute):
        if not self.connected:
            return

        try:
            self.MainTVAgent2.SetMute(desired_mute)
        except AttributeError:
            self.set_channel_mute('Master', desired_mute)

    @property
    def network_information(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.GetNetworkInformation()[1]

    def next(self):
        if not self.connected:
            return

        self.AVTransport.Next(0)

    def origin_360_view(self):
        if not self.connected:
            return

        self.RenderingControl.X_Origin360View(0)

    def pause(self):
        if not self.connected:
            return

        self.AVTransport.Pause(0)

    def play(self, speed='1'):
        if not self.connected:
            return

        self.AVTransport.Play(0, speed)

    @property
    def play_mode(self):
        if not self.connected:
            return

        return self.transport_settings[0]

    @play_mode.setter
    def play_mode(self, new_play_mode='NORMAL'):
        if not self.connected:
            return

        self.AVTransport.SetPlayMode(0, new_play_mode)

    def player_app_hint(self, upnp_class):
        if not self.connected:
            return

        self.AVTransport.X_PlayerAppHint(0, upnp_class)

    def play_recorded_item(self, uid):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.PlayRecordedItem(uid)[0]

    @property
    def position_info(self):
        if not self.connected:
            return

        (
            track,
            track_duration,
            track_metadata,
            track_uri,
            relative_time,
            absolute_time,
            relative_count,
            absolute_count
        ) = self.AVTransport.GetPositionInfo(0)

        return (
            track,
            track_duration,
            track_metadata,
            track_uri,
            relative_time,
            absolute_time,
            relative_count,
            absolute_count
        )

    def prefetch_uri(self, prefetch_uri, prefetch_uri_meta_data):
        if not self.connected:
            return

        self.AVTransport.X_PrefetchURI(0, prefetch_uri, prefetch_uri_meta_data)

    def prepare_for_connection(
        self,
        remote_protocol_info,
        peer_connection_manager,
        direction,
        peer_connection_id=0
    ):
        if not self.connected:
            return

        (
            connection_id,
            av_transport_id,
            rcs_id
        ) = self.ConnectionManager.PrepareForConnection(
            remote_protocol_info,
            peer_connection_manager,
            peer_connection_id,
            direction
        )

        return connection_id, av_transport_id, rcs_id

    def previous(self):
        if not self.connected:
            return

        self.AVTransport.Previous(0)

    @property
    def program_information_url(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return (
                self.MainTVAgent2.GetCurrentProgramInformationURL()[1]
            )

    @property
    def protocol_info(self):
        if not self.connected:
            return

        source, sink = self.ConnectionManager.GetProtocolInfo()
        return source, sink

    def regional_variant_list(self, antenna_mode, channel):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.GetRegionalVariantList(
                antenna_mode,
                channel
            )[1]

    def reorder_satellite_channel(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.ReorderSatelliteChannel()[0]

    def run_app(self, application_id):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.RunApp(application_id)[0]

    def run_browser(self, browser_url):
        if not self.connected:
            return

        return self.MainTVAgent2.RunBrowser(browser_url)[0]

    def run_widget(self, widget_title, payload):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.RunWidget(widget_title, payload)[0]

    def set_record_duration(self, channel, record_duration):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.SetRecordDuration(
                channel,
                record_duration
            )[0]

    def set_regional_variant(self, antenna_mode, channel):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.SetRegionalVariant(
                antenna_mode,
                channel
            )[1]

    def send_room_eq_data(
        self,
        total_count,
        current_count,
        room_eq_id,
        room_eq_data
    ):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.SendRoomEQData(
                total_count,
                current_count,
                room_eq_id,
                room_eq_data
            )[0]

    def set_room_eq_test(self, room_eq_id):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.SetRoomEQTest(
                room_eq_id
            )[0]






    @property
    def schedule_list_url(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.GetScheduleListURL()[1]

    def seek(self, target, unit='REL_TIME'):
        if not self.connected:
            return

        self.AVTransport.Seek(0, unit, target)

    def select_preset(self, preset_name):
        if not self.connected:
            return

        self.RenderingControl.SelectPreset(0, preset_name)

    def send_key_code(self, key_code, key_description):
        if not self.connected:
            return

        try:
            self.TestRCRService.SendKeyCode(key_code, key_description)
        except AttributeError:
            self.MultiScreenService.SendKeyCode(key_code, key_description)

    @property
    def service_capabilities(self):
        if not self.connected:
            return

        service_capabilities = self.RenderingControl.X_GetServiceCapabilities(
            0)
        return service_capabilities

    def set_av_transport_uri(self, current_uri, current_uri_metadata):
        if not self.connected:
            return

        self.AVTransport.SetAVTransportURI(0, current_uri, current_uri_metadata)

    def set_break_aux_stream_playlist(
        self,
        break_splice_out_position,
        expiration_time,
        aux_stream_playlist,
        break_id=0
    ):
        if not self.connected:
            return

        self.StreamSplicing.SetBreakAuxStreamPlaylist(
            break_id,
            break_splice_out_position,
            expiration_time,
            aux_stream_playlist
        )

    def set_break_aux_stream_trigger(
        self,
        break_id=0,
        break_trigger_high=0,
        break_trigger_low=0
    ):
        if not self.connected:
            return

        self.StreamSplicing.SetBreakAuxStreamTrigger(
            break_id,
            break_trigger_high,
            break_trigger_low
        )

    def set_channel_list_sort(self, channel_list_type, satellite_id, sort):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.SetChannelListSort(
                channel_list_type,
                satellite_id,
                sort
            )[0]

    def set_clone_view_channel(self, channel_up_down):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.SetCloneViewChannel(
                channel_up_down
            )[0]

    def set_next_av_transport_uri(self, next_uri, next_uri_metadata):
        if not self.connected:
            return

        self.AVTransport.SetNextAVTransportURI(0, next_uri, next_uri_metadata)

    def set_zoom(self, x, y, w, h):
        if not self.connected:
            return

        self.RenderingControl.X_SetZoom(0, x, y, w, h)

    @property
    def sharpness(self):
        if not self.connected:
            return

        return self.RenderingControl.GetSharpness(0)[0]

    @sharpness.setter
    def sharpness(self, desired_sharpness):
        if not self.connected:
            return

        self.RenderingControl.SetSharpness(0, desired_sharpness)

    @property
    def source(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            source_id = self.MainTVAgent2.GetCurrentExternalSource()[2]
            for source in self.sources:
                if source.id == int(source_id):
                    return source

    @source.setter
    def source(self, source):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            if isinstance(source, int):
                source_id = source
                for source in self.sources:
                    if source.id == source_id:
                        break
                else:
                    raise ValueError(
                        'Source id not found ({0})'.format(source_id))

            elif not isinstance(source, Source):
                source_name = source
                for source in self.sources:
                    if source_name in (
                        source.name,
                        source.label,
                        source.device_name
                    ):
                        break

                else:
                    raise ValueError(
                        'Source name not found ({0})'.format(source_name)
                    )

            source.activate()

    @property
    def sources(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            source_list = self.MainTVAgent2.GetSourceList()[1]
            source_list = saxutils.unescape(source_list)
            root = etree.fromstring(source_list)

            sources = []

            for src in root:
                if src.tag == 'Source':
                    source_name = src.find('SourceType').text
                    source_id = int(src.find('ID').text)
                    source_editable = src.find('Editable').text == 'Yes'
                    sources += [
                        Source(
                            source_id,
                            source_name,
                            self,
                            source_editable
                        )
                    ]

            return sources
        return []

    def start_ext_source_view(self, source, id):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            forced_flag, banner_info, ext_source_view_url = (
                self.MainTVAgent2.StartExtSourceView(source, id)[1:]
            )

            return forced_flag, banner_info, ext_source_view_url

    def start_clone_view(self, forced_flag):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            banner_info, clone_view_url, clone_info = (
                self.MainTVAgent2.StartCloneView(forced_flag)[1:]
            )
            return banner_info, clone_view_url, clone_info

    def start_instant_recording(self, channel):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.StartInstantRecording(channel)[1]

    def start_iperf_client(self, time, window_size):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.StartIperfClient(
                time,
                window_size
            )[0]

    def start_iperf_server(self, time, window_size):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.StartIperfServer(
                time,
                window_size
            )[0]

    def start_second_tv_view(
        self,
        antenna_mode,
        channel_list_type,
        satellite_id,
        channel,
        forced_flag
    ):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            banner_info, second_tv_url = (
                self.MainTVAgent2.StartSecondTVView(
                    antenna_mode,
                    channel_list_type,
                    satellite_id,
                    channel,
                    forced_flag
                )[1:]
            )

            return banner_info, second_tv_url

    def stop(self):
        if not self.connected:
            return

        self.AVTransport.Stop(0)

    @property
    def stopped_reason(self):
        if not self.connected:
            return

        (
            stopped_reason,
            stopped_reason_data
        ) = self.AVTransport.X_GetStoppedReason(0)

        return stopped_reason, stopped_reason_data

    def stop_iperf(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.StopIperf()[0]

    def stop_record(self, channel):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.StopRecord(channel)[0]

    def stop_view(self, view_url):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.StopView(view_url)[0]

    def sync_remote_control_pannel(self, channel):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            return self.MainTVAgent2.SyncRemoteControlPannel(channel)[1]

    @property
    def transport_info(self):
        if not self.connected:
            return

        (
            current_transport_state,
            current_transport_status,
            current_speed
        ) = self.AVTransport.GetTransportInfo(0)
        return (
            current_transport_state,
            current_transport_status,
            current_speed
        )

    @property
    def transport_settings(self):
        if not self.connected:
            return

        play_mode, rec_quality_mode = self.AVTransport.GetTransportSettings(0)
        return play_mode, rec_quality_mode

    @property
    def tv_slide_show(self):
        if not self.connected:
            return

        (
            current_show_state,
            current_theme_id,
            total_theme_number
        ) = self.RenderingControl.X_GetTVSlideShow(0)

        return current_show_state, current_theme_id, total_theme_number

    @tv_slide_show.setter
    def tv_slide_show(self, value):
        if not self.connected:
            return

        current_show_state, current_show_theme = value
        self.RenderingControl.X_SetTVSlideShow(
            0,
            current_show_state,
            current_show_theme
        )

    @property
    def video_selection(self):
        if not self.connected:
            return

        video_pid, video_encoding = self.RenderingControl.X_GetVideoSelection(
            0)
        return video_pid, video_encoding

    @video_selection.setter
    def video_selection(self, value):
        if not self.connected:
            return

        if isinstance(value, tuple):
            video_encoding, video_pid = value
        else:
            video_pid = 0
            video_encoding = value

        self.RenderingControl.X_UpdateVideoSelection(
            0,
            video_pid,
            video_encoding
        )

    @property
    def volume(self):
        if not self.connected:
            return

        try:
            current_volume = self.MainTVAgent2.GetVolume()[1]
        except AttributeError:
            current_volume = self.get_channel_volume('Master')

        return current_volume

    @volume.setter
    def volume(self, desired_volume):
        if not self.connected:
            return

        try:
            self.MainTVAgent2.SetVolume(desired_volume)
        except AttributeError:
            self.set_channel_volume('Master', desired_volume)

    @property
    def watching_information(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            tv_mode, information = (
                self.MainTVAgent2.GetWatchingInformation()[1:]
            )
            return tv_mode, information

    def zoom_360_view(self, scale_factor_offset=1.0):
        if not self.connected:
            return

        self.RenderingControl.X_Zoom360View(0, scale_factor_offset)

    # ** END UPNP FUNCTIONS ***************************************************

    def destory_group_owner(self):
        if not self.connected:
            return

        self.MainTVAgent2.DestoryGroupOwner()

    @property
    def acr_current_channel_name(self):
        if not self.connected:
            return

        ChannelName = self.MainTVAgent2.GetACRCurrentChannelName()[1]
        return ChannelName

    @property
    def acr_current_program_name(self):
        if not self.connected:
            return

        ProgramName = self.MainTVAgent2.GetACRCurrentProgramName()[1]
        return ProgramName

    @property
    def acr_message(self):
        if not self.connected:
            return

        Message = self.MainTVAgent2.GetACRMessage()[1]
        return Message

    @property
    def ap_information(self):
        if not self.connected:
            return

        APInformation = self.MainTVAgent2.GetAPInformation()[1]
        return APInformation

    @property
    def available_actions(self):
        if not self.connected:
            return

        AvailableActions = self.MainTVAgent2.GetAvailableActions()[1]
        return AvailableActions

    @property
    def channel_list_url(self):
        if not self.connected:
            return

        (
            ChannelListVersion,
            SupportChannelList,
            ChannelListURL,
            ChannelListType,
            SatelliteID
        ) = self.MainTVAgent2.GetChannelListURL()[1:]

        return (
            ChannelListVersion,
            SupportChannelList,
            ChannelListURL,
            ChannelListType,
            SatelliteID
        )

    @property
    def browser_mode(self):
        if not self.connected:
            return

        BrowserMode = self.MainTVAgent2.GetCurrentBrowserMode()[1]
        return BrowserMode

    @property
    def browser_url(self):
        if not self.connected:
            return

        BrowserURL = self.MainTVAgent2.GetCurrentBrowserURL()[1]
        return BrowserURL

    @property
    def hts_speaker_layout(self):
        if not self.connected:
            return

        SpeakerLayout = self.MainTVAgent2.GetCurrentHTSSpeakerLayout()[1]
        return SpeakerLayout

    def filtered_progarm_url(self, Keyword):
        if not self.connected:
            return

        FilteredProgramURL = (
            self.MainTVAgent2.GetFilteredProgarmURL(Keyword)[1]
        )
        return FilteredProgramURL

    @property
    def hts_all_speaker_distance(self):
        if not self.connected:
            return

        (
            MaxDistance,
            AllSpeakerDistance
        ) = self.MainTVAgent2.GetHTSAllSpeakerDistance()[1:]
        return MaxDistance, AllSpeakerDistance

    @hts_all_speaker_distance.setter
    def hts_all_speaker_distance(self, AllSpeakerDistance):
        if not self.connected:
            return

        self.MainTVAgent2.SetHTSAllSpeakerDistance(AllSpeakerDistance)

    @property
    def hts_all_speaker_level(self):
        if not self.connected:
            return

        (
            MaxLevel,
            AllSpeakerLevel
        ) = self.MainTVAgent2.GetHTSAllSpeakerLevel()[1:]
        return MaxLevel, AllSpeakerLevel

    @hts_all_speaker_level.setter
    def hts_all_speaker_level(self, AllSpeakerLevel):
        if not self.connected:
            return

        self.MainTVAgent2.SetHTSAllSpeakerLevel(AllSpeakerLevel)

    @property
    def hts_sound_effect(self):
        if not self.connected:
            return

        (
            SoundEffect,
            SoundEffectList
        ) = self.MainTVAgent2.GetHTSSoundEffect()[1:]
        return  SoundEffect, SoundEffectList

    @hts_sound_effect.setter
    def hts_sound_effect(self, SoundEffect):
        if not self.connected:
            return

        self.MainTVAgent2.SetHTSSoundEffect(SoundEffect)

    @property
    def hts_speaker_config(self):
        if not self.connected:
            return

        (
            SpeakerChannel,
            SpeakerLFE
        ) = self.MainTVAgent2.GetHTSSpeakerConfig()[1:]
        return SpeakerChannel, SpeakerLFE

    @property
    def mbr_device_list(self):
        if not self.connected:
            return

        MBRDeviceList = self.MainTVAgent2.GetMBRDeviceList()[1]
        return MBRDeviceList

    @property
    def mbr_dongle_status(self):
        if not self.connected:
            return

        MBRDongleStatus = self.MainTVAgent2.GetMBRDongleStatus()[1]
        return MBRDongleStatus

    @property
    def record_channel(self):
        if not self.connected:
            return

        (
            RecordChannel,
            RecordChannel2
        ) = self.MainTVAgent2.GetRecordChannel()[1:]
        return RecordChannel, RecordChannel2

    def send_browser_command(self, BrowserCommand):
        if not self.connected:
            return

        self.MainTVAgent2.SendBrowserCommand(BrowserCommand)

    def send_mbrir_key(self, ActivityIndex, MBRDevice, MBRIRKey):
        if not self.connected:
            return

        self.MainTVAgent2.SendMBRIRKey(ActivityIndex, MBRDevice, MBRIRKey)

    def stop_browser(self):
        if not self.connected:
            return

        self.MainTVAgent2.StopBrowser()

    def set_auto_slide_show_mode(self, AutoSlideShowMode='ON'):
        if not self.connected:
            return

        self.AVTransport.X_SetAutoSlideShowMode(0, AutoSlideShowMode)

    def set_slide_show_effect_hint(self, SlideShowEffectHint='ON'):
        if not self.connected:
            return

        self.AVTransport.X_SetSlideShowEffectHint(0, SlideShowEffectHint)

    # *************************************************************************

    @property
    def operating_system(self):
        if not self.connected:
            return

        if 'OS' in self._tv_options:
            return self._tv_options['OS']
        return 'Unknown'

    @property
    def frame_tv_support(self):
        if not self.connected:
            return

        if 'FrameTVSupport' in self._tv_options:
            return self._tv_options['FrameTVSupport']
        return 'Unknown'

    @property
    def game_pad_support(self):
        if not self.connected:
            return

        if 'GamePadSupport' in self._tv_options:
            return self._tv_options['GamePadSupport']
        return 'Unknown'

    @property
    def dmp_drm_playready(self):
        if not self.connected:
            return

        if 'DMP_DRM_PLAYREADY' in self.is_support:
            return self.is_support['DMP_DRM_PLAYREADY']
        return False

    @property
    def dmp_drm_widevine(self):
        if not self.connected:
            return

        if 'DMP_DRM_WIDEVINE' in self.is_support:
            return self.is_support['DMP_DRM_WIDEVINE']
        return False

    @property
    def dmp_available(self):
        if not self.connected:
            return

        if 'DMP_available' in self.is_support:
            return self.is_support['DMP_available']
        return False

    @property
    def eden_available(self):
        if not self.connected:
            return

        if 'EDEN_available' in self.is_support:
            return self.is_support['EDEN_available']
        return False

    @property
    def apps_list_available(self):
        if not self.connected:
            return

        if self._tv_options:
            return True
        return False

    @property
    def ime_synced_support(self):
        if not self.connected:
            return

        if 'ImeSyncedSupport' in self.is_support:
            return self.is_support['ImeSyncedSupport']
        return False

    @property
    def remote_four_directions(self):
        if not self.connected:
            return

        if 'remote_fourDirections' in self.is_support:
            return self.is_support['remote_fourDirections']
        return False

    @property
    def remote_touch_pad(self):
        if not self.connected:
            return

        if 'remote_touchPad' in self.is_support:
            return self.is_support['remote_touchPad']
        return False

    @property
    def voice_support(self):
        if not self.connected:
            return

        if 'VoiceSupport' in self.tv_options:
            return self.tv_options['VoiceSupport']
        return 'Unknown'

    @property
    def firmware_version(self):
        if not self.connected:
            return

        if 'firmwareVersion' in self.tv_options:
            return self.tv_options['firmwareVersion']

        return 'Unknown'

    @property
    def network_type(self):
        if not self.connected:
            return

        if 'networkType' in self.tv_options:
            return self.tv_options['networkType']
        return 'Unknown'

    @property
    def resolution(self):
        if not self.connected:
            return

        if 'resolution' in self.tv_options:
            return self.tv_options['resolution']
        return 'Unknown'

    @property
    def token_auth_support(self):
        if not self.connected:
            return

        if 'TokenAuthSupport' in self.tv_options:
            return self.tv_options['TokenAuthSupport']
        return 'Unknown'

    @property
    def wifi_mac(self):
        if not self.connected:
            return

        if 'wifiMac' in self.tv_options:
            return self.tv_options['wifiMac']
        return 'Unknown'

    @property
    def device_id(self):
        if not self.connected:
            return

        try:
            return self.MainTVAgent2.deviceID
        except AttributeError:
            for service in self.services:
                if hasattr(service, 'deviceId'):
                    return service.deviceId
            raise

    @property
    def panel_technology(self):
        if not self.connected:
            return

        technology_mapping = dict(
            Q='QLED',
            U='LED',
            P='Plasma',
            L='LCD',
            H='DLP',
            K='OLED',
        )

        try:
            return technology_mapping[self.model[0]]
        except KeyError:
            return 'Unknown'

    @property
    def panel_type(self):
        if not self.connected:
            return

        model = self.model
        if model[0] == 'Q' and model[4] == 'Q':
            return 'UHD'
        if model[5].isdigit():
            return 'FullHD'

        panel_mapping = dict(
            S='Slim' if self.year == 2012 else 'SUHD',
            U='UHD',
            P='Plasma',
            H='Hybrid',
        )

        return panel_mapping[model[5]]

    @property
    def size(self):
        if not self.connected:
            return

        return int(self.model[2:][:2])

    @property
    def model(self):
        if not self.connected:
            return

        return self.AVTransport.modelName

    @property
    def year(self):
        if not self.connected:
            return

        try:
            dtv_information = self.dtv_information
            year = dtv_information.find('SupportTVVersion').text
        except AttributeError:
            year = self.RemoteControlReceiver.ProductCap.split(',')[0]

        return int(year)

    @property
    def region(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            dtv_information = self.dtv_information
            location = dtv_information.find('TargetLocation')
            return location.text.replace('TARGET_LOCATION_', '')
        return 'Unknown'

    @property
    def tuner_count(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            dtv_information = self.dtv_information
            tuner_count = dtv_information.find('TunerCount')
            return int(tuner_count.text)
        return 'Unknown'

    @property
    def dtv_support(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            dtv_information = self.dtv_information
            dtv = dtv_information.find('SupportDTV')
            return True if dtv.text == 'Yes' else False
        return 'Unknown'

    @property
    def pvr_support(self):
        if not self.connected:
            return

        if hasattr(self, 'MainTVAgent2'):
            dtv_information = self.dtv_information
            pvr = dtv_information.find('SupportPVR')
            return True if pvr.text == 'Yes' else False
        return 'Unknown'


@six.add_metaclass(InstanceSingleton)
class Channel(object):

    def __init__(self, channel_num, node, parent):
        self._channel_num = channel_num
        self._node = node
        self._parent = parent

    def __getattr__(self, item):

        if item in self.__dict__:
            return self.__dict__[item]

        for child in self._node:
            if child.tag == item:
                value = child.text
                if value.isdigit():
                    value = int(value)

                return value

        raise AttributeError(item)

    @property
    def number(self):
        return self._channel_number

    @number.setter
    def number(self, channel_number=(0, 0)):
        """ channel_number = (major, minor)
        return self.MainTVAgent2.EditChannelNumber(
            antenna_mode,
            source,
            destination,
            forced_flag
        )[0]
        """

        raise NotImplementedError

    @property
    def lock(self):
        raise NotImplementedError

    @lock.setter
    def lock(self, value):
        """
        return self.MainTVAgent2.SetChannelLock(
            antenna_mode,
            channel_list,
            lock,
            pin,
            start_time,
            end_time
        )[0]
        """
        raise NotImplementedError

    @property
    def pin(self):
        raise NotImplementedError

    @pin.setter
    def pin(self, value):
        """
        return self.MainTVAgent2.SetMainTVChannelPIN(
            antenna_mode,
            channel_list_type,
            pin,
            satellite_id,
            channel
        )[0]
        """
        raise NotImplementedError

    @property
    def name(self):
        return self._node.find('PTC').text

    @name.setter
    def name(self, value):
        """
        return self.MainTVAgent2.ModifyChannelName(
            antenna_mode,
            channel,
            channel_name
        )[1]
        """
        raise NotImplementedError

    @property
    def is_recording(self):
        channel = self._parent.MainTVAgent2.GetRecordChannel()[1]
        channel_num = (
            channel.find('MajorCh').text,
            channel.find('MinorCh').text
        )
        return self._channel_num == channel_num

    @property
    def is_active(self):
        return self._parent.channel == self

    def activate(self):
        antenna_mode = 1
        channel_list_type, satellite_id = (
            self._parent.MainTVAgent2.GetChannelListURL()[4:1]
        )

        channel = etree.tostring(self._node)
        channel = saxutils.escape(channel)

        self._parent.MainTVAgent2.SetMainTVChannel(
            antenna_mode,
            channel_list_type,
            satellite_id,
            channel
        )


@six.add_metaclass(InstanceSingleton)
class Source(object):

    def __init__(
        self,
        id,
        name,
        parent,
        editable,
    ):
        self._id = id
        self.__name__ = name
        self._parent = parent
        self._editable = editable

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self.__name__

    @property
    def is_viewable(self):
        source = self.__source
        return source.find('SupportView').text == 'Yes'

    @property
    def is_editable(self):
        return self._editable

    @property
    def __source(self):
        source_list = self._parent.MainTVAgent2.GetSourceList()[1]
        source_list = saxutils.unescape(source_list)
        root = etree.fromstring(source_list)

        for src in root:
            if src.tag == 'Source':
                if int(src.find('ID').text) == self.id:
                    return src

    @property
    def is_connected(self):
        source = self.__source

        connected = source.find('Connected')
        if connected is not None:
            if connected.text == 'Yes':
                return True
            if connected.text == 'No':
                return False

    @property
    def label(self):
        if self.is_editable:
            source = self.__source

            label = source.find('EditNameType')
            if label is not None:
                label = label.text
                if label != 'NONE':
                    return label

        return self.name

    @label.setter
    def label(self, value):
        if self.is_editable:
            self._parent.MainTVAgent2.EditSourceName(self.name, value)

    @property
    def device_name(self):
        source = self.__source
        device_name = source.find('DeviceName')
        if device_name is not None:
            return device_name.text

    @property
    def is_active(self):
        source_list = self._parent.MainTVAgent2.GetSourceList()[1]
        source_list = saxutils.unescape(source_list)
        root = etree.fromstring(source_list)
        return int(root.find('ID').text) == self.id

    def activate(self):
        if self.is_connected:
            self._parent.MainTVAgent2.SetMainTVSource(
                self.name,
                str(self.id),
                str(self.id)
            )

    def __str__(self):
        return self.label
