#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 SatyrDiamond
# SPDX-License-Identifier: GPL-3.0-or-later

from functions import plug_conv
from objects import core as dv_core
from objects import globalstore
from objects import format_detect
from objects.exceptions import ProjectFileParserException
from pathlib import Path
from plugins import base as dv_plugins

from PyQt6 import QtWidgets, uic, QtCore, QtGui
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QFileDialog

import logging
import os
import sys
import traceback

from objects.convproj import fileref
filesearcher = fileref.filesearcher

scriptfiledir = os.path.dirname(os.path.realpath(__file__))

from objects.ui.ui_pyqt import Ui_MainWindow

logging.disable(logging.INFO)

class converterstate():
	is_converting = False
	is_plugscan = False

dragdroploctexts = ['Beside Original', 'In "output" folder', 'Always out.*']

globalstore.extplug.load()

dawvert_intent = dv_core.dawvert_intent()
dawvert_intent.config_load('./__config/config.ini')

dawvert_core = dv_core.core()

dawvert_config__main = {}
dawvert_config__main['songnum'] = dawvert_intent.songnum
#dawvert_config__main['extrafile'] = dv_core.config_data.path_extrafile
dawvert_config__main['ui__drag_drop'] = 0
dawvert_config__main['ui__overwrite_out'] = False
dawvert_config__main['ui__auto_convert'] = False

dawvert_config__nopl_splitter = {}
dawvert_config__nopl_splitter['mode'] = dawvert_intent.splitter_mode
dawvert_config__nopl_splitter['detect_start'] = dawvert_intent.splitter_detect_start
dawvert_config__mi2m = {}

def debugtxt(intxt):
	if intxt == 'route': return 'RO'
	if intxt == 'rack': return 'CH'
	if intxt == 'groupreturn': return 'GR'
	return '__'

class ConversionWorker(QtCore.QObject):
	finished = QtCore.pyqtSignal()
	update_ui = QtCore.pyqtSignal(list)

	def __init__(self, *args, **kwargs):
		super(ConversionWorker, self).__init__(*args, **kwargs)

	def run(self):
		try:
			converterstate.is_converting = True

			inname = dawvert_core.input_get_current_name()
			outname = dawvert_core.output_get_current_name()

			plug_conv.load_plugins()

			file_name = os.path.splitext(os.path.basename(dawvert_intent.input_file))[0]

			dawvert_intent.flags_compat = []
			if 'output_unused_nle' in dawvert_config__mi2m: dawvert_intent.flags_compat.append('mi2m-output-unused-nle')
			dawvert_intent.splitter_mode = dawvert_config__nopl_splitter['mode']
			dawvert_intent.splitter_detect_start = dawvert_config__nopl_splitter['detect_start']

			if 'songnum' in dawvert_config__main: dawvert_intent.songnum = dawvert_config__main['songnum']
