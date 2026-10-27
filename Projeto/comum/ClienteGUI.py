# Janela do cliente (baseada no ClienteGUI do Kurose).
# Botões: Play (pede a stream), Pause (deixa de a pedir), Teardown (sai).
# A frame mais recente chega por db.entregar_local -> self.ultima_frame e a
# janela vai buscá-la de 40 em 40 ms (o Tkinter só pode ser usado nesta thread).

import io
from tkinter import Button, Label, W, E, N, S

from PIL import Image, ImageTk


class ClienteGUI:
    def __init__(self, master, ao_play, ao_pause):
        self.master = master
        self.ao_play = ao_play
        self.ao_pause = ao_pause
        self.ultima_frame = None
        self.frame_mostrada = None
        self.createWidgets()
        self.master.protocol("WM_DELETE_WINDOW", self.exitClient)
        self.master.after(40, self.updateMovie)

    def createWidgets(self):
        self.start = Button(self.master, width=20, padx=3, pady=3, text="Play", command=self.ao_play)
        self.start.grid(row=1, column=0, padx=2, pady=2)
        self.pause = Button(self.master, width=20, padx=3, pady=3, text="Pause", command=self.ao_pause)
        self.pause.grid(row=1, column=1, padx=2, pady=2)
        self.teardown = Button(self.master, width=20, padx=3, pady=3, text="Teardown", command=self.exitClient)
        self.teardown.grid(row=1, column=2, padx=2, pady=2)
        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=3, sticky=W + E + N + S, padx=5, pady=5)

    def updateMovie(self):
        """Mostra a frame mais recente (se for nova)."""
        frame = self.ultima_frame
        if frame is not None and frame is not self.frame_mostrada:
            self.frame_mostrada = frame
            try:
                photo = ImageTk.PhotoImage(Image.open(io.BytesIO(frame)))
                self.label.configure(image=photo, height=288)
                self.label.image = photo
            except Exception:
                pass                          # frame corrompida: salta
        self.master.after(40, self.updateMovie)

    def exitClient(self):
        self.master.quit()
