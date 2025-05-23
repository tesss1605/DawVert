# SPDX-FileCopyrightText: 2024 SatyrDiamond
# SPDX-License-Identifier: GPL-3.0-or-later

import plugins
from functions import xtramath
from functions_spec import soundbridge as soundbridge_func
from objects import globalstore
from objects.convproj import fileref
from objects.data_bytes import bytereader
import io
import math
import numpy as np
import os
import struct
import uuid

sb_auto_dtype = np.dtype([('pos', '>I'), ('val', '>f'),('unk1', '>f'),('unk2', '>f')])

native_names = {}
native_names['2ed34074c14566409f62442c8545929f'] = 'eq'
native_names['544d1ae3e2c91548b932574932c83885'] = 'filter_unit'
native_names['1423f146b5fcaa40904b2c3fe24495fa'] = 'analyzer'
native_names['f487b09e6f329a41b2cfc280068079a4'] = 'chorus_flanger'
native_names['0d47d236d52df342bf3b8635a4b89f07'] = 'delay'
native_names['b2a57c0cc1996d468f38a87332010bc9'] = 'phaser'
native_names['8f64f7b97060ca449e89456f9a2684d0'] = 'reverb'
native_names['2793169f4a4b554087755fafff91b3e9'] = 'bit_crusher'
native_names['0b44f1c343a1de4ab108069e3ec0f7e4'] = 'resonance_filter'
native_names['1158f6956478e749a123534b7d943e3d'] = 'compressor_expander'
native_names['ee2b5cce1faeb54f9081ad2575736075'] = 'noise_gate'
native_names['80700b7cbbf6234189e21d862baf0d19'] = 'limiter'

def calc_vol(vol):
	vol = (vol/0.824999988079071)**4
	return vol
	
def parse_auto(blockdata):
	blockdata = io.BytesIO(soundbridge_func.decode_chunk(blockdata))
	unk_x = blockdata.read(4)
	dataread = blockdata.read()
	numnotes = len(dataread)//sb_auto_dtype.itemsize
	autodata = np.frombuffer(dataread[0:numnotes*sb_auto_dtype.itemsize], dtype=sb_auto_dtype)

	#print('I')
	#for x in autodata:
	#	print(x)

	return autodata[np.where(autodata['unk1']!=0)]

def add_auto(defaultValue, valtype, convproj_obj, autoloc, sb_blocks, add, mul):

	for block in sb_blocks:
		autopl_obj = convproj_obj.automation.add_pl_points(autoloc, 'float')
		autopl_obj.time.position = block.position
		autopl_obj.time.duration = block.framesCount
		autopl_obj.visual.name = block.name
		if 'BlockColor' in block.metadata: autopl_obj.visual.color.set_hex(block.metadata['BlockColor'])
		for point in parse_auto(block.blockData):
			autopoint_obj = autopl_obj.data.add_point()
			autopoint_obj.pos = point['pos']
			if valtype == 'vol':
				autopoint_obj.value = calc_vol(point['val'])
			elif valtype == 'invert':
				autopoint_obj.value = int(point['val']<0.5)
			else:
				autopoint_obj.value = (point['val']+add)*mul
			autopoint_obj.tension = math.log10(point['unk1'])
			autopoint_obj.type = 'normal'

	auto_obj = convproj_obj.automation.get_opt(autoloc)
	if auto_obj is not None: 
		if valtype == 'vol':
			auto_obj.defualt_val = calc_vol(defaultValue)
		elif valtype == 'invert':
			auto_obj.defualt_val = int(defaultValue<0.5)
		else:
			auto_obj.defualt_val = (defaultValue+add)*mul

sb_notes_dtype = np.dtype([('id', '>I'),('pos', '>I'),('dur', '>I'),('key', 'B'),('vol', 'B'),('unk1', 'B'),('unk2', 'B')])

def parse_notes(notes_data):
	unk_x = notes_data.read(4)
	dataread = notes_data.read()
	numnotes = len(dataread)//sb_notes_dtype.itemsize
	notedata = np.frombuffer(dataread[0:numnotes*sb_notes_dtype.itemsize], dtype=sb_notes_dtype)
	outdata = notedata[np.where(notedata['dur']!=0)]
	return outdata

