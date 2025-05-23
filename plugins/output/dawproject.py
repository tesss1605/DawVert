# SPDX-FileCopyrightText: 2024 SatyrDiamond
# SPDX-License-Identifier: GPL-3.0-or-later

import plugins
import zipfile
import io
import os
import uuid
import xml.etree.ElementTree as ET
from xml.dom import minidom
from objects import globalstore
from functions import data_values
from functions import note_data

import logging
logger_output = logging.getLogger('output')

from objects.file_proj._dawproject import clips
from objects.file_proj._dawproject import points
from objects.file_proj._dawproject import track
from objects.file_proj._dawproject import device
from objects.file_proj._dawproject import param

def do_visual(visual_obj, dp_track):
	if visual_obj.name: dp_track.name = visual_obj.name
	if visual_obj.color: dp_track.color = '#'+visual_obj.color.get_hex()

def do_visual_clip(visual_obj, dp_clip):
	if visual_obj.name: dp_clip.name = visual_obj.name
	if visual_obj.color: dp_clip.color = '#'+visual_obj.color.get_hex()

def do_autopoints(autopoints_obj, dppoints_obj):
	if autopoints_obj.val_type == 'float':
		autopoints_obj.remove_instant()
		for autopoint_obj in autopoints_obj:
			dppoint_obj = points.dawproject_realpoint()
			dppoint_obj.time = autopoint_obj.pos
			dppoint_obj.value = autopoint_obj.value
			if autopoint_obj.type != 'instant': dppoint_obj.interpolation = "linear" 
			dppoints_obj.points.append(dppoint_obj)
	if autopoints_obj.val_type == 'bool':
		for autopoint_obj in autopoints_obj:
			dppoint_obj = points.dawproject_boolpoint()
			dppoint_obj.time = autopoint_obj.pos
			dppoint_obj.value = bool(autopoint_obj.value)
			dppoints_obj.points_bool.append(dppoint_obj)

def from_cvpj_auto(convproj_obj, points_obj, autoloc, intype, dpautoid, i_addmul):
	autofound, autoseries = convproj_obj.automation.get(autoloc, intype)
	if autofound and autoseries.nopl_points:
		if i_addmul:
			autoseries.nopl_points.calc('addmul', i_addmul[0], i_addmul[1], 0, 0)
		dppoints_obj = points.dawproject_points()
		dppoints_obj.target = points.dawproject_pointtarget()
		dppoints_obj.target.parameter = dpautoid
		do_autopoints(autoseries.nopl_points, dppoints_obj)
		points_obj.append(dppoints_obj)

def from_cvpj_auto_dppoints_obj(convproj_obj, dppoints_obj, autoloc, intype, dpautoid, i_addmul):
	autofound, autoseries = convproj_obj.automation.get(autoloc, intype)
	if autofound and autoseries.nopl_points:
		if i_addmul:
			autoseries.nopl_points.calc('addmul', i_addmul[0], i_addmul[1], 0, 0)
		dppoints_obj.target = points.dawproject_pointtarget()
		dppoints_obj.target.parameter = dpautoid
		do_autopoints(autoseries.nopl_points, dppoints_obj)

def do_params(convproj_obj, lane_obj, paramset_obj, dp_channel, starttxt, autoloc):
	dp_channel.mute.used = True
	dp_channel.mute.value = not paramset_obj.get('enabled', True).value
	dp_channel.mute.id = starttxt+'enabled'
	dp_channel.solo = bool(paramset_obj.get('solo', False).value)
	dp_channel.pan.used = True
	dp_channel.pan.value = (paramset_obj.get('pan', 0).value/2)+0.5
	dp_channel.pan.id = starttxt+'pan'
	dp_channel.volume.used = True
	dp_channel.volume.unit = 'linear'
	dp_channel.volume.value = paramset_obj.get('vol', 1).value
	dp_channel.volume.id = starttxt+'vol'

	from_cvpj_auto(convproj_obj, lane_obj.points, autoloc+['enabled'], 'bool', dp_channel.mute.id, [-1, -1])
	from_cvpj_auto(convproj_obj, lane_obj.points, autoloc+['pan'], 'float', dp_channel.pan.id, [1, 0.5])
	from_cvpj_auto(convproj_obj, lane_obj.points, autoloc+['vol'], 'float', dp_channel.volume.id, None)

def make_time(clip_obj, cvpjtime_obj):
	clip_obj.time = round(cvpjtime_obj.position, 7)
	clip_obj.duration = round(cvpjtime_obj.duration, 7)
	clip_obj.playStart = round(cvpjtime_obj.cut_start, 7)
	if cvpjtime_obj.cut_type in ['loop','loop_off','loop_adv','loop_adv_off','loop_eq']:
		clip_obj.loopStart = round(cvpjtime_obj.cut_loopstart, 7)
		clip_obj.loopEnd = round(cvpjtime_obj.cut_loopend, 7)

def do_mpe_val(value, mpetype):
	dppoints_obj = points.dawproject_points()
	if mpetype == 'pitch': 
		mpetype = 'transpose'
		dppoints_obj.unit = 'semitones'
	elif mpetype == 'formant': dppoints_obj.unit = 'semitones'
	else: dppoints_obj.unit = 'linear'
	dppoints_obj.target = points.dawproject_pointtarget()
	dppoints_obj.target.expression = mpetype
	dppoint_obj = points.dawproject_realpoint()
	dppoint_obj.time = 0
	dppoint_obj.value = value
	dppoint_obj.interpolation = "linear" 
	dppoints_obj.points.append(dppoint_obj)
	return mpetype, dppoints_obj

