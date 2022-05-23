import threading
import re

from telegram.ext import CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardMarkup

from bot import DOWNLOAD_DIR, dispatcher
from bot.helper.telegram_helper.message_utils import *
from bot.helper.telegram_helper import button_build
from bot.helper.ext_utils.bot_utils import is_url
from bot.helper.ext_utils.bot_utils import get_readable_file_size
from bot.helper.mirror_utils.download_utils.youtube_dl_download_helper import YoutubeDLHelper
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from .mirror import MirrorListener

listener_dict = {}

def _watch(bot, update, isZip=False, isLeech=False, pswd=None):
    mssg = update.message.text
    message_args = mssg.split(' ', maxsplit=2)
    name_args = mssg.split('|', maxsplit=1)
    user_id = update.message.from_user.id
    msg_id = update.message.message_id

    try:
        link = message_args[1].strip()
        if link.startswith("|") or link.startswith("pswd: "):
            link = ''
    except IndexError:
        link = ''
    link = re.split(r"pswd:|\|", link)[0]
    link = link.strip()

    try:
        name = name_args[1]
        name = name.split(' pswd: ')[0]
        name = name.strip()
    except IndexError:
        name = ''

    pswdMsg = mssg.split(' pswd: ')
    if len(pswdMsg) > 1:
        pswd = pswdMsg[1]

    reply_to = update.message.reply_to_message
    if reply_to is not None:
        link = reply_to.text.strip()

    if not is_url(link):
        help_msg = "<b>Send link along with command line:</b>"
        help_msg += "\n<code>/command</code> {link} |newname pswd: mypassword [𝚣𝚒𝚙]"
        help_msg += "\n\n<b>By replying to link:</b>"
        help_msg += "\n<code>/command</code> |newname pswd: mypassword [𝚣𝚒𝚙]"
        return sendMessage(help_msg, bot, update)

    listener = MirrorListener(bot, update, isZip, isLeech=isLeech, pswd=pswd)
    buttons = button_build.ButtonMaker()
    best_video = "bv*+ba/b"
    best_audio = "ba/b"
    ydl = YoutubeDLHelper(listener)
    try:
        result = ydl.extractMetaData(link, name, True)
    except Exception as e:
        return sendMessage(str(e), bot, update)
    if 'entries' in result:
        for i in ['144', '240', '360', '480', '720', '1080', '1440', '2160']:
            video_format = f"bv*[height<={i}]+ba/b"
            buttons.sbutton(str(i), f"qu {msg_id} {video_format} t")
        buttons.sbutton("Best Videos", f"qu {msg_id} {best_video} t")
        buttons.sbutton("Best Audios", f"qu {msg_id} {best_audio} t")
        buttons.sbutton("Cancel", f"qu {msg_id} cancel")
        YTBUTTONS = InlineKeyboardMarkup(buttons.build_menu(2))
        listener_dict[msg_id] = [listener, user_id, link, name]
        sendMarkup('Choose Playlist Quality:', bot, update, YTBUTTONS)
    else:
        formats = result.get('formats')
        if formats is not None:
            formats_dict = {}
            tbr = []
            for frmt in formats:
                if not frmt.get('tbr') or not frmt.get('height'):
                    continue

                if frmt.get('fps'):
                    quality = f"{frmt['height']}p{frmt['fps']}-{frmt['ext']}"
                else:
                    quality = f"{frmt['height']}p-{frmt['ext']}"

                if frmt.get('filesize'):
                    size = frmt['filesize']
                elif frmt.get('filesize_approx'):
                    size = frmt['filesize_approx']
                else:
                    size = 0

                if quality in formats_dict:
                    formats_dict[quality][frmt['tbr']] = size
                else:
                    subformat = {}
                    subformat[frmt['tbr']] = size
                    formats_dict[quality] = subformat

            for forDict in formats_dict:
                if len(formats_dict[forDict]) == 1:
                    qual_fps_ext = re.split(r'p|-', forDict, maxsplit=2)
                    height = qual_fps_ext[0]
                    fps = qual_fps_ext[1]
                    ext = qual_fps_ext[2]
                    if fps != '':
                        video_format = f"bv*[height={height}][fps={fps}][ext={ext}]+ba/b"
                    else:
                        video_format = f"bv*[height={height}][ext={ext}]+ba/b"
                    size = list(formats_dict[forDict].values())[0]
                    buttonName = f"{forDict} ({get_readable_file_size(size)})"
                    buttons.sbutton(str(buttonName), f"qu {msg_id} {video_format}")
                else:
                    buttons.sbutton(str(forDict), f"qu {msg_id} dict {forDict}")
        buttons.sbutton("Best Video", f"qu {msg_id} {best_video}")
        buttons.sbutton("Best Audio", f"qu {msg_id} {best_audio}")
        buttons.sbutton("Cancel", f"qu {msg_id} cancel")
        YTBUTTONS = InlineKeyboardMarkup(buttons.build_menu(2))
        listener_dict[msg_id] = [listener, user_id, link, name, formats_dict, YTBUTTONS]
        sendMarkup('Choose Video Quality:', bot, update, YTBUTTONS)