def add_params(stateobj, params_obj):
	if stateobj:
		statebin = soundbridge_func.decode_chunk(stateobj)
		mute, vol, unk, pan = struct.unpack('>ffff', statebin)
		params_obj.add('enabled', mute!=1, 'bool')
		params_obj.add('vol', calc_vol(vol), 'float')
		params_obj.add('pan', (pan-0.5)*2, 'float')

global_returnids = 0

def make_sendauto(convproj_obj, sb_track, track_obj, cvpj_trackid):
	for x in sb_track.sendsAutomationContainer.automationTracks:
		splitret = x.returnTrackPath.split('/')
		if len(splitret) == 3:
			if splitret[0]=='' and splitret[1].isnumeric() and splitret[2]=='R':
				sendautoid = cvpj_trackid+'__'+'return__'+str(splitret[1])
				track_obj.sends.add('return__'+str(splitret[1]), sendautoid, x.defaultValue)
				add_auto(x.defaultValue, None, convproj_obj, ['send', sendautoid, 'amount'], x.blocks, 0, 1)

def make_stretch(pitchTempoProcessorMode, stretch_obj):
	if pitchTempoProcessorMode == 0:
		stretch_obj.algorithm = 'elastique_v3'
		stretch_obj.algorithm_mode = 'mono'

	if pitchTempoProcessorMode == 4:
		stretch_obj.algorithm = 'soundtouch'

def do_filter_type(filter_obj, num):
	if num == 1: filter_obj.type.set('low_pass', None)
	if num == 2: filter_obj.type.set('high_pass', None)
	if num == 3: filter_obj.type.set('band_pass', None)
	if num == 4: filter_obj.type.set('notch', None)

