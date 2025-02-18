# SPDX-FileCopyrightText: 2024 SatyrDiamond
# SPDX-License-Identifier: GPL-3.0-or-later

import plugins
import json
import os

from objects.convproj import fileref

def make_auto(convproj_obj, autoloc, plpos, pldur, startval, endval):
	autopl_obj = convproj_obj.automation.add_pl_points(autoloc, 'float')
	autopl_obj.time.set_posdur(plpos, pldur)

	autopoint_obj = autopl_obj.data.add_point()
	autopoint_obj.pos = 1
	autopoint_obj.value = startval
	autopoint_obj.type = 'normal'

	autopoint_obj = autopl_obj.data.add_point()
	autopoint_obj.pos = pldur-0.0001
	autopoint_obj.value = endval
	autopoint_obj.type = 'normal'

def make_auto_clip(placement_obj, mpetype, plpos, pldur, startval, endval):
	autopoints_obj = placement_obj.add_autopoints(mpetype, 4, True)

	autopoint_obj = autopoints_obj.add_point()
	autopoint_obj.pos = 0
	autopoint_obj.value = startval
	autopoint_obj.type = 'normal'

	autopoint_obj = autopoints_obj.add_point()
	autopoint_obj.pos = (pldur)
	autopoint_obj.value = endval
	autopoint_obj.type = 'normal'

class input_fruitytracks(plugins.base):
	def is_dawvert_plugin(self):
		return 'input'

	def get_shortname(self):
		return 'fruitytracks'

	def get_name(self):
		return 'FruityTracks'

	def get_priority(self):
		return 0

	def get_prop(self, in_dict): 
		in_dict['file_ext'] = ['ftr']
		in_dict['placement_cut'] = True
		in_dict['audio_filetypes'] = ['wav', 'mp3']
		in_dict['placement_loop'] = ['loop', 'loop_off', 'loop_adv']
		in_dict['audio_stretch'] = ['rate']
		in_dict['auto_types'] = ['pl_points']
		in_dict['projtype'] = 'r'

	def get_detect_info(self, detectdef_obj):
		detectdef_obj.headers.append([0, b'FThd'])

	def parse(self, convproj_obj, dawvert_intent):
		from objects.file_proj_past import fruitytracks as proj_fruitytracks

		convproj_obj.type = 'r'
		convproj_obj.set_timings(4, True)

		fileref.filesearcher.add_searchpath_partial('fruitytracks', '../Samples/', 'projectfile')

		project_obj = proj_fruitytracks.ftr_song()
		if dawvert_intent.input_mode == 'file':
			if not project_obj.load_from_file(dawvert_intent.input_file): exit()

		convproj_obj.params.add('bpm', project_obj.bpm, 'float')
		convproj_obj.track_master.params.add('vol', project_obj.vol/128, 'float')

		bpmdiv = 120/project_obj.bpm
		bpmticks = 5512

		if project_obj.title: convproj_obj.metadata.name = project_obj.title
		if project_obj.url: convproj_obj.metadata.url = project_obj.url
		if project_obj.comment:
			convproj_obj.metadata.comment_text = project_obj.comment
			convproj_obj.metadata.comment_datatype = 'rtf'
		convproj_obj.metadata.show = project_obj.showinfo

		if project_obj.loopend:
			convproj_obj.transport.loop_active = True
			convproj_obj.transport.loop_start = (project_obj.loopstart/bpmticks)/bpmdiv
			convproj_obj.transport.loop_end = ((project_obj.loopstart+project_obj.loopend)/bpmticks)/bpmdiv

		for tracknum, ftr_track in enumerate(project_obj.tracks):
			trackid = str(tracknum)
			track_obj = convproj_obj.track__add(trackid, 'audio', 1, False)
			track_obj.visual.name = ftr_track.name if ftr_track.name else 'Track '+str(tracknum)
			track_obj.params.add('pan', (ftr_track.pan-64)/64, 'float')
			track_obj.params.add('vol', ftr_track.vol/128, 'float')

			for ftr_clip in ftr_track.clips:
				placement_obj = track_obj.placements.add_audio()
				placement_obj.visual.name = ftr_clip.name

				sampleref_obj = convproj_obj.sampleref__add(ftr_clip.file, ftr_clip.file, 'win')
				sampleref_obj.find_relative('projectfile')
				sampleref_obj.find_relative('fruitytracks')
				placement_obj.sample.sampleref = ftr_clip.file
				placement_obj.muted = bool(ftr_clip.muted)

				plpos = (ftr_clip.pos/bpmticks)/bpmdiv
				if ftr_clip.stretch == 0:
					pldur = (ftr_clip.dur/bpmticks)
					placement_obj.time.set_loop_data(0, 0, (ftr_clip.repeatlen/bpmticks))
				else:
					audduration = sampleref_obj.dur_sec*8
					pldur = (ftr_clip.dur/bpmticks)/bpmdiv
					placement_obj.time.set_loop_data(0, 0, (ftr_clip.repeatlen/bpmticks)/bpmdiv)
					placement_obj.sample.stretch.algorithm = 'resample'
					placement_obj.sample.stretch.set_rate_tempo(project_obj.bpm, audduration/ftr_clip.stretch, False)
				placement_obj.time.set_posdur(plpos, pldur)

				make_auto_clip(placement_obj, 'gain', plpos, pldur, ftr_clip.vol_start/128, ftr_clip.vol_end/128)
				make_auto(convproj_obj, ['track', trackid, 'pan'], plpos, pldur, (ftr_clip.pan_start-64)/64, (ftr_clip.pan_end-64)/64)