def make_send(send_obj, returnid, convproj_obj, dptrack_obj, lane_obj):
	dp_send = track.dawproject_send()
	dp_send.destination = 'channel_return__'+returnid
	dp_send.type = 'post'
	dp_send.volume.used = True
	dp_send.volume.max = 1
	dp_send.volume.min = 0
	dp_send.volume.unit = 'linear'
	dp_send.volume.value = send_obj.params.get('amount', 0).value
	dp_send.volume.name = 'Send'
	if send_obj.sendautoid: 
		dp_send.volume.id = 'send__'+send_obj.sendautoid+'__param__amount'
		from_cvpj_auto(convproj_obj, lane_obj.points, ['send', send_obj.sendautoid, 'amount'], 'float', dp_send.volume.id, None)
	return dp_send

def make_sends(master_returns, cvpj_sendsdata, dp_track, convproj_obj, lane_obj):
	for returnid, x in master_returns.items():
		if returnid in cvpj_sendsdata:
			send_obj = cvpj_sendsdata[returnid]
			dp_send = make_send(send_obj, returnid, convproj_obj, dp_track, lane_obj)
			dp_track.channel.sends.append(dp_send)

def do_auto_mpe(autopoints_obj, mpetype, dppoints_obj):
	if mpetype == 'pitch': 
		mpetype = 'transpose'
		dppoints_obj.unit = 'semitones'
	elif mpetype == 'formant': dppoints_obj.unit = 'semitones'
	else: dppoints_obj.unit = 'linear'
	dppoints_obj.target = points.dawproject_pointtarget()
	dppoints_obj.target.expression = mpetype
	do_autopoints(autopoints_obj, dppoints_obj)
	return mpetype

def make_dp_audio(convproj_obj, samplepart_obj):
	dp_audio = None
	dp_warps = None
	zip_filepath = None
	filepath = None
	ref_found, sampleref_obj = convproj_obj.sampleref__get(samplepart_obj.sampleref)
	if ref_found: 
		filepath = sampleref_obj.fileref.get_path(None, False)
		basename = sampleref_obj.fileref.file.basename
		dp_audio = clips.dawproject_audio()
		dp_audio.channels = sampleref_obj.channels
		dp_audio.duration = sampleref_obj.dur_sec
		dp_audio.sampleRate = sampleref_obj.hz

		stretch_obj = samplepart_obj.stretch

		if bool(stretch_obj):
			if stretch_obj.preserve_pitch:
				dp_audio.algorithm = 'stretch_subbands'
				if stretch_obj.algorithm == 'stretch_subbands':
					dp_audio.algorithm = 'stretch_subbands'

				if stretch_obj.algorithm == 'slice':
					dp_audio.algorithm = 'slice'

				if stretch_obj.algorithm == 'elastique_v3':
					if stretch_obj.algorithm_mode == 'mono': dp_audio.algorithm = 'elastique_solo'
					elif stretch_obj.algorithm_mode == 'speech': dp_audio.algorithm = 'elastique_solo'
					elif stretch_obj.algorithm_mode == 'efficient': dp_audio.algorithm = 'elastique_eco'
					elif stretch_obj.algorithm_mode == 'pro': dp_audio.algorithm = 'elastique_pro'
					else: dp_audio.algorithm = 'elastique'

				if stretch_obj.algorithm == 'elastique_v2':
					if stretch_obj.algorithm_mode == 'mono': dp_audio.algorithm = 'elastique_solo'
					elif stretch_obj.algorithm_mode == 'speech': dp_audio.algorithm = 'elastique_solo'
					elif stretch_obj.algorithm_mode == 'efficient': dp_audio.algorithm = 'elastique_eco'
					elif stretch_obj.algorithm_mode == 'pro': dp_audio.algorithm = 'elastique_pro'
					else: dp_audio.algorithm = 'elastique'
			else:
				dp_audio.algorithm = 'repitch'

		else:
			dp_audio.algorithm = 'raw'

		maxlen = 0

		if stretch_obj.is_warped:
			maxlen = 0
			dp_warps = clips.dawproject_warps()
			dp_warps.contentTimeUnit = 'seconds'
			dp_warps.timeUnit = 'beats'
			dp_warps.audio = dp_audio

			warp_obj = stretch_obj.warp
			for warppoint in warp_obj.points__iter():
				dp_warppoint = clips.dawproject_warppoint()
				dp_warppoint.time = round(warppoint.beat, 9)
				dp_warppoint.contentTime = round(warppoint.second, 9)
				dp_warps.points.append(dp_warppoint)
				maxlen = warppoint.beat

		zip_filepath = 'audio/'+basename
		dp_audio.file.set(zip_filepath)

	return dp_audio, dp_warps, zip_filepath, filepath, maxlen