def create_plugin(convproj_obj, sb_plugin, issynth, track_obj):
	from objects.file_proj._soundbridge import sampler
	from objects.file_proj._soundbridge import mathalgo
	uiddata = soundbridge_func.decode_chunk(sb_plugin.uid)
	statedata = soundbridge_func.decode_chunk(sb_plugin.state)
	pluginid = None

	if len(uiddata) == 16 and statedata:
		hexdata = uiddata.hex()

		if uiddata == b'CTSV7prritmix\x00\x00\x00':
			track_obj.is_drum = True

		if uiddata == b'\xb7\xe4~\xd75\xc2\xa8H\x97JL\xe1\x82.\xc2^':
			statereader = bytereader.bytereader()
			statereader.load_raw(statedata)
			#with open('s_in.bin', 'wb') as f: f.write(statedata)

			sampler_data = sampler.soundbridge_sampler_main()
			sampler_data.read(statereader)

			#from objects.data_bytes import bytewriter
			#statw = bytewriter.bytewriter()
			#sampler_data.write(statw)
			#with open('s_out.bin', 'wb') as f: f.write(statw.getvalue())

			if len(sampler_data.samples)==1:
				sb_sample = sampler_data.samples[0]
				sample_params = sampler_data.params[sampler_data.samples[0].params_num]
				if not sb_sample.slicemode:
					plugin_obj, pluginid = convproj_obj.plugin__add__genid('universal', 'sampler', 'single')
					plugin_obj.role = 'synth'
					samplepart_obj = plugin_obj.samplepart_add('sample')
					samplepart_obj.from_sampleref(convproj_obj, sb_sample.filename)
					samplepart_obj.point_value_type = "samples"
					samplepart_obj.start = sb_sample.start
					samplepart_obj.end = sb_sample.end
					samplepart_obj.data['vel_sens'] = sample_params.vol_vel
					track_obj.datavals.add('middlenote', (sample_params.key_root-60))
					filter_obj = plugin_obj.filter
					filter_obj.on = bool(sb_sample.filter_type)
					filter_obj.freq = mathalgo.freq__from_one(sample_params.filter_freq)
					filter_obj.q = sample_params.filter_res
					do_filter_type(filter_obj, sb_sample.filter_type)

				else:
					plugin_obj, pluginid = convproj_obj.plugin__add__genid('universal', 'sampler', 'slicer')
					plugin_obj.role = 'synth'
					samplepart_obj = plugin_obj.samplepart_add('sample')
					samplepart_obj.from_sampleref(convproj_obj, sb_sample.filename)
					for sslice in sb_sample.slices:
						slice_param = sampler_data.params[sslice[0]]
						slice_obj = samplepart_obj.add_slice()
						slice_obj.start = sslice[1]
						slice_obj.is_custom_key = True
						slice_obj.custom_key = slice_param.key_root-60

				samplepart_obj.visual.name = sb_sample.name
				track_obj.visual_inst.name = sb_sample.name
				if 'SampleColor' in sb_sample.metadata:
					samplecolor = sb_sample.metadata['SampleColor']
					samplepart_obj.visual.color.set_hex(samplecolor)
					plugin_obj.visual.color.set_hex(samplecolor)
					track_obj.visual_inst.color.set_hex(samplecolor)

				stretch_obj = samplepart_obj.stretch
				stretch_obj.set_rate_speed(120, 1, False)
				stretch_obj.preserve_pitch = True

			elif sampler_data.sampler_mode>0:
				plugin_obj, pluginid = convproj_obj.plugin__add__genid('universal', 'sampler', 'multi')

				if sampler_data.sampler_mode==1: plugin_obj.datavals.add('multi_mode', 'all')
				if sampler_data.sampler_mode==2: plugin_obj.datavals.add('multi_mode', 'random')
				if sampler_data.sampler_mode==3: plugin_obj.datavals.add('multi_mode', 'forward')
				if sampler_data.sampler_mode==4: plugin_obj.datavals.add('multi_mode', 'backward')
				if sampler_data.sampler_mode==5: plugin_obj.datavals.add('multi_mode', 'forward_backward')
 
				for layernum, sb_sample in enumerate(sampler_data.samples):
					endstr = str(layernum)
					sample_params = sampler_data.params[sb_sample.params_num]
					sp_obj = plugin_obj.sampleregion_add(sample_params.key_min-60, sample_params.key_max-60, sample_params.key_root-60, None)
					sp_obj.vel_min = sample_params.vel_min/127
					sp_obj.vel_max = sample_params.vel_max/127
					sp_obj.vol = sample_params.gain
					sp_obj.pan = sample_params.pan
					sp_obj.sampleref = sb_sample.filename
					sp_obj.point_value_type = "samples"
					sp_obj.start = sb_sample.start
					sp_obj.end = sb_sample.end
					sp_obj.visual.name = sb_sample.name
					sp_obj.stretch.set_rate_speed(120, 1, False)
					sp_obj.stretch.preserve_pitch = True
					if 'SampleColor' in sb_sample.metadata:
						sp_obj.visual.color.set_hex(sb_sample.metadata['SampleColor'])

					filter_obj = plugin_obj.named_filter_add(endstr)
					sp_obj.filter_assoc = endstr
					filter_obj.on = bool(sb_sample.filter_type)
					filter_obj.freq = mathalgo.freq__from_one(sample_params.filter_freq)
					filter_obj.q = sample_params.filter_res
					do_filter_type(filter_obj, sb_sample.filter_type)

		elif uiddata[0:8] == b'\x00\x00\x00\x00SV2T':
			fourid = struct.unpack('>I', uiddata[8:12])[0]

			plugin_obj, pluginid = convproj_obj.plugin__add__genid('external', 'vst2', 'win')
			plugin_obj.role = 'synth' if issynth else 'fx'
			plugin_obj.external_info.name = sb_plugin.name
			plugin_obj.external_info.fourid = fourid
			plugin_obj.external_info.creator = sb_plugin.vendor
			if issynth: track_obj.visual_inst.name = sb_plugin.name

			extmanu_obj = plugin_obj.create_ext_manu_obj(convproj_obj, pluginid)

			statereader = bytereader.bytereader()
			statereader.load_raw(statedata)

			#print(len(statedata), statedata[0:300])

			if statereader.magic_check(b'CcnK'):
				statereader.skip(8)
				disabled = statereader.float_b()
				plugin_obj.fxdata_add(not disabled, None)
				programnum = statereader.uint32_b()
				plugin_obj.clear_prog_keep(programnum)
				if statereader.magic_check(b'CcnK'):
					statereader.skip(4)
					chunk_type = statereader.read(4)
					if chunk_type == b'FBCh':
						statereader.skip(16)
						statereader.skip(128)
						chunkdata = statereader.raw(statereader.uint32_b())
						plugin_obj.clear_prog_keep(programnum)
						extmanu_obj.vst2__replace_data('id', fourid, chunkdata, 'win', True)
					if chunk_type == b'FxBk':
						statereader.skip(16)
						statereader.skip(128)
						plugin_obj.clear_prog_keep(programnum)
						extmanu_obj.vst2__import_presetdata('raw', statereader.rest(), 'win')

					for x in sb_plugin.automationContainer.automationTracks:
						paramid = 'ext_param_'+str(x.parameterIndex)
						plugin_obj.params.add(paramid, x.defaultValue, 'float')
						outparam = x.parameterIndex-1
						if outparam>=0:
							paramid = 'ext_param_'+str(outparam)
							add_auto(x.defaultValue, None, convproj_obj, ['plugin', pluginid, paramid], x.blocks, 0, 1)
						else:
							add_auto(x.defaultValue, 'invert', convproj_obj, ['slot', pluginid, 'enabled'], x.blocks, 0, 1)

		elif hexdata in native_names:
			plugin_enabled = struct.unpack('>f', statedata[0:4])[0]
			native_name = native_names[hexdata]
			plugin_obj, pluginid = convproj_obj.plugin__add__genid('native', 'soundbridge', native_name)

			fldso = globalstore.dataset.get_obj('soundbridge', 'plugin', native_name)
			if fldso:
				plugin_obj.from_bytes(statedata[4:], 'soundbridge', 'soundbridge', 'plugin', native_name, native_name)
				autonum = dict([[x.num, n] for n, x in fldso.params.iter()])

			for x in sb_plugin.automationContainer.automationTracks:
				parameterIndex = x.parameterIndex
				if parameterIndex>0:
					if fldso:
						if parameterIndex in autonum:
							paramid = autonum[parameterIndex]
							plugin_obj.params.add(paramid, x.defaultValue, 'float')
							add_auto(x.defaultValue, None, convproj_obj, ['plugin', pluginid, paramid], x.blocks, 0, 1)
				else:
					add_auto(x.defaultValue, 'invert', convproj_obj, ['slot', pluginid, 'enabled'], x.blocks, 0, 1)

		else:
			plugin_obj, pluginid = convproj_obj.plugin__add__genid('external', 'vst3', 'win')
			dev_uuid = uuid.UUID(int=int.from_bytes(uiddata, 'big')).bytes_le
			pluguuid = dev_uuid.hex().upper()

			extmanu_obj = plugin_obj.create_ext_manu_obj(convproj_obj, pluginid)
			if issynth: track_obj.visual_inst.name = sb_plugin.name

			statereader = bytereader.bytereader()
			statereader.load_raw(statedata)
			size = statereader.uint32_b()
			statereader.skip(12)
			chunkdata = statereader.raw(size)
			extmanu_obj.vst3__replace_data('id', pluguuid, chunkdata, 'win')

			for x in sb_plugin.automationContainer.automationTracks:
				paramid = 'ext_param_'+str(x.parameterIndex)
				plugin_obj.params.add(paramid, x.defaultValue, 'float')
				outparam = x.parameterIndex-1
				if outparam>=0:
					paramid = 'ext_param_'+str(outparam)
					add_auto(x.defaultValue, None, convproj_obj, ['plugin', pluginid, paramid], x.blocks, 0, 1)
				else:
					add_auto(x.defaultValue, 'invert', convproj_obj, ['slot', pluginid, 'enabled'], x.blocks, 0, 1)

	return pluginid