#			if 'extrafile' in dawvert_config__main: dv_core.config_data.path_extrafile = dawvert_config__main['extrafile']

			if dawvert_intent.output_samples:
				dawvert_intent.output_samples += '/'

				dawvert_intent.path_samples['extracted'] = dawvert_intent.output_samples+'extracted/'
				dawvert_intent.path_samples['downloaded'] = dawvert_intent.output_samples+'downloaded/'
				dawvert_intent.path_samples['generated'] = dawvert_intent.output_samples+'generated/'
				dawvert_intent.path_samples['converted'] = dawvert_intent.output_samples+'converted/'

			else:
				dawvert_intent.set_projname_path(file_name)

			os.makedirs(dawvert_intent.path_samples['extracted'], exist_ok=True)
			os.makedirs(dawvert_intent.path_samples['downloaded'], exist_ok=True)
			os.makedirs(dawvert_intent.path_samples['generated'], exist_ok=True)
			os.makedirs(dawvert_intent.path_samples['converted'], exist_ok=True)

			filesearcher.reset()
			filesearcher.add_basepath('projectfile', os.path.dirname(dawvert_intent.input_file))
			filesearcher.add_basepath('dawvert', scriptfiledir)

			filesearcher.add_searchpath_partial('projectfile', '.', 'projectfile')
			filesearcher.add_searchpath_full_append('projectfile', os.path.dirname(dawvert_intent.input_file), None)

			filesearcher.add_searchpath_full_filereplace('extracted', dawvert_intent.path_samples['extracted'], None)
			filesearcher.add_searchpath_full_filereplace('downloaded', dawvert_intent.path_samples['downloaded'], None)
			filesearcher.add_searchpath_full_filereplace('generated', dawvert_intent.path_samples['generated'], None)
			filesearcher.add_searchpath_full_filereplace('converted', dawvert_intent.path_samples['converted'], None)
			filesearcher.add_searchpath_full_filereplace('external_data', os.path.join(scriptfiledir, '__external_data'), None)

			self.update_ui.emit([1, 0])
			self.update_ui.emit([0, 'Processing Input...'])
			dawvert_core.parse_input(dawvert_intent)
			self.update_ui.emit([1, 25])
			self.update_ui.emit([0, 'Converting Project Type and Samples...'])
			dawvert_core.convert_type_output(dawvert_intent)
			self.update_ui.emit([1, 50])
			self.update_ui.emit([0, 'Converting Plugins...'])
			dawvert_core.convert_plugins(dawvert_intent)
			self.update_ui.emit([1, 75])
			self.update_ui.emit([0, 'Processing Output...'])
			dawvert_core.parse_output(dawvert_intent)
			converterstate.is_converting = False
			self.update_ui.emit([1, 100])
			self.update_ui.emit([2, ['OK', '']])
		except ProjectFileParserException:
			converterstate.is_converting = False
			ex_type, ex_value, ex_traceback = sys.exc_info()
			self.update_ui.emit([2, ['Project File Error', str(ex_value)]])
		except SystemExit:
			converterstate.is_converting = False
			ex_type, ex_value, ex_traceback = sys.exc_info()
			self.update_ui.emit([2, ['Exited with no output, See Console.', '']])
			print(traceback.format_exc())
		except:
			converterstate.is_converting = False
			ex_type, ex_value, ex_traceback = sys.exc_info()
			self.update_ui.emit([2, ['Error. See Console.', ex_type.__name__+': '+str(ex_value)]])
			print(traceback.format_exc())
		self.finished.emit()

class PlugScanWorker(QtCore.QObject):
	finished = QtCore.pyqtSignal()
	update_ui = QtCore.pyqtSignal(list)

	def __init__(self, *args, **kwargs):
		super(PlugScanWorker, self).__init__(*args, **kwargs)

	def run(self):
		if not converterstate.is_plugscan:
			try:
				oldplugcount = globalstore.extplug.count('all')
				converterstate.is_plugscan = True
				dv_plugins.load_plugindir('externalsearch', '')
		
				externalsearch_obj = dv_plugins.create_selector('externalsearch')
				for shortname, dvplugin in externalsearch_obj.iter_dvp():
					self.update_ui.emit([0, 'Scanning '+dvplugin.name+'...'])
					dvplugin.plug_obj.import_plugins()
				globalstore.extplug.write()
	
				newplugcount = globalstore.extplug.count('all')
				if newplugcount>oldplugcount:
					self.update_ui.emit([0, 'Done, '+str(newplugcount-oldplugcount)+' new plugins found.'])
				else:
					self.update_ui.emit([0, 'Done.'])

				vst2_count = globalstore.extplug.count('vst2')
				vst3_count = globalstore.extplug.count('vst3')
				clap_count = globalstore.extplug.count('clap')
				self.update_ui.emit([1, [vst2_count, vst3_count, clap_count]])
			except:
				self.update_ui.emit([0, 'Error. See Console.'])
				print(traceback.format_exc())
				pass
	
			converterstate.is_plugscan = False
		self.finished.emit()