def make_audioclip(convproj_obj, cvpj_audioclip, dp_clips_obj, dotime):

	dp_clip_obj = clips.dawproject_clip()
	dp_clip_obj.contentTimeUnit = 'beats'
	do_visual_clip(cvpj_audioclip.visual, dp_clip_obj)

	stretch_obj = cvpj_audioclip.sample.stretch

	warp_obj = stretch_obj.warp
	warp_obj.fix__onlyone()
	warp_obj.calcpoints__speed()
	#warp_obj.fixpl__offset(cvpj_audioclip.time, 1)




	dp_audio, dp_warps, zip_filepath, real_filepath, maxlen = make_dp_audio(convproj_obj, cvpj_audioclip.sample)
	if dp_warps: dp_clip_obj.warps = dp_warps
	else: dp_clip_obj.audio = dp_audio

	if dotime: make_time(dp_clip_obj, cvpj_audioclip.time)
	else: 
		dp_clip_obj.time = 0
		dp_clip_obj.duration = round(maxlen, 7)
		dp_clip_obj.playStart = 0

	#print(dp_clip_obj.time, dp_clip_obj.duration, dp_clip_obj.playStart, dp_clip_obj.loopStart, dp_clip_obj.loopEnd)

	if os.path.exists(real_filepath) and zip_filepath not in dawproject_zip.namelist(): 
		dawproject_zip.write(real_filepath, zip_filepath)

	autodata = {}

	if cvpj_audioclip.sample.pan != 0: 
		mpetype, dp_points = do_mpe_val(cvpj_audioclip.sample.pan, 'pan')
		autodata[mpetype] = dp_points

	if cvpj_audioclip.sample.pitch != 0:
		mpetype, dp_points = do_mpe_val(cvpj_audioclip.sample.pitch, 'pitch')
		autodata[mpetype] = dp_points

	if cvpj_audioclip.sample.vol != 1:
		mpetype, dp_points = do_mpe_val(cvpj_audioclip.sample.vol, 'gain')
		autodata[mpetype] = dp_points

	stretchparams = cvpj_audioclip.sample.stretch.params
	if 'formant' in stretchparams:
		if stretchparams['formant'] != 0:
			mpetype, dp_points = do_mpe_val(stretchparams['formant'], 'formant')
			autodata[mpetype] = dp_points

	for n, x in cvpj_audioclip.auto.items():
		dp_points = points.dawproject_points()
		mpetype = do_auto_mpe(x, n, dp_points)
		autodata[mpetype] = dp_points

	if autodata:
		inlane_obj = clips.dawproject_lane()
		inlane_obj.warps = dp_clip_obj.warps
		inlane_obj.audio = dp_clip_obj.audio
		for _, x in autodata.items(): inlane_obj.points.append(x)
		dp_clip_obj.warps = None
		dp_clip_obj.audio = None
		dp_clip_obj.lanes = inlane_obj

	dp_clips_obj.clips.append(dp_clip_obj)
	return dp_clip_obj

def make_clips(starttxt, convproj_obj, track_obj, lane_obj, trackid):
	for notespl_obj in track_obj.placements.pl_notes:
		clip_obj = clips.dawproject_clip()
		make_time(clip_obj, notespl_obj.time)
		do_visual_clip(notespl_obj.visual, clip_obj)

		clip_obj.notes = clips.dawproject_notes()
		for t_pos, t_dur, t_keys, t_vol, t_inst, t_extra, t_auto, t_slide in notespl_obj.notelist.iter():
			for t_key in t_keys:
				note_obj = clips.dawproject_note()
				note_obj.time = t_pos
				note_obj.duration = t_dur
				note_obj.key = t_key+60
				note_obj.vel = t_vol
				if t_extra: 
					note_obj.channel = t_extra['channel'] if 'channel' in t_extra else 0
					note_obj.rel = t_extra['release'] if 'release' in t_extra else t_vol
				if t_auto:
					if len(t_auto) == 1:
						mpetype = list(t_auto)[0]
						note_obj.points = points.dawproject_points()
						do_auto_mpe(t_auto[mpetype], mpetype, note_obj.points)
					if len(t_auto) > 1:
						note_obj.lanes = clips.dawproject_lane()
						for mpetype, a in t_auto.items():
							dp_points = points.dawproject_points()
							do_auto_mpe(a, mpetype, dp_points)
							note_obj.lanes.points.append(dp_points)
			clip_obj.notes.notes.append(note_obj)
		lane_obj.clips.clips.append(clip_obj)

	for audiopl_obj in track_obj.placements.pl_audio:
		clip_obj = clips.dawproject_clip()
		make_time(clip_obj, audiopl_obj.time)
		do_visual_clip(audiopl_obj.visual, clip_obj)
		clip_obj.clips = clips.dawproject_clips()
		dp_clip_obj = make_audioclip(convproj_obj, audiopl_obj, clip_obj.clips, False)
		dp_clip_obj.fadeTimeUnit = 'beats'
		dp_clip_obj.fadeInTime = audiopl_obj.fade_in.get_dur_seconds(bpm)
		dp_clip_obj.fadeOutTime = audiopl_obj.fade_out.get_dur_seconds(bpm)
		lane_obj.clips.clips.append(clip_obj)

	for nestedaudiopl_obj in track_obj.placements.pl_audio_nested:
		clip_obj = clips.dawproject_clip()
		make_time(clip_obj, nestedaudiopl_obj.time)
		do_visual_clip(nestedaudiopl_obj.visual, clip_obj)
		clip_obj.clips = clips.dawproject_clips()
		for insideaudiopl_obj in nestedaudiopl_obj.events: make_audioclip(convproj_obj, insideaudiopl_obj, clip_obj.clips, True)
		lane_obj.clips.clips.append(clip_obj)

