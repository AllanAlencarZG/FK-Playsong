from pytube import YouTube, Playlist, Search
from random import shuffle
import sys
import pystray
from PIL import Image
from threading import Thread
from pygame import mixer
from time import sleep, time
import PySimpleGUI as sg 
from io import BytesIO
from subprocess import Popen, PIPE
import sqlite3


class App:
    def __init__(self) -> None:
        self.url = None
        self.query = None
        self.search_method = None
        self.songs_urls = None
        self.paused = False
        self.random_song = False
        self.songs_finished = False
        self.current_song_changed = True
        self.main_thread_rungui = False
        self.song_index = 0
        self.system_tray = Thread(target=self.systemTray)
        self.song_channel = mixer.Channel(0)
        self.database = sqlite3.connect('database.db')
    
    def runGui(self, w=''):
        sg.theme('FlukerBr')
        sg.set_global_icon('icon.ico')
        
        table_data = self.readSongs()
        
        window = sg.Window('Toca música', layout=[
            [sg.Text('Search Method'), sg.OptionMenu(values=['Text', 'Link'], default_value='Text', key='-om-')],
            [sg.Frame('Link', [
                [sg.Text('Url : ', size=(6,1)), sg.Input(key='-url-')],
                [sg.Button('Play', size=(5,1), key='-p-'), sg.Button('Cancel')],
                [sg.Checkbox('random song', key='-rv-')]
                ], element_justification='center', key='-l-'), 
            sg.Frame('Search', [
                [sg.Text('Text : ', size=(6,1)), sg.Input(key='-sn-')],
                [sg.Button('Play', size=(5,1), key='-p3-'), sg.Button('Cancel')],
                ], element_justification='center', key='-t-', visible=False)],
            [sg.Text(w, text_color='red')],
            [sg.Frame('Recent', [
                [sg.Table(values=[[i[1], i[2]] for i in table_data], headings=['Título', 'Songs'], expand_x=True, expand_y=True, justification='center', key='-table-')],
                [sg.Button('Play', size=(5,1), key='-p2-')],
                
                [sg.Checkbox('random song', key='-rv2-')]
            ], expand_x=True, expand_y=True, element_justification='center')]
        ], icon='icon.ico', element_justification='center', return_keyboard_events=True)
        
        olds_input = []
        
        t = time()
        
        while True:
            event, values = window.read(timeout=100)
            
            if event == '-p-' and len(values['-url-']) > 0:
                self.random_song = values['-rv-']
                self.url = values['-url-']
                self.current_song_changed = True
                window.close()
                break
            elif event == 'Cancel':
                window.close()
                break
            elif event == sg.WIN_CLOSED:
                window.close()
                self.system_tray_icon.stop()
                sys.exit()
            elif event == '-p2-' and len(values['-table-']) > 0:
                self.random_song = values['-rv2-']
                self.url = table_data[values['-table-'][0]][0]
                self.current_song_changed = True
                self.search_method = 'Link'
                window.close()
                break 
            elif event == '-p3-':
                self.query = values['-sn-']
                self.current_song_changed = True
                window.close()
                break
            elif event == 'z:90' and window.Element('-url-') == window.FindElementWithFocus():
                try:
                    window['-url-'].update(olds_input[-2])
                    del olds_input[-1]
                except IndexError:
                    window['-url-'].update('')

            if window.Element('-l-').visible:
                if time() - t > 0.5 and window.Element('-url-') == window.FindElementWithFocus():
                    if len(olds_input) > 0 and olds_input[-1] != values['-url-'] and len(values['-url-']) > 0:
                        olds_input.append(values['-url-'])
                    elif len(olds_input) == 0 and len(values['-url-']) > 0:
                        olds_input.append(values['-url-'])
                    t = time()
            if window.Element('-t-').visible:
                if time() - t > 0.5 and window.Element('-sn-') == window.FindElementWithFocus():
                    if len(olds_input) > 0 and olds_input[-1] != values['-sn-'] and len(values['-sn-']) > 0:
                        olds_input.append(values['-sn-'])
                    elif len(olds_input) == 0 and len(values['-sn-']) > 0:
                        olds_input.append(values['-sn-'])
                    t = time()
            
            if not self.system_tray.is_alive():
                window.close()
                sys.exit()

            if len(values['-table-']) > 0:
                window['-rv2-'].update(disabled=True) if table_data[values['-table-'][0]]['songs'] == 1 else window['-rv2-'].update(disabled=False)

            if values["-om-"] == 'Text':
                window["-l-"].update(visible=False)
                window["-t-"].update(visible=True)
            elif values["-om-"] == 'Link':
                window["-t-"].update(visible=False)
                window["-l-"].update(visible=True)
            self.search_method = values['-om-']
        
    def downloadPlaySong(self):
        self.runGui()
        
        if self.search_method == 'Link':
            while not ('/playlist?' in str(self.url) or '/watch?' in str(self.url)):
                self.runGui(w='Link inválido, verifique-o e tente novamente.')
            while True:
                if '/playlist?' in self.url:
                    try:
                        pl = Playlist(self.url)
                        self.songs_urls = list(pl)
                        self.addPlaylist(new_playlist=(pl.playlist_url, pl.title, pl.length))
                    except:
                        sleep(1)
                        continue
                    
                    if self.random_song:
                        shuffle(self.songs_urls)
                    
                elif '/watch?' in self.url:
                    self.songs_urls = [self.url]
                break
            
        elif self.search_method == 'Text':
                search = Search(query=self.query) 
                results = search.results
                self.songs_urls = [results[0].watch_url]
        
        self.songs_finished = False
        self.current_song_changed = False
        self.song_index = 0
        
        while not self.songs_finished:
            try:
                yt = YouTube(str(self.songs_urls[self.song_index]))
                
                self.addSong(new_song=(yt.watch_url, yt.title)) if len(self.songs_urls) == 1 else None
            except:
                sleep(1)
                continue
            
            try:
                video = yt.streams.filter(only_audio=True).first()
                video_bytes = BytesIO()

                video.stream_to_buffer(video_bytes)
                video_bytes.seek(0)
            except:
                sleep(1)
                continue
            
            ffmpeg_command = ['ffmpeg', '-i', '-', '-vn', '-y', '-f', 'wav', '-hide_banner', '-loglevel', 'panic', '-nostdin', '-']

            process = Popen(ffmpeg_command, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True)
            audio, _ = process.communicate(input=video_bytes.getvalue())
            
            song = mixer.Sound(audio)
            
            self.song_channel.play(song)
            self.song_channel.set_volume(0)
            sleep(0.5)
            self.song_channel.set_volume(1)
            
            while self.song_channel.get_busy():
                sleep(0.1)
                if not self.system_tray.is_alive():
                    sys.exit()
                if self.main_thread_rungui:
                    self.runGui()
                    
                    if self.current_song_changed:
                        self.songs_finished = True
                        self.skipSong()
                        self.main_thread_rungui = False
                    else:
                        self.song_channel.unpause()
            del audio
            
            self.song_index += 1
            
            if self.song_index+1 > len(self.songs_urls):
                self.songs_finished = True
        
    def changeSong(self):
        self.song_channel.pause()
        
        self.main_thread_rungui = True
        
    def skipSong(self):
        self.song_channel.stop()
        self.paused = False
    
    def pauseUnpauseSong(self):
        self.song_channel.unpause() if self.paused else self.song_channel.pause()
        self.paused = not self.paused
        
    def readSongs(self) -> list:
        cursor = self.database.cursor()
        
        cursor.execute("CREATE TABLE songs (url text, title text, songs integer)")
        self.database.commit()
        cursor.execute("SELECT * FROM songs")
        
        data = cursor.fetchall()
        
        return data
    
    def addPlaylist(self, new_playlist):
        
        cursor = self.database.cursor()
        
        cursor.execute(f"INSERT INTO songs VALUES({new_playlist[0]}, {new_playlist[1]}, {new_playlist[2]})")

        self.database.commit()
    
    def addSong(self, new_song):
        cursor = self.database.cursor()
        
        cursor.execute(f"INSERT INTO songs VALUES({new_song[0]}, {new_song[1]}, 1)")

        self.database.commit()
    
    def systemTray(self):  
        self.system_tray_icon = pystray.Icon(name='FK play song')
        self.system_tray_icon.title = 'FK play song'
        self.system_tray_icon.icon = Image.open('./icon.ico')
        self.system_tray_icon.menu = pystray.Menu(
            pystray.MenuItem('Reproduzir / Pausar', self.pauseUnpauseSong),
            pystray.MenuItem('Passar', self.skipSong),
            pystray.MenuItem('Mudar de música/playlist', self.changeSong),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Sair', self.system_tray_icon.stop),
        )
        
        self.system_tray_icon.run()
        self.database.close()
    def run(self):
        while True:
            app.downloadPlaySong()
if __name__ == '__main__':
    mixer.init()
    
    app = App()
    
    app.system_tray.start()
    app.run()