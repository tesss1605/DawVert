# SPDX-FileCopyrightText: 2024 SatyrDiamond
# SPDX-License-Identifier: GPL-3.0-or-later

from objects import globalstore

def midiid_to_num(i_bank, i_patch, i_isdrum, i_iskey): 
	return i_bank*256 + i_patch + int(i_isdrum)<<8 + int(i_iskey)<<16

def midiid_from_num(value): 
	v_isdrum = int(bool(value&0b10000000))
	v_iskey = int(bool((value>>8)&0b10000000))
	v_patch = (value%128)
	v_bank = (value>>8)
	return v_bank, v_patch, v_isdrum, v_iskey

def get_visual_inst(m_bank_hi, m_bank, m_inst, m_drum, m_dev):
	out_color = None
	out_name = None

	midi_dev = m_dev if m_dev else 'gm'
	globalstore.dataset.load('midi', './data_main/dataset/midi.dset')
	if midi_dev == 'xg':
		startcat = 'xg_inst'
		if m_drum: m_bank = 127

		d = globalstore.dataset.get_obj('midi', startcat, str(m_bank_hi)+'_'+str(m_bank)+'_'+str(m_inst))
		if d:
			if d.visual.color: out_color = d.visual.color
			if d.visual.color: out_name = d.visual.name

		d = globalstore.dataset.get_obj('midi', startcat, '0_'+str(m_bank)+'_'+str(m_inst))
		if d:
			if d.visual.color and not out_color: out_color = d.visual.color
			if d.visual.color and not out_name: out_name = d.visual.name

		d = globalstore.dataset.get_obj('midi', startcat, '0_0_'+str(m_inst))
		if d:
			if d.visual.color and not out_color: out_color = d.visual.color
			if d.visual.color and not out_name: out_name = d.visual.name

	else:
		startcat = midi_dev+'_inst' if not m_drum else midi_dev+'_drums'
		d = globalstore.dataset.get_obj('midi', startcat, str(m_bank_hi)+'_'+str(m_bank)+'_'+str(m_inst))

		if d:
			if d.visual.color: out_color = d.visual.color
			if d.visual.color: out_name = d.visual.name

		d = globalstore.dataset.get_obj('midi', startcat, '0_0_'+str(m_inst))
		if d:
			if d.visual.color and not out_color: out_color = d.visual.color
			if d.visual.color and not out_name: out_name = d.visual.name

	return out_name, out_color


class midi_autoinfo:
	def __init__(self):
		self.math_add = 0
		self.math_mul = 1
		self.defualtval = 0
		self.name = None
		self.fx_name = None
		self.fx_send = False
		self.uses_channel = False

	def get_autoloc(self, channel, fxoffset):
		autochannum = str(channel+1+fxoffset)

		if self.name:
			if not self.uses_channel: return ['fxmixer', autochannum, self.name]
			else: 
				if self.fx_send: return ['send', autochannum+'_reverb', self.name]
				else: return ['plugin', autochannum+'_reverb', self.name]

	def get_autoloc_track(self, trackid):
		if self.name:
			if not self.uses_channel: 
				return ['track', trackid, self.name]

def get_cc_info(ctrlnum):
	midiautoinfo = midi_autoinfo()

	if ctrlnum == 1: 
		midiautoinfo.name = 'modulation'

	elif ctrlnum == 2: 
		midiautoinfo.name = 'breath'

	elif ctrlnum == 7: 
		midiautoinfo.name = 'vol'
		midiautoinfo.defualtval = 1

	elif ctrlnum == 10: 
		midiautoinfo.name = 'pan'
		midiautoinfo.math_add = -0.5

	elif ctrlnum == 11: 
		midiautoinfo.name = 'expression'
		midiautoinfo.defualtval = 1

	elif ctrlnum == 64: 
		midiautoinfo.name = 'sustain'
		midiautoinfo.math_add = -0.5

	elif ctrlnum == 65: 
		midiautoinfo.name = 'portamento'
		midiautoinfo.math_add = -0.5

	elif ctrlnum == 66: 
		midiautoinfo.name = 'sostenuto'
		midiautoinfo.math_add = -0.5

	elif ctrlnum == 67: 
		midiautoinfo.name = 'soft_pedal'
		midiautoinfo.math_add = -0.5

	elif ctrlnum == 68: 
		midiautoinfo.name = 'legato'
		midiautoinfo.math_add = -0.5
				
	elif ctrlnum == 71: 
		midiautoinfo.name = 'resonance'
		midiautoinfo.fx_name = 'filter'
		midiautoinfo.defualtval = 1
				
	elif ctrlnum == 74: 
		midiautoinfo.name = 'cutoff'
		midiautoinfo.fx_name = 'filter'
		midiautoinfo.defualtval = 1
				
	elif ctrlnum == 91:
		midiautoinfo.name = 'amount'
		midiautoinfo.fx_send = True
		midiautoinfo.uses_channel = True
		midiautoinfo.fx_name = 'reverb'

	elif ctrlnum == 92:
		midiautoinfo.name = 'amount'
		midiautoinfo.uses_channel = True
		midiautoinfo.fx_name = 'tremolo'

	elif ctrlnum == 93:
		midiautoinfo.name = 'amount'
		midiautoinfo.uses_channel = True
		midiautoinfo.fx_name = 'chorus'

	elif ctrlnum == 94:
		midiautoinfo.name = 'amount'
		midiautoinfo.uses_channel = True
		midiautoinfo.fx_name = 'detune'

	elif ctrlnum == 95:
		midiautoinfo.name = 'amount'
		midiautoinfo.uses_channel = True
		midiautoinfo.fx_name = 'phaser'

	return midiautoinfo