def make_track(contentType, role, trackid, chanid):
	dp_track = track.dawproject_track()
	dp_track.contentType = contentType
	dp_track.loaded = True
	dp_track.id = trackid
	dp_channel = dp_track.channel
	dp_channel.role = role
	dp_channel.audioChannels = 2
	dp_channel.id = chanid
	return dp_track, dp_channel

def make_lane(starttxt):
	lane_obj = clips.dawproject_lane()
	lane_obj.track = starttxt
	lane_obj.clips = clips.dawproject_clips()
	lane_obj.clips.id = 'clips__'+starttxt
	lane_obj.id = 'lanes__'+starttxt
	arrangement_obj.lanes.lanes.append(lane_obj)
	return lane_obj

def do_extparams(param_obj, pluginid, convproj_obj, lane_obj, dp_device):
	extparams = {}

	for cvpj_paramid in param_obj.list():
		if cvpj_paramid.startswith('ext_param_'):
			cvpj_paramdata = param_obj.get(cvpj_paramid, 1)
			paramnum = int(cvpj_paramid[10:])
			dp_realparam = device.dawproject_realparameter()
			dp_realparam.value = cvpj_paramdata.value
			dp_realparam.parameterID = paramnum
			dp_realparam.id = 'plugin__'+pluginid+'__param__'+cvpj_paramid
			if cvpj_paramdata.visual.name: dp_realparam.name = cvpj_paramdata.visual.name
			dp_device.realparameter.append(dp_realparam)
			#from_cvpj_auto(convproj_obj, lane_obj.points, ['plugin', pluginid, cvpj_paramid], 'float', dp_realparam.id, 0)
			extparams[paramnum] = dp_realparam

	for autoloc, autodata, paramnum in convproj_obj.automation.iter_nopl_points_external(pluginid):
		if paramnum not in extparams:
			dp_realparam = device.dawproject_realparameter()
			dp_realparam.parameterID = paramnum
			dp_realparam.id = 'plugin__'+pluginid+'__param__ext_param_'+str(paramnum)
			dp_device.realparameter.append(dp_realparam)
		else:
			dp_realparam = extparams[paramnum]

		dppoints_obj = points.dawproject_points()
		dppoints_obj.target = points.dawproject_pointtarget()
		dppoints_obj.target.parameter = 'plugin__'+pluginid+'__param__ext_param_'+str(paramnum)
		do_autopoints(autodata, dppoints_obj)
		lane_obj.points.append(dppoints_obj)

def add_device_param_from_paramobj(convproj_obj, lane_obj, plugin_obj, pluginid, dp_device, unit, name, dpname, p_min, p_max):
	if name in plugin_obj.params.list():
		dp_param_id = 'plugin__'+pluginid+'__param__'+name
	
		param_obj = plugin_obj.params.get(name, 0)
	
		if param_obj.type in ["int", "float"]: 
			dp_param = param.dawproject_param_numeric(dpname)
			dp_param.max = p_max
			dp_param.min = p_min
		if param_obj.type in ["bool"]: 
			dp_param = param.dawproject_param_bool(dpname)
		dp_param.used = True
		dp_param.unit = unit
		dp_param.value = param_obj.value
		dp_param.id = dp_param_id
		dp_param.name = dpname
		dp_device.params[dpname] = dp_param
	
		from_cvpj_auto(convproj_obj, lane_obj.points, ['plugin', pluginid, name], 'float', dp_param_id, None)

