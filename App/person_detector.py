# /*=========================================================*\
# |      /============================================\       |
# |     ||  -   Código para contagem de pessoas,    - ||      |
# |     ||  -  Entrando e saindo do local, c/ WIFI  - ||      |
# |     ||  -        Projeto: People Counter        - ||      |
# |     ||  -  Tecnologia: IA + Color Track + WIFI  - ||      |
# |     ||  -    Módulo: Sipeed MAix Bit ou duino   - ||      |
# |     ||  -          DataLab de IA - PTI          - ||      |
# |     ||  -                                       - ||      |
# |     ||  -   Desenvolvido por: Thiago Piovesan   - ||      |
# |     ||  -          Versao atual: 4.0.0          - ||      |
# |      \============================================/       |
# \*=========================================================*/

# Firmware utilizado: v0.5.0 ou v0.6.2_66
# Link do Github: https://github.com/ThiagoPiovesan

# O presente programa usa como base a mudança de pixels/cor na area monitorada, portanto nao
# necessariamente possui um modelo para reconhecimento de um objeto por tras dele.

#==================================================================================================#
# Bibliotecas utilizadas:
import sensor, image, lcd
import usocket, ustruct, utime
import json, time, os

from machine import WDT                                     # Importing wacthdog Lib

from libs.network_esp32 import wifi
from libs.simple_tracker import Tracker
from libs.simple import MQTTClient

from libs.log import Log

mac = 'c50f1c499346925eaa8c509469e80d5c'
#================================== PROGRAMA WATCHDOG ============================================#
# Função dedicada para desenhar as linhas:

def on_wdt(self):
    print(self.context(), self)
    self.feed()

#--------------------------------------------------------------------------------------------------#
# Configurações Iniciais
wdt1 = WDT(id=1, timeout=10000, callback=on_wdt, context={})# Watchdog init
lib = os.listdir("/sd")                                     # Configuração do cartão SD

#--------------------------------------------------------------------------------------------------#

# Grayscale Color Tracking --> Threshold [118, 168]
#--------------------------------------------------------------------------------------------------#
lcd.init(freq=15000000)                                     # Iniciando LCD

#==================================================================================================#
# Aviso de Inicialização:

print()
print('#-----------------------------------------------------------------------------------------#')
print("Initializing Setup")
print("Letting auto algorithms run. Don't put anything in front of the camera!")
print('#-----------------------------------------------------------------------------------------#')

#print("files:", os.listdir("/flash"))
#print("files:", os.listdir("/sd/libs"))
#==================================================================================================#
# Configuraçoes Iniciais:

sensor.reset(dual_buff=True)                                # Initialize the camera sensor.
sensor.set_pixformat(sensor.GRAYSCALE)                      # Deixa em tons de cinza
sensor.set_framesize(sensor.QVGA)                           # set frame size to QVGA (320x240)

sensor.skip_frames(time = 3000)
sensor.set_auto_gain(False)                                 # must be turned off for color tracking
sensor.set_auto_whitebal(False)                             # must be turned off for color tracking

wdt1.feed()                                                 # Alimenta o Watchdog

clock = time.clock()

timeout = 15                                                # Timeout para remover o ID
tracker = Tracker(max_distance=70, timeout=timeout)         # Inicialização do object Tracker

# -----------------------------
# Configurando Wi-fi --> SSID + Pasw

SSID = "SmartPTI"
PASW = "SmartPT12017."
#SSID = "LabdeIA_teste"
#PASW = "labdeia123"

# -----------------------------
# Configurando MQTT --> Port + User + Password + tópico + host

serverPort = 1883
usr = "SipeedMV"
passwd = "labia"
server = "192.168.1.103"                                    # 172.25.239.72 # "test.mosquitto.org"
client_id = "Sipeed_1"
topic = "lab/personCT"

#==================================================================================================#
# Definiçoes importantes:

# Capture the color thresholds for whatever was in the center of the image.

threshold = [127, 127]                                      #[120, 160] 90, 160 (80, 125)
TRIGGER_THRESHOLD = 15                                      # Diferença mínima entre o objeto e o fundo

#==================================================================================================#
# Variaveis de Controle:

width = 320                                                 # Comprimento total da imagem capturada
height = 240                                                # Altura total da imagem capturada

line_alignment = 'Vertical'                                 # Alinhamento vertical

log_init = True                                             # True: Habilita o log, False: desabilita
log_file = "/sd/logs/log_personModule.txt"                  # Local onde estará o arquivo de log
#--------------------------------------------------------------------------------------------------#
# Marcação do posicionamento das linhas:

if (line_alignment == 'Vertical'):
    line_down = int(width*(2/3))                            # Desenha uma linha em 2/3 do comprimento
    line_up = int(width*(1/3))                              # Desenha uma linha em 1/3 do comprimento
