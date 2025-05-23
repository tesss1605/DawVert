# SPDX-FileCopyrightText: 2024 SatyrDiamond
# SPDX-License-Identifier: GPL-3.0-or-later

from objects.data_bytes import bytewriter
from objects.data_bytes import bytereader
from functions import data_values
from objects.file import preset_vst2
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
	globalstore.extplug.load()
	return globalstore.extplug.check('vst2', bycat, in_val)

def replace_data(convproj_obj, plugin_obj, bycat, platform, in_val, datatype, data, numparams):
	globalstore.extplug.load()
	global cpu_arch_list
	platformtxt = getplatformtxt(platform)

	pluginfo_obj = globalstore.extplug.get('vst2', bycat, in_val, platformtxt, cpu_arch_list)

	if pluginfo_obj.out_exists:
		if plugin_obj.type.type != 'vst2': 
			plugin_obj.replace_keepprog('external', 'vst2', platformtxt)
		else: 
			plugin_obj.type.subtype = platformtxt

		plugin_obj.external__from_pluginfo_obj(convproj_obj, pluginfo_obj, cpu_arch_list)

		if datatype == 'chunk':
			plugin_obj.external__set_chunk(data)
		if datatype == 'param':
			plugin_obj.external_info.datatype = 'param'
			plugin_obj.external_info.numparams = numparams
		if datatype == 'bank':
			plugin_obj.external_info.datatype = 'bank'
	else:
		pluginname = plugin_obj.external_info.name
		outtxt = '"'+str(in_val)+'" from '+str(bycat)
		if pluginname: outtxt = pluginname
		logger_plugins.warning('vst2: plugin not found in database: '+outtxt)

	return pluginfo_obj

def import_presetdata_file(convproj_obj, plugin_obj, platform, preset_filename):
	if os.path.exists(preset_filename):
		byr_stream = bytereader.bytereader()
		byr_stream.load_file(preset_filename)
		import_presetdata(convproj_obj, plugin_obj, byr_stream, platform)

def import_presetdata_raw(convproj_obj, plugin_obj, rawdata, platform):
	byr_stream = bytereader.bytereader()
	byr_stream.load_raw(rawdata)
	return import_presetdata(convproj_obj, plugin_obj, byr_stream, platform)

def import_presetdata(convproj_obj, plugin_obj, byr_stream, platform):
	fxp_obj = preset_vst2.vst2_main()
	fxp_obj.parse(byr_stream)
	vst_prog = fxp_obj.program
	if vst_prog.type in [1,4]:
		fpch = vst_prog.data
		if fpch.fourid: plugin_obj.external_info.fourid = fpch.fourid
		else: fpch.fourid = plugin_obj.external_info.fourid
		pluginfo_obj = replace_data(convproj_obj, plugin_obj, 'id', platform, fpch.fourid, 'chunk', fpch.chunk, None)
		plugin_obj.external_info.version_bytes = fpch.version
		if vst_prog.type == 4: plugin_obj.external_info.is_bank = True
		return pluginfo_obj
	if vst_prog.type == 2:
		fxck = vst_prog.data
		if fxck.fourid: plugin_obj.external_info.fourid = fxck.fourid
		else: fxck.fourid = plugin_obj.external_info.fourid
		pluginfo_obj = replace_data(convproj_obj, plugin_obj, 'id', platform, fxck.fourid, 'param', None, fxck.num_params)
		plugin_obj.external_info.version_bytes = fxck.version
		for c, p in enumerate(fxck.params): plugin_obj.params.add('ext_param_'+str(c), p, 'float')
		return pluginfo_obj
	if vst_prog.type == 3:
		fxck = vst_prog.data
		plugin_obj.current_program = fxck.current_program
		cvpj_programs = []
		plugin_obj.external_info.fourid = fxck.fourid
		for vst_program in fxck.programs:
			cvpj_program = {}
			if vst_program[1].type == 2:
				pprog = vst_program[1].data
				cvpj_program['datatype'] = 'params'
				cvpj_program['numparams'] = pprog.num_params
				cvpj_program['params'] = {}
				for paramnum, val in enumerate(pprog.params): cvpj_program['params'][str(paramnum)] = {'value': val}
				cvpj_program['program_name'] = pprog.prgname
				cvpj_programs.append(cvpj_program)
		return replace_data(convproj_obj, plugin_obj, 'id', platform, fxck.fourid, 'bank', None, cvpj_programs)

def export_presetdata_file(plugin_obj, preset_filename):
	filepath = pathlib.Path(preset_filename)
	if not os.path.exists(filepath.parent): os.makedirs(filepath.parent)
	fid = open(preset_filename, 'wb')
	fid.write(export_presetdata(plugin_obj))

def export_presetdata(plugin_obj):
	byw_stream = bytewriter.bytewriter()
	fxp_obj = preset_vst2.vst2_main()
	datatype = plugin_obj.external_info.datatype
	fourid = plugin_obj.external_info.fourid
	if fourid != None:
		if datatype == 'chunk':
			fxp_obj.program.type = 1 if not plugin_obj.external_info.is_bank else 4
			fxp_obj.program.data = preset_vst2.vst2_fxChunkSet(None)
			fpch = fxp_obj.program.data
			fpch.fourid = fourid
			fpch.version = plugin_obj.external_info.version_bytes
			fpch.num_programs = 1
			fpch.prgname = ''
			fpch.chunk = plugin_obj.rawdata_get('chunk')
			fxp_obj.write(byw_stream)
			return byw_stream.getvalue()

		if datatype == 'param':
			fxp_obj.program.type = 2
			fxp_obj.program.data = preset_vst2.vst2_fxProgram(None)
			fxck = fxp_obj.program.data
			fxck.fourid = fourid
			fxck.version = plugin_obj.external_info.version_bytes
			fxck.num_params = plugin_obj.external_info.numparams
			fxck.prgname = ''
			fxck.params = [plugin_obj.params.get('ext_param_'+str(c), 0).value for c in range(fxck.num_params)]
			fxp_obj.write(byw_stream)
			return byw_stream.getvalue()

		if datatype == 'bank':
			fxp_obj.program.type = 3
			fxp_obj.program.data = preset_vst2.vst2_fxBank(None)
			fxbk = fxp_obj.program.data
			fxbk.fourid = fourid
			fxbk.version = plugin_obj.external_info.version_bytes
			fxbk.current_program = plugin_obj.current_program
			programs = plugin_obj.external_info.programs
			for program in programs:
				fxck = preset_vst2.vst2_fxProgram(None)
				fxck.fourid = fourid
				fxck.version = fxbk.version
				fxck.num_params = program['numparams']
				fxck.prgname = program['program_name']
				fxck.params = [program['params'][str(c)]['value'] for c in range(fxck.num_params)]
				fxbk.programs.append([fourid, fxck])
			fxp_obj.write(byw_stream)
			return byw_stream.getvalue()
	else:
		logger_plugins.warning('vst2: fourid is missing')
		return b''

def export_presetdata_b64(plugin_obj):
	return base64.b64encode(export_presetdata(plugin_obj)).decode('ascii')