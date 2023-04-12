# SPDX-FileCopyrightText: 2023 SatyrDiamond
# SPDX-License-Identifier: GPL-3.0-or-later

import shlex
import json
import plugin_input
import json
from functions import placements

def average(lst):
    return sum(lst) / len(lst)

def get_used_insts(channeldata):
    usedinsts = []
    PatternList = channeldata['Patterns']
    for Pattern in PatternList:
        PatData = PatternList[Pattern]
        for Note in PatData:
            NoteData = PatData[Note]
            if 'Instrument' in NoteData:
                if NoteData['Instrument'] not in usedinsts:
                    usedinsts.append(NoteData['Instrument'])
    return usedinsts

def decode_fst(infile):
    f_fst = open(infile, 'r')
    famistudiotxt_lines = f_fst.readlines()
      
    fst_Main = {}
    
    fst_instruments = {}
    fst_Arpeggios = {}
    fst_Songs = {}
    fst_DPCMSamples = {}
    fst_DPCMMappings = {}
    
    for line in famistudiotxt_lines:
        t_cmd = line.split(" ", 1)
        t_precmd = t_cmd[0]
        tabs_num = t_precmd.count('\t')
    
        cmd_name = t_precmd.split()[0]
        cmd_params = dict(token.split('=') for token in shlex.split(t_cmd[1]))
    
        #print(tabs_num, cmd_name, cmd_params)

        if cmd_name == 'Project' and tabs_num == 0:
            fst_Main = cmd_params
    
        elif cmd_name == 'DPCMSample' and tabs_num == 1:
            fst_DPCMSamples[cmd_params['Name']] = cmd_params['Data']
        elif cmd_name == 'DPCMMapping' and tabs_num == 1:
            mapnote = cmd_params['Note']
            fst_DPCMMappings[mapnote] = {}
            fst_DPCMMappings[mapnote]['Sample'] = cmd_params['Sample']
            fst_DPCMMappings[mapnote]['Pitch'] = cmd_params['Pitch']
            fst_DPCMMappings[mapnote]['Loop'] = cmd_params['Loop']
    
        elif cmd_name == 'Instrument' and tabs_num == 1:
            instname = cmd_params['Name']
            fst_instruments[instname] = {}
            fst_Instrument = fst_instruments[instname]
            fst_Instrument['Name'] = cmd_params['Name']
            fst_Instrument['Envelopes'] = {}
            if 'N163WavePreset' in cmd_params: fst_Instrument['N163WavePreset'] = cmd_params['N163WavePreset']
            if 'N163WaveSize' in cmd_params: fst_Instrument['N163WaveSize'] = cmd_params['N163WaveSize']
            if 'N163WavePos' in cmd_params: fst_Instrument['N163WavePos'] = cmd_params['N163WavePos']
            if 'N163WaveCount' in cmd_params: fst_Instrument['N163WaveCount'] = cmd_params['N163WaveCount']

            if 'Vrc7Patch' in cmd_params: 
                if cmd_params['Vrc7Patch'] != '0':
                    fst_Instrument['Vrc7Patch'] = cmd_params['Vrc7Patch']
                else:
                    Vrc7Reg = [0,0,0,0,0,0,0,0]
                    if 'Vrc7Reg0' in cmd_params: Vrc7Reg[0] = int(cmd_params['Vrc7Reg0'])
                    if 'Vrc7Reg1' in cmd_params: Vrc7Reg[1] = int(cmd_params['Vrc7Reg1'])
                    if 'Vrc7Reg2' in cmd_params: Vrc7Reg[2] = int(cmd_params['Vrc7Reg2'])
                    if 'Vrc7Reg3' in cmd_params: Vrc7Reg[3] = int(cmd_params['Vrc7Reg3'])
                    if 'Vrc7Reg4' in cmd_params: Vrc7Reg[4] = int(cmd_params['Vrc7Reg4'])
                    if 'Vrc7Reg5' in cmd_params: Vrc7Reg[5] = int(cmd_params['Vrc7Reg5'])
                    if 'Vrc7Reg6' in cmd_params: Vrc7Reg[6] = int(cmd_params['Vrc7Reg6'])
                    if 'Vrc7Reg7' in cmd_params: Vrc7Reg[7] = int(cmd_params['Vrc7Reg7'])
                    fst_Instrument['Vrc7Reg'] = Vrc7Reg

        elif cmd_name == 'Arpeggio' and tabs_num == 1:
            arpname = cmd_params['Name']
            fst_Arpeggios[arpname] = cmd_params

        elif cmd_name == 'Envelope' and tabs_num == 2:
            envtype = cmd_params['Type']
            fst_Instrument['Envelopes'][envtype] = {}
            fst_Instrument['Envelopes'][envtype] = cmd_params

        elif cmd_name == 'Song' and tabs_num == 1:
            songname = cmd_params['Name']
            fst_Songs[songname] = cmd_params
            fst_Song = fst_Songs[songname]
            fst_Song['PatternCustomSettings'] = {}
            fst_Song['Channels'] = {}
    
        elif cmd_name == 'PatternCustomSettings' and tabs_num == 2:
            pattime = cmd_params['Time']
            fst_Song['PatternCustomSettings'][pattime] = cmd_params

        elif cmd_name == 'Channel' and tabs_num == 2:
            chantype = cmd_params['Type']
            fst_Song['Channels'][chantype] = {}
            fst_Channel = fst_Song['Channels'][chantype]
            fst_Channel['Instances'] = {}
            fst_Channel['Patterns'] = {}
    
        elif cmd_name == 'Pattern' and tabs_num == 3:
            patname = cmd_params['Name']
            fst_Channel['Patterns'][patname] = {}
            fst_Pattern = fst_Channel['Patterns'][patname]
    
        elif cmd_name == 'PatternInstance' and tabs_num == 3:
            pattime = cmd_params['Time']
            fst_Channel['Instances'][pattime] = cmd_params
    
        elif cmd_name == 'Note' and tabs_num == 4:
            notetime = cmd_params['Time']
            fst_Pattern[notetime] = cmd_params
    
        else:
            print('unexpected command and/or wrong tabs:', cmd_name)
            exit()
    
    fst_Main['Instruments'] = fst_instruments
    fst_Main['Songs'] = fst_Songs
    fst_Main['Arpeggios'] = fst_Arpeggios
    fst_Main['DPCMSamples'] = fst_DPCMSamples
    fst_Main['DPCMMappings'] = fst_DPCMMappings
    return fst_Main

