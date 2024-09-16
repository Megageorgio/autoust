# made by m and HHS_kt, early alpha version. this code will be completely rewritten!!!

import sys

sys.path.append("./SOME")
import utaupy
from deeprhythm import DeepRhythmPredictor
import pretty_midi
import FreeSimpleGUI as sg
import webbrowser
import threading
import os
from infer import infer

tempo_model = DeepRhythmPredictor()
some_model_path = (
    "./some_models/0917_continuous256_clean_3spk/model_ckpt_steps_72000_simplified.ckpt"
)
error = False
finished = False
phonemes_dir_path = "./phonemes/"
phonemes_dirs = os.listdir(phonemes_dir_path)


def make_ust():
    global midi_path, tempo

    if not wav_path:
        raise Exception("Wav file is required!")
    if not lab_path:
        raise Exception("Lab file is required!")

    if tempo:
        tempo = int(tempo)
    else:
        tempo = tempo_model.predict(wav_path) + 1

        print("predicted tempo: " + str(tempo))

    if not midi_path:
        midi_path = wav_path.replace(".wav", ".mid")
        infer(
            ["--model", some_model_path, "--wav", wav_path, "--tempo", tempo],
            standalone_mode=False,
        )
    mid = pretty_midi.PrettyMIDI(midi_path)
    notes = mid.instruments[0].notes
    ust = utaupy.ust.Ust()
    ust.tempo = tempo

    word_dict = None

    if dict_path:
        with open(dict_path, "r", encoding="utf-8") as f:
            word_dict = {
                item.split("  ")[1].strip(): item.split("  ")[0].strip()
                for item in f.read().strip().split("\n")
            }

    phones_dict = dict()

    with open(phones_path, "r") as f:
        for line in f.read().splitlines():
            arr = line.split("\t")
            phones_dict[arr[0]] = arr[1] == "vowel"

    with open(lab_path, "r") as f:
        lab_list = list(map(lambda line: line.split(), f.read().splitlines()))

    syllables = []
    current_syllable = []
    i = 0
    n = len(lab_list)

    while i < n:
        current_syllable = []
        while i < n and lab_list[i][2] not in phones_dict:
            i += 1

        while (
            i < n and lab_list[i][2] in phones_dict and not phones_dict[lab_list[i][2]]
        ):
            current_syllable.append(lab_list[i])
            i += 1

        if (
            i < n
            and lab_list[i][2]
            and lab_list[i][2] in phones_dict
            and phones_dict[lab_list[i][2]]
        ):
            current_syllable.append(lab_list[i])
            i += 1

        consonants_after_vowel = []
        while (
            i < n
            and lab_list[i][2]
            and lab_list[i][2] in phones_dict
            and not phones_dict[lab_list[i][2]]
        ):
            consonants_after_vowel.append(lab_list[i])
            i += 1
        if n == i:
            current_syllable.extend(consonants_after_vowel)
            consonants_after_vowel = []

        elif len(consonants_after_vowel) >= 2:
            current_syllable.append(consonants_after_vowel.pop(0))

        if any([phones_dict[phoneme[2]] for phoneme in current_syllable]):
            syllables.append(current_syllable)
        else:
            syllables[-1].extend(current_syllable)

        lab_list = consonants_after_vowel + lab_list[i:]
        n = len(lab_list)
        i = 0

    syllables = list(filter(lambda syllable: len(syllable) != 0, syllables))

    last_end = 0

    def fix_length(length):
        if not fix_note_length:
            return length
        if length <= 15:
            return 15
        diff = length % 15
        if diff == 0:
            return length
        elif diff > 7:
            return length + 15 - diff
        else:
            return length - diff

    def fix_lyric(phonemes):
        if word_dict:
            return word_dict.get(phonemes, phonemes)
        return "[" + phonemes + "]"

    for syllable in syllables:
        start = int(syllable[0][0])
        offset = abs(last_end - start)
        if offset != 0:
            r_note = utaupy.ust.Note()
            r_note.lyric = "R"
            r_note.tempo = tempo
            r_note.length_ms = offset // 10000
            r_note.length = fix_length(r_note.length)
            ust.notes.append(r_note)
        last_end = end = int(syllable[-1][1])
        lyric = " ".join(map(lambda phoneme: phoneme[2], syllable))
        note = utaupy.ust.Note()
        max_diff = sys.maxsize
        max_pitch = 60
        has_inside = False
        for n in notes:
            n_start = int(n.start * 10000000)
            n_end = int(n.end * 10000000)
            if n_start <= start and n_end >= end:
                max_pitch = n.pitch
                break
            elif n_start >= start and n_start <= end:
                diff = n_start - (end if n_end > end else n_end)
            elif n_end >= start and n_end <= end:
                diff = ((start if n_start < start else n_start) - n_end) * 0.75
            elif not has_inside:
                diff = min(
                    abs(start - n_start),
                    abs(end - n_end),
                    abs(start - n_end),
                    abs(end - n_start),
                )
            if diff < max_diff:
                max_diff = diff
                max_pitch = n.pitch
        note.notenum = max_pitch
        note.lyric = fix_lyric(lyric)
        note.tempo = tempo
        note.length_ms = (end - start) // 10000
        note.length = fix_length(note.length)
        ust.notes.append(note)

    ust.write(wav_path.replace(".wav", ".ust"))
    print("created ust")


