# SPDX-FileCopyrightText: 2024 SatyrDiamond
# SPDX-License-Identifier: GPL-3.0-or-later

import plugins
import json
import struct
import os
import math
import numpy as np
import uuid
from functions import data_values
from functions import xtramath
from objects import globalstore
from objects.data_bytes import bytewriter
from functions_spec import soundbridge as soundbridge_func
import logging

PROJECT_FREQ = 22050

logger_output = logging.getLogger('output')

sb_notes_dtype = np.dtype([('id', '>I'),('pos', '>I'),('dur', '>I'),('key', 'B'),('vol', 'B'),('unk1', 'B'),('unk2', 'B')])

native_names = {}
native_names['eq'] = ['2ed34074c14566409f62442c8545929f', 'ZPlane', 'EQ']
native_names['filter_unit'] = ['544d1ae3e2c91548b932574932c83885', 'ZPlane', 'Filter Unit']
native_names['analyzer'] = ['1423f146b5fcaa40904b2c3fe24495fa', 'ZPlane', 'Analyzer']
native_names['chorus_flanger'] = ['f487b09e6f329a41b2cfc280068079a4', 'ZPlane', 'Chorus/Flanger']
native_names['delay'] = ['0d47d236d52df342bf3b8635a4b89f07', 'ZPlane', 'Delay']
native_names['phaser'] = ['b2a57c0cc1996d468f38a87332010bc9', 'ZPlane', 'Phaser']
native_names['reverb'] = ['8f64f7b97060ca449e89456f9a2684d0', 'ZPlane', 'Reverb']
native_names['bit_crusher'] = ['2793169f4a4b554087755fafff91b3e9', 'ZPlane', 'Bit Crusher']
native_names['resonance_filter'] = ['0b44f1c343a1de4ab108069e3ec0f7e4', 'ZPlane', 'Resonance Filter']
native_names['compressor_expander'] = ['1158f6956478e749a123534b7d943e3d', 'ZPlane', 'Compressor/Expander']
native_names['noise_gate'] = ['ee2b5cce1faeb54f9081ad2575736075', 'ZPlane', 'Noise Gate']
native_names['limiter'] = ['80700b7cbbf6234189e21d862baf0d19', 'ZPlane', 'Limiter']

def calc_lattime(latency_offset):
	return int(latency_offset*(PROJECT_FREQ/500))

def calc_vol(vol):
	vol = vol**(1/4)
	vol = (vol*0.824999988079071)
	return vol
	
def set_params(params_obj):
	mute = 0.5 if params_obj.get('enabled', True).value else 1
	vol = calc_vol(params_obj.get('vol', 1).value)
	pan = params_obj.get('pan', 0).value/2 + 0.5
	return soundbridge_func.encode_chunk(struct.pack('>ffff', *(mute, vol, vol, pan)))

def make_group(convproj_obj, groupid, groups_data, sb_maintrack):
	from objects.file_proj import soundbridge as proj_soundbridge
	if groupid not in groups_data:
		group_obj = convproj_obj.fx__group__get(groupid)
		if group_obj:
			sb_grouptrack = proj_soundbridge.soundbridge_track(None)
			sb_grouptrack.latencyOffset = calc_lattime(group_obj.latency_offset)
			do_markers(group_obj.timemarkers, sb_grouptrack.markers)
			make_plugins_fx(convproj_obj, sb_grouptrack, group_obj.plugslots)
			make_sends(convproj_obj, sb_grouptrack, group_obj.sends)
			sb_grouptrack.type = 1
			sb_grouptrack.state = set_params(group_obj.params)

			make_auto_contains_master(convproj_obj, sb_grouptrack, group_obj.params, ['group', groupid])

			sb_maintrack.tracks.append(sb_grouptrack)
			if group_obj.visual.name: sb_grouptrack.name = group_obj.visual.name
			sb_grouptrack.metadata["SequencerTrackCollapsedState"] = 8
			sb_grouptrack.metadata["SequencerTrackHeightState"] = 43
			if group_obj.visual.color: 
				sb_grouptrack.metadata["TrackColor"] = '#'+group_obj.visual.color.get_hex()
			else:
				sb_grouptrack.metadata["TrackColor"] = '#b0ff91'

			groups_data[groupid] = sb_grouptrack

sb_auto_dtype = np.dtype([('pos', '>I'), ('val', '>f'),('unk1', '>f'),('unk2', '>f')])

def make_auto(autopoints_obj, valtype, add, mul):
	autopoints_obj.sort()
	fixauto = []
	for a in autopoints_obj:
		if not fixauto: 
			fixauto.append(a)
		else:
			if fixauto[-1].pos != a.pos: fixauto.append(a)

	autoarray = np.zeros(len(fixauto), dtype=sb_auto_dtype)
	autoarray['unk1'] = 0.99
	autoarray['unk2'] = 1
	for n, a in enumerate(fixauto):
		autopos = int(max(a.pos, 0))

		autoarray[n]['pos'] = int(max(a.pos, 0))
		if a.tension: autoarray[n]['unk1'] = pow(10, -a.tension)

		if valtype == 'invert':
			autoarray[n]['val'] = 1-a.value
		elif valtype == 'vol':
			autoarray[n]['val'] = calc_vol(a.value)
		else:
			autoarray[n]['val'] = (a.value/mul)-add

	#print('O')
	#for x in autoarray:
	#	print(x)

	outbytes = b'\x00\x00\x00\x14'+autoarray.tobytes()
	padsize = 4*len(fixauto)
	outbytes += b'\x00'*padsize
	return soundbridge_func.encode_chunk(outbytes)

def make_auto_track(valtype, convproj_obj, autoloc, blocks, add, mul, trackmeta):
	from objects.file_proj import soundbridge as proj_soundbridge
	aid_found, aid_data = convproj_obj.automation.get(autoloc, 'float')

	if aid_found:
		if aid_data.pl_points:
			aid_data.pl_points.remove_loops([])
			for autopl_obj in aid_data.pl_points:
				autopl_obj.data.remove_instant()

				time_obj = autopl_obj.time

				block = proj_soundbridge.soundbridge_block(None)
				block.name = autopl_obj.visual.name if autopl_obj.visual.name else ""
				block.timeBaseMode = 0
				block.position = int(time_obj.position)
				block.positionStart = 0
				block.positionEnd = int(time_obj.duration+1)
				block.loopOffset = 0
				block.framesCount = int(time_obj.duration+1)
				block.loopEnabled = 0
				block.muted = 0
				block.version = 1

				if autopl_obj.time.cut_type == 'cut':
					block.positionStart = time_obj.cut_start
					block.loopOffset = time_obj.cut_start
					block.positionEnd += time_obj.cut_start
					block.loopOffset = max(block.loopOffset, 0)
					block.positionStart = max(block.positionStart, 0)

				if autopl_obj.visual.color:
					block.metadata["BlockColor"] = '#'+autopl_obj.visual.color.get_hex()
				elif 'TrackColor' in trackmeta:
					block.metadata["BlockColor"] = trackmeta["TrackColor"]

				block.blockData = make_auto(autopl_obj.data, valtype,add, mul)

				blocks.append(block)
			return True
		else: return False
	else: return False