def qual_subbuttons(task_id, qual, msg):
    buttons = button_build.ButtonMaker()
    task_info = listener_dict[task_id]
    formats_dict = task_info[4]
    qual_fps_ext = re.split(r'p|-', qual, maxsplit=2)
    height = qual_fps_ext[0]
    fps = qual_fps_ext[1]
    ext = qual_fps_ext[2]
    tbrs = []
    for tbr in formats_dict[qual]:
        tbrs.append(tbr)
    tbrs.sort(reverse=True)
    for index, br in enumerate(tbrs):
        if index == 0:
            tbr = f">{br}"
        else:
            sbr = index - 1
            tbr = f"<{tbrs[sbr]}"
        if fps != '':
            video_format = f"bv*[height={height}][fps={fps}][ext={ext}][tbr{tbr}]+ba/b"
        else:
            video_format = f"bv*[height={height}][ext={ext}][tbr{tbr}]+ba/b"
        size = formats_dict[qual][br]
        buttonName = f"{br} ({get_readable_file_size(size)})"
        buttons.sbutton(str(buttonName), f"qu {task_id} {video_format}")
    buttons.sbutton("Back", f"qu {task_id} back")
    buttons.sbutton("Cancel", f"qu {task_id} cancel")
    SUBBUTTONS = InlineKeyboardMarkup(buttons.build_menu(2))
    editMessage(f"Choose Video Bitrate for <b>{qual}</b>:", msg, SUBBUTTONS)

def select_format(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    msg = query.message
    data = data.split(" ")
    task_id = int(data[1])
    task_info = listener_dict[task_id]
    uid = task_info[1]
    if user_id != uid:
        return query.answer(text="Don't waste your time!", show_alert=True)
    elif data[2] == "dict":
        query.answer()
        qual = data[3]
        return qual_subbuttons(task_id, qual, msg)
    elif data[2] == "back":
        query.answer()
        return editMessage('Choose Video Quality:', msg, task_info[5])
    elif data[2] != "cancel":
        query.answer()
        listener = task_info[0]
        link = task_info[2]
        name = task_info[3]
        qual = data[2]
        if len(data) == 4:
            playlist = True
        else:
            playlist = False
        ydl = YoutubeDLHelper(listener)
        threading.Thread(target=ydl.add_download,args=(link, f'{DOWNLOAD_DIR}{task_id}', name, qual, playlist)).start()
        uname = f'<a href="tg://user?id={update.message.from_user.id}">{update.message.from_user.first_name}</a>'
        uid = f"<a>{update.message.from_user.id}</a>"
        msg = f"𝗟𝗢𝗚𝗚𝗘𝗥\n\n𝑼𝒔𝒆𝒓: {uname}\n𝑼𝒔𝒆𝒓 𝑰𝑫: {uid}\n\n𝑳𝒊𝒏𝒌 𝑺𝒆𝒏𝒅𝒆𝒅:\n<code>{link}</code>"
        sendtextlog(msg, bot, update)
        sendStatusMessage(update, bot)
    del listener_dict[task_id]
    query.message.delete()

def watch(update, context):
    _watch(context.bot, update)

def watchZip(update, context):
    _watch(context.bot, update, True)

def leechWatch(update, context):
    _watch(context.bot, update, isLeech=True)

def leechWatchZip(update, context):
    _watch(context.bot, update, True, True)

watch_handler = CommandHandler(BotCommands.WatchCommand, watch,
                                filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
zip_watch_handler = CommandHandler(BotCommands.ZipWatchCommand, watchZip,
                                    filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
leech_watch_handler = CommandHandler(BotCommands.LeechWatchCommand, leechWatch,
                                filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
leech_zip_watch_handler = CommandHandler(BotCommands.LeechZipWatchCommand, leechWatchZip,
                                    filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
quality_handler = CallbackQueryHandler(select_format, pattern="qu", run_async=True)

dispatcher.add_handler(watch_handler)
dispatcher.add_handler(zip_watch_handler)
dispatcher.add_handler(leech_watch_handler)
dispatcher.add_handler(leech_zip_watch_handler)
dispatcher.add_handler(quality_handler)