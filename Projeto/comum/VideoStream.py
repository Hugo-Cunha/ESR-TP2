# Leitura de um vídeo .Mjpeg (exemplo do Kurose).
#
# Formato do ficheiro: cada frame é guardada como
#     5 bytes em texto com o tamanho da frame  +  a imagem JPEG
# ex.: b"04712" seguido de 4712 bytes de JPEG.


class VideoStream:
    def __init__(self, filename):
        self.filename = filename
        self.file = open(filename, "rb")
        self.frameNum = 0

    def nextFrame(self):
        """Devolve a próxima frame; no fim do ficheiro recomeça (stream contínua)."""
        data = self.file.read(5)
        if not data:
            self.file.seek(0)
            data = self.file.read(5)
        framelength = int(data)
        self.frameNum += 1
        return self.file.read(framelength)

    def frameNbr(self):
        return self.frameNum