def make_ust_gui():
    global finished, error, output_message
    try:
        make_ust()
        output_message = "finished!"
        finished = True
    except Exception as err:

        if hasattr(err, "message"):
            output_message = err.message
        else:
            output_message = str(err)

        error = True


sg.theme("Dark")

layout = [
    [
        sg.Text(
            "note: if you want to get a good result, your lab file should be perfect"
        )
    ],
    [sg.Text("phonemes")],
    [
        sg.Combo(
            key="-PHONES-",
            enable_events=True,
            readonly=True,
            default_value="ru-hhskt",
            values=phonemes_dirs,
            size=(50, 1),
        ),
    ],
    [sg.Text("wav file")],
    [
        sg.InputText(key="-WAV-", enable_events=True),
        sg.FileBrowse(file_types=(("WAV Files", "*.wav"),)),
    ],
    [sg.Text("lab file")],
    [
        sg.InputText(key="-LAB-", enable_events=True),
        sg.FileBrowse(file_types=(("LAB Files", "*.lab"),)),
    ],
    [sg.Text("midi file (OPTIONAL)")],
    [
        sg.InputText(key="-MIDI-", enable_events=True),
        sg.FileBrowse(file_types=(("MIDI Files", "*.mid"),)),
    ],
    [sg.Text("tempo (OPTIONAL)")],
    [sg.InputText(key="-TEMPO-", enable_events=True)],
    [
        sg.Checkbox(
            key="-FIX-", text="fix note length", default=True, enable_events=True
        ),
        sg.Checkbox(
            key="-DICT-",
            text="convert phonemes to dict values",
            default=False,
            disabled=True,
            enable_events=True,
        ),
    ],
    [sg.Text(key="-OUTPUT-", size=(50, 1))],
    [sg.Button("Make ust"), sg.Button("More utils")],
]

window = sg.Window(
    "autoust v0.1 (made by m and HHS_kt)",
    layout,
    resizable=False,
    icon="./assets/app.ico",
)

while True:
    event, values = window.read(timeout=500)

    if finished:
        finished = False
        window["-MIDI-"].update(midi_path)
        window["-TEMPO-"].update(int(tempo))
        window["-OUTPUT-"].update(output_message, text_color="green")
        window["Make ust"].update(disabled=False)

    if error:
        error = False
        window["-OUTPUT-"].update("error: " + output_message, text_color="red")
        window["Make ust"].update(disabled=False)
        output_message = "Unknown"

    if event == sg.WIN_CLOSED:
        break
    elif event == "-WAV-":
        lab_test_path = values["-WAV-"].replace(".wav", ".lab")
        window["-LAB-"].update(lab_test_path if os.path.isfile(lab_test_path) else "")
        midi_test_path = values["-WAV-"].replace(".wav", ".mid")
        window["-MIDI-"].update(
            midi_test_path if os.path.isfile(midi_test_path) else ""
        )
        window["-TEMPO-"].update("")
    elif event == "-PHONES-":
        current_dict_path = phonemes_dir_path + values["-PHONES-"] + "/dict.txt"
        has_dict = os.path.isfile(current_dict_path)
        window["-DICT-"].update(
            values["-DICT-"] if has_dict else False, disabled=not has_dict
        )
    elif event == "More utils":
        webbrowser.open("https://t.me/+AmQjUalgGFc3NTUy")
    elif event == "Make ust":
        wav_path = values["-WAV-"]
        lab_path = values["-LAB-"]
        midi_path = values["-MIDI-"]
        dict_path = current_dict_path if values["-DICT-"] else ""
        phones_path = phonemes_dir_path + values["-PHONES-"] + "/phones.txt"
        tempo = values["-TEMPO-"]
        fix_note_length = values["-FIX-"]
        window["-OUTPUT-"].update("please wait...", text_color="yellow")
        window["Make ust"].update(disabled=True)
        threading.Thread(target=make_ust_gui, daemon=True).start()