else:
    line_down = int(height*(2/3))                           # Desenha uma linha em 2/3 do comprimento
    line_up = int(height*(1/3))                             # Desenha uma linha em 1/3 do comprimento
#--------------------------------------------------------------------------------------------------#
# Controladores de pessoas:

person_in = 0                                               # Pessoas que entraram na cena
person_out = 0                                              # Pessoas que saíram da cena
person_total = 0                                            # Pessoas total dentro do recinto

#--------------------------------------------------------------------------------------------------#
# Configurações Iniciais - DATETIME:
set_time = (2022, 01, 03, 16, 35, 0, 0, 27)                 # Alterar em todo início de programa

#--------------------------------------------------------------------------------------------------#
# Salvando Imagem para subtração de fundos:

img = sensor.snapshot()                                     # Tira uma "foto" do fundo
img2 = img.copy()                                           # Salva uma cópia
lcd.display(img)                                            # Printa no LCD

print("Saved background image - Now frame differencing!")
#print('#-----------------------------------------------------------------------------------------#')


#================================= PROGRAMA DRAW LINES ============================================#
# Função dedicada para desenhar as linhas:

def drawLines(img, width, height, line_alignment):
    if (line_alignment == 'Vertical'):
        # x0,y0, x1,y1 ---> y0 = y1 -> Linha na horizontal // x0 = x1 -> Linha na verticual
        img.draw_line(int(width*(1/3)), 0, int(width*(1/3)), int(height), color=(100,100,100), thickness=3)     # Desenha a linha Vertical
        img.draw_line(int(width*(2/3)), 0, int(width*(2/3)), int(height), color=(100,100,100), thickness=3)     # Desenha a linha Vertical
    else:
        # x0,y0, x1,y1 ---> y0 = y1 -> Linha na horizontal // x0 = x1 -> Linha na verticual
        img.draw_line(int(height*(1/3)), 0, int(height*(1/3)), int(width), color=(100,100,100), thickness=3)     # Desenha a linha Vertical
        img.draw_line(int(height*(2/3)), 0, int(height*(2/3)), int(width), color=(100,100,100), thickness=3)     # Desenha a linha Vertical

#================================= PROGRAMA GOING UP ==============================================#

def goingup(line_down, line_up, objects, state):

    # Ve se tem pelo menos 2 dados de movimento do objeto para saber a direçao dele
    if len(objects) >= 2:
        # Ve se o status é 0
        if state == 0:
            # Checa o sentido da passagem:
            if objects[-1][0] < line_up and objects[-2][0] >= line_up:

                return True
#--------------------------------------------------------------------------------------------------#
        else:
            return False
#--------------------------------------------------------------------------------------------------#
    else:
        return False

#================================= PROGRAMA GOING DOWN ============================================#

def goingdown(line_down, line_up, objects, state):

    # Ve se tem pelo menos 2 dados de movimento do objeto para saber a direçao dele
    if len(objects) >= 2:
        # Ve se o status
        if state == 0:
            # Checa o sentido da passagem:
            if objects[-1][0] > line_down and objects[-2][0] <= line_down:
                print(objects[-1][0])
                return True
#--------------------------------------------------------------------------------------------------#
        else:
            return False
#--------------------------------------------------------------------------------------------------#
    else:
        return False

#============================== PROGRAMA WIFI CONECT ==============================================#
def wifi_conect(SSID, PASW):
    while wifi.isconnected() == False:
        try:

            wifi.reset()

            print()
            print('#-----------------------------------------------------------------------------------------#')
            print('Trying to connect wifi...')

            wifi.connect(SSID, PASW)

            if wifi.isconnected():
                break

        except Exception as e:
            print(e)

    print('Network Status: ', wifi.isconnected(), wifi.ifconfig())
    print('Wifi conected...')
    print('#-----------------------------------------------------------------------------------------#')


#============================== PROGRAMA MQTT CONECT ==============================================#
def mqtt_conect():
    print('Trying to connect to MQTT server...')
#--------------------------------------------------------------------------------------------------#
    client = MQTTClient(client_id=client_id, server=server, port=serverPort, user=usr, password=passwd)
    client.connect()                                                    # Try to conect to MQTT server

#--------------------------------------------------------------------------------------------------#
    client.publish(topic=topic, msg="Conected")                         # Publish a msg on the topic
    time.sleep_ms(100)

    client.disconnect()                                                 # Broke conection
#--------------------------------------------------------------------------------------------------#
    print('Successful connected to MQTT server...')
    print('#-----------------------------------------------------------------------------------------#')


#============================== PROGRAMA MQTT Send ================================================#
def mqtt_send(person_in, person_out, total):
    wdt1.feed()
    print('Sending message to MQTT server...')
