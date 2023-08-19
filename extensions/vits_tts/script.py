import re
import requests
from pathlib import Path

import gradio as gr

from modules import chat, shared
from modules.utils import gradio
from modules.logging_colors import logger

params = {
    'activate': True,
    'autoplay': False,
    'show_text': True,
    'base_url': None,
}

voices = None
wav_idx = 0

def update_base_url(url):
    params['base_url'] = url


def remove_tts_from_history(history):
    for i, entry in enumerate(history['internal']):
        history['visible'][i] = [history['visible'][i][0], entry[1]]

    return history


def toggle_text_in_history(history):
    for i, entry in enumerate(history['visible']):
        visible_reply = entry[1]
        if visible_reply.startswith('<audio'):
            if params['show_text']:
                reply = history['internal'][i][1]
                history['visible'][i] = [history['visible'][i][0], f"{visible_reply.split('</audio>')[0]}</audio>\n\n{reply}"]
            else:
                history['visible'][i] = [history['visible'][i][0], f"{visible_reply.split('</audio>')[0]}</audio>"]

    return history


def remove_surrounded_chars(string):
    # this expression matches to 'as few symbols as possible (0 upwards) between any asterisks' OR
    # 'as few symbols as possible (0 upwards) between an asterisk and the end of the string'
    return re.sub('\*[^\*]*?(\*|$)', '', string)


def state_modifier(state):
    if not params['activate']:
        return state

    state['stream'] = False
    return state


def input_modifier(string):
    if not params['activate']:
        return string

    shared.processing_message = "*Is recording a voice message...*"
    return string


def history_modifier(history):
    # Remove autoplay from the last reply
    if len(history['internal']) > 0:
        history['visible'][-1] = [
            history['visible'][-1][0],
            history['visible'][-1][1].replace('controls autoplay>', 'controls>')
        ]

    return history


def output_modifier(string):
    global params, wav_idx

    if not params['activate']:
        return string

    original_string = string
    string = remove_surrounded_chars(string)
    string = string.replace('"', '')
    string = string.replace('“', '')
    string = string.replace('\n', ' ')
    string = string.strip()
    if string == '':
        string = 'empty reply, try regenerating'

    output_file = Path(f'extensions/vits_tts/outputs/{wav_idx:06d}.wav'.format(wav_idx))

    url = f"{params['base_url']}/ttsapi/{string}"
    res = requests.get(url)
    with open(str(output_file), "wb") as f:
        f.write(res.content)
        print(f'Audio has been generated in {str(output_file)}')

    autoplay = 'autoplay' if params['autoplay'] else ''
    string = f'<audio src="file/{output_file.as_posix()}" controls {autoplay}></audio>'
    wav_idx += 1

    if params['show_text']:
        string += f'\n\n{original_string}'

    shared.processing_message = "*Is typing...*"
    return string


def ui():
    # Gradio elements
    with gr.Row():
        activate = gr.Checkbox(value=params['activate'], label='Activate TTS')
        autoplay = gr.Checkbox(value=params['autoplay'], label='Play TTS automatically')
        show_text = gr.Checkbox(value=params['show_text'], label='Show message text under audio player')

    with gr.Row():
        if params['base_url']:
            base_url = gr.Textbox(value=params['base_url'], label='Base URL')
            update_base_url(params['base_url'])
        else:
            base_url = gr.Textbox(placeholder="Enter your VITS base url.", label='Base URL')

    with gr.Row():
        convert = gr.Button('Permanently replace audios with the message texts')
        convert_cancel = gr.Button('Cancel', visible=False)
        convert_confirm = gr.Button('Confirm (cannot be undone)', variant="stop", visible=False)

    if shared.is_chat():
        # Convert history with confirmation
        convert_arr = [convert_confirm, convert, convert_cancel]
        convert.click(lambda: [gr.update(visible=True), gr.update(visible=False), gr.update(visible=True)], None, convert_arr)
        convert_confirm.click(
            lambda: [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)], None, convert_arr).then(
            remove_tts_from_history, gradio('history'), gradio('history')).then(
            chat.save_persistent_history, gradio('history', 'character_menu', 'mode'), None).then(
            chat.redraw_html, shared.reload_inputs, gradio('display'))

        convert_cancel.click(lambda: [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)], None, convert_arr)

        # Toggle message text in history
        show_text.change(
            lambda x: params.update({"show_text": x}), show_text, None).then(
            toggle_text_in_history, gradio('history'), gradio('history')).then(
            chat.save_persistent_history, gradio('history', 'character_menu', 'mode'), None).then(
            chat.redraw_html, shared.reload_inputs, gradio('display'))

    # Event functions to update the parameters in the backend
    activate.change(lambda x: params.update({'activate': x}), activate, None)
    # voice.change(lambda x: params.update({'selected_voice': x}), voice, None)
    base_url.change(update_base_url, base_url, None)
    # Event functions to update the parameters in the backend
    autoplay.change(lambda x: params.update({"autoplay": x}), autoplay, None)