class configinput():
	qt_ui = None
	qt_item = None
	d_data = {}
	d_key = None
	ctrltype = None

	def change_control(ctrltype):
		configinput.ctrltype = ctrltype
		qt_ui = configinput.qt_ui
		if configinput.ctrltype == 'int':
			qt_ui.ConfigInt.show()
			qt_ui.ConfigFloat.hide()
			qt_ui.ConfigString.hide()
			qt_ui.ConfigBool.hide()
			qt_ui.ConfigInt.setValue(configinput.get_value())
		if configinput.ctrltype == 'float':
			qt_ui.ConfigInt.hide()
			qt_ui.ConfigFloat.show()
			qt_ui.ConfigString.hide()
			qt_ui.ConfigBool.hide()
			qt_ui.ConfigFloat.setValue(configinput.get_value())
		if configinput.ctrltype == 'str':
			qt_ui.ConfigInt.hide()
			qt_ui.ConfigFloat.hide()
			qt_ui.ConfigString.show()
			qt_ui.ConfigBool.hide()
			qt_ui.ConfigString.setText(configinput.get_value())
		if configinput.ctrltype == 'bool':
			qt_ui.ConfigInt.hide()
			qt_ui.ConfigFloat.hide()
			qt_ui.ConfigString.hide()
			qt_ui.ConfigBool.show()
			qt_ui.ConfigBool.setChecked(configinput.get_value())
				
	def update_value(value):
		value = configinput.d_data[configinput.d_key] = bool(value) if configinput.ctrltype == 'bool' else value
		if configinput.qt_item:
			configinput.qt_item.setText(1, str(value))

	def get_value():
		if configinput.d_key in configinput.d_data: return configinput.d_data[configinput.d_key]
		else:
			if configinput.ctrltype == 'int': return 0
			if configinput.ctrltype == 'float': return 0.0
			if configinput.ctrltype == 'str': return ''
			if configinput.ctrltype == 'bool': return False

	def select_item():
		qt_ui = configinput.qt_ui
		selected_items = qt_ui.ConfigList.selectedItems()
		if len(selected_items)==1:
			ptrid = id(selected_items[0])
			if ptrid in configdata.ptrnames:
				configinput.qt_item = selected_items[0]
				configinput.d_data, configinput.d_key, ctrltype, listpart = configdata.ptrnames[ptrid]
				configinput.change_control(ctrltype)

class configdata():
	ptrnames = {}

	def __init__(self, qt_ui, configparts, configlabel, dictdata):
		listtree_temp = QtWidgets.QTreeWidgetItem(qt_ui.ConfigList)
		listtree_temp.setText(0, configlabel)
		self.configparts = configparts
		self.dictdata = dictdata

		for key, data in configparts.items():
			valuetype, fullname = data

			listpart_temp = QtWidgets.QTreeWidgetItem(listtree_temp)
			listpart_temp.setText(0, fullname)
			if key in dictdata: listpart_temp.setText(1, str(dictdata[key]))
			configdata.ptrnames[id(listpart_temp)] = [dictdata, key, valuetype, listpart_temp]

configparts_main = {
	'songnum': ['int', 'Song Number'],
#	'extrafile': ['str', 'Extra File'],
}

configparts_soundfont = {
	'gm': ['str', 'GM'],
	'xg': ['str', 'XG'],
	'gs': ['str', 'GS'],
	'mt32': ['str', 'MT32'],
	'mariopaint': ['str', 'Mario Paint']
}

configparts_splitter = {
	'mode': ['int', 'Mode'],
	'detect_start': ['bool', 'Detect Start']
}

configparts_mi2m = {
	'output_unused_nle': ['bool', 'OutUnused']
}

filedetector_obj = format_detect.file_detector()
filedetector_obj.load_def('data_main/autodetect.xml')

DEBUG_VIEW = 0

