# SPDX-FileCopyrightText: 2024 SatyrDiamond
# SPDX-License-Identifier: GPL-3.0-or-later

from objects.data_bytes import bytereader
from objects.data_bytes import bytewriter
from functions import data_values
from objects.file import preset_vst3
from objects import globalstore
import struct
import platform
import os
import pathlib
import base64

import logging
logger_plugins = logging.getLogger('plugins')

cpu_arch_list = [64, 32]

def set_cpu_arch_list(cpu_arch_list_in):
	global cpu_arch_list
	cpu_arch_list = cpu_arch_list_in

def getplatformtxt(in_platform):
	if in_platform == 'win': platform_txt = 'win'
	if in_platform == 'lin': platform_txt = 'lin'
	else: 
		platform_architecture = platform.architecture()
		if platform_architecture[1] == 'WindowsPE': platform_txt = 'win'
		else: platform_txt = 'lin'
	return platform_txt

# -------------------- VST List --------------------

def check_exists(bycat, in_val):
	return globalstore.extplug.check('vst3', bycat, in_val)

def replace_data(convproj_obj, plugin_obj, bycat, platform, in_val, data):
	globalstore.extplug.load()
	global cpu_arch_list
	platformtxt = getplatformtxt(platform)

	pluginfo_obj = globalstore.extplug.get('vst3', bycat, in_val, platformtxt, cpu_arch_list)

	if pluginfo_obj.out_exists:
		if plugin_obj.type.type != 'vst3': plugin_obj.replace('external', 'vst3', platformtxt)
		else: plugin_obj.type.subtype = platformtxt

		plugin_obj.external__from_pluginfo_obj(convproj_obj, pluginfo_obj, cpu_arch_list)
		plugin_obj.external__set_chunk(data)
	else:
		pluginname = plugin_obj.external_info.name
		outtxt = '"'+str(in_val)+'" from '+str(bycat)
		if pluginname: outtxt = pluginname
		logger_plugins.warning('vst3: plugin not found in database: '+outtxt)

	return pluginfo_obj

def import_presetdata_raw(convproj_obj, plugin_obj, databytes, platform):
	byr_stream = bytereader.bytereader()
	byr_stream.load_raw(databytes)
	preset_obj = preset_vst3.vst3_main()
	preset_obj.parse(byr_stream)
	replace_data(convproj_obj, plugin_obj, 'id', platform, preset_obj.uuid, preset_obj.data)

def import_presetdata(convproj_obj, plugin_obj, byr_stream, platform):
	preset_obj = preset_vst3.vst3_main()
	preset_obj.parse(byr_stream)
	replace_data(convproj_obj, plugin_obj, 'id', platform, preset_obj.uuid, preset_obj.data)

def import_presetdata_file(convproj_obj, plugin_obj, fxfile, platform):
	preset_obj = preset_vst3.vst3_main()
	preset_obj.read_file(fxfile)
	replace_data(convproj_obj, plugin_obj, 'id', platform, preset_obj.uuid, preset_obj.data)

def export_presetdata(plugin_obj):
	byw_stream = bytewriter.bytewriter()
	preset_obj = preset_vst3.vst3_main()
	datatype = plugin_obj.external_info.datatype
	vstid = plugin_obj.external_info.id
	if vstid != None:
		preset_obj.uuid = vstid
		preset_obj.data = plugin_obj.rawdata_get('chunk')
		preset_obj.write(byw_stream)
		return byw_stream.getvalue()
	else:
		logger_plugins.warning('vst3: id is missing')
		return b''