def do_device(convproj_obj, dp_channel, lane_obj, pluginid, role):
	plugin_found, plugin_obj = convproj_obj.plugin__get(pluginid)
	if plugin_found:
		dp_device = None

		if plugin_obj.check_match('universal', 'compressor', None):
			dp_device = device.dawproject_device('Compressor')
			add_device_param_from_paramobj(convproj_obj, lane_obj, plugin_obj, pluginid, dp_device, 'seconds', 'attack', 'Attack', 0.000204, 0)
			add_device_param_from_paramobj(convproj_obj, lane_obj, plugin_obj, pluginid, dp_device, '', 'automakeup', 'AutoMakeup', 0, 1)
			add_device_param_from_paramobj(convproj_obj, lane_obj, plugin_obj, pluginid, dp_device, 'decibel', 'pregain', 'InputGain', -20, 20)
			add_device_param_from_paramobj(convproj_obj, lane_obj, plugin_obj, pluginid, dp_device, 'decibel', 'gain', 'OutputGain', -20, 20)
			add_device_param_from_paramobj(convproj_obj, lane_obj, plugin_obj, pluginid, dp_device, 'percent', 'ratio', 'Ratio', 0, 100)
			add_device_param_from_paramobj(convproj_obj, lane_obj, plugin_obj, pluginid, dp_device, 'seconds', 'release', 'Release', 0.038905, 1.412538)
			add_device_param_from_paramobj(convproj_obj, lane_obj, plugin_obj, pluginid, dp_device, 'decibel', 'threshold', 'Threshold', -60, 0)

		if plugin_obj.check_match('universal', 'limiter', None):
			dp_device = device.dawproject_device('Limiter')
			add_device_param_from_paramobj(convproj_obj, lane_obj, plugin_obj, pluginid, dp_device, 'decibel', 'pregain', 'InputGain', -36, 36)
			add_device_param_from_paramobj(convproj_obj, lane_obj, plugin_obj, pluginid, dp_device, 'seconds', 'release', 'Release', 0.01, 10)
			add_device_param_from_paramobj(convproj_obj, lane_obj, plugin_obj, pluginid, dp_device, 'decibel', 'threshold', 'Threshold', -36, 0)

		if plugin_obj.check_match('universal', 'noise_gate', None):
			dp_device = device.dawproject_device('NoiseGate')
			add_device_param_from_paramobj(convproj_obj, lane_obj, plugin_obj, pluginid, dp_device, 'seconds', 'attack', 'Attack', 0.001, 0.1)
			add_device_param_from_paramobj(convproj_obj, lane_obj, plugin_obj, pluginid, dp_device, 'decibel', 'range', 'Range', 120, 0)
			add_device_param_from_paramobj(convproj_obj, lane_obj, plugin_obj, pluginid, dp_device, 'seconds', 'release', 'Release', 0.001, 1)
			add_device_param_from_paramobj(convproj_obj, lane_obj, plugin_obj, pluginid, dp_device, 'decibel', 'threshold', 'Threshold', -1000000, 0)

		if plugin_obj.check_match('universal', 'filter', None):
			dp_device = device.dawproject_device('Equalizer')
			dp_device.deviceID = 'e4815188-ba6f-4d14-bcfc-2dcb8f778ccb'
			dp_device.deviceName = plugin_obj.external_info.name
			dp_device.name = 'EQ+'
			dp_device.deviceRole = 'audioFX'

			band = device.dawproject_band()
			filter_obj = plugin_obj.filter
			cvpjbandtype = filter_obj.type.type

			if cvpjbandtype == 'notch': band.type = 'notch'
			if cvpjbandtype == 'high_shelf': band.type = 'highShelf'
			if cvpjbandtype == 'low_pass': band.type = 'lowPass'
			if cvpjbandtype == 'peak': band.type = 'bell'
			if cvpjbandtype == 'low_shelf': band.type = 'lowShelf'
			if cvpjbandtype == 'high_pass': band.type = 'highPass'

			band.enabled.value = 'true' if filter_obj.on else 'false'
			band.enabled.used = True
			band.enabled.id = 'nfilter__'+pluginid+'__enabled'

			band.freq.value = filter_obj.freq
			band.freq.used = True
			band.freq.id = 'nfilter__'+pluginid+'__freq'
			band.freq.unit = 'hertz'
			band.freq.max = 20
			band.freq.min = 20000

			band.gain.value = filter_obj.gain
			band.gain.used = True
			band.gain.id = 'nfilter__'+pluginid+'__gain'
			band.gain.unit = 'decibel'
			band.gain.max = 30.000000
			band.gain.min = -30.000000

			band.q.value = filter_obj.q
			band.q.used = True
			band.q.id = 'nfilter__'+pluginid+'__q'
			band.q.unit = 'linear'
			band.q.max = 40.003685
			band.q.min = 0.024998

			from_cvpj_auto(convproj_obj, lane_obj.points, ['filter', pluginid, 'on'], 'bool', band.enabled.id, None)
			from_cvpj_auto(convproj_obj, lane_obj.points, ['filter', pluginid, 'freq'], 'float', band.freq.id, None)
			from_cvpj_auto(convproj_obj, lane_obj.points, ['filter', pluginid, 'gain'], 'float', band.gain.id, None)
			from_cvpj_auto(convproj_obj, lane_obj.points, ['filter', pluginid, 'q'], 'float', band.q.id, None)

			dp_device.bands.append(band)

		is_eq_bands = plugin_obj.type.check_wildmatch('universal', 'eq', 'bands')
		is_eq_8limited = plugin_obj.type.check_wildmatch('universal', 'eq', '8limited')
		if is_eq_bands or is_eq_8limited:
			if is_eq_8limited: plugin_obj.eq.from_8limited(pluginid)
			dp_device = device.dawproject_device('Equalizer')
			dp_device.deviceID = 'e4815188-ba6f-4d14-bcfc-2dcb8f778ccb'
			dp_device.deviceName = plugin_obj.external_info.name
			dp_device.name = 'EQ+'
			dp_device.deviceRole = 'audioFX'

			for filter_id, filter_obj in plugin_obj.eq:
				band = device.dawproject_band()

				cvpjbandtype = filter_obj.type.type

				if cvpjbandtype == 'notch': band.type = 'notch'
				if cvpjbandtype == 'high_shelf': band.type = 'highShelf'
				if cvpjbandtype == 'low_pass': band.type = 'lowPass'
				if cvpjbandtype == 'peak': band.type = 'bell'
				if cvpjbandtype == 'low_shelf': band.type = 'lowShelf'
				if cvpjbandtype == 'high_pass': band.type = 'highPass'

				band.enabled.value = 'true' if filter_obj.on else 'false'
				band.enabled.used = True
				band.enabled.id = 'nfilter__'+filter_id+'__enabled'

				band.freq.value = filter_obj.freq
				band.freq.used = True
				band.freq.id = 'nfilter__'+pluginid+'__'+filter_id+'__freq'
				band.freq.unit = 'hertz'
				band.freq.max = 20
				band.freq.min = 20000

				band.gain.value = filter_obj.gain
				band.gain.used = True
				band.gain.id = 'nfilter__'+pluginid+'__'+filter_id+'__gain'
				band.gain.unit = 'decibel'
				band.gain.max = 30.000000
				band.gain.min = -30.000000

				band.q.value = filter_obj.q
				band.q.used = True
				band.q.id = 'nfilter__'+pluginid+'__'+filter_id+'__q'
				band.q.unit = 'linear'
				band.q.max = 40.003685
				band.q.min = 0.024998

				from_cvpj_auto(convproj_obj, lane_obj.points, ['n_filter', pluginid, filter_id, 'on'], 'bool', band.enabled.id, None)
				from_cvpj_auto(convproj_obj, lane_obj.points, ['n_filter', pluginid, filter_id, 'freq'], 'float', band.freq.id, None)
				from_cvpj_auto(convproj_obj, lane_obj.points, ['n_filter', pluginid, filter_id, 'gain'], 'float', band.gain.id, None)
				from_cvpj_auto(convproj_obj, lane_obj.points, ['n_filter', pluginid, filter_id, 'q'], 'float', band.q.id, None)

				dp_device.bands.append(band)

		if plugin_obj.check_wildmatch('external', 'vst2', None):
			fourid = plugin_obj.external_info.fourid
			if fourid:
				dp_device = device.dawproject_device('Vst2Plugin')
				dp_device.deviceID = fourid
				dp_device.deviceName = plugin_obj.external_info.name
				dp_device.name = plugin_obj.external_info.name

				extmanu_obj = plugin_obj.create_ext_manu_obj(convproj_obj, pluginid)
				fxpdata = extmanu_obj.vst2__export_presetdata(None)

				statepath = 'plugins/'+str(uuid.uuid4())+'.fxp'
				dawproject_zip.writestr(statepath, fxpdata)
				dp_device.state.set(statepath)

				extparams = {}

				do_extparams(plugin_obj.params, pluginid, convproj_obj, lane_obj, dp_device)
			else:
				logger_output.warning('VST2 plugin not placed: no ID found.')

		if plugin_obj.check_wildmatch('external', 'vst3', None):
			vstid = plugin_obj.external_info.id
			if vstid:
				dp_device = device.dawproject_device('Vst3Plugin')
				dp_device.deviceID = vstid
				dp_device.deviceName = plugin_obj.external_info.name
				dp_device.name = plugin_obj.external_info.name

				extmanu_obj = plugin_obj.create_ext_manu_obj(convproj_obj, pluginid)
				fxpdata = extmanu_obj.vst3__export_presetdata(None)

				statepath = 'plugins/'+str(uuid.uuid4())+'.vstpreset'
				dawproject_zip.writestr(statepath, fxpdata)
				dp_device.state.set(statepath)

				do_extparams(plugin_obj.params, pluginid, convproj_obj, lane_obj, dp_device)
			else:
				logger_output.warning('VST3 plugin not placed: no ID found.')

		if plugin_obj.check_wildmatch('external', 'clap', None):
			clapid = plugin_obj.external_info.id
			if clapid:
				dp_device = device.dawproject_device('ClapPlugin')
				dp_device.deviceID = plugin_obj.external_info.id
				dp_device.deviceName = plugin_obj.external_info.name
				dp_device.name = plugin_obj.external_info.name

				extmanu_obj = plugin_obj.create_ext_manu_obj(convproj_obj, pluginid)
				fxpdata = extmanu_obj.clap__export_presetdata(None)

				if fxpdata:
					statepath = 'plugins/'+str(uuid.uuid4())+'.clap-preset'
					dawproject_zip.writestr(statepath, fxpdata)
					dp_device.state.set(statepath)

				do_extparams(plugin_obj.params, pluginid, convproj_obj, lane_obj, dp_device)
			else:
				logger_output.warning('CLAP plugin not placed: no ID found.')

		if dp_device:
			dp_device.deviceRole = role
			dp_device.loaded = True
			dp_device.id = 'plugin__'+pluginid

			dp_device.enabled.used = True
			dp_device.enabled.value = plugin_obj.params_slot.get('enabled', True).value
			dp_device.enabled.id = dp_device.id+'__slot__enabled'
			dp_device.enabled.name = 'On/Off'

			dp_channel.devices.append(dp_device)