def do_fx(cvpj_trackid, convproj_obj, sb_track, track_obj):
	track_obj.plugslots.slots_audio_enabled = not bool(sb_track.audioUnitsBypass)
	for x in sb_track.audioUnits:
		pluginid = create_plugin(convproj_obj, x, False, track_obj)
		if pluginid:
			track_obj.plugslots.slots_audio.append(pluginid)

	if bool(sb_track.inverse):
		inverse_fxid = cvpj_trackid+'_inverse'
		plugin_obj = convproj_obj.plugin__add(inverse_fxid, 'universal', 'invert', None)
		track_obj.plugslots.slots_mixer.append(inverse_fxid)

def make_track(convproj_obj, sb_track, groupname, num, pfreq):
	global global_returnids

	metadata = sb_track.metadata
	trackcolor = metadata['TrackColor'] if 'TrackColor' in metadata else None

	visual_size = 1

	if 'SequencerTrackHeightState' in metadata:
		SequencerTrackHeightState = int(metadata['SequencerTrackHeightState'])
		size_first = SequencerTrackHeightState&0xffff
		size_second = SequencerTrackHeightState>>20
		if 44>size_first>39 and size_second<50:
			visual_size = (((size_first-40) + size_second)+1)/4

	cvpj_trackid = ('main' if not groupname else groupname)+'__'+str(num)

	if sb_track.type == 4:
		track_obj = convproj_obj.track__add(cvpj_trackid, 'instrument', 1, False)
		track_visual(track_obj.visual, sb_track)
		add_params(sb_track.state, track_obj.params)
		do_fx(cvpj_trackid, convproj_obj, sb_track, track_obj)
		track_obj.latency_offset = sb_track.latencyOffset/(pfreq/500)

		pitchTempoProcessorMode = sb_track.pitchTempoProcessorMode
		track_obj.armed.on = bool(sb_track.armed)
		track_obj.armed.in_keys = bool(sb_track.armed)
		track_obj.visual_ui.height = visual_size

		if groupname:
			track_obj.group = groupname
			track_obj.sends.to_master_active = False

		for block in sb_track.blocks:
			placement_obj = track_obj.placements.add_notes()
			if block.loopEnabled: 
				placement_obj.time.set_posdur(block.position, block.framesCount)
				placement_obj.time.set_loop_data(block.loopOffset, block.positionStart, block.positionEnd)
			else: 
				placement_obj.time.set_posdur(block.position, block.positionEnd-block.positionStart)
				placement_obj.time.set_offset(block.positionStart)
			blockdata = soundbridge_func.decode_chunk(block.blockData)
			trackcolor = block.metadata['BlockColor'] if 'BlockColor' in block.metadata else None
			placement_obj.visual.color.set_hex(trackcolor)
			placement_obj.visual.name = block.name
			placement_obj.muted = bool(block.muted)
			for note in parse_notes(io.BytesIO(blockdata)): placement_obj.notelist.add_r(int(note['pos']), int(note['dur']), int(note['key'])-60, int(note['vol'])/127, None)
			for block in block.automationBlocks:
				valmul = 1
				valadd = 0
				ccnum = block.index-1
				if ccnum == -1: 
					mpetype = 'midi_pressure'
					valmul = 127
				elif ccnum == 0: 
					mpetype = 'midi_pitch'
					valmul = 8192*2
					valadd = 0.5
				else: 
					mpetype = 'midi_cc_'+str(ccnum)
					valmul = 127

				autopoints_obj = placement_obj.add_autopoints(mpetype)
				for a in parse_auto(block.blockData):
					autopoint_obj = autopoints_obj.add_point()
					autopoint_obj.pos = a['pos']-block.positionStart
					autopoint_obj.value = (a['val']-valadd)*valmul

		if sb_track.midiInstrument:
			midiinst = sb_track.midiInstrument
			track_obj.plugslots.set_synth( create_plugin(convproj_obj, midiinst, True, track_obj) )

		if sb_track.midiInput:
			track_obj.midi.in_chanport.chan = sb_track.midiInput.channelIndex+1

		if sb_track.midiOutput:
			track_obj.midi.out_chanport.chan = sb_track.midiOutput.channelIndex+1

	if sb_track.type == 3:
		track_obj = convproj_obj.track__add(cvpj_trackid, 'audio', 1, False)
		track_visual(track_obj.visual, sb_track)
		add_params(sb_track.state, track_obj.params)
		do_fx(cvpj_trackid, convproj_obj, sb_track, track_obj)
		track_obj.latency_offset = sb_track.latencyOffset/(pfreq/500)

		track_obj.armed.on = bool(sb_track.armed)
		track_obj.armed.in_audio = bool(sb_track.armed)
		track_obj.visual_ui.height = visual_size

		stretch_algo = 'stretch'
		pitchTempoProcessorMode = sb_track.pitchTempoProcessorMode

		if groupname:
			track_obj.group = groupname
			track_obj.sends.to_master_active = False

		if sb_track.blockContainers:
			for block in sb_track.blockContainers[0].blocks:
				placement_obj = track_obj.placements.add_nested_audio()
				clipmetadata = block.metadata
				placement_obj.visual.name = block.name
				placement_obj.muted = bool(block.muted)
				if 'BlockColor' in clipmetadata: 
					placement_obj.visual.color.set_hex(clipmetadata['BlockColor'])
				placement_obj.time.set_posdur(block.position, block.framesCount)
				for blockevent in block.events:
					placement_obj.time.set_offset(blockevent.positionStart)
					placement_obj = placement_obj.add()
					placement_obj.time.set_posdur(blockevent.position, blockevent.framesCount+blockevent.positionStart)

					if 'BlockColor' in clipmetadata: placement_obj.visual.color.set_hex(clipmetadata['BlockColor'])

					sp_obj = placement_obj.sample
					sp_obj.sampleref = blockevent.fileName

					sp_obj.vol = xtramath.from_db(blockevent.gain)
					sp_obj.pitch = math.log2(1/blockevent.pitch)*-12

					stretch_obj = sp_obj.stretch
					stretch_obj.preserve_pitch = True
					stretch_obj.is_warped = True
					
					make_stretch(pitchTempoProcessorMode, stretch_obj)

					warp_obj = stretch_obj.warp

					placement_obj.fade_in.set_dur(blockevent.fadeInLength/pfreq, 'beats')
					placement_obj.fade_out.set_dur(blockevent.fadeOutLength/pfreq, 'beats')

					ref_found, sampleref_obj = convproj_obj.sampleref__get(sp_obj.sampleref)

					maxbeat = 0

					warp_obj.seconds = sampleref_obj.dur_sec
					for stretchMark in blockevent.stretchMarks:
						warp_point_obj = warp_obj.points__add()
						warp_point_obj.beat = stretchMark.newPosition/pfreq
						warp_point_obj.second = stretchMark.initPosition/(sampleref_obj.hz if sampleref_obj else pfreq)
						maxbeat = stretchMark.newPosition

					warp_obj.calcpoints__speed()
					
					for autoblock in blockevent.automationBlocks:
						autopoints_obj = placement_obj.add_autopoints('gain', pfreq, True)
						for a in parse_auto(autoblock.blockData):
							autopoint_obj = autopoints_obj.add_point()
							autopoint_obj.pos = a['pos']-autoblock.positionStart
							autopoint_obj.value = a['val']/2

	if sb_track.type in [3,4]:
		make_sendauto(convproj_obj, sb_track, track_obj, cvpj_trackid)
		for x in sb_track.automationContainer.automationTracks:
			if x.parameterIndex == 2: add_auto(x.defaultValue, 'vol', convproj_obj, ['track', cvpj_trackid, 'vol'], x.blocks, 0, 1)
			if x.parameterIndex == 3: add_auto(x.defaultValue, None, convproj_obj, ['track', cvpj_trackid, 'pan'], x.blocks, -.5, 2)

	if sb_track.type == 2:
		returnid = 'return__'+str(global_returnids)
		track_obj = convproj_obj.track_master.fx__return__add(returnid)
		track_obj.latency_offset = sb_track.latencyOffset/(pfreq/500)
		track_obj.visual_ui.height = visual_size

		track_visual(track_obj.visual, sb_track)
		add_params(sb_track.state, track_obj.params)
		do_fx(returnid, convproj_obj, sb_track, track_obj)
		global_returnids += 1
		make_sendauto(convproj_obj, sb_track, track_obj, cvpj_trackid)
		for x in sb_track.automationContainer.automationTracks:
			if x.parameterIndex == 2: add_auto(x.defaultValue, 'vol', convproj_obj, ['return', returnid, 'vol'], x.blocks, 0, 1)
			if x.parameterIndex == 3: add_auto(x.defaultValue, None, convproj_obj, ['return', returnid, 'pan'], x.blocks, -.5, 2)

	if sb_track.type == 1:
		track_obj = convproj_obj.fx__group__add(cvpj_trackid)
		track_visual(track_obj.visual, sb_track)
		add_params(sb_track.state, track_obj.params)
		do_fx(cvpj_trackid, convproj_obj, sb_track, track_obj)
		do_markers(track_obj, sb_track.markers)
		track_obj.latency_offset = sb_track.latencyOffset/(pfreq/500)
		make_sendauto(convproj_obj, sb_track, track_obj, cvpj_trackid)
		track_obj.visual_ui.height = visual_size

		for x in sb_track.automationContainer.automationTracks:
			if x.parameterIndex == 2: add_auto(x.defaultValue, 'vol', convproj_obj, ['group', cvpj_trackid, 'vol'], x.blocks, 0, 1)
			if x.parameterIndex == 3: add_auto(x.defaultValue, None, convproj_obj, ['group', cvpj_trackid, 'pan'], x.blocks, -.5, 2)

		for gnum, gb_track in enumerate(sb_track.tracks):
			make_track(convproj_obj, gb_track, cvpj_trackid, gnum, pfreq)