#--------------------------------------------------------------------------------------------------#
    client = MQTTClient(client_id=client_id, server=server, port=serverPort, user=usr, password=passwd)
    client.connect()                                                    # Try to conect to MQTT server

#--------------------------------------------------------------------------------------------------#
    string = "Person in: " + str(person_in) + "\n Person out: " + str(person_out) + "\n Total inside: " + str(total)

    client.publish(topic=topic, msg=string)                             # Publish a msg on the topic
    time.sleep_ms(10)

    client.disconnect()                                                 # Broke conection
#--------------------------------------------------------------------------------------------------#
    print('Message sent successfully to MQTT server...')
    print('#-----------------------------------------------------------------------------------------#')

#============================== PROGRAMA MQTT Send JSON ===========================================#
def create_json(event, value, mac):
    wdt1.feed()
    print('Creating JSON packet to send...')
#--------------------------------------------------------------------------------------------------#
    # Montando a string json

    string = '''
    {
        "Action": "",

        "Description": "",

        "Value": "",

        "MacAddr": ""
    }
    '''
#--------------------------------------------------------------------------------------------------#
    jsonn = json.loads(string)
#--------------------------------------------------------------------------------------------------#

    jsonn["Action"] = event

    if event == "Person In":
        jsonn["Description"] = "Pessoa entrou no recinto"
    else:
        jsonn["Description"] = "Pessoa deixou o recinto"

    jsonn["Value"] = value
    jsonn["MacAddr"] = mac

    print(jsonn)
    print('#-----------------------------------------------------------------------------------------#')
#--------------------------------------------------------------------------------------------------#
    return jsonn

#============================== PROGRAMA MQTT Send JSON ===========================================#
def mqtt_send_json(string):
    wdt1.feed()
    print('Sending JSON message to MQTT server...')
#--------------------------------------------------------------------------------------------------#
    #client = MQTTClient(client_id=client_id, server=server, port=serverPort, user=usr, password=passwd)
    #client.connect()                                                    # Try to conect to MQTT server

#--------------------------------------------------------------------------------------------------#

    #client.publish(topic=topic, msg=jsonn)                              # Publish a msg on the topic
    time.sleep_ms(10)

    #client.disconnect()                                                 # Broke conection
#--------------------------------------------------------------------------------------------------#
    print('Message sent successfully to MQTT server...')
    print('#-----------------------------------------------------------------------------------------#')

#================================= PROGRAMA MAIN ==================================================#
def main(threshold, person_in, person_out, width, height, line_down, line_up, line_alignment):
    # Salva a quantidade de objetos presentes na cena e a posiçao deles
    objects = []

    # Armazena os IDs que estao atualmente no frame
    counter_id = []

    # Status atual --> 0 = Nao passou; 1 = Passou:
    state = 0

    # Direcao da pessoa:
    direct = ''

    # Total de pessoas interno:
    total = 0
#--------------------------------------------------------------------------------------------------#
    # Evento ocorrido --> "Entrou" ou "Saiu":
    event = ""

    # Valor da última atualização:
    value = 0

#--------------------------------------------------------------------------------------------------#
    while(True):
        wdt1.feed()                                                     # Alimenta o Watchdog

        clock.tick()
        img = sensor.snapshot()                                         # Tira foto do frame atual
#--------------------------------------------------------------------------------------------------#
        # Replace the image with the "abs(NEW-OLD)" frame difference.
        img.difference(img2)                                            # Compara o frame atual com o inicial

        hist = img.get_histogram()                                      # Pega o histograma da comparação
        # This code below works by comparing the 99th percentile value (e.g. the
        # non-outlier max value against the 90th percentile value (e.g. a non-max
        # value. The difference between the two values will grow as the difference
        # image seems more pixels change.
        diff = hist.get_percentile(0.99).l_value() - hist.get_percentile(0.90).l_value()
#--------------------------------------------------------------------------------------------------#
        triggered = diff > TRIGGER_THRESHOLD                            # Ve se a diferença é suficientemente