def do_devices(convproj_obj, dp_channel, lane_obj, inst_pluginid, fxslots_audio):
	if inst_pluginid: 
		do_device(convproj_obj, dp_channel, lane_obj, inst_pluginid, 'instrument')
	for x in fxslots_audio: 
		do_device(convproj_obj, dp_channel, lane_obj, x, 'audioFX')

def maketrack_notes(convproj_obj, track_obj, trackid, lane_obj):
	dp_track, dp_channel = make_track('notes', 'regular', 'track__'+trackid, 'channel__'+trackid)
	dp_channel.destination = 'masterchannel' if not track_obj.group else 'channel_group__'+track_obj.group
	do_visual(track_obj.visual, dp_track)
	do_params(convproj_obj, lane_obj, track_obj.params, dp_channel, dp_track.id+'__param__', ['track', trackid])
	make_clips(dp_track.id, convproj_obj, track_obj, lane_obj, trackid)
	do_devices(convproj_obj, dp_channel, lane_obj, track_obj.plugslots.synth, track_obj.plugslots.slots_audio)
	return dp_track

def maketrack_audio(convproj_obj, track_obj, trackid, lane_obj):
	dp_track, dp_channel = make_track('audio', 'regular', 'track__'+trackid, 'channel__'+trackid)
	dp_channel.destination = 'masterchannel' if not track_obj.group else 'channel_group__'+track_obj.group
	do_visual(track_obj.visual, dp_track)
	do_params(convproj_obj, lane_obj, track_obj.params, dp_channel, dp_track.id+'__param__', ['track', trackid])
	make_clips(dp_track.id, convproj_obj, track_obj, lane_obj, trackid)
	do_devices(convproj_obj, dp_channel, lane_obj, None, track_obj.plugslots.slots_audio)
	return dp_track