def track_visual(visual_obj, ab_track):
	visual_obj.name = ab_track.name
	visual_obj.color.set_hex(ab_track.metadata['TrackColor'] if 'TrackColor' in ab_track.metadata else None)

def do_markers(convproj_obj, sb_markers):
	for marker in sb_markers:
		timemarker_obj = convproj_obj.timemarker__add()
		timemarker_obj.position = marker.position
		if marker.label: timemarker_obj.visual.name = marker.label
		if marker.comment: timemarker_obj.visual.comment = marker.comment
		if marker.tag: 
			try:
				timemarker_obj.visual.color.set_hex(marker.tag)
			except:
				pass

class input_soundbridge(plugins.base):
	def is_dawvert_plugin(self):
		return 'input'
	
	def get_shortname(self):
		return 'soundbridge'
	
	def get_name(self):
		return 'SoundBridge'
	
	def get_priority(self):
		return 0
	
	def get_prop(self, in_dict): 
		in_dict['audio_filetypes'] = ['wav']
		in_dict['audio_stretch'] = ['warp']
		in_dict['auto_types'] = ['pl_points']
		in_dict['file_ext'] = ['soundbridge']
		in_dict['fxtype'] = 'groupreturn'
		in_dict['placement_cut'] = True
		in_dict['placement_loop'] = ['loop', 'loop_eq', 'loop_off', 'loop_adv', 'loop_adv_off']
		in_dict['plugin_ext'] = ['vst2', 'vst3']
		in_dict['plugin_ext_arch'] = [64]
		in_dict['plugin_ext_platforms'] = ['win']
		in_dict['plugin_included'] = ['native:soundbridge','universal:invert']
		in_dict['audio_nested'] = True
		
	def parse(self, convproj_obj, dawvert_intent):
		from objects.file_proj import soundbridge as proj_soundbridge

		convproj_obj.type = 'r'
		convproj_obj.fxtype = 'groupreturn'

		project_obj = proj_soundbridge.soundbridge_song()
		if dawvert_intent.input_mode == 'file':
			project_obj.load_from_file(os.path.join(dawvert_intent.input_file, 'project.xml'))

		convproj_obj.metadata.name = project_obj.name

		convproj_obj.params.add('bpm', project_obj.tempo, 'float')
		
		pfreq = int(project_obj.sampleRate)/2
		convproj_obj.set_timings(pfreq, False)

		globalstore.datadef.load('soundbridge', './data_main/datadef/soundbridge.ddef')
		globalstore.dataset.load('soundbridge', './data_main/dataset/soundbridge.dset')

		for audiosource in project_obj.pool.audioSources:
			filename = audiosource.fileName
			ofilename = filename
			if dawvert_intent.input_file.endswith('.soundbridge'): 
				ofilename = os.path.join(dawvert_intent.input_file, filename)
			convproj_obj.sampleref__add(filename, ofilename, None)

		for videosource in project_obj.pool.videoSources:
			filename = videosource.fileName
			ofilename = filename
			if dawvert_intent.input_file.endswith('.soundbridge'): 
				ofilename = os.path.join(dawvert_intent.input_file, filename)
			convproj_obj.fileref__add(filename, ofilename, None)

		master_track = project_obj.masterTrack

		video_track = project_obj.videoTrack
		if video_track.blocks:
			track_obj = convproj_obj.track__add('videotrack', 'video', 1, False)
			track_obj.visual.name = video_track.name
			track_obj.visual.color.set_hex(video_track.metadata['Color'] if 'Color' in video_track.metadata else None)
			track_obj.params.add('vol', 0, 'float')
			for block in video_track.blocks:
				placement_obj = track_obj.placements.add_video()
				placement_obj.visual.name = block.name
				placement_obj.muted = bool(block.muted)
				clipmetadata = block.metadata
				if 'BlockColor' in clipmetadata: 
					placement_obj.visual.color.set_hex(clipmetadata['BlockColor'])
				placement_obj.time.set_posdur(block.position, block.framesCount)
				placement_obj.video_fileref = block.filename

		add_params(master_track.state, convproj_obj.track_master.params)
		track_visual(convproj_obj.track_master.visual, master_track)
		do_fx('master', convproj_obj, master_track, convproj_obj.track_master)
		convproj_obj.track_master.latency_offset = master_track.latencyOffset/(pfreq/500)

		for x in master_track.automationContainer.automationTracks:
			if x.parameterIndex == 2: add_auto(x.defaultValue, 'vol', convproj_obj, ['master', 'vol'], x.blocks, 0, 1)
			if x.parameterIndex == 3: add_auto(x.defaultValue, None, convproj_obj, ['master', 'pan'], x.blocks, -.5, 2)

		for num, sb_track in enumerate(master_track.tracks):
			make_track(convproj_obj, sb_track, None, num, pfreq)

		sb_timeSignature = project_obj.timeline.timeSignature
		sb_tempo = project_obj.timeline.tempo

		do_markers(convproj_obj, project_obj.timeline.markers)

		convproj_obj.timesig[0] = sb_timeSignature.timeSigNumerator
		convproj_obj.timesig[1] = sb_timeSignature.timeSigDenominator

		for x in sb_timeSignature.sections:
			convproj_obj.timesig_auto.add_point(x.position, [x.timeSigNumerator, x.timeSigDenominator])

		for x in sb_tempo.sections:
			autopl_obj = convproj_obj.automation.add_pl_points(['main', 'bpm'], 'float')
			autopl_obj.time.position = x.position
			autopl_obj.time.duration = x.length

			metacolorkey = 'Color_%s_%s' % (x.startTempo*1000, x.endTempo*1000)
			if metacolorkey in sb_tempo.metadata:
				colorval = sb_tempo.metadata[metacolorkey]
				colorval = colorval[3:]
				if len(colorval)==6: autopl_obj.visual.color.set_hex('#'+colorval)

			autopoint_obj = autopl_obj.data.add_point()
			autopoint_obj.pos = 0
			autopoint_obj.value = x.startTempo
			autopoint_obj.type = 'normal'
		
			autopoint_obj = autopl_obj.data.add_point()
			autopoint_obj.pos = x.length-1
			autopoint_obj.value = x.endTempo
			autopoint_obj.type = 'normal'

		projmeta = project_obj.metadata
		if 'TransportLoop' in projmeta: convproj_obj.transport.loop_active = projmeta['TransportLoop'] == 'true'
		if 'TransportPlayPositionL' in projmeta: convproj_obj.transport.loop_start = int(float(projmeta['TransportPlayPositionL']))
		if 'TransportPlayPositionR' in projmeta: convproj_obj.transport.loop_end = int(float(projmeta['TransportPlayPositionR']))

		convproj_obj.automation.set_persist_all(False)