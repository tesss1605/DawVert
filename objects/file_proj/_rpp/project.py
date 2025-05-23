from objects.file_proj._rpp import func as reaper_func
from objects.file_proj._rpp import track as rpp_track
from objects.file_proj._rpp import fxchain as rpp_fxchain
from objects.file_proj._rpp import env as rpp_env

rvd = reaper_func.rpp_value
rvs = reaper_func.rpp_value.single_var
robj = reaper_func.rpp_obj
ts = reaper_func.to_string

markertypes = [int, float, str, int, int, int, str, str, int]

class rpp_project:
	def __init__(self):
		self.groupoverride = rvd([0,0,0], None, None, True)
		self.mixeruiflags = rvd([11,48], None, [int, int], True)
		self.projoffs = rvd([0,0,0], None, None, True)
		self.maxprojlen = rvd([0,0], None, None, True)
		self.grid = rvd([3199,8,1,8,1,0,0,0], None, None, True)
		self.timemode = rvd([1,5,-1,30,0,0,-1], None, None, True)
		self.video_config = rvd([0,0,256], None, None, False)
		self.zoom = rvd([100,0,0], None, None, True)
		self.vzoomex = rvd([6,0], None, None, True)
		self.smptesync = rvd([0,30,100,40,1000,300,0,0,1,0,0], None, None, True)
		self.loopgran = rvd([0,4], None, None, True)
		self.record_path = rvd(["Media",""], None, [str, str], True)
		self.render_fmt = rvd([0,2,0], None, None, True)
		self.render_range = rvd([1,0,0,18,1000], None, None, True)
		self.render_resample = rvd([3,0,1], None, None, True)
		self.defpitchmode = rvd([589824,0], None, None, True)
		self.samplerate = rvd([44100,0,0], None, None, True)
		self.tempo = rvd([120,4,4], ['tempo','num','denom'], None, True)
		self.playrate = rvd([1,0,0.25,4.0], None, None, True)
		self.selection = rvd([0,0], ['start','end'], [float, float], True)
		self.selection2 = rvd([0,0], ['start','end'], [float, float], True)
		self.mastertrackheight = rvd([0,0], None, None, True)
		self.mastertrackview = rvd([0,0.6667,0.5,0.5,0,0,0,0,0,0,0,0,0,0], None, None, True)
		self.masterhwout = rvd([0,0,1,0,0,0,0,-1], None, None, True)
		self.master_nch = rvd([2,2], None, None, True)
		self.master_volume = rvd([1,0,-1,-1,1], None, None, True)
		self.notes_vals = rvd([0,2], None, [int, int], True)
		self.notes_data = []
		self.record_cfg = b''
		self.applyfx_cfg = b''
		self.render_cfg = b''
		self.title = rvs('', str, False)
		self.author = rvs('', str, False)
		self.ripple = rvs(0, float, True)
		self.autoxfade = rvs(1, float, True)
		self.envattach = rvs(3, float, True)
		self.pooledenvattach = rvs(0, float, True)
		self.envfadesz10 = rvs(0, float, False)
		self.peakgain = rvs(1, float, True)
		self.feedback = rvs(0, float, True)
		self.panlaw = rvs(1, float, True)
		self.panmode = rvs(0, float, False)
		self.panlawflags = rvs(0, float, False)
		self.cursor = rvs(0, float, True)
		self.use_rec_cfg = rvs(0, float, True)
		self.recmode = rvs(1, float, True)
		self.loop = rvs(0, float, True)
		self.render_file = rvs("", str, True)
		self.render_pattern = rvs('', str, False)
		self.render_1x = rvs(0, float, True)
		self.render_addtoproj = rvs(0, float, True)
		self.render_stems = rvs(0, float, True)
		self.render_dither = rvs(0, float, True)
		self.timelockmode = rvs(1, float, True)
		self.tempoenvlockmode = rvs(2, float, True)
		self.itemmix = rvs(1, float, True)
		self.takelane = rvs(1, float, True)
		self.lock = rvs(1, float, True)
		self.global_auto = rvs(-1, float, True)
		self.masterautomode = rvs(0, float, True)
		self.masterpeakcol = rvs(16576, float, True)
		self.mastermutesolo = rvs(0, float, True)
		self.master_panmode = rvs(0, float, False)
		self.master_panlawflags = rvs(0, float, False)
		self.master_fx = rvs(1, float, True)
		self.master_sel = rvs(0, float, True)
		self.masterfxlist = rvs(0, float, False)
		self.masterplayspeedenv = rpp_env.rpp_env()
		self.tempoenvex = rpp_env.rpp_env()
		self.tracks = []
		self.markers = []
		self.pooledenvs = []

	def load(self, rpp_data):
		for name, is_dir, values, inside_dat in reaper_func.iter_rpp(rpp_data):
			if name == 'TITLE': self.title.set(values[0])
			if name == 'AUTHOR': self.author.set(values[0])
			if name == 'RECORD_CFG': self.record_cfg = reaper_func.getbin(inside_dat)
			if name == 'APPLYFX_CFG': self.applyfx_cfg = reaper_func.getbin(inside_dat)
			if name == 'RENDER_CFG': self.render_cfg = reaper_func.getbin(inside_dat)
			if name == 'RIPPLE': self.ripple.set(values[0])
			if name == 'GROUPOVERRIDE': self.groupoverride.read(values)
			if name == 'AUTOXFADE': self.autoxfade.set(values[0])
			if name == 'ENVATTACH': self.envattach.set(values[0])
			if name == 'POOLEDENVATTACH': self.pooledenvattach.set(values[0])
			if name == 'MIXERUIFLAGS': self.mixeruiflags.read(values)
			if name == 'ENVFADESZ10': self.envfadesz10.set(values[0])
			if name == 'PEAKGAIN': self.peakgain.set(values[0])
			if name == 'FEEDBACK': self.feedback.set(values[0])
			if name == 'PANLAW': self.panlaw.set(values[0])
			if name == 'PROJOFFS': self.projoffs.read(values)
			if name == 'MAXPROJLEN': self.maxprojlen.read(values)
			if name == 'GRID': self.grid.read(values)
			if name == 'TIMEMODE': self.timemode.read(values)
			if name == 'VIDEO_CONFIG': self.video_config.read(values)
			if name == 'PANMODE': self.panmode.set(values[0])
			if name == 'PANLAWFLAGS': self.panlawflags.set(values[0])
			if name == 'CURSOR': self.cursor.set(values[0])
			if name == 'ZOOM': self.zoom.read(values)
			if name == 'VZOOMEX': self.vzoomex.read(values)
			if name == 'USE_REC_CFG': self.use_rec_cfg.set(values[0])
			if name == 'RECMODE': self.recmode.set(values[0])
			if name == 'SMPTESYNC': self.smptesync.read(values)
			if name == 'LOOP': self.loop.set(values[0])
			if name == 'LOOPGRAN': self.loopgran.read(values)
			if name == 'RECORD_PATH': self.record_path.read(values)
			if name == 'RENDER_FILE': self.render_file.set(values[0])
			if name == 'RENDER_PATTERN': self.render_pattern.set(values[0])
			if name == 'RENDER_FMT': self.render_fmt.read(values)
			if name == 'RENDER_1X': self.render_1x.set(values[0])
			if name == 'RENDER_RANGE': self.render_range.read(values)
			if name == 'RENDER_RESAMPLE': self.render_resample.read(values)
			if name == 'RENDER_ADDTOPROJ': self.render_addtoproj.set(values[0])
			if name == 'RENDER_STEMS': self.render_stems.set(values[0])
			if name == 'RENDER_DITHER': self.render_dither.set(values[0])
			if name == 'TIMELOCKMODE': self.timelockmode.set(values[0])
			if name == 'TEMPOENVLOCKMODE': self.tempoenvlockmode.set(values[0])
			if name == 'ITEMMIX': self.itemmix.set(values[0])
			if name == 'DEFPITCHMODE': self.defpitchmode.read(values)
			if name == 'TAKELANE': self.takelane.set(values[0])
			if name == 'SAMPLERATE': self.samplerate.read(values)
			if name == 'LOCK': self.lock.set(values[0])
			if name == 'GLOBAL_AUTO': self.global_auto.set(values[0])
			if name == 'TEMPO': self.tempo.read(values)
			if name == 'PLAYRATE': self.playrate.read(values)
			if name == 'SELECTION': self.selection.read(values)
			if name == 'SELECTION2': self.selection2.read(values)
			if name == 'MASTERAUTOMODE': self.masterautomode.set(values[0])
			if name == 'MASTERTRACKHEIGHT': self.mastertrackheight.read(values)
			if name == 'MASTERPEAKCOL': self.masterpeakcol.set(values[0])
			if name == 'MASTERMUTESOLO': self.mastermutesolo.set(values[0])
			if name == 'MASTERTRACKVIEW': self.mastertrackview.read(values)
			if name == 'MASTERHWOUT': self.masterhwout.read(values)
			if name == 'MASTER_NCH': self.master_nch.read(values)
			if name == 'MASTER_VOLUME': self.master_volume.read(values)
			if name == 'MASTER_PANMODE': self.master_panmode.set(values[0])
			if name == 'MASTER_PANLAWFLAGS': self.master_panlawflags.set(values[0])
			if name == 'MASTER_FX': self.master_fx.set(values[0])
			if name == 'MASTER_SEL': self.master_sel.set(values[0])
			if name == 'MASTERPLAYSPEEDENV': self.masterplayspeedenv.read(inside_dat, values)
			if name == 'TEMPOENVEX': self.tempoenvex.read(inside_dat, values)
			if name == 'NOTES':
				self.notes_vals.read(values)
				for x in inside_dat:
					if x:
						if x[0] == '|':
							self.notes_data.append(x[1:])

			if name == 'MASTERFXLIST': 
				fxchain_obj = rpp_fxchain.rpp_fxchain()
				fxchain_obj.load(inside_dat)
				self.masterfxlist = fxchain_obj
			if name == 'TRACK': 
				track_obj = rpp_track.rpp_track()
				track_obj.load(inside_dat)
				self.tracks.append(track_obj)
			if name == 'MARKER': 
				marker = rvd(
					[0,0,'',0,0,1,'R','',0], 
					['id','pos','name','unk1','color','unk2','unk3','unk4','unk5'], 
					[int, float, str, int, int, int, str, str, int], True)
				marker.read(values)
				self.markers.append(marker.values)
			if name == 'POOLEDENV': 
				pooledenv_obj = rpp_env.rpp_pooledenv()
				pooledenv_obj.load(inside_dat)
				self.pooledenvs.append(pooledenv_obj)

	def add_track(self):
		track_obj = rpp_track.rpp_track()
		self.tracks.append(track_obj)
		return track_obj

	def add_pooledenv(self):
		pooledenv_obj = rpp_env.rpp_pooledenv()
		self.pooledenvs.append(pooledenv_obj)
		return pooledenv_obj

	def write(self, rpp_data):
		self.title.write('TITLE',rpp_data)
		self.author.write('AUTHOR',rpp_data)
		rpp_notes = robj('NOTES',[self.notes_vals.values])
		for x in self.notes_data: rpp_notes.children.append('|'+x)
		rpp_data.children.append(rpp_notes)
		self.ripple.write('RIPPLE',rpp_data)
		self.groupoverride.write('GROUPOVERRIDE', rpp_data)
		self.autoxfade.write('AUTOXFADE',rpp_data)
		self.envattach.write('ENVATTACH',rpp_data)
		self.pooledenvattach.write('POOLEDENVATTACH',rpp_data)
		self.mixeruiflags.write('MIXERUIFLAGS', rpp_data)
		self.envfadesz10.write('ENVFADESZ10',rpp_data)
		self.peakgain.write('PEAKGAIN',rpp_data)
		self.feedback.write('FEEDBACK',rpp_data)
		self.panlaw.write('PANLAW',rpp_data)
		self.projoffs.write('PROJOFFS', rpp_data)
		self.maxprojlen.write('MAXPROJLEN', rpp_data)
		self.grid.write('GRID', rpp_data)
		self.timemode.write('TIMEMODE', rpp_data)
		self.video_config.write('VIDEO_CONFIG', rpp_data)
		self.panmode.write('PANMODE',rpp_data)
		self.panlawflags.write('PANLAWFLAGS',rpp_data)
		self.cursor.write('CURSOR',rpp_data)
		self.zoom.write('ZOOM', rpp_data)
		self.vzoomex.write('VZOOMEX', rpp_data)
		self.use_rec_cfg.write('USE_REC_CFG',rpp_data)
		self.recmode.write('RECMODE',rpp_data)
		self.smptesync.write('SMPTESYNC', rpp_data)
		self.loop.write('LOOP',rpp_data)
		self.loopgran.write('LOOPGRAN', rpp_data)
		self.record_path.write('RECORD_PATH', rpp_data)
		reaper_func.writebin_named(rpp_data, 'RECORD_CFG', self.record_cfg)
		reaper_func.writebin_named(rpp_data, 'APPLYFX_CFG', self.applyfx_cfg)
		self.render_file.write('RENDER_FILE',rpp_data)
		self.render_pattern.write('RENDER_PATTERN',rpp_data)
		self.render_fmt.write('RENDER_FMT', rpp_data)
		self.render_1x.write('RENDER_1X',rpp_data)
		self.render_range.write('RENDER_RANGE', rpp_data)
		self.render_resample.write('RENDER_RESAMPLE', rpp_data)
		self.render_addtoproj.write('RENDER_ADDTOPROJ',rpp_data)
		self.render_stems.write('RENDER_STEMS',rpp_data)
		self.render_dither.write('RENDER_DITHER',rpp_data)
		self.timelockmode.write('TIMELOCKMODE',rpp_data)
		self.tempoenvlockmode.write('TEMPOENVLOCKMODE',rpp_data)
		self.itemmix.write('ITEMMIX',rpp_data)
		self.defpitchmode.write('DEFPITCHMODE', rpp_data)
		self.takelane.write('TAKELANE',rpp_data)
		self.samplerate.write('SAMPLERATE', rpp_data)
		reaper_func.writebin_named(rpp_data, 'RENDER_CFG', self.render_cfg)
		self.lock.write('LOCK',rpp_data)
		self.global_auto.write('GLOBAL_AUTO',rpp_data)
		self.tempo.write('TEMPO', rpp_data)
		self.playrate.write('PLAYRATE', rpp_data)
		self.selection.write('SELECTION', rpp_data)
		self.selection2.write('SELECTION2', rpp_data)
		self.masterautomode.write('MASTERAUTOMODE',rpp_data)
		self.mastertrackheight.write('MASTERTRACKHEIGHT', rpp_data)
		self.masterpeakcol.write('MASTERPEAKCOL',rpp_data)
		self.mastermutesolo.write('MASTERMUTESOLO',rpp_data)
		self.mastertrackview.write('MASTERTRACKVIEW', rpp_data)
		self.masterhwout.write('MASTERHWOUT', rpp_data)
		self.master_nch.write('MASTER_NCH', rpp_data)
		self.master_volume.write('MASTER_VOLUME', rpp_data)
		self.master_panmode.write('MASTER_PANMODE',rpp_data)
		self.master_panlawflags.write('MASTER_PANLAWFLAGS',rpp_data)
		self.master_fx.write('MASTER_FX',rpp_data)
		self.master_sel.write('MASTER_SEL',rpp_data)
		if self.masterfxlist != None:
			self.masterfxlist.write('MASTERFXLIST', rpp_data)
		if self.pooledenvs:
			for x in self.pooledenvs:
				x.write('POOLEDENV', rpp_data)

		self.masterplayspeedenv.write('MASTERPLAYSPEEDENV', rpp_data)
		self.tempoenvex.write('TEMPOENVEX', rpp_data)

		for p in self.markers:
			rpp_data.children.append(['MARKER']+[ts(markertypes[n], x) for n, x in enumerate(p)])

		for track in self.tracks:
			rpp_trackdata = robj('TRACK',[track.trackid.get()])
			track.write(rpp_trackdata)
			rpp_data.children.append(rpp_trackdata)