def add_envelope(plugdata, fst_Instrument, cvpj_name, fst_name):
    if fst_name in fst_Instrument['Envelopes']:
        plugdata[cvpj_name] = {}
        envdata = plugdata[cvpj_name]
        if fst_name == 'FDSWave':
            if 'Values' in fst_Instrument['Envelopes'][fst_name]:
                envdata['values'] = [int(i) for i in fst_Instrument['Envelopes'][fst_name]['Values'].split(',')]
            if 'Loop' in fst_Instrument['Envelopes'][fst_name]:
                envdata['loop'] = fst_Instrument['Envelopes'][fst_name]['Loop']
            if 'Release' in fst_Instrument['Envelopes'][fst_name]:
                envdata['release'] = fst_Instrument['Envelopes'][fst_name]['Release']
        elif fst_name == 'N163Wave':
            if 'Values' in fst_Instrument['Envelopes'][fst_name]:
                envdata['values'] = [int(i) for i in fst_Instrument['Envelopes'][fst_name]['Values'].split(',')]
            if 'Loop' in fst_Instrument['Envelopes'][fst_name]:
                envdata['loop'] = fst_Instrument['Envelopes'][fst_name]['Loop']
            envdata['preset'] = fst_Instrument['N163WavePreset']
            envdata['size'] = fst_Instrument['N163WaveSize']
            envdata['pos'] = fst_Instrument['N163WavePos']
            envdata['count'] = fst_Instrument['N163WaveCount']
        else:
            plugdata[cvpj_name] = [int(i) for i in fst_Instrument['Envelopes'][fst_name]['Values'].split(',')]
            