def maketrack_hybrid(convproj_obj, track_obj, trackid, lane_obj):
	dp_track, dp_channel = make_track('audio notes', 'regular', 'track__'+trackid, 'channel__'+trackid)
	dp_channel.destination = 'masterchannel' if not track_obj.group else 'channel_group__'+track_obj.group
	do_visual(track_obj.visual, dp_track)
	do_params(convproj_obj, lane_obj, track_obj.params, dp_channel, dp_track.id+'__param__', ['track', trackid])
	make_clips(dp_track.id, convproj_obj, track_obj, lane_obj, trackid)
	do_devices(convproj_obj, dp_channel, lane_obj, track_obj.plugslots.synth, track_obj.plugslots.slots_audio)
	return dp_track

def maketrack_group(convproj_obj, group_obj, trackid, lane_obj):
	dp_track, dp_channel = make_track('tracks', 'master', 'group__'+trackid, 'channel_group__'+trackid)
	dp_channel.destination = 'masterchannel' if not group_obj.group else 'channel_group__'+group_obj.group
	do_visual(group_obj.visual, dp_track)
	do_params(convproj_obj, lane_obj, group_obj.params, dp_channel, dp_track.id+'__param__', ['group', trackid])
	make_clips(dp_track.id, convproj_obj, group_obj, lane_obj, trackid)
	do_devices(convproj_obj, dp_channel, lane_obj, None, group_obj.plugslots.slots_audio)
	return dp_track

def maketrack_return(convproj_obj, return_obj, returnid):
	dp_track, dp_channel = make_track('audio', 'effect', 'return__'+returnid, 'channel_return__'+returnid)
	do_visual(return_obj.visual, dp_track)
	lane_obj = make_lane('return__'+returnid)
	do_params(convproj_obj, lane_obj, return_obj.params, dp_channel, dp_track.id+'__param__', ['return', returnid])
	do_devices(convproj_obj, dp_channel, lane_obj, None, return_obj.plugslots.slots_audio)
	return dp_track

def maketrack_master(convproj_obj, track_obj, arrangement):
	dp_track, dp_channel = make_track('audio notes', 'master', 'mastertrack', 'masterchannel')
	track_obj.visual.name = 'Master'
	do_visual(track_obj.visual, dp_track)
	lane_obj = make_lane('mastertrack')
	do_params(convproj_obj, lane_obj, track_obj.params, dp_channel, dp_track.id+'__param__', ['master'])
	autofound, autoseries = convproj_obj.automation.get(['main', 'bpm'], 'float')
	do_devices(convproj_obj, dp_channel, lane_obj, None, track_obj.plugslots.slots_audio)
	if autofound:
		tempoauto = arrangement.tempoautomation = points.dawproject_points()
		tempoauto.unit = 'bpm'
		from_cvpj_auto_dppoints_obj(convproj_obj, tempoauto, ['main', 'bpm'], 'float', 'main__bpm', None)
	return dp_track