def make_auto_contains_master(convproj_obj, sb_track, params_obj, startauto):
	from objects.file_proj import soundbridge as proj_soundbridge
	automationTracks = sb_track.automationContainer.automationTracks

	vol = calc_vol(params_obj.get('vol', 1).value)
	pan = params_obj.get('pan', 0).value/0.5 + 0.5

	automationTrack = proj_soundbridge.soundbridge_automationTrack(None)
	automationTrack.parameterIndex = 2
	automationTrack.mode = 3
	automationTrack.enabled = 1
	automationTrack.defaultValue = vol
	make_auto_track('vol', convproj_obj, startauto+['vol'], automationTrack.blocks, 0, 1, sb_track.metadata)
	automationTracks.append(automationTrack)

	automationTrack = proj_soundbridge.soundbridge_automationTrack(None)
	automationTrack.parameterIndex = 3
	automationTrack.mode = 3
	automationTrack.enabled = 1
	automationTrack.defaultValue = pan
	make_auto_track(None, convproj_obj, startauto+['pan'], automationTrack.blocks, -.5, 2, sb_track.metadata)
	automationTracks.append(automationTrack)

def make_auto_trackcontains(convproj_obj, sb_track, params_obj, n, startauto):
	from objects.file_proj import soundbridge as proj_soundbridge
	automationTracks = sb_track.automationContainer.automationTracks

	vol = calc_vol(params_obj.get('vol', 1).value)
	pan = params_obj.get('pan', 0).value/0.5 + 0.5

	automationTrack = proj_soundbridge.soundbridge_automationTrack(None)
	automationTrack.parameterIndex = 0
	automationTrack.mode = 3
	automationTrack.enabled = 1
	automationTrack.defaultValue = 0.5 if params_obj.get('enabled', True).value else 1
	automationTracks.append(automationTrack)

	if n == 0:
		automationTrack = proj_soundbridge.soundbridge_automationTrack(None)
		automationTrack.parameterIndex = 1
		automationTrack.mode = 3
		automationTrack.enabled = 1
		automationTrack.defaultValue = 0.5
		automationTracks.append(automationTrack)

	automationTrack = proj_soundbridge.soundbridge_automationTrack(None)
	automationTrack.parameterIndex = 2
	automationTrack.mode = 3
	automationTrack.enabled = 1
	automationTrack.defaultValue = vol
	make_auto_track('vol', convproj_obj, startauto+['vol'], automationTrack.blocks, 0, 1, sb_track.metadata)
	automationTracks.append(automationTrack)

	automationTrack = proj_soundbridge.soundbridge_automationTrack(None)
	automationTrack.parameterIndex = 3
	automationTrack.mode = 3
	automationTrack.enabled = 1
	automationTrack.defaultValue = pan
	make_auto_track(None, convproj_obj, startauto+['pan'], automationTrack.blocks, -.5, 2, sb_track.metadata)
	automationTracks.append(automationTrack)

def make_sends(convproj_obj, sb_track, sends_obj):
	from objects.file_proj import soundbridge as proj_soundbridge
	cur_returns = {}
	automationTracks = sb_track.sendsAutomationContainer.automationTracks

	values = []
	for n, x in enumerate(sb_returns):
		automationTrack = proj_soundbridge.soundbridge_automationTrack(None)
		automationTrack.parameterIndex = n
		automationTrack.mode = 3
		automationTrack.enabled = 1
		automationTrack.defaultValue = 0
		automationTrack.returnTrackPath = '/'+str(n)+'/R'
		automationTracks.append(automationTrack)
		cur_returns[x] = automationTrack
		values.append(0)

	for i, x in sends_obj.iter():
		if i in cur_returns:
			automationTrack = cur_returns[i]
			automationTrack.defaultValue = x.params.get('amount', 0).value
			if x.sendautoid: make_auto_track(None, convproj_obj, ['send', x.sendautoid, 'amount'], automationTrack.blocks, 0, 1, sb_track.metadata)
			values[sb_returns.index(i)] = automationTrack.defaultValue
		else:
			logger_output.warning('return id %s is missing! This might cause the DAW to crash.' % i)
	sb_track.sendsAutomationContainer.state = soundbridge_func.encode_chunk(struct.pack('>'+('f'*len(values)), *values))

def make_plugins_fx(convproj_obj, sb_track, plugslots):
	from objects.file_proj import soundbridge as proj_soundbridge
	sb_track.audioUnitsBypass = int(not plugslots.slots_audio_enabled)

	for pluginid in plugslots.slots_mixer:
		plugin_found, plugin_obj = convproj_obj.plugin__get(pluginid)
		if plugin_found:
			if plugin_obj.check_match('universal', 'invert', None):
				inverse_on, _ = plugin_obj.fxdata_get()
				sb_track.inverse = int(inverse_on)

	for pluginid in plugslots.slots_audio:
		plugin_found, plugin_obj = convproj_obj.plugin__get(pluginid)
		if plugin_found: 
			if plugin_obj.check_wildmatch('native', 'soundbridge', None):
				if plugin_obj.type.subtype in native_names:
					fx_on, fx_wet = plugin_obj.fxdata_get()
					uuid, vendor, name = native_names[plugin_obj.type.subtype]
					sb_plugin = proj_soundbridge.soundbridge_audioUnit(None)
					sb_plugin.uid = soundbridge_func.encode_chunk(bytearray.fromhex(uuid))
					sb_plugin.vendor = vendor
					sb_plugin.name = name

					automationTrack = proj_soundbridge.soundbridge_automationTrack(None)
					automationTrack.parameterIndex = 0
					automationTrack.mode = 3
					automationTrack.enabled = 1
					automationTrack.defaultValue = 0
					make_auto_track('invert', convproj_obj, ['slot', pluginid, 'enabled'], automationTrack.blocks, 0, 1, sb_track.metadata)
					sb_plugin.automationContainer.automationTracks.append(automationTrack)

					fldso = globalstore.dataset.get_obj('soundbridge', 'plugin', plugin_obj.type.subtype)
					if fldso:
						outbytes = plugin_obj.to_bytes('soundbridge', 'soundbridge', 'plugin', plugin_obj.type.subtype, plugin_obj.type.subtype)
						sb_plugin.state = soundbridge_func.encode_chunk(struct.pack('>f', int(not fx_on)) + outbytes)

						for n, x in fldso.params.iter():
							if x.num>0:
								automationTrack = proj_soundbridge.soundbridge_automationTrack(None)
								automationTrack.parameterIndex = x.num
								automationTrack.mode = 3
								automationTrack.enabled = 1
								automationTrack.defaultValue = 0
								if make_auto_track(None, convproj_obj, ['plugin', pluginid, n], automationTrack.blocks, 0, 1, sb_track.metadata):
									sb_plugin.automationContainer.automationTracks.append(automationTrack)

					sb_track.audioUnits.append(sb_plugin)

			if plugin_obj.check_wildmatch('external', 'vst2', None):
				auplug = make_vst2(convproj_obj, plugin_obj, False, pluginid, sb_track)
				if auplug:
					sb_track.audioUnits.append(auplug)
			if plugin_obj.check_wildmatch('external', 'vst3', None):
				auplug = make_vst3(convproj_obj, plugin_obj, False, pluginid, sb_track)
				if auplug:
					sb_track.audioUnits.append(auplug)