#--------------------------------------------------------------------------------------------------#
        # Threshold -> Cor que eu quero ficar monitoreando [min, max] -> Escala de cinza
        # Pixels th -> Quantidade minima de pixels que o objeto deve ter para ser manitorado
        # Area thrs -> Area minima em pixels que o objeto deve ter para ser manitorado
        # Merge = False -> Nao junta objetivo proximos
        # Margin -> Margem minima entre dois objetos para serem agrupados juntos
        if triggered:
            lo = hist.get_percentile(0.01) # Get the CDF of the histogram at the 1% range (ADJUST AS NECESSARY)!
            hi = hist.get_percentile(0.99) # Get the CDF of the histogram at the 99% range (ADJUST AS NECESSARY)!
            # Average in percentile values.
            threshold[0] = (threshold[0] + lo.value() + diff) // 2      # Atualiza o Threshold
            threshold[1] = (threshold[1] + hi.value() + diff) // 2      # Atualiza o Threshold

            #print(threshold)

            bob = img.find_blobs([threshold], pixels_threshold=700, area_threshold=550, merge=True, margin=50)

    #--------------------------------------------------------------------------------------------------#
            drawLines(img, width, height, line_alignment)               # Desenha a linha na tela

    #--------------------------------------------------------------------------------------------------#
            for blob in bob:
                # Pega as dimensoes da bounding box criada -->
                x, y, w, h = blob.rect()

                img.draw_rectangle(blob.rect())                         # Desenha um retangulo em torno
                img.draw_cross(blob.cx(), blob.cy(), color=(0,0,150))   # Desenha uma cruz no centro
                img.draw_circle(blob.cx(), blob.cy(), 3, color=(0,0,150), thickness=2, fill=True)

                #lcd.display(img)
    #--------------------------------------------------------------------------------------------------#
                # Define o centroide e ID:

                centroids = [(blob.cx(), blob.cy())]
                lost_tracking = tracker.update(centroids)

                if lost_tracking != []:
                    print("ID saiu: " + str(lost_tracking[0]['id']))
                    objects = []                                        # Apaga o ID quando sai
                    #counter_id[lost_tracking[0]['id']] = null

                for id, point in tracker.points.items():
                    pid = id
                    img.draw_string(point[0], point[1], str(id), scale=2)   # Desenha o ID
                    #objcts.append([blob.cx(), blob.cy(), blob.rect()])
    #--------------------------------------------------------------------------------------------------#

                if ( abs(x - blob.cx()) <= h and abs(y - blob.cy()) <= w ): # Ve onde o objeto está
                    objects.append([blob.cx(), blob.cy()])              # Salva a posição

                    if (goingup(line_down, line_up, objects, state) == True):
                        person_in += 1                                  # Pessoa Entrou:
                        print("Person crossed goung up")
                        state = 1
                        direct = "up"

                    elif (goingdown(line_down, line_up, objects, state) == True):
                        person_out += 1                                 # Pessoa Saiu:
                        print("Person crossed goung down")
                        state = 1
                        direct = "down"

    #--------------------------------------------------------------------------------------------------#
                if state == 1:                                          # Estado do movimento:
                    if direct == "down" and x > line_up:
                        objects = []
                        direct = ""
                        state = 0
                        event = "Person Out"
                        value = person_out

                    if direct == "up" and x < line_down:
                        objects = []
                        direct = ""
                        state = 0
                        event = "Person In"
                        value = person_in
#--------------------------------------------------------------------------------------------------#
                    total = person_in - person_out                      # Total de pessoas
                    if total < 0:
                        total = 0

                    #mqtt_send(person_in, person_out, total)
                    jsn = create_json(event, value, mac)
                    #mqtt_send_json(jsn)
                    logger.update_inference(person_in, person_out, total)

#==================================================================================================#
        # Atualiza Contagem de pessoas --> Printss
        drawLines(img, width, height, line_alignment)                   # Desenha a linha na tela

        st1 = "In:[" + str(person_in) + "]"
        st2 = "Out:[" + str(person_out) + "]"
        st3 = "Total:[" + str(total) + "]"

        img.draw_string(3, 180, st1, color=(85, 85, 85), scale=1.5)     # Desenha String 1
        img.draw_string(3, 200, st2, color=(85, 85, 85), scale=1.5)     # Desenha String 2
        img.draw_string(3, 220, st3, color=(85, 85, 85), scale=1.5)     # Desenha String 3

        fps = clock.fps()                                               # Salva o FPS
        img.draw_string(width-50, 2, ("%2.1ffps" %(fps)), color=(100,100,100), scale = 1.25)   # Display FPS

        lcd.display(img)                                                # Printa no LCD
        #print(clock.fps())


#================================= PROGRAMA PRINCIPAL =============================================#
print('#-----------------------------------------------------------------------------------------#')
wdt1.feed()                                                             # Alimenta o Watchdog

wifi_conect(SSID, PASW)                                                 # Conecta no Wi-fi
#mqtt_conect()                                                           # Conecta no MQTT
wdt1.feed()                                                             # Alimenta o Watchdog

#--------------------------------------------------------------------------------------------------#
logger = Log(log = log_init, wifi_conection = True, aq_name = log_file, init_time = set_time)
logger.initialization()

content = logger.read_log()

print("Readed:\n" + content)
#--------------------------------------------------------------------------------------------------#
# Programa Principal:
main(threshold, person_in, person_out, width, height, line_down, line_up, line_alignment)
#==================================================================================================#