def add_envelopes(plugdata, fst_Instrument):
    if 'Envelopes' in fst_Instrument:
        add_envelope(plugdata, fst_Instrument, 'env_vol', 'Volume')
        add_envelope(plugdata, fst_Instrument, 'env_duty', 'DutyCycle')
        add_envelope(plugdata, fst_Instrument, 'env_pitch', 'Pitch')

def create_inst(WaveType, fst_Instrument, cvpj_l_instrument_data, cvpj_l_instrument_order, fxrack_channel):
    instname = fst_Instrument['Name']

    cvpj_inst = {}
    cvpj_inst["enabled"] = 1
    cvpj_inst['fxrack_channel'] = fxrack_channel
    cvpj_inst["instdata"] = {}
    cvpj_instdata = cvpj_inst["instdata"]
    plugname = cvpj_instdata['plugin'] = 'none'
    plugdata = cvpj_instdata['plugindata'] = {}
    cvpj_instdata['pitch'] = 0
    if WaveType == 'Square1' or WaveType == 'Square2' or WaveType == 'Triangle' or WaveType == 'Noise':
        plugname = '2a03'
        if WaveType == 'Square1' or WaveType == 'Square2': plugdata['wave'] = 'square'
        if WaveType == 'Triangle': plugdata['wave'] = 'triangle'
        if WaveType == 'Noise': plugdata['wave'] = 'noise'
        add_envelopes(plugdata, fst_Instrument)

    if WaveType == 'VRC7FM':
        plugname = 'vrc7'
        add_envelopes(plugdata, fst_Instrument)
        if 'Vrc7Patch' in fst_Instrument:
            plugdata['use_patch'] = True
            plugdata['patch'] = fst_Instrument['Vrc7Patch']
        else:
            plugdata['use_patch'] = False
            plugdata['regs'] = fst_Instrument['Vrc7Reg']

    if WaveType == 'VRC6Square' or WaveType == 'VRC6Saw':
        plugname = 'vrc6'
        if WaveType == 'VRC6Saw': plugdata['wave'] = 'saw'
        if WaveType == 'VRC6Square': plugdata['wave'] = 'square'
        add_envelopes(plugdata, fst_Instrument)

    if WaveType == 'FDS':
        plugname = 'fds'
        add_envelopes(plugdata, fst_Instrument)
        add_envelope(plugdata, fst_Instrument, 'wave', 'FDSWave')

    if WaveType == 'N163':
        plugname = 'namco_163_famistudio'
        add_envelopes(plugdata, fst_Instrument)
        add_envelope(plugdata, fst_Instrument, 'wave', 'N163Wave')

    if WaveType == 'S5B':
        plugdata['wave'] = 'square'
        plugname = 'sunsoft_5b'
        add_envelopes(plugdata, fst_Instrument)


    #print('DATA ------------' , fst_Instrument)
    #print('OUT ------------' , plugname, plugdata)

    cvpj_instdata['usemasterpitch'] = 1
    if WaveType == 'Square1': cvpj_inst['color'] = [0.97, 0.56, 0.36]
    if WaveType == 'Square2': cvpj_inst['color'] = [0.97, 0.56, 0.36]
    if WaveType == 'Triangle': cvpj_inst['color'] = [0.94, 0.33, 0.58]
    if WaveType == 'Noise': cvpj_inst['color'] = [0.33, 0.74, 0.90]
    if WaveType == 'FDS': cvpj_inst['color'] = [0.94, 0.94, 0.65]
    if WaveType == 'VRC7FM': cvpj_inst['color'] = [1.00, 0.46, 0.44]
    if WaveType == 'VRC6Square': cvpj_inst['color'] = [0.60, 0.44, 0.93]
    if WaveType == 'VRC6Saw': cvpj_inst['color'] = [0.46, 0.52, 0.91]
    if WaveType == 'S5B': cvpj_inst['color'] = [0.58, 0.94, 0.33]
    if WaveType == 'N163': cvpj_inst['color'] = [0.97, 0.97, 0.36]
    cvpj_inst["name"] = WaveType+'-'+instname
    cvpj_inst["pan"] = 0.0
    cvpj_inst["vol"] = 0.6
    cvpj_l_instrument_data[WaveType+'-'+instname] = cvpj_inst
    if WaveType+'-'+instname not in cvpj_l_instrument_order:
        cvpj_l_instrument_order.append(WaveType+'-'+instname)