class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
	def __init__(self, *args, obj=None, **kwargs):
		super(MainWindow, self).__init__(*args, **kwargs)

		wid = QtWidgets.QWidget(self)
		self.ui = Ui_MainWindow()
		self.ui.setupUi(wid)
		self.setWindowTitle('DawVert - The DAW Converter')
		self.setWindowIcon(QtGui.QIcon('icon.png'))
		self.setCentralWidget(wid)
		self.setAcceptDrops(True)

		layout = QtWidgets.QVBoxLayout()

		configinput.qt_ui = self.ui

		self.ui.InputFileButton.clicked.connect(self.__choose_input)
		self.ui.OutputFileButton.clicked.connect(self.__choose_output)
		self.ui.OutputSampleButton.clicked.connect(self.__choose_samples)

		self.ui.ListWidget_InPlugSet.currentRowChanged.connect(self.__change_input_plugset)
		self.ui.ListWidget_InPlugin.currentRowChanged.connect(self.__change_input_plugin_nofb)

		self.ui.ListWidget_OutPlugSet.currentRowChanged.connect(self.__change_output_plugset)
		self.ui.ListWidget_OutPlugin.currentRowChanged.connect(self.__change_output_plugin)

		self.ui.ConvertButton.setEnabled(False)
		self.ui.ConvertButton.clicked.connect(self.__do_convert)
		self.ui.PluginScanButton.clicked.connect(self.__do_extplugscan)

		self.ui.AutoDetectButton.clicked.connect(self.__do_auto_detect)

		for x in dawvert_core.input_get_pluginsets_names(): self.ui.ListWidget_InPlugSet.addItem(x)
		for x in dawvert_core.output_get_pluginsets_names(): self.ui.ListWidget_OutPlugSet.addItem(x)

		self.ui.ExtPlugG_Shareware.clicked.connect(self.__extplugcheck_shareware)
		self.ui.ExtPlugG_FOSS.clicked.connect(self.__extplugcheck_foss)
		self.ui.ExtPlugG_Old.clicked.connect(self.__extplugcheck_old)
		self.ui.ExtPlugG_NonFree.clicked.connect(self.__extplugcheck_nonfree)

		self.__update_convst()
		self.__set_checks()
		self.__display_extplugcount()

		configinput.change_control('float')

		self.ui.ConfigInt.valueChanged.connect(configinput.update_value)
		self.ui.ConfigFloat.valueChanged.connect(configinput.update_value)
		self.ui.ConfigString.textChanged.connect(configinput.update_value)
		self.ui.ConfigBool.stateChanged.connect(configinput.update_value)

		for dragdroploctext in dragdroploctexts:
			self.ui.DndOutPathSelection.addItem(dragdroploctext)
		self.ui.DndOutPathSelection.currentIndexChanged.connect(self.__change_dd_setting)
		self.ui.OverwriteOut.stateChanged.connect(self.__change_overwrite_setting)
		self.ui.AutoConvert.stateChanged.connect(self.__change_auto_convert_setting)

		configdata(self.ui, configparts_main, 'Main', dawvert_config__main)
		configdata(self.ui, configparts_soundfont, 'Soundfonts', dawvert_intent.path_soundfonts)
		configdata(self.ui, configparts_splitter, 'NoPl Splitter', dawvert_config__nopl_splitter)
		configdata(self.ui, configparts_mi2m, 'MI2M', dawvert_config__mi2m)

		self.ui.ConfigList.itemSelectionChanged.connect(configinput.select_item)

		#self.ui.ConfigList.topLevelItem(0).setText(0, 'Input')
		#self.ui.ConfigList.topLevelItem(0).setText(0, 'Output')
		#self.ui.ConfigList.topLevelItem(0).setText(0, 'SF2')
		#self.ui.ConfigList.topLevelItem(0).setText(0, 'Splitter')
		testdict = {}

	def __display_extplugcount(self):
		vst2_count = globalstore.extplug.count('vst2')
		vst3_count = globalstore.extplug.count('vst3')
		clap_count = globalstore.extplug.count('clap')
		self.ui.ExtCountVST2.setText('VST2: '+str(vst2_count))
		self.ui.ExtCountVST3.setText('VST3: '+str(vst3_count))
		self.ui.ExtCountCLAP.setText('CLAP: '+str(clap_count))

	def __set_checks(self):
		extplug_cat = dawvert_intent.extplug_cat
		self.ui.ExtPlugG_Shareware.setChecked('shareware' in extplug_cat)
		self.ui.ExtPlugG_FOSS.setChecked('foss' in extplug_cat)
		self.ui.ExtPlugG_Old.setChecked('old' in extplug_cat)
		self.ui.ExtPlugG_NonFree.setChecked('nonfree' in extplug_cat)

	def __plugcatmod(self, name, isset):
		extplug_cat = dawvert_intent.extplug_cat
		if name not in extplug_cat and isset: extplug_cat.append(name)
		if name in extplug_cat and not isset: extplug_cat.remove(name)

	def __extplugcheck_shareware(self, event):
		self.__plugcatmod('shareware', event)

	def __extplugcheck_foss(self, event):
		self.__plugcatmod('foss', event)

	def __extplugcheck_old(self, event):
		self.__plugcatmod('old', event)

	def __extplugcheck_nonfree(self, event):
		self.__plugcatmod('nonfree', event)

	def dragEnterEvent(self, event):
		if event.mimeData().hasUrls(): event.accept()
		else: event.ignore()

	def set_dd_output(self, f):
		self.ui.InputFilePath.setText(f)
		if dawvert_config__main['ui__drag_drop'] == 0:
			self.ui.OutputFilePath.setText(f.rsplit('.',1)[0])
			self.ui.OutputSamplePath.setText(f.rsplit('.',1)[0]+'_samples')
		if dawvert_config__main['ui__drag_drop'] == 1:
			outfile = os.path.join(globalstore.dawvert_script_path, 'output', os.path.basename(f))
			self.ui.OutputFilePath.setText(outfile.rsplit('.',1)[0])
			self.ui.OutputSamplePath.setText(outfile.rsplit('.',1)[0]+'_samples')
		if dawvert_config__main['ui__drag_drop'] == 2:
			outfile = os.path.join(globalstore.dawvert_script_path, 'out')
			self.ui.OutputFilePath.setText(outfile.rsplit('.',1)[0])
			samplepath = os.path.join(globalstore.dawvert_script_path, '__samples', os.path.basename(f))
			self.ui.OutputSamplePath.setText(samplepath)

	def dropEvent(self, event):
		files = [u.toLocalFile() for u in event.mimeData().urls()]
		if files:
			self.set_dd_output(files[0])
			self.__do_auto_detect()
			self.__change_output_path()
			if dawvert_config__main['ui__auto_convert']:
				if self.__can_convert(): self.__do_convert()

	def __change_dd_setting(self, num):
		dawvert_config__main['ui__drag_drop'] = num

	def __change_overwrite_setting(self, val):
		dawvert_config__main['ui__overwrite_out'] = val
		self.__update_convst()

	def __change_auto_convert_setting(self, val):
		dawvert_config__main['ui__auto_convert'] = val

	def __choose_input(self):
		filename, _filter = QFileDialog.getOpenFileName(self, "Open File", "", "")
		self.ui.InputFilePath.setText(filename)

	def __choose_output(self):
		filename, _filter = QFileDialog.getSaveFileName(self, "Save File", "", "")
		self.ui.OutputFilePath.setText(filename)

	def __choose_samples(self):
		filename, _filter = QFileDialog.getSaveFileName(self, "Save File", "", "")
		self.ui.OutputSamplePath.setText(filename)

	def __do_auto_detect(self):
		filename = self.ui.InputFilePath.text()
		if os.path.exists(filename):
			try:
				plugsetlist = list(dv_core.pluginsets_input)
				outdetected = filedetector_obj.detect_file(filename)
				if outdetected:
					plugset, plugname = outdetected
					self.__change_input_plugset_named(plugset)
					self.ui.ListWidget_InPlugSet.setCurrentRow(plugsetlist.index(plugset))
					plugnames = dawvert_core.input_get_plugins()
					self.ui.ListWidget_InPlugin.setCurrentRow(plugnames.index(plugname))
					dawvert_core.input_set(plugname)
					return True
				return False
			except:
				pass

	def __can_convert(self):
		dawvert_intent.set_file_input(self.ui.InputFilePath.text().replace('/', '\\'))
		dawvert_intent.set_file_output(self.ui.OutputFilePath.text().replace('/', '\\'))
		inplug = dawvert_core.input_get_current()
		outplug = dawvert_core.output_get_current()
		not_same = dawvert_intent.input_file!=dawvert_intent.output_file
		out_exists = (not os.path.exists(dawvert_intent.output_file)) or dawvert_config__main['ui__overwrite_out']
		in_usable, in_usable_msg = dawvert_core.input_get_usable()
		out_usable, out_usable_msg = dawvert_core.output_get_usable()
		return bool(inplug and outplug and not_same and out_exists and in_usable and out_usable)

	def __update_convst(self):
		dawvert_intent.input_file = self.ui.InputFilePath.text().replace('/', '\\')
		dawvert_intent.output_file = self.ui.OutputFilePath.text().replace('/', '\\')
		inplug = dawvert_core.input_get_current()
		outplug = dawvert_core.output_get_current()
		not_same = dawvert_intent.input_file!=dawvert_intent.output_file
		out_exists = (not os.path.exists(dawvert_intent.output_file)) or dawvert_config__main['ui__overwrite_out']
		in_usable, in_usable_msg = dawvert_core.input_get_usable()
		out_usable, out_usable_msg = dawvert_core.output_get_usable()
		outstate = bool(inplug and outplug and not_same and out_exists and in_usable and out_usable)

		self.ui.ConvertButton.setEnabled(outstate and not converterstate.is_converting)
		if converterstate.is_converting: 
			self.ui.StatusText.setText('Status: Converting')
			self.ui.SubStatusText.setText('')
			return False
		elif not outstate:
			if not DEBUG_VIEW: self.ui.StatusText.setText('Status: Not Ready')
			else: self.ui.StatusText.setText('Status: Not Ready (DEBUG VIEW ON)')
			if not dawvert_intent.input_file: self.ui.SubStatusText.setText('No input file.')
			elif not dawvert_intent.output_file: self.ui.SubStatusText.setText('No output file.')
			elif not inplug: self.ui.SubStatusText.setText('Input plugin not selected.')
			elif not outplug: self.ui.SubStatusText.setText('Output plugin not selected.')
			elif not not_same: self.ui.SubStatusText.setText('Not overwriting input file.')
			elif not out_exists: self.ui.SubStatusText.setText('Not overwriting output file.')
			elif not in_usable: 
				self.ui.StatusText.setText('Status: Input Plugin Unusable')
				self.ui.SubStatusText.setText(in_usable_msg)
			elif not out_usable: 
				self.ui.StatusText.setText('Status: Output Plugin Unusable')
				self.ui.SubStatusText.setText(out_usable_msg)
			return False
		else:
			if not DEBUG_VIEW: self.ui.StatusText.setText('Status: Ready')
			else: self.ui.StatusText.setText('Status: Ready (DEBUG VIEW ON)')
			self.ui.SubStatusText.setText('')
			return True


	def __change_input_plugset_named(self, plugsetname):
		dawvert_core.input_load_plugins(plugsetname)
		self.__update_input_plugins()
		self.__change_input_plugin(0)

	def __change_input_plugset(self, num):
		plugsetname = dawvert_core.input_get_pluginsets_index(num)
		dawvert_core.input_load_plugins(plugsetname)
		self.__update_input_plugins()
		self.__change_input_plugin(0)

	def __change_input_plugin(self, num):
		pluginname = dawvert_core.input_get_plugins_index(num)
		if pluginname: dawvert_core.input_set(pluginname)
		else: 
			plugnames = dawvert_core.input_get_plugins()
			if plugnames: dawvert_core.input_set(plugnames[0])
		self.__update_convst()

	def __change_input_plugin_nofb(self, num):
		pluginname = dawvert_core.input_get_plugins_index(num)
		if pluginname: dawvert_core.input_set(pluginname)
		self.__update_convst()

	def __update_input_plugins(self):
		self.ui.ListWidget_InPlugin.clear()
		if not DEBUG_VIEW:
			for x in dawvert_core.input_get_plugins_names():
				self.ui.ListWidget_InPlugin.addItem(x)
		else:
			props = dawvert_core.input_get_plugins_props()
			for n, x in enumerate(dawvert_core.input_get_plugins_names()):
				o = x
				fxt = debugtxt(props[n].fxtype)
				fdt = props[n].projtype.upper()
				if DEBUG_VIEW == 1: o = ('[%s] ' % fxt)+o
				if DEBUG_VIEW == 2: o = ('[%s] ' % fdt)+o
				if DEBUG_VIEW == 3: o = ('[%s:%s] ' % (fxt, fdt)+o)
				self.ui.ListWidget_InPlugin.addItem(o)

	def __change_output_plugset(self, num):
		plugsetname = dawvert_core.output_get_pluginsets_index(num)
		dawvert_core.output_load_plugins(plugsetname)
		self.__update_output_plugins()
		self.__change_output_path()

	def __change_output_plugin(self, num):
		pluginname = dawvert_core.output_get_plugins_index(num)
		if pluginname: dawvert_core.output_set(pluginname)
		self.__update_convst()
		self.__change_output_path()

	def __change_output_path(self):
		outfound = dawvert_core.output_get_current()
		filename = self.ui.OutputFilePath.text()
		if outfound and filename:
			try:
				fileext = dawvert_core.output_get_extension()
				filename = Path(filename)
				filename = filename.with_suffix('.'+fileext)
				self.ui.OutputFilePath.setText(str(filename))
			except:
				pass
		self.__update_convst()

	def __update_output_plugins(self):
		self.ui.ListWidget_OutPlugin.clear()
		if not DEBUG_VIEW:
			for x in dawvert_core.output_get_plugins_names():
				self.ui.ListWidget_OutPlugin.addItem(x)
		else:
			props = dawvert_core.output_get_plugins_props()
			for n, x in enumerate(dawvert_core.output_get_plugins_names()):
				o = x
				fxt = debugtxt(props[n].fxtype)
				fdt = props[n].projtype.upper()
				if DEBUG_VIEW == 1: o = ('[%s] ' % fxt)+o
				if DEBUG_VIEW == 2: o = ('[%s] ' % fdt)+o
				if DEBUG_VIEW == 3: o = ('[%s:%s] ' % (fxt, fdt)+o)
				self.ui.ListWidget_OutPlugin.addItem(o)


	def __update_ui_ele(self, n):
		update_type, update_data = n
		if update_type == 0:
			self.ui.SubStatusText.setText(update_data)
		if update_type == 1:
			self.ui.progressBar.setValue(update_data)
		if update_type == 2:
			self.ui.StatusText.setText('Status: '+update_data[0])
			self.ui.SubStatusText.setText(update_data[1])

	def __update_ui_ele_ext(self, n):
		update_type, update_data = n
		if update_type == 0:
			self.ui.PluginScanStatus.setText(update_data)
		if update_type == 1:
			self.ui.ExtCountVST2.setText('VST2: '+str(update_data[0]))
			self.ui.ExtCountVST3.setText('VST3: '+str(update_data[1]))
			self.ui.ExtCountCLAP.setText('CLAP: '+str(update_data[2]))

	def __do_convert(self):
		if not converterstate.is_converting:
			converterstate.is_converting = True
			self.__update_convst()

			dawvert_intent.input_file = self.ui.InputFilePath.text()
			dawvert_intent.output_file = self.ui.OutputFilePath.text()
			dawvert_intent.output_samples = self.ui.OutputSamplePath.text()
	
			self.thread = QtCore.QThread(parent=self)
			self.worker = ConversionWorker()
			self.worker.moveToThread(self.thread)
			self.thread.started.connect(self.worker.run)
			self.worker.finished.connect(self.thread.quit)
			self.worker.finished.connect(self.worker.deleteLater)
			self.thread.finished.connect(self.thread.deleteLater)
			self.worker.update_ui.connect(self.__update_ui_ele)
			self.thread.start()

	def __do_extplugscan(self):
		if not converterstate.is_plugscan:
			self.thread = QtCore.QThread(parent=self)
			self.worker = PlugScanWorker()
			self.worker.moveToThread(self.thread)
			self.thread.started.connect(self.worker.run)
			self.worker.finished.connect(self.thread.quit)
			self.worker.finished.connect(self.worker.deleteLater)
			self.thread.finished.connect(self.thread.deleteLater)
			self.worker.update_ui.connect(self.__update_ui_ele_ext)
			self.thread.start()

app = QtWidgets.QApplication(sys.argv)

window = MainWindow()
window.show()
app.exec()