def make_vst3(convproj_obj, plugin_obj, issynth, pluginid, sb_track):
	from objects.file_proj import soundbridge as proj_soundbridge
	vid = plugin_obj.external_info.id
	sb_plugin = None

	if vid: 
		sb_plugin = proj_soundbridge.soundbridge_audioUnit(None)
		sb_plugin.uid = soundbridge_func.encode_chunk(uuid.UUID(vid).bytes_le)
		sb_plugin.name = plugin_obj.external_info.name
		sb_plugin.vendor = plugin_obj.external_info.creator
		if issynth: sb_plugin.metadata['AudioUnitType'] = 3

		rawdata = plugin_obj.rawdata_get('chunk')

		statewriter = bytewriter.bytewriter()
		statewriter.uint32(len(rawdata))
		statewriter.raw(b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
		statewriter.raw(rawdata)
		sb_plugin.state = soundbridge_func.encode_chunk(statewriter.getvalue())

		automationTrack = proj_soundbridge.soundbridge_automationTrack(None)
		automationTrack.parameterIndex = 0
		automationTrack.mode = 3
		automationTrack.enabled = 1
		automationTrack.defaultValue = 0
		make_auto_track('invert', convproj_obj, ['slot', pluginid, 'enabled'], automationTrack.blocks, 0, 1, sb_track.metadata)
		sb_plugin.automationContainer.automationTracks.append(automationTrack)

		for autoloc, autodata, paramnum in convproj_obj.automation.iter_pl_points_external(pluginid):
			paramid = 'ext_param_'+str(paramnum)
			automationTrack = proj_soundbridge.soundbridge_automationTrack(None)
			automationTrack.parameterIndex = paramnum+1
			automationTrack.mode = 3
			automationTrack.enabled = 1
			automationTrack.defaultValue = plugin_obj.params.get(paramid, 0)
			make_auto_track(None, convproj_obj, autoloc.get_list(), automationTrack.blocks, 0, 1, sb_track.metadata)
			sb_plugin.automationContainer.automationTracks.append(automationTrack)
	else:
		logger_output.warning('VST3 plugin not placed: no ID found.')

	return sb_plugin

def make_sampler(convproj_obj, plugin_obj):
	from objects.file_proj import soundbridge as proj_soundbridge
	fourid = plugin_obj.external_info.fourid
	sb_plugin = proj_soundbridge.soundbridge_audioUnit(None)
	sb_plugin.uid = soundbridge_func.encode_chunk(b'\xb7\xe4~\xd75\xc2\xa8H\x97JL\xe1\x82.\xc2^')
	sb_plugin.name = 'Sampler'
	sb_plugin.vendor = ''
	return sb_plugin

def make_vst2(convproj_obj, plugin_obj, issynth, pluginid, sb_track):
	from objects.file_proj import soundbridge as proj_soundbridge
	fourid = plugin_obj.external_info.fourid
	sb_plugin = None

	if fourid: 
		uid = b'\x00\x00\x00\x00SV2T'+struct.pack('>I', fourid)+b'\x00\x00\x00\x00'
		sb_plugin = proj_soundbridge.soundbridge_audioUnit(None)
		sb_plugin.uid = soundbridge_func.encode_chunk(uid)
		sb_plugin.name = plugin_obj.external_info.name
		sb_plugin.vendor = plugin_obj.external_info.creator
		if issynth: sb_plugin.metadata['AudioUnitType'] = 3

		extmanu_obj = plugin_obj.create_ext_manu_obj(convproj_obj, pluginid)
		vstchunk = extmanu_obj.vst2__export_presetdata(None)

		if len(vstchunk)>12:
			vsttype = vstchunk[8:12]

			fx_on, fx_wet = plugin_obj.fxdata_get()

			statewriter = bytewriter.bytewriter()
			statewriter.raw(b'CcnK')
			statewriter.raw(b'\x14\x00\x00\x00')
			statewriter.raw(b'\x00\x00\x00\x00')
			statewriter.float_b(int(not int(fx_on)))
			statewriter.uint32_b(plugin_obj.current_program)
			statewriter.raw(b'CcnK')
			statewriter.raw(b'\x00\x00\x00\x00')

			if vsttype == b'FBCh':
				statewriter.raw(b'FBCh')
				statewriter.raw(vstchunk[12:16])
				statewriter.raw(b'\x00\x00\x00\x00')
				statewriter.raw(b'\x00\x00\x00\x00')
				statewriter.raw(vstchunk[24:28])
				statewriter.raw(b'\x00'*128)
				statewriter.raw(vstchunk[56:])
			if vsttype == b'FPCh':
				statewriter.raw(b'FBCh')
				statewriter.raw(vstchunk[12:16])
				statewriter.raw(b'\x00\x00\x00\x00')
				statewriter.raw(b'\x00\x00\x00\x00')
				statewriter.raw(vstchunk[24:28])
				statewriter.raw(b'\x00'*128)
				statewriter.raw(vstchunk[56:])
			if vsttype == b'FxBk':
				statewriter.raw(b'FxBk')
				statewriter.raw(vstchunk[12:16])
				statewriter.raw(b'\x00\x00\x00\x00')
				statewriter.raw(b'\x00\x00\x00\x00')
				statewriter.raw(vstchunk[24:28])
				statewriter.raw(b'\x00'*128)
				statewriter.raw(vstchunk)
			if vsttype == b'FxCk':
				statewriter.raw(b'FxBk')
				statewriter.raw(vstchunk[12:16])
				statewriter.raw(b'\x00\x00\x00\x00')
				statewriter.raw(b'\x00\x00\x00\x00')
				statewriter.raw(vstchunk[24:28])
				statewriter.raw(b'\x00'*128)
				statewriter.raw(vstchunk)

		state = statewriter.getvalue()

		sb_plugin.state = soundbridge_func.encode_chunk(state)

		automationTrack = proj_soundbridge.soundbridge_automationTrack(None)
		automationTrack.parameterIndex = 0
		automationTrack.mode = 3
		automationTrack.enabled = 1
		automationTrack.defaultValue = 0
		make_auto_track('invert', convproj_obj, ['slot', pluginid, 'enabled'], automationTrack.blocks, 0, 1, sb_track.metadata)
		sb_plugin.automationContainer.automationTracks.append(automationTrack)

		for autoloc, autodata, paramnum in convproj_obj.automation.iter_pl_points_external(pluginid):
			paramid = 'ext_param_'+str(paramnum)
			automationTrack = proj_soundbridge.soundbridge_automationTrack(None)
			automationTrack.parameterIndex = paramnum+1
			automationTrack.mode = 3
			automationTrack.enabled = 1
			automationTrack.defaultValue = plugin_obj.params.get(paramid, 0)
			make_auto_track(None, convproj_obj, autoloc.get_list(), automationTrack.blocks, 0, 1, sb_track.metadata)
			sb_plugin.automationContainer.automationTracks.append(automationTrack)
	else:
		logger_output.warning('VST2 plugin not placed: no ID found.')

	return sb_plugin

def time_add(event, time_obj, otherblock):

	loop_1, loop_2, loop_3 = time_obj.get_loop_data()

	while loop_1<0:
		loop_1 += loop_3

	if time_obj.cut_type == 'cut':
		event.positionStart = time_obj.cut_start
		event.loopOffset = 0
		event.positionEnd = int(event.framesCount-time_obj.cut_start)
		event.loopOffset = int(max(event.loopOffset, 0))
		event.positionStart = int(max(event.positionStart, 0))
		event.positionEnd = int(time_obj.duration+event.positionStart)
		if otherblock:
			otherblock.framesCount = int(time_obj.duration+event.positionStart)
		
	elif time_obj.cut_type in ['loop', 'loop_eq']:
		event.positionStart = int(loop_1)
		event.loopOffset = int(loop_2)
		event.positionEnd = int(loop_3)
		event.loopEnabled = 1
		event.loopOffset = int(max(event.loopOffset, 0))
		event.positionStart = int(max(event.positionStart, 0))

	elif time_obj.cut_type == 'loop_off':
		event.loopOffset = int(loop_1)
		event.positionStart = int(loop_2)
		event.positionEnd = int(loop_3)
		event.loopEnabled = 1
		event.loopOffset = int(max(event.loopOffset, 0))
		event.positionStart = int(max(event.positionStart, 0))

def add_tempo_section(sb_tempo_obj, position, length, startTempo, endTempo):
	from objects.file_proj import soundbridge as proj_soundbridge
	temposection = proj_soundbridge.soundbridge_tempo_section(None)
	temposection.position = position
	temposection.length = length
	temposection.startTempo = startTempo
	temposection.endTempo = endTempo
	sb_tempo_obj.sections.append(temposection)

def do_markers(timemarkers_obj, sb_markers):
	from objects.file_proj import soundbridge as proj_soundbridge
	for num, timemarker_obj in enumerate(timemarkers_obj):
		sb_marker = proj_soundbridge.soundbridge_marker(None)
		sb_marker.label = timemarker_obj.visual.name if timemarker_obj.visual.name else ''
		sb_marker.comment = timemarker_obj.visual.comment if timemarker_obj.visual.comment else ''
		if timemarker_obj.visual.color:
			sb_marker.tag = '#'+timemarker_obj.visual.color.get_hex()
		sb_marker.position = timemarker_obj.position
		sb_marker.linearTimeBase = 0
		sb_markers.append(sb_marker)

def sampler_do_filter(sampler_entry, sample_params, filter_obj):
	from objects.file_proj._soundbridge import mathalgo
	sample_params.filter_freq = mathalgo.freq__to_one(filter_obj.freq)
	sample_params.filter_res = filter_obj.q

	if filter_obj.on:
		filtertype = filter_obj.type
		i_type = filtertype.type
		if i_type == 'low_pass': sampler_entry.filter_type = 1
		if i_type == 'high_pass': sampler_entry.filter_type = 2
		if i_type == 'band_pass': sampler_entry.filter_type = 3
		if i_type == 'notch': sampler_entry.filter_type = 4

class output_soundbridge(plugins.base):
	def is_dawvert_plugin(self):
		return 'output'
	
	def get_shortname(self):
		return 'soundbridge'
	
	def get_name(self):
		return 'SoundBridge'
	
	def gettype(self):
		return 'r'
	
	def get_prop(self, in_dict): 
		in_dict['audio_filetypes'] = ['wav']
		in_dict['audio_stretch'] = ['warp']
		in_dict['auto_types'] = ['pl_points']
		in_dict['file_ext'] = 'soundbridge'
		in_dict['fxtype'] = 'groupreturn'
		in_dict['placement_cut'] = True
		in_dict['placement_loop'] = ['loop', 'loop_off', 'loop_eq']
		in_dict['plugin_ext'] = ['vst2', 'vst3']
		in_dict['plugin_ext_arch'] = [64]
		in_dict['plugin_ext_platforms'] = ['win']
		in_dict['plugin_included'] = ['native:soundbridge','universal:invert']
		in_dict['projtype'] = 'r'
	
	def parse(self, convproj_obj, dawvert_intent):
		from objects.file_proj import soundbridge as proj_soundbridge
		from objects.file_proj._soundbridge import sampler
		global sb_returns

		convproj_obj.change_timings(PROJECT_FREQ, False)

		project_obj = proj_soundbridge.soundbridge_song()
		project_obj.masterTrack.defualts_master()
		project_obj.pool.defualts()
		project_obj.videoTrack.defualts()
		project_obj.sampleRate = PROJECT_FREQ*2

		globalstore.datadef.load('soundbridge', './data_main/datadef/soundbridge.ddef')
		globalstore.dataset.load('soundbridge', './data_main/dataset/soundbridge.dset')

		if convproj_obj.metadata.name is not None:
			project_obj.name = convproj_obj.metadata.name

		tempo = convproj_obj.params.get('bpm', 120).value

		sb_timeSignature = project_obj.timeline.timeSignature
		sb_tempo = project_obj.timeline.tempo

		sb_timeSignature.timeSigNumerator = convproj_obj.timesig[0]
		sb_timeSignature.timeSigDenominator = convproj_obj.timesig[1]
		project_obj.tempo = tempo
		sb_tempo.tempo = tempo

		master_track = convproj_obj.track_master

		make_plugins_fx(convproj_obj, project_obj.masterTrack, convproj_obj.track_master.plugslots)

		if master_track.visual.color: project_obj.masterTrack.metadata["TrackColor"] = '#'+master_track.visual.color.get_hex()
		if master_track.visual.name: project_obj.masterTrack.name = master_track.visual.name

		project_obj.masterTrack.latencyOffset = calc_lattime(master_track.latency_offset)
		project_obj.masterTrack.state = set_params(master_track.params)
		make_auto_contains_master(convproj_obj, project_obj.masterTrack, master_track.params, ['master'])

		master_returns = master_track.returns

		sb_returns = [x for x in master_track.returns]

		audio_ids = {}
		video_ids = {}
		
		#convproj_obj.sampleref__remove_nonaudiopl()

		for sampleref_id, sampleref_obj in convproj_obj.sampleref__iter():
			if sampleref_obj.fileref.exists(None):
				obj_filename = sampleref_obj.fileref.get_path(None, False)
				obj_outfilename = sampleref_obj.fileref.copy()
				obj_outfilename.file.extension = 'wav'

				if dawvert_intent.output_mode == 'file':
					filename = str(obj_filename)
					outfilename = os.path.join(dawvert_intent.output_file, str(obj_outfilename.file))
					if sampleref_obj.found:
						sampleref_obj.copy_resample(None, outfilename)
					else:
						sampleref_obj.set_path(None, outfilename)

				audio_ids[sampleref_id] = sampleref_obj.fileref.file

				audioSource = proj_soundbridge.soundbridge_audioSource(None)
				audioSource.fileName = str(obj_outfilename.file)
				audioSource.sourceFileName = filename.replace('\\', '/')
				project_obj.pool.audioSources.append(audioSource)

		for fileref_id, fileref_obj in convproj_obj.fileref__iter():
			if fileref_obj.file.extension in ['mp4','mpeg','avi','mpg','mkv']:
				obj_filename = fileref_obj.get_path('win', False)
				obj_outfilename = fileref_obj.copy()

				if dawvert_intent.output_mode == 'file':
					filename = str(obj_filename)
					outfilename = os.path.join(dawvert_intent.output_file, str(obj_outfilename.file))

				video_ids[fileref_id] = fileref_obj.file
				if fileref_obj.exists(None):
					videoSource = proj_soundbridge.soundbridge_videoSource(None)
					videoSource.fileName = str(obj_outfilename.file)
					videoSource.sourceFileName = filename.replace('\\', '/')
					project_obj.pool.videoSources.append(videoSource)

		groups_data = {}
		for groupid, insidegroup in convproj_obj.group__iter_inside():
			sb_tracks = project_obj.masterTrack

			if insidegroup: 
				make_group(convproj_obj, groupid, groups_data, groups_data[insidegroup])
			else: 
				make_group(convproj_obj, groupid, groups_data, sb_tracks)

		videotrack_obj = None

		for trackid, track_obj in convproj_obj.track__iter():
			sb_tracks = project_obj.masterTrack.tracks

			if track_obj.type == 'video':
				if not videotrack_obj: videotrack_obj = track_obj

			if track_obj.group: sb_tracks = groups_data[track_obj.group].tracks

			sb_track = None

			if track_obj.type == 'instrument':
				sb_track = proj_soundbridge.soundbridge_track(None)
				sb_track.state = set_params(track_obj.params)
				if track_obj.visual.name: sb_track.name = track_obj.visual.name
				if track_obj.visual.color: sb_track.metadata["TrackColor"] = '#'+track_obj.visual.color.get_hex()
				sb_track.midiInput = proj_soundbridge.soundbridge_deviceRoute(None)
				sb_track.midiInput.externalDeviceIndex = 0
				sb_track.midiInput.channelIndex = track_obj.midi.in_chanport.chan-1
				sb_track.midiOutput = proj_soundbridge.soundbridge_deviceRoute(None)
				sb_track.midiOutput.externalDeviceIndex = -1
				sb_track.midiOutput.channelIndex = track_obj.midi.out_chanport.chan-1
				sb_track.blocks = []
				sb_track.latencyOffset = calc_lattime(track_obj.latency_offset)

				sb_track.armed = int(track_obj.armed.in_keys)

				make_auto_trackcontains(convproj_obj, sb_track, track_obj.params, 0, ['track', trackid])
				make_sends(convproj_obj, sb_track, track_obj.sends)
				make_plugins_fx(convproj_obj, sb_track, track_obj.plugslots)

				middlenote = track_obj.datavals.get('middlenote', 0)

				is_sampler = False

				if track_obj.plugslots.synth:
					plugin_found, plugin_obj = convproj_obj.plugin__get(track_obj.plugslots.synth)
					if plugin_found: 
						pitch = track_obj.params.get('pitch',0).value

						if plugin_obj.check_wildmatch('external', 'vst2', None):
							sb_track.midiInstrument = make_vst2(convproj_obj, plugin_obj, True, track_obj.plugslots.synth, sb_track)
						if plugin_obj.check_wildmatch('external', 'vst3', None):
							sb_track.midiInstrument = make_vst3(convproj_obj, plugin_obj, True, track_obj.plugslots.synth, sb_track)
						if plugin_obj.check_match('universal', 'sampler', 'single'):
							is_sampler = True
							sp_obj = plugin_obj.samplepart_get('sample')
							if sp_obj.sampleref in audio_ids:
								sb_id = audio_ids[sp_obj.sampleref]
								isfound, sampleref_obj = convproj_obj.sampleref__get(sp_obj.sampleref)
	
								hzchange = (PROJECT_FREQ*2)/sampleref_obj.hz if sampleref_obj.hz else 1

								sp_obj.convpoints_samples(sampleref_obj)

								if isfound:
									filter_obj = plugin_obj.filter
									sb_plugin = sb_track.midiInstrument = make_sampler(convproj_obj, plugin_obj)
									statewriter = bytewriter.bytewriter()
									sampler_data = sampler.soundbridge_sampler_main()
									sampler_d = sampler_data.add_single()
									if sampler_d:
										sampler_entry, sample_params = sampler_d
										sampler_entry.filename = str(sb_id)
										sampler_entry.name = sp_obj.visual.name if sp_obj.visual.name else str(sb_id.filename)
										if sp_obj.visual.color: sampler_entry.metadata['SampleColor'] = '#'+sp_obj.visual.color.get_hex()
										elif plugin_obj.visual.color: sampler_entry.metadata['SampleColor'] = '#'+plugin_obj.visual.color.get_hex()
										sampler_entry.start = int(sp_obj.start*hzchange)
										sampler_entry.end = int(sp_obj.end*hzchange)
										sampler_entry.env_amp_on = int(sp_obj.trigger != 'oneshot')
										sample_params.vol_vel = 1
										sample_params.key_root = (middlenote)+60
										sample_params.env_a = 0
										sample_params.env_d = 0
										sample_params.env_s = 1
										sample_params.env_r = 0
										sample_params.pitch_semi = pitch.__floor__()*0.5
										sample_params.pitch_cent = (pitch%1)*100
										if 'vel_sens' in sp_obj.data:
											sample_params.vol_vel = sp_obj.data['vel_sens']
										sampler_do_filter(sampler_entry, sample_params, filter_obj)

									sampler_data.write(statewriter)
									sb_plugin.state = soundbridge_func.encode_chunk(statewriter.getvalue())

						if plugin_obj.check_match('universal', 'sampler', 'drums'):
							sb_plugin = sb_track.midiInstrument = make_sampler(convproj_obj, plugin_obj)
							statewriter = bytewriter.bytewriter()
							sampler_data = sampler.soundbridge_sampler_main()
							sampler_data.sampler_mode = 1

							is_sampler = True
							ordernum = 0
							for spn, sampleregion in enumerate(plugin_obj.sampleregions):
								key_l, key_h, key_r, samplerefid, extradata = sampleregion
								sp_obj = plugin_obj.samplepart_get(samplerefid)

								if sp_obj.sampleref in audio_ids:
									sb_id = audio_ids[sp_obj.sampleref]
									isfound, sampleref_obj = convproj_obj.sampleref__get(sp_obj.sampleref)
									hzchange = (PROJECT_FREQ*2)/sampleref_obj.hz if sampleref_obj.hz else 1
									sp_obj.convpoints_samples(sampleref_obj)
 
									if isfound:
										sampler_d = sampler_data.add_single()
										if sampler_d:
											sampler_entry, sample_params = sampler_d
											sampler_entry.filename = str(sb_id)
											sampler_entry.name = sp_obj.visual.name if sp_obj.visual.name else str(sb_id.filename)
											sampler_entry.start = int(sp_obj.start*hzchange)
											sampler_entry.end = int(sp_obj.end*hzchange)
											sampler_entry.order = ordernum
											sample_params.vol_vel = 1
											sample_params.key_root = (middlenote)+60
											sample_params.key_root = 60+key_r
											sample_params.key_min = 60+key_l
											sample_params.key_max = 60+key_h
											sample_params.vel_min = int(sp_obj.vel_min*127)
											sample_params.vel_max = int(sp_obj.vel_max*127)
											sample_params.pitch_semi = sp_obj.pitch.__floor__()*0.5
											sample_params.pitch_cent = (sp_obj.pitch%1)*100
											if 'vel_sens' in sp_obj.data:
												sample_params.vol_vel = sp_obj.data['vel_sens']
										ordernum += 1

							sampler_data.write(statewriter)
							sb_plugin.state = soundbridge_func.encode_chunk(statewriter.getvalue())

						if plugin_obj.check_match('universal', 'sampler', 'multi'):
							sb_plugin = sb_track.midiInstrument = make_sampler(convproj_obj, plugin_obj)
							statewriter = bytewriter.bytewriter()
							sampler_data = sampler.soundbridge_sampler_main()

							multi_mode = plugin_obj.datavals.get('multi_mode', 'all')
							if multi_mode == 'all': sampler_data.sampler_mode = 1
							elif multi_mode == 'random': sampler_data.sampler_mode = 2
							elif multi_mode == 'forward': sampler_data.sampler_mode = 3
							elif multi_mode == 'backward': sampler_data.sampler_mode = 4
							elif multi_mode == 'forward_backward': sampler_data.sampler_mode = 5
							else: sampler_data.sampler_mode = 1

							is_sampler = True
							ordernum = 0
							for spn, sampleregion in enumerate(plugin_obj.sampleregions):
								key_l, key_h, key_r, samplerefid, extradata = sampleregion
								sp_obj = plugin_obj.samplepart_get(samplerefid)

								if sp_obj.sampleref in audio_ids:
									sb_id = audio_ids[sp_obj.sampleref]
									isfound, sampleref_obj = convproj_obj.sampleref__get(sp_obj.sampleref)
									hzchange = (PROJECT_FREQ*2)/sampleref_obj.hz if sampleref_obj.hz else 1
									sp_obj.convpoints_samples(sampleref_obj)
 
									if isfound:
										sampler_d = sampler_data.add_single()
										if sampler_d:
											sampler_entry, sample_params = sampler_d
											sampler_entry.filename = str(sb_id)
											sampler_entry.name = sp_obj.visual.name if sp_obj.visual.name else str(sb_id.filename)
											sampler_entry.start = int(sp_obj.start*hzchange)
											sampler_entry.end = int(sp_obj.end*hzchange)
											sampler_entry.env_amp_on = int(sp_obj.trigger != 'oneshot')
											sampler_entry.order = ordernum
											sample_params.vol_vel = 1
											sample_params.key_root = (middlenote)+60
											sample_params.env_a = 0
											sample_params.env_d = 0
											sample_params.env_s = 1
											sample_params.env_r = 0
											sample_params.key_root = 60+key_r
											sample_params.key_min = 60+key_l
											sample_params.key_max = 60+key_h
											sample_params.vel_min = int(sp_obj.vel_min*127)
											sample_params.vel_max = int(sp_obj.vel_max*127)
											sample_params.pitch_semi = sp_obj.pitch.__floor__()*0.5
											sample_params.pitch_cent = (sp_obj.pitch%1)*100
											filt_exists, filt_obj = plugin_obj.named_filter_get_exists(sp_obj.filter_assoc)
											if filt_exists:
												sampler_do_filter(sampler_entry, sample_params, filt_obj)
											if 'vel_sens' in sp_obj.data:
												sample_params.vol_vel = sp_obj.data['vel_sens']
										ordernum += 1

							sampler_data.write(statewriter)
							sb_plugin.state = soundbridge_func.encode_chunk(statewriter.getvalue())

						if plugin_obj.check_match('universal', 'sampler', 'slicer'):
							is_sampler = True
							sp_obj = plugin_obj.samplepart_get('sample')
							if sp_obj.sampleref in audio_ids:
								sb_id = audio_ids[sp_obj.sampleref]
								isfound, sampleref_obj = convproj_obj.sampleref__get(sp_obj.sampleref)
								hzchange = (PROJECT_FREQ*2)/sampleref_obj.hz if sampleref_obj.hz else 1
								sp_obj.convpoints_samples(sampleref_obj)

								if isfound:
									sb_plugin = sb_track.midiInstrument = make_sampler(convproj_obj, plugin_obj)
									statewriter = bytewriter.bytewriter()
									sampler_data = sampler.soundbridge_sampler_main()
									
									data = sampler_data.add_slices(len(sp_obj.slicer_slices))
									if data:
										sampler_entry, slicedata = data
										sampler_entry.filename = str(sb_id)
										sampler_entry.name = sp_obj.visual.name if sp_obj.visual.name else str(sb_id.filename)
										if sp_obj.visual.color: sampler_entry.metadata['SampleColor'] = '#'+sp_obj.visual.color.get_hex()
										elif plugin_obj.visual.color: sampler_entry.metadata['SampleColor'] = '#'+plugin_obj.visual.color.get_hex()
										sampler_entry.start = int(sp_obj.start*hzchange)
										sampler_entry.end = int(sp_obj.end*hzchange)
										sampler_entry.env_amp_on = 1
										for num, sld in enumerate(slicedata):
											slice_obj = sp_obj.slicer_slices[num]
											sample_params = sld[1]
											sample_params.vol_vel = 1
											sample_params.env_a = 0
											sample_params.env_d = 0
											sample_params.env_s = 1
											sample_params.env_r = 0
											if not slice_obj.is_custom_key:
												sample_params.key_root = 60+num
												sample_params.key_min = 60+num
												sample_params.key_max = 60+num
											else:
												sample_params.key_root = 60+slice_obj.custom_key
												sample_params.key_min = 60+slice_obj.custom_key
												sample_params.key_max = 60+slice_obj.custom_key
											sampler_entry.slices[num][1] = int(slice_obj.start*hzchange)
									sampler_data.write(statewriter)
									sb_plugin.state = soundbridge_func.encode_chunk(statewriter.getvalue())

				plugin_found, plugin_obj = convproj_obj.plugin__get(track_obj.plugslots.synth)
				if plugin_found: middlenote += plugin_obj.datavals_global.get('middlenotefix', 0)

				for notespl_obj in track_obj.placements.pl_notes:
					if not is_sampler: notespl_obj.notelist.mod_transpose(-middlenote)
					notespl_obj.notelist.mod_limit(-60, 67)
					numnotes = notespl_obj.notelist.count()
					notearray = np.zeros(numnotes, dtype=sb_notes_dtype)

					block = proj_soundbridge.soundbridge_block(None)
					if notespl_obj.visual.name: block.name = notespl_obj.visual.name
					block.timeBaseMode = 0
					block.position = notespl_obj.time.position
					block.positionStart = 0
					block.positionEnd = notespl_obj.time.duration
					block.loopOffset = 0
					block.framesCount = notespl_obj.time.duration
					block.loopEnabled = 0
					block.muted = int(notespl_obj.muted)

					time_add(block, notespl_obj.time, None)

					numnote = 0
					for t_pos, t_dur, t_keys, t_vol, t_inst, t_extra, t_auto, t_slide in notespl_obj.notelist.iter():
						for t_key in t_keys:
							notearray[numnote]['id'] = numnote
							notearray[numnote]['pos'] = t_pos
							notearray[numnote]['dur'] = t_dur
							notearray[numnote]['key'] = t_key+60
							notearray[numnote]['vol'] = int(min(t_vol*127, 127))
							numnote += 1

					if notespl_obj.visual.color: 
						block.metadata["BlockColor"] = '#'+notespl_obj.visual.color.get_hex()

					datasize = sb_notes_dtype.itemsize*numnotes

					outbytes = b'\x00\x00\x00\x14'+notearray.tobytes()
					padsize = 4*numnotes
					outbytes += b'\x00'*padsize

					block.blockData = soundbridge_func.encode_chunk(outbytes)
					block.automationBlocks = []

					for n, x in notespl_obj.auto.items():

						autonum = None
						valmul = 1
						valadd = 0

						if n == 'midi_pressure': 
							autonum = 0
							valmul = 127
						if n == 'midi_pitch': 
							autonum = 1
							valmul = 8192*2
							valadd = -0.5
						if n.startswith('midi_cc_'): 
							autonum = int(n[8:])+1
							valmul = 127

						if autonum is not None:
							autoblock = proj_soundbridge.soundbridge_block(None)
							autoblock.index = autonum
							autoblock.name = ""
							autoblock.timeBaseMode = 0
							autoblock.position = 0
							autoblock.positionStart = block.positionStart
							autoblock.positionEnd = block.positionEnd
							autoblock.loopOffset = block.loopOffset
							autoblock.framesCount = block.framesCount
							autoblock.loopEnabled = block.loopEnabled
							autoblock.muted = 0
							autoblock.version = 1
							autoblock.blockData = make_auto(x, None, valadd, valmul)

							block.automationBlocks.append(autoblock)

					sb_track.blocks.append(block)

				sb_track.midiUnits = []
				sb_track.type = 4

			if track_obj.type == 'audio':
				sb_track = proj_soundbridge.soundbridge_track(None)
				sb_track.state = set_params(track_obj.params)
				if track_obj.visual.name: sb_track.name = track_obj.visual.name
				if track_obj.visual.color: sb_track.metadata["TrackColor"] = '#'+track_obj.visual.color.get_hex()
				sb_track.type = 3
				sb_track.channelCount = 2
				sb_track.pitchTempoProcessorMode = 2
				sb_track.audioInput = proj_soundbridge.soundbridge_deviceRoute(None)
				sb_track.blockContainers = []
				sb_track.latencyOffset = calc_lattime(track_obj.latency_offset)

				sb_track.armed = int(track_obj.armed.in_audio)
				
				make_auto_trackcontains(convproj_obj, sb_track, track_obj.params, 0, ['track', trackid])
				make_sends(convproj_obj, sb_track, track_obj.sends)
				make_plugins_fx(convproj_obj, sb_track, track_obj.plugslots)

				blockContainer = proj_soundbridge.soundbridge_blockContainer(None)

				stretchrep = {}

				for audiopl_obj in track_obj.placements.pl_audio:
					block = proj_soundbridge.soundbridge_block(None)

					if audiopl_obj.visual.name: blockContainer.name = audiopl_obj.visual.name
					if audiopl_obj.visual.name: block.name = audiopl_obj.visual.name

					block.position = audiopl_obj.time.position
					block.framesCount = audiopl_obj.time.duration
					block.muted = int(audiopl_obj.muted)
					block.timeBaseMode = 0

					if audiopl_obj.visual.color: 
						block.metadata["BlockColor"] = '#'+audiopl_obj.visual.color.get_hex()

					block.crossfades = []
					block.events = []

					sp_obj = audiopl_obj.sample
					ref_found, sampleref_obj = convproj_obj.sampleref__get(sp_obj.sampleref)

					if ref_found:
						if sampleref_obj.found:
							stretch_obj = audiopl_obj.sample.stretch

							pitchTempoProcessorMode = 2

							if stretch_obj.algorithm == 'elastique_v3':
								if stretch_obj.algorithm_mode in ['mono', 'speech']:
									pitchTempoProcessorMode = 0

							if stretch_obj.algorithm == 'elastique_v2':
								if stretch_obj.algorithm_mode in ['mono', 'speech']:
									pitchTempoProcessorMode = 0

							if stretch_obj.algorithm == 'soundtouch':
								pitchTempoProcessorMode = 4

							if pitchTempoProcessorMode not in stretchrep: stretchrep[pitchTempoProcessorMode] = 0
							stretchrep[pitchTempoProcessorMode] += 1

							warp_obj = stretch_obj.warp

							warp_obj.points__add__based_beat(0)
							warp_obj.fix__last()
							warp_obj.fix__fill()
							warp_obj.fix__round()

							warp_obj.fixpl__offset(audiopl_obj.time, PROJECT_FREQ)

							warp_obj.fix__alwaysplus()
							warp_obj.fix__remove_dupe_sec()
							warp_obj.fix__sort()

							#warp_obj.debugtxt_warp()

							event = proj_soundbridge.soundbridge_event(None)
							event.position = 0
							event.positionStart = 0
							event.positionEnd = int(audiopl_obj.time.duration)
							event.loopOffset = 0
							event.framesCount = int(audiopl_obj.time.duration)
							event.loopEnabled = 0
							event.tempo = 120
							event.inverse = 0
							event.gain = xtramath.to_db(sp_obj.vol)
							event.fadeInLength = int(audiopl_obj.fade_in.get_dur_beat(tempo)*PROJECT_FREQ)
							event.fadeOutLength = int(audiopl_obj.fade_out.get_dur_beat(tempo)*PROJECT_FREQ)
							event.fadeInCurve = 4
							event.fadeOutCurve = 4
							event.fadeInConvexity = 0.5
							event.fadeOutConvexity = 0.5
							event.pitch = pow(2, sp_obj.pitch/12)
							event.fileName = audio_ids[sp_obj.sampleref]

							time_add(event, audiopl_obj.time, block)

							event.stretchMarks = []

							event.positionStart = int(event.positionStart)
							event.loopOffset = int(event.loopOffset)
							event.positionEnd = int(event.positionEnd)

							warppoints = {}

							halfrate = project_obj.sampleRate/2

							for warp_point_obj in warp_obj.points__iter():
								newPosition = warp_point_obj.beat
								initPosition = warp_point_obj.second

								initPosition *= halfrate
								newPosition *= halfrate
	
								initPosition = int(initPosition)
								newPosition = int(newPosition)

								warppoints[initPosition] = newPosition

							if len(warppoints)>2:
								if 0 not in warppoints:
									firstpos = list(warppoints)[0]
									warppoints = dict([[x-firstpos, y-firstpos] for x, y in warppoints.items()])
									#secondpoint = warppoints[pointlist[1]]
									#warppoints[0] = warppoints

							for initPosition, newPosition in warppoints.items():

								#print([initPosition, newPosition], end=' ')

								stretchMark = proj_soundbridge.soundbridge_stretchMark(None)
								stretchMark.initPosition = initPosition*2
								stretchMark.newPosition = newPosition
								event.stretchMarks.append(stretchMark)
							#print()

							for n, x in audiopl_obj.auto.items():
								if n == 'gain':
									autoblock = proj_soundbridge.soundbridge_block(None)
									autoblock.index = 0
									autoblock.name = ""
									autoblock.timeBaseMode = 0
									autoblock.position = 0
									autoblock.positionStart = event.positionStart
									autoblock.positionEnd = event.positionEnd
									autoblock.loopOffset = event.loopOffset
									autoblock.framesCount = event.framesCount
									autoblock.loopEnabled = event.loopEnabled
									autoblock.muted = 0
									autoblock.version = 1
									autoblock.blockData = make_auto(x, None, 0, 2)
									event.automationBlocks.append(autoblock)
							block.events.append(event)
						else:
							logger_output.warning('clip is not placed - file missing: '+str(sampleref_obj.fileref.get_path('win', False)))
						blockContainer.blocks.append(block)
					else:
						clipsnotplaced += 1

				if stretchrep:
					stretchrep = sorted(stretchrep.items(), key=lambda item: item[1])
					sb_track.pitchTempoProcessorMode = stretchrep[0][0]

				sb_track.blockContainers.append(blockContainer)

			if sb_track:
				sb_tracks.append(sb_track)

		sb_tracks = project_obj.masterTrack.tracks
		for returnid, return_obj in master_returns.items():
			sb_track = proj_soundbridge.soundbridge_track(None)
			sb_track.state = set_params(track_obj.params)
			if return_obj.visual.name: sb_track.name = return_obj.visual.name
			if return_obj.visual.color: sb_track.metadata["TrackColor"] = '#'+return_obj.visual.color.get_hex()
			sb_track.type = 2
			sb_track.sourceBufferType = 2
			sb_track.audioOutput = proj_soundbridge.soundbridge_deviceRoute(None)
			sb_track.blockContainers = []
			sb_track.latencyOffset = calc_lattime(track_obj.latency_offset)
			make_auto_trackcontains(convproj_obj, sb_track, return_obj.params, 1, ['return', returnid])
			make_sends(convproj_obj, sb_track, return_obj.sends)
			make_plugins_fx(convproj_obj, sb_track, return_obj.plugslots)
			sb_tracks.append(sb_track)

		sb_videotrack = project_obj.videoTrack

		if videotrack_obj:
			if videotrack_obj.visual.color: 
				sb_videotrack.metadata["Color"] = '#'+videotrack_obj.visual.color.get_hex()

			for videopl_obj in videotrack_obj.placements.pl_video:
				time_obj = videopl_obj.time

				block = proj_soundbridge.soundbridge_block(None)
				block.name = videopl_obj.visual.name if videopl_obj.visual.name else ""
				if videopl_obj.visual.color:
					block.metadata["BlockColor"] = '#'+videopl_obj.visual.color.get_hex()
				block.timeBaseMode = 1
				block.position = int(time_obj.position)
				block.positionStart = 0
				block.positionEnd = int(time_obj.duration+1)
				block.loopOffset = 0
				block.framesCount = int(time_obj.duration+1)
				block.loopEnabled = 0
				block.muted = int(videopl_obj.muted)
				block.filename = video_ids[videopl_obj.video_fileref]

				#if videopl_obj.time.cut_type == 'cut':
				#	block.positionStart = time_obj.cut_start
				#	block.loopOffset = time_obj.cut_start
				#	block.positionEnd += time_obj.cut_start
				#	block.loopOffset = max(block.loopOffset, 0)
				#	block.positionStart = max(block.positionStart, 0)

				block.stretchMarks = []
				stretchMark = proj_soundbridge.soundbridge_stretchMark(None)
				block.stretchMarks.append(stretchMark)

				stretchMark = proj_soundbridge.soundbridge_stretchMark(None)
				stretchMark.initPosition = int(block.framesCount*(120/tempo))
				stretchMark.newPosition = block.framesCount
				block.stretchMarks.append(stretchMark)

				sb_videotrack.blocks.append(block)

		aid_found, aid_data = convproj_obj.automation.get(['main', 'bpm'], 'float')
		if aid_found:
			aid_data.convert____pl_points__nopl_points()

			if aid_data.u_nopl_points:
				if len(aid_data.nopl_points):
					numpoints = len(aid_data.nopl_points)

					sb_tempo_obj = project_obj.timeline.tempo

					prev_val = data_values.dif_val(aid_data.nopl_points[0].value)
					first_pos = aid_data.nopl_points[0].pos
					first_val = aid_data.nopl_points[0].value

					aid_data.nopl_points.sort()

					for n, autopoint_obj in enumerate(aid_data.nopl_points):
						val_dif = prev_val.do_value(autopoint_obj.value)
						s_block_pos = aid_data.nopl_points[n-1].pos if n>0 else 0
						s_block_val = aid_data.nopl_points[n-1].value
						e_block_pos = autopoint_obj.pos
						e_block_val = autopoint_obj.value if not autopoint_obj.type == 'instant' else s_block_val
						tempolen = e_block_pos-s_block_pos
						if tempolen:
							add_tempo_section(sb_tempo_obj, s_block_pos, tempolen, s_block_val, e_block_val)
						if autopoint_obj.type == 'instant' and n == numpoints-1:
							add_tempo_section(sb_tempo_obj, e_block_pos, e_block_pos+PROJECT_FREQ, autopoint_obj.value, autopoint_obj.value)

		if convproj_obj.transport.loop_active:
			project_obj.metadata['TransportLoop'] = 'true'
			project_obj.metadata['TransportPlayPositionL'] = int(convproj_obj.transport.loop_start)
			project_obj.metadata['TransportPlayPositionR'] = int(convproj_obj.transport.loop_end)
		else:
			project_obj.metadata['TransportLoop'] = 'false'
			project_obj.metadata['TransportPlayPositionL'] = convproj_obj.transport.start_pos
			project_obj.metadata['TransportPlayPositionR'] = convproj_obj.get_dur()

		do_markers(convproj_obj.timemarkers, project_obj.timeline.markers)

		if dawvert_intent.output_mode == 'file':
			outfile = os.path.join(dawvert_intent.output_file, '')
			os.makedirs(dawvert_intent.output_file, exist_ok=True)
			f = open(os.path.join(dawvert_intent.output_file, 'output.sb'), 'wb')
			f.write(b'\0' + '\0&Soundbridge Project'.encode('UTF-16LE') + b'\0')
			f = open(os.path.join(dawvert_intent.output_file, 'desktop.ini'), 'wb')
			f.write(b'[.ShellClassInfo]\nIconResource=C:\\Program Files\\SoundBridge\\SoundBridge\\DAW.ico,0')
			project_obj.write_to_file(os.path.join(dawvert_intent.output_file, 'project.xml'))