class output_dawproject(plugins.base):
	def is_dawvert_plugin(self):
		return 'output'
	
	def get_shortname(self):
		return 'dawproject'
	
	def get_name(self):
		return 'DawProject'
	
	def gettype(self):
		return 'r'
	
	def get_prop(self, in_dict): 
		in_dict['file_ext'] = 'dawproject'
		in_dict['placement_loop'] = ['loop', 'loop_eq', 'loop_off', 'loop_adv','loop_adv_off']
		in_dict['audio_filetypes'] = ['wav', 'mp3', 'ogg', 'flac', 'm4a']
		in_dict['placement_cut'] = True
		in_dict['auto_types'] = ['nopl_points']
		in_dict['audio_stretch'] = ['warp']
		in_dict['audio_nested'] = True
		in_dict['plugin_ext'] = ['vst2', 'vst3', 'clap']
		in_dict['plugin_ext_arch'] = [32, 64]
		in_dict['plugin_ext_platforms'] = ['win', 'unix']
		in_dict['fxtype'] = 'groupreturn'
		in_dict['projtype'] = 'r'
		in_dict['plugin_included'] = ['universal:compressor', 'universal:limiter', 'universal:noise_gate', 'universal:eq:bands']
	
	def parse(self, convproj_obj, dawvert_intent):
		from objects.file_proj import dawproject as proj_dawproject

		global arrangement_obj
		global dawproject_zip
		global bpm

		convproj_obj.change_timings(1, True)

		project_obj = proj_dawproject.dawproject_song()
		project_obj.application.name = 'DawVert'
		arrangement_obj = project_obj.arrangement

		zip_bio = io.BytesIO()
		dawproject_zip = zipfile.ZipFile(zip_bio, mode='w', compresslevel=None)

		dp_tempo = project_obj.transport.Tempo
		dp_tempo.used = True
		bpm = dp_tempo.value = convproj_obj.params.get('bpm', 120).value
		dp_tempo.id = 'main__bpm'

		dp_timesig = project_obj.transport.TimeSignature
		dp_timesig.used = True
		dp_timesig.numerator = convproj_obj.timesig[0]
		dp_timesig.denominator = convproj_obj.timesig[1]
		dp_timesig.id = 'main__timesig'

		master_returns = convproj_obj.track_master.returns

		groups_data = {}

		for groupid, insidegroup in convproj_obj.group__iter_inside():
			grp_lane_obj = make_lane('group__'+groupid)
			group_obj = convproj_obj.fx__group__get(groupid)
			dp_group = maketrack_group(convproj_obj, group_obj, groupid, grp_lane_obj)
			make_sends(master_returns, group_obj.sends.data, dp_group, convproj_obj, grp_lane_obj)
			groups_data[groupid] = dp_group
			if insidegroup: 
				groups_data[insidegroup].tracks.append(dp_group)
			else:
				project_obj.tracks.append(dp_group)

		for trackid, track_obj in convproj_obj.track__iter():

			if track_obj.type in ['instrument', 'audio', 'hybrid']:
				lane_obj = make_lane('track__'+trackid)
				dp_tracks = project_obj.tracks
				dp_track = None

				if track_obj.group:
					dp_tracks = groups_data[track_obj.group].tracks

				if track_obj.type == 'instrument':
					dp_track = maketrack_notes(convproj_obj, track_obj, trackid, lane_obj)

				if track_obj.type == 'audio':
					dp_track = maketrack_audio(convproj_obj, track_obj, trackid, lane_obj)

				if track_obj.type == 'hybrid':
					dp_track = maketrack_hybrid(convproj_obj, track_obj, trackid, lane_obj)

				if dp_track:
					dp_tracks.append(dp_track)

				make_sends(master_returns, track_obj.sends.data, dp_track, convproj_obj, lane_obj)

		for returnid, return_obj in master_returns.items():
			dp_track = maketrack_return(convproj_obj, return_obj, returnid)
			for ireturnid, x in master_returns.items():
				lane_obj = make_lane('return__'+trackid)
				if ireturnid in return_obj.sends.data:
					send_obj = return_obj.sends.data[ireturnid]
					dp_send = make_send(send_obj, returnid, convproj_obj, dp_track, lane_obj)
					dp_track.channel.sends.append(dp_send)
			project_obj.tracks.append(dp_track)

		project_obj.arrangement.id = 'main__arr'
		arr_lanes = project_obj.arrangement.lanes
		arr_lanes.timeUnit = 'beats'
		arr_lanes.id = 'main__arrlanes'

		dp_track = maketrack_master(convproj_obj, convproj_obj.track_master, project_obj.arrangement)
		project_obj.tracks.append(dp_track)

		if convproj_obj.timemarkers:
			project_obj.arrangement.markers = proj_dawproject.dawproject_markers()
			markers = project_obj.arrangement.markers.markers
			for timemarker_obj in convproj_obj.timemarkers:
				marker = proj_dawproject.dawproject_marker()
				if timemarker_obj.visual.name: marker.name = timemarker_obj.visual.name
				if timemarker_obj.visual.color: marker.color = '#'+timemarker_obj.visual.color.get_hex()
				marker.time = timemarker_obj.position
				markers.append(marker)

		if bool(convproj_obj.timesig_auto):

			dp_timesig = project_obj.arrangement.timesignatureautomation = points.dawproject_points_timesig()
			dp_timesig.id = 'main__timesig'

			firstpoint = True
			for pos, value in convproj_obj.timesig_auto:
				if firstpoint:
					if pos != 0:
						point_obj = points.dawproject_timesigpoint()
						point_obj.time = 0
						point_obj.numerator = convproj_obj.timesig[0]
						point_obj.denominator = convproj_obj.timesig[1]
						dp_timesig.points.append(point_obj)
				point_obj = points.dawproject_timesigpoint()
				point_obj.time = pos
				point_obj.numerator = value[0]
				point_obj.denominator = value[1]
				dp_timesig.points.append(point_obj)
				firstpoint = False

		dp_obj = project_obj.metadata
		meta_obj = convproj_obj.metadata

		if meta_obj.name: dp_obj['Title'] = meta_obj.name
		if meta_obj.author: dp_obj['Artist'] = meta_obj.author
		if meta_obj.album: dp_obj['Album'] = meta_obj.album
		if meta_obj.original_author: dp_obj['OriginalArtist'] = meta_obj.original_author
		if meta_obj.songwriter: dp_obj['Songwriter'] = meta_obj.songwriter
		if meta_obj.producer: dp_obj['Producer'] = meta_obj.producer
		if meta_obj.t_year != -1: dp_obj['Year'] = str(meta_obj.t_year)
		if meta_obj.genre: dp_obj['Genre'] = meta_obj.genre
		if meta_obj.copyright: dp_obj['Copyright'] = meta_obj.copyright
		if meta_obj.comment_text: dp_obj['Comment'] = meta_obj.comment_text

		dawproject_zip.writestr('project.xml', project_obj.save_to_text())
		dawproject_zip.writestr('metadata.xml', project_obj.save_metadata())
		dawproject_zip.close()

		if dawvert_intent.output_mode == 'file':
			open(dawvert_intent.output_file, 'wb').write(zip_bio.getbuffer())

		open('outdebug.xml', 'wb').write(project_obj.save_to_text())