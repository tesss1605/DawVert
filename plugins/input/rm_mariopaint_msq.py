# SPDX-FileCopyrightText: 2024 SatyrDiamond
# SPDX-License-Identifier: GPL-3.0-or-later

from objects.songinput import mariopaint
from functions import xtramath
import io
import plugins

import logging
logger_input = logging.getLogger('input')

instnames = ['mario','toad','yoshi','star','flower','gameboy','dog','cat','pig','swan','face','plane','boat','car','heart']

def readpart(msq_score_str):
	msq_notes = {}
	char1 = int(msq_score_str.read(1), 16)
	char2 = int(msq_score_str.read(1), 16)
	char3 = int(msq_score_str.read(1), 16)

	if char1 == 0:
		if char2 == 0: numnotes = 0 if char3 == 0 else 1
		else: numnotes = 2
	else: numnotes = 3

	if numnotes == 1:
		msq_notes[char3] = int(msq_score_str.read(1), 16)

	if numnotes == 2:
		msq_notes[char2] = char3
		t_note = int(msq_score_str.read(1), 16)
		msq_notes[t_note] = int(msq_score_str.read(1), 16)

	if numnotes == 3:
		msq_notes[char1] = char2
		msq_notes[char3] = int(msq_score_str.read(1), 16)
		t_note = int(msq_score_str.read(1), 16)
		msq_notes[t_note] = int(msq_score_str.read(1), 16)

	return msq_notes

class input_mariopaint_msq(plugins.base):
	def __init__(self): pass
	def is_dawvert_plugin(self): return 'input'
	def getshortname(self): return 'mariopaint_msq'
	def gettype(self): return 'rm'
	def getdawinfo(self, dawinfo_obj): 
		dawinfo_obj.file_ext = 'msq'
		dawinfo_obj.name = 'MarioSequencer'
		dawinfo_obj.track_lanes = True
		dawinfo_obj.track_nopl = True
		dawinfo_obj.fxtype = 'rack'
		dawinfo_obj.plugin_included = ['midi']
	def supported_autodetect(self): return False
	def parse(self, convproj_obj, input_file, dv_config):
		convproj_obj.type = 'rm'
		mariopaint_obj = mariopaint.mariopaint_song()

		msq_values = {}
		f_msq = open(input_file, 'r')
		lines_msq = f_msq.readlines()
		for n, line in enumerate(lines_msq):
			if '=' not in line:
				logger_input.error('mariopaint_msq: Line '+str(n+1)+': "=" not found.')
				exit()
			msq_name, fmf_val = line.rstrip().split('=', 1)
			msq_values[msq_name] = fmf_val

		if 'TIME44' in msq_values: 
			mariopaint_obj.measure = 4 if msq_values['TIME44'] == 'TRUE' else 2
		else: 
			mariopaint_obj.measure = 4

		mariopaint_obj.tempo = int(msq_values['TEMPO']) if 'TEMPO' in msq_values else 180
		msq_score = msq_values['SCORE']
		msq_score_size = len(msq_score)
		msq_score_str = io.StringIO(msq_score)

		curpos = 0
		while msq_score_str.tell() < msq_score_size:
			msq_notes = readpart(msq_score_str)
			mp_chord = mariopaint_obj.add_chord(curpos)

			for key, instnum in msq_notes.items():
				keynum = 12-key
				mp_note = mp_chord.add_note()
				mp_note.inst = instnames[instnum-1]
				mp_note.key = keynum%7
				mp_note.oct = keynum//7

			curpos += 1

		mariopaint_obj.to_cvpj(convproj_obj)