def create_dpcm_inst(DPCMMappings, DPCMSamples, cvpj_l_instrument_data, cvpj_l_instrument_order, fxrack_channel):
    instname = 'DPCM'
    cvpj_inst = {}
    cvpj_inst["enabled"] = 1
    cvpj_inst['fxrack_channel'] = fxrack_channel
    cvpj_inst["instdata"] = {}
    cvpj_instdata = cvpj_inst["instdata"]
    cvpj_instdata['pitch'] = 0
    cvpj_instdata['plugin'] = 'none'
    cvpj_instdata['usemasterpitch'] = 1
    cvpj_inst['color'] = [0.48, 0.83, 0.49]
    cvpj_inst["name"] = 'DPCM'
    cvpj_inst["pan"] = 0.0
    cvpj_inst["vol"] = 0.6
    cvpj_l_instrument_data['DPCM'] = cvpj_inst
    cvpj_l_instrument_order.append('DPCM')

def NoteToMidi(keytext):
    l_key = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    s_octave = (int(keytext[-1])-5)*12
    lenstr = len(keytext)
    if lenstr == 3: t_key = keytext[:-1]
    else: t_key = keytext[:-1]
    s_key = l_key.index(t_key)

    return s_key + s_octave

class input_famistudio(plugin_input.base):
    def __init__(self): pass
    def is_dawvert_plugin(self): return 'input'
    def getshortname(self): return 'famistudio_txt'
    def getname(self): return 'FamiStudio Text'
    def gettype(self): return 'mi'
    def getdawcapabilities(self): 
        return {
        'fxrack': False,
        'r_track_lanes': True,
        'placement_cut': False,
        'placement_warp': False,
        'no_pl_auto': True,
        'no_placements': False
        }
    def supported_autodetect(self): return False
    def parse(self, input_file, extra_param):
        fst_Main = decode_fst(input_file)

        InstShapes = {'Square1': 'Square1', 
        'Square2': 'Square2', 
        'Triangle': 'Triangle', 
        'Noise': 'Noise', 
        'VRC6Square1': 'VRC6Square', 
        'VRC6Square2': 'VRC6Square', 
        'VRC6Saw': 'VRC6Saw', 
        'VRC7FM1': 'VRC7FM', 
        'VRC7FM2': 'VRC7FM', 
        'VRC7FM3': 'VRC7FM', 
        'VRC7FM4': 'VRC7FM', 
        'VRC7FM5': 'VRC7FM', 
        'VRC7FM6': 'VRC7FM', 
        'FDS': 'FDS', 
        'N163Wave1': 'N163', 
        'N163Wave2': 'N163', 
        'N163Wave3': 'N163', 
        'N163Wave4': 'N163', 
        'S5BSquare1': 'S5B', 
        'S5BSquare2': 'S5B', 
        'S5BSquare3': 'S5B'}

        cvpj_l = {}
        cvpj_l_instrument_data = {}
        cvpj_l_instrument_order = []
        cvpj_l_notelistindex = {}
        cvpj_l_playlist = {}
        cvpj_l_fxrack = {}
        
        fst_instruments = fst_Main['Instruments']
        fst_arpeggios = fst_Main['Arpeggios']
        fst_currentsong = next(iter(fst_Main['Songs'].values()))
        fst_channels = fst_currentsong['Channels']
        fst_beatlength = int(fst_currentsong['BeatLength'])
        fst_groove = fst_currentsong['Groove']

        PatternLength = int(fst_currentsong['PatternLength'])
        SongLength = int(fst_currentsong['Length'])
        NoteLength = int(fst_currentsong['NoteLength'])
        LoopPoint = int(fst_currentsong['LoopPoint'])
        DPCMMappings = fst_Main['DPCMMappings']
        DPCMSamples = fst_Main['DPCMSamples']

        groovetable = []
        groovesplit = fst_groove.split('-')
        for groovenumber in groovesplit:
            groovetable.append(int(groovenumber))
        bpm = 60/(average(groovetable)/60*fst_beatlength)

        PatternLengthList = []
        for number in range(SongLength):
            if str(number) not in fst_currentsong['PatternCustomSettings']: PatternLengthList.append(PatternLength)
            else: PatternLengthList.append(int(fst_currentsong['PatternCustomSettings'][str(number)]['Length']))

        PointsPos = []
        PointsAdd = 0
        for number in range(SongLength):
            PointsPos.append(PointsAdd)
            PointsAdd += PatternLengthList[number]

        channum = 1
        for Channel in fst_channels:
            WaveType = None
            used_insts = get_used_insts(fst_channels[Channel])
            if Channel in InstShapes: WaveType = InstShapes[Channel]
            elif Channel == 'DPCM': 
                create_dpcm_inst(DPCMMappings, DPCMSamples, cvpj_l_instrument_data, cvpj_l_instrument_order, channum)
                cvpj_l_fxrack[str(channum)] = {'name': 'DPCM'}
                cvpj_l_fxrack[str(channum)]['color'] = [0.48, 0.83, 0.49]
            if WaveType != None:
                cvpj_l_fxrack[str(channum)] = {'name': WaveType}
                if WaveType == 'Square1': cvpj_l_fxrack[str(channum)]['color'] = [0.97, 0.56, 0.36]
                if WaveType == 'Square2': cvpj_l_fxrack[str(channum)]['color'] = [0.97, 0.56, 0.36]
                if WaveType == 'Triangle': cvpj_l_fxrack[str(channum)]['color'] = [0.94, 0.33, 0.58]
                if WaveType == 'Noise': cvpj_l_fxrack[str(channum)]['color'] = [0.33, 0.74, 0.90]
                if WaveType == 'FDS': cvpj_l_fxrack[str(channum)]['color'] = [0.94, 0.94, 0.65]
                if WaveType == 'VRC7FM': cvpj_l_fxrack[str(channum)]['color'] = [1.00, 0.46, 0.44]
                if WaveType == 'VRC6Square': cvpj_l_fxrack[str(channum)]['color'] = [0.60, 0.44, 0.93]
                if WaveType == 'VRC6Saw': cvpj_l_fxrack[str(channum)]['color'] = [0.46, 0.52, 0.91]
                if WaveType == 'S5B': cvpj_l_fxrack[str(channum)]['color'] = [0.58, 0.94, 0.33]
                if WaveType == 'N163': cvpj_l_fxrack[str(channum)]['color'] = [0.97, 0.97, 0.36]
                for inst in used_insts:
                    create_inst(WaveType, fst_instruments[inst], cvpj_l_instrument_data, cvpj_l_instrument_order, channum)
            channum += 1

        playlistnum = 1
        for Channel in fst_channels:
            ChannelName = Channel
            cvpj_l_playlist[str(playlistnum)] = {}
            cvpj_l_playlist[str(playlistnum)]['color'] = [0.13, 0.15, 0.16]
            cvpj_l_playlist[str(playlistnum)]['name'] = Channel
            cvpj_l_playlist[str(playlistnum)]['placements_notes'] = []
            Channel_Patterns = fst_channels[Channel]['Patterns']
            for Pattern in Channel_Patterns:
                cvpj_patternid = Channel+'-'+Pattern
                cvpj_l_notelistindex[cvpj_patternid] = {}
                cvpj_l_notelistindex[cvpj_patternid]['notelist'] = []
                cvpj_l_notelistindex[cvpj_patternid]['color'] = [0.13, 0.15, 0.16]
                cvpj_l_notelistindex[cvpj_patternid]['name'] = Pattern+' ('+Channel+')'
                patternnotelist = cvpj_l_notelistindex[cvpj_patternid]['notelist']
                for fst_note in Channel_Patterns[Pattern]:
                    notedata = Channel_Patterns[Pattern][fst_note]
                    if ChannelName != 'DPCM':
                        if 'Duration' in notedata and 'Instrument' in notedata:

                            t_instrument = InstShapes[Channel]+'-'+notedata['Instrument']
                            t_duration = int(notedata['Duration'])/NoteLength
                            t_position = int(notedata['Time'])/NoteLength
                            t_key = NoteToMidi(notedata['Value']) + 24

                            cvpj_multikeys = []
                            if 'Arpeggio' in notedata:
                                if notedata['Arpeggio'] in fst_arpeggios:
                                    cvpj_multikeys = fst_arpeggios[notedata['Arpeggio']]['Values'].split(',')
                                    cvpj_multikeys = [*set(cvpj_multikeys)]

                            cvpj_notemod = {}
                            if 'SlideTarget' in notedata:
                                t_slidenote = NoteToMidi(notedata['SlideTarget']) + 24
                                cvpj_notemod['slide'] = [{'position': 0, 'duration': t_duration, 'key': t_slidenote-t_key}]
                                cvpj_notemod['auto'] = {}
                                cvpj_notemod['auto']['pitch'] = [{'position': 0, 'value': 0}, {'position': t_duration, 'value': t_slidenote-t_key}]

                            if cvpj_multikeys == []:
                                cvpj_note = {'instrument': t_instrument, 'duration': t_duration, 'position': t_position, 'key': t_key, 'notemod': cvpj_notemod}
                                patternnotelist.append(cvpj_note)
                            else:
                                for cvpj_multikey in cvpj_multikeys:
                                    addkey = int(cvpj_multikey)
                                    cvpj_note = {'instrument': t_instrument, 'duration': t_duration, 'position': t_position, 'key': t_key+addkey, 'notemod': cvpj_notemod}
                                    patternnotelist.append(cvpj_note)

                    else:
                        if 'Duration' in notedata:
                            cvpj_note = {}
                            cvpj_note['instrument'] = 'DPCM'
                            cvpj_note['duration'] = int(notedata['Duration'])/NoteLength
                            cvpj_note['position'] = int(notedata['Time'])/NoteLength
                            cvpj_note['key'] = NoteToMidi(notedata['Value']) + 24
                            patternnotelist.append(cvpj_note)
            Channel_Instances = fst_channels[Channel]['Instances']
            durationnum = 0
            for fst_Placement in Channel_Instances:
                fst_PData = Channel_Instances[fst_Placement]
                fst_time = int(fst_PData['Time'])
                cvpj_l_placement = {}
                cvpj_l_placement['type'] = "instruments"
                cvpj_l_placement['position'] = PointsPos[int(fst_time)]
                cvpj_l_placement['duration'] = PatternLengthList[durationnum]
                cvpj_l_placement['fromindex'] = Channel+'-'+fst_PData['Pattern']
                cvpj_l_playlist[str(playlistnum)]['placements_notes'].append(cvpj_l_placement)
                durationnum += 1
            playlistnum += 1

        timesig = placements.get_timesig(PatternLength, fst_beatlength)

        cvpj_l['info'] = {}
        if 'Name' in fst_Main: cvpj_l['info']['title'] = fst_Main['Name']
        if 'Author' in fst_Main: cvpj_l['info']['author'] = fst_Main['Author']

        cvpj_l['do_addwrap'] = True
        
        cvpj_l['use_instrack'] = False
        cvpj_l['use_fxrack'] = True
        
        cvpj_l['timesig_numerator'] = timesig[0]
        cvpj_l['timesig_denominator'] = timesig[1]
        cvpj_l['timemarkers'] = placements.make_timemarkers(timesig, PatternLengthList, LoopPoint)
        cvpj_l['notelistindex'] = cvpj_l_notelistindex
        cvpj_l['instruments_data'] = cvpj_l_instrument_data
        cvpj_l['instruments_order'] = cvpj_l_instrument_order
        cvpj_l['playlist'] = cvpj_l_playlist
        cvpj_l['fxrack'] = cvpj_l_fxrack
        cvpj_l['bpm'] = bpm
        return json.dumps(cvpj_l)