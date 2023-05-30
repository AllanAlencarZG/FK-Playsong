from pytube import YouTube, Playlist
from os import remove
from random import shuffle
import sys
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt5.QtGui import QIcon
from threading import Thread
from pygame import mixer
from time import sleep, time
import PySimpleGUI as sg 
from tempfile import mktemp
from io import BytesIO
import json
from subprocess import call

class App:
    def __init__(self) -> None:
        self.url = None
        self.playlist_urls = None
        self.paused = False
        self.random_song = False
        self.playlist_finished = False
        self.song_index = 0
        self.system_tray = Thread(target=self.systemTray)
        self.song_channel = mixer.Channel(0)
    
    def runGui(self, w=''):
        sg.theme('SystemDefault')
        sg.set_global_icon('icon.ico')
        
        table_data = self.readPlaylist()
        
        window = sg.Window('Toca música', layout=[
            [sg.Frame('Link', [
                [sg.Text('Url : '), sg.Input(key='-url-')],
                [sg.Button('Play', size=(5,1), key='-p-'), sg.Button('Cancel')],
                [sg.Checkbox('random song', key='-rv-')]
                ], element_justification='center')],
            [sg.Text(w, text_color='red')],
            [sg.Frame('Recent playlists', [
                [sg.Table(values=[[p['title'], p['songs']] for p in table_data], headings=['título', 'songs'], expand_x=True, expand_y=True, justification='center', key='-table-')],
                [sg.Button('Play', size=(5,1), key='-p2-')],
                [sg.Checkbox('random song', key='-rv2-')]
            ], expand_x=True, expand_y=True, element_justification='center')]
        ], icon='icon.ico', element_justification='center', return_keyboard_events=True)
        
        old_input = []
        
        t = time()
        
        while True:
            event, values = window.read(timeout=100)
            
            if event == '-p-' and len(values['-url-']) > 0:
                self.random_song = values['-rv-']
                self.url = values['-url-']
                window.close()
                break
            elif event == 'Cancel':
                window.close()
                break
            elif event == sg.WIN_CLOSED:
                window.close()
                self.system_tray_app.exit()
                sys.exit()
            elif event == '-p2-' and len(values['-table-']) > 0:
                self.random_song = values['-rv2-']
                self.url = table_data[values['-table-'][0]]["url"]
                window.close()
                break
            elif event == 'z:90' and window.Element('-url-') == window.FindElementWithFocus():
                try:
                    window['-url-'].update(old_input[-2])
                    del old_input[-1]
                except IndexError:
                    window['-url-'].update('')
            if time() - t > 0.5 and window.Element('-url-') == window.FindElementWithFocus():
                if len(old_input) > 0 and old_input[-1] != values['-url-'] and len(values['-url-']) > 0:
                    old_input.append(values['-url-'])
                elif len(old_input) == 0 and len(values['-url-']) > 0:
                    old_input.append(values['-url-'])
                t = time()

            
            if not self.system_tray.is_alive():
                window.close()
                sys.exit()

    def downloadStartSong(self):
        self.runGui()
        while not ('/playlist?' in str(self.url) or '/watch?' in str(self.url)):
            self.runGui(w='Link inválido, verifique-o e tente novamente')
        while True:
            if '/playlist?' in self.url:
                try:
                    pl = Playlist(self.url)
                    self.playlist_urls = list(pl)
                    
                    self.addPlaylist(new_playlist={"url": pl.playlist_url, "title": pl.title, "songs": pl.length})
                except:
                    sleep(1)
                    continue
                
                if self.random_song:
                    shuffle(self.playlist_urls)
                
            elif '/watch?' in self.url:
                self.playlist_urls = [self.url]
            
            break
        
        self.playlist_finished = False
            
        while not self.playlist_finished:
            try:
                yt = YouTube(str(self.playlist_urls[self.song_index]))
                
                print(yt.title)
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
            
            temp_path_video = mktemp(suffix='.mp4')
            temp_path_audio = mktemp(suffix='.wav')

            with open(temp_path_video, 'wb') as tfv:
                tfv.write(video_bytes.getvalue())

            cmd_ffmpeg = [
                'ffmpeg',
                '-i', temp_path_video,
                '-vn',
                '-acodec', 'pcm_s16le',
                '-ar', '44100',
                '-ac', '2',
                temp_path_audio
            ]

            try:
                call(cmd_ffmpeg, shell=True)
            except:
                sleep(1)
                continue
            finally:
                remove(temp_path_video)
                video_bytes.close()
            
            with open(temp_path_audio, 'rb') as tfa:
                audio = tfa.read()
            
            song = mixer.Sound(audio)
            
            self.song_channel.play(song)
            self.song_channel.set_volume(0)
            sleep(0.1)
            self.song_channel.set_volume(1)
            
            while self.song_channel.get_busy():
                sleep(0.1)
                if not self.system_tray.is_alive():
                    sys.exit()

            remove(temp_path_audio)
            
            self.song_index += 1
            
            if self.song_index+1 > len(self.playlist_urls):
                self.playlist_finished = True
        
        self.downloadStartSong()

    def changeSong(self):
        self.url = None
        self.playlist_finished = True
        self.song_index = 0
        self.skipSong()
        
    def skipSong(self):
        self.song_channel.stop()
        self.paused = False
    
    def pauseUnpauseSong(self):
        self.song_channel.unpause() if self.paused else self.song_channel.pause()
        self.paused = not self.paused
        
    def readPlaylist(self) -> list:
        with open('playlists.json', 'rb') as plj:
            pl_json = json.load(plj)
            return pl_json
        
    def addPlaylist(self, new_playlist=dict):
        
        playlist_list = list(self.readPlaylist())
        
        if not new_playlist in playlist_list:
            playlist_list.append(new_playlist)
        
            with open('playlists.json', 'w') as plj:
                plj.write(json.dumps(playlist_list))
    
    def systemTray(self):
        self.system_tray_app = QApplication(sys.argv)

        trayIcon = QSystemTrayIcon(QIcon('./icon.ico'), parent=self.system_tray_app)
        trayIcon.setToolTip('Toca Música')
        trayIcon.show()

        menu = QMenu()

        play_pause = menu.addAction('Reproduzir / Pausar')
        passar = menu.addAction('Passar')
        change = menu.addAction('Mudar de música/playlist')
        
        menu.addSeparator()
        
        exitwindow = menu.addAction('Sair')
        
        play_pause.triggered.connect(self.pauseUnpauseSong)
        passar.triggered.connect(self.skipSong)
        change.triggered.connect(self.changeSong)
        exitwindow.triggered.connect(self.system_tray_app.exit)
        
        trayIcon.setContextMenu(menu)
        
        self.system_tray_app.exec_()
        
if __name__ == '__main__':
    mixer.init()
    
    app = App()
    
    app.system_tray.start()
    app.downloadStartSong()