# SPDX-FileCopyrightText: 2024 SatyrDiamond
# SPDX-License-Identifier: GPL-3.0-or-later

import plugins
import logging
from functions import data_bytes
from functions import extpluglog

logger_plugconv = logging.getLogger('plugconv')

class plugconv(plugins.base):
	def is_dawvert_plugin(self):
		return 'plugconv'
	
	def get_priority(self):
		return -90
	
	def get_prop(self, in_dict): 
		in_dict['in_plugins'] = [['universal', 'midi', None]]
		in_dict['in_daws'] = []
		in_dict['out_plugins'] = [['universal', 'soundfont2', None]]
		in_dict['out_daws'] = []

	def convert(self, convproj_obj, plugin_obj, pluginid, dawvert_intent):

		if convproj_obj.type not in ['cm', 'cs']:
			sf2_loc = None
			if 'global' in dawvert_intent.path_soundfonts:
				sf2_loc = dawvert_intent.path_soundfonts['global']
	
			if sf2_loc == None: 
				mididevice = plugin_obj.datavals.get('device', 'gm')
				if mididevice in dawvert_intent.path_soundfonts:
					if dawvert_intent.path_soundfonts[mididevice]:
						logger_plugconv.info('Using '+mididevice.upper()+' SF2.')
						sf2_loc = dawvert_intent.path_soundfonts[mididevice]
	
			if sf2_loc:
				extpluglog.convinternal('MIDI', 'MIDI', 'SoundFont2', 'SoundFont2')
				plugin_obj.replace('universal', 'soundfont2', None)
				convproj_obj.fileref__add(sf2_loc, sf2_loc, None)
				plugin_obj.filerefs['file'] = sf2_loc
				return 1

		#if sf2_loc == None: print('[plug-conv] No Soundfont Argument or Configured:',pluginid)
		return 2