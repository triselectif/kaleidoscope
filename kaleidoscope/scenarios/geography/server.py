from os.path import dirname, join, realpath
from os import walk
from kaleidoscope.scenario import KalScenarioServer
from time import time, sleep
from json import load
from random import random

from kivy.core.window import Window
from kivy.uix.widget import Widget
from kivy.core.image import Image
from kivy.uix.image import Image as ImageWidget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scatter import Scatter
from map_common import Map, MapThumbnail
from random import randint
from kivy.resources import resource_add_path, resource_remove_path
from kivy.lang import Builder
from kivy.animation import Animation
from kivy.properties import ListProperty, DictProperty, StringProperty, NumericProperty

TIMER_1 = 40
TIMER_2 = 25
TIMER_3 = 9
MAX_CLIENT_ITEMS = 3

background = Image(join(dirname(__file__), 'background.png'))
background.texture.wrap = 'repeat'
btnbg = Image(join(dirname(__file__), 'buttonbackground.png')).texture

# vert, jaune, bleu, rose
map_colors = (
    (92, 179, 103),
    (194, 222, 65),
    (92, 145, 179),
    (227, 53, 119),
)
map_logos = (
    'umbrella',
    'horse',
    'plane',
    'ying',
)
layers = ["regions","mountains","rivers","cities"]

map_coordinates = (
    (200,20),
    (703,642)
)#pos, size

scenariol = -2




class MapServerLayout(FloatLayout):
    pass

from kivy.factory import Factory
Factory.register('MapServerLayout', cls=MapServerLayout)


class MapServer(KalScenarioServer):
    json_filename = StringProperty('')
    scenariol = NumericProperty(-2)
    layers = ListProperty( ["mountains","rivers","cities","regions"] )

    def search_data_files(self):
        blacklist = ('__init__.py', )
        curdir = realpath(dirname(__file__))
        for root, dirnames, filenames in walk(dirname(__file__)):
            for filename in filenames:
                if filename.startswith('.'):
                    continue
                if filename in blacklist:
                    continue
                filename = join(root, filename)
                filename = realpath(filename)
                if filename.startswith(curdir):
                    filename = filename[len(curdir):]
                if filename.startswith('/'):
                    filename = filename[1:]
                yield filename

    def __init__(self, *largs):
        self.resources = list(self.search_data_files())
        resource_add_path(dirname(__file__))
        Builder.load_file(join(dirname(__file__), 'map.kv'))
        super(MapServer, self).__init__(*largs)
        self.timeout = 0
        self.timemsg = 0
        self.players = {}

        # init client table
        for client in self.controler.clients:
            self.players[client] = {
                'client': client,
                'name': self.controler.get_client_name(client),
                'ready': False,
                'done': False,
                'place': self.controler.metadata[client]['place'],
                'count': 0
            }
        #store mapitems and thumbs in order to display them on main screen
        #or remove them from clients
        self.mapitems = {} #filename: [client, index]
        self.thumbs = {} #index: [client, pos]

        #get map layers list from json
        self.load_json() 

    def load_json(self):
        global layers
        curdir = join(dirname(__file__), 'data')
        json_filename = join(curdir, 'scenario.json')
        resource_add_path(curdir)
        with open(json_filename, 'r') as fd:
            data = load(fd)
        layers = data['layers']       

    def client_login(self, client):
        self.players[client]['ready'] = True

    def client_logout(self, client):
        del self.players[client]

    def start(self):
        '''Scenario start, wait for all player to be ready
        '''
        super(MapServer, self).start()
        self.send_all('WAITREADY')
        self.state = 'waitready'

    def stop(self):
        Builder.unload_file(join(dirname(__file__), 'map.kv'))
        resource_remove_path(dirname(__file__))

    def init_ui(self):   
        size = map_coordinates[1]
        cx,cy = Window.center
        pos = (cx - size[0]/3.,cy - size[1]/3.)
        if scenariol == -2 : layers2 = []
        elif scenariol == -1 : layers2 = layers
        else : layers2 = layers[int(scenariol)]

        self.layout = MapServerLayout()
        self.imagemap = imagemap = Map(
                server=True, 
                size_hint=(None, None),
                size = size,
                layers = layers2
                )
        self.map_background = ImageWidget(
                 source = 'data/map.png',
                 size_hint = imagemap.size_hint,
                 size = imagemap.size,
                 )
        self.scat = Scatter(
                size_hint = imagemap.size_hint,
                size = imagemap.size,
                center = pos, 
                scale = .8,
                rotation = 0,
                do_translation = False,
                do_scale = False   
                )
        self.layout.add_widget(self.scat)
        self.scat.add_widget(self.map_background)
        self.scat.add_widget(self.imagemap)
        self.controler.app.show(self.layout)

    #
    # Client commands received
    # do_client_<command>(client, [...])
    #
    def do_client_scenario(self, client, args):
        global scenariol
        scenariol = int(args[0])

    def do_client_ready(self, client, args):
        self.players[client]['ready'] = True
        count = len([x for x in self.players.itervalues() if not x['ready']])
        if count:
            self.msg_all('@%s ok, en attente de %d joueur(s)' % (
                self.players[client]['name'], count))

    def do_client_flagchange(self, client, args):
        filename = self.index2filename( int(args[0]) )
        thumb_index = int(args[1])
        #print "SERVER : do_client_flagchange: "+ str(client)+','+str(filename)+str(thumb_index)

        if filename not in self.mapitems.keys():
            self.mapitems[filename] = []
        if thumb_index not in self.thumbs.keys():
            self.thumbs[thumb_index] = [None, (0,-300)]
        c = len( self.mapitems[filename] )    

        #hide from screen and free current thumb_index 
        if thumb_index == -1 :
            #get thumb
            d = self.mapitems[filename]
            for i in d:
                cl,ti = i
                if cl == client :
                    d = ti
            thumb = self.index2thumb(d) 
            #remove thumb from screen
            self.scat.remove_widget(thumb)
            #save
            if (client, d) in self.mapitems[filename] :
                self.mapitems[filename].remove( (client, d) )      
            #remove mapitem from screen
            if len( self.mapitems[filename] ) == 0 :
                self.imagemap.hide_mapitem(filename)
            """ 
            #add thumb to other clients
            self.display_thumb(client, d)
            self.display_mapitem(client,filename) 
            """
            
        #display
        elif c >= 0 :
            #store new
            self.mapitems[filename].append( (client, thumb_index) )
            self.thumbs[thumb_index] = [client, self.thumbs[thumb_index][1] ]
            if c == 0:
                #display mapitem on main screen
                self.imagemap.display_mapitem(filename, True, (0,0,0,1))
            thumb = self.create_and_add_item(client, thumb_index)
            """
            #hide thumb on clients except client
            self.hide_thumb(client, thumb_index)
            self.hide_mapitem(client, filename)         
            """ 
    def index2filename(self,index):
        #trick to pass mapitem.filename (string) as a integer (protocol blocks strings..)
        return self.imagemap.data[index]['filename']

    def create_and_add_item(self, client, index):
        th = self.index2thumb(index) 
        thumb = self.imagemap.get_thumb(index)
        player_place = int(self.players[client]["place"])-1
        r,g,b = map_colors[ player_place ]
        thumb.color = [r/255.,g/255.,b/255.,1.]
        thumb.pos = (0,-400)
        right_pos = self.imagemap.retrieve_pixels_location(thumb.item['filename'])
        if right_pos is not None : 
            thumb.right_pos = right_pos
        else : 
            thumb.right_pos = (0,0)
        self.scat.add_widget(thumb)
        if index in self.thumbs.keys() and thumb != None:
            thumb.center = self.thumbs[index][1]
        thumb.locked = True
        return thumb

    def do_client_pos(self, client, args):
        index = int(args[0])
        x = int(args[1])
        y = int(args[2])
        thumb = self.index2thumb(index)
        if thumb is not None :
            thumb.center = (x,y)
            self.thumbs[index] = [client, (x,y)]

    def do_client_color(self, client, args):
        index = int(args[0])
        a = int(args[1])/255.
        b = int(args[2])/255.
        c = int(args[3])/255.
        thumb = self.index2thumb(index)
        if thumb is not None :
            thumb.color = (a,b,c)
            
        
    def index2thumb(self,index):
        for child in self.scat.children:
            if isinstance(child,MapThumbnail) and child.index == index:
                return child
        return None

    def index2filename(self,index):
        data = self.imagemap.data
        return data[index]['filename'] 

    def do_client_scale(self, client, scale): 
        pass

    def do_client_rotate(self, client, rot):
        #anim = Animation(rotation = rot)
        #anim.start(self.scat)
        self.scat.rotation += int(rot[0])

    #
    # Commands to send to clients
    #
    
    def hide_thumb(self, client, index):
        for cl in self.players.itervalues() :
            cl = cl['client']
            if cl != client :
                self.send_to(cl, 'HIDETH %d' % index)

    def display_thumb(self,client, index):
        for cl in self.players.itervalues() :
            cl = cl['client']
            if cl != client :
                self.send_to(cl, 'DISPLAYTH %d' % index)

    def hide_mapitem(self,client,filename):
        for cl in self.players.itervalues() :
            cl = cl['client']
            if cl != client :
                self.send_to(cl, 'HIDEMAPITEM %s' % str(filename))

    def display_mapitem(self,client,filename):
        for cl in self.players.itervalues() :
            cl = cl['client']
            if cl != client :
                self.send_to(cl, 'DISPLAYMAPITEM %s' % str(filename))
    
    def thumb_index_match_layer(self, index, client):
        filename = self.imagemap.data[index]['filename']
        return self.filename_match_layer(filename, client)

    def filename_match_layer(self, filename, client):
        #print self.f1(self.layers)
        parts = filename.rsplit('-', 1)
        #print parts[0], self.layers_given, client
        if len(parts) != 2 : 
            return False
        if client not in self.layers_given.keys():
            return False  
        if parts[0] != self.layers_given[ client ]:
            return False
        #print parts[0], self.layers_given, client
        return True

    def clear(self):
        self.send_all('CLEAR')
        #self clear as well
        self.mapitems = {}
        self.thumbs = {}
        self.layout.remove_widget(self.scat)
        self.scat.remove_widget(self.map_background)
        self.scat.remove_widget(self.imagemap)
        self.scat = ''
        self.imagemap = ''
        self.map_background = ''
        self.layout = ''
        
    
    #
    # State machine
    #

    def run_waitready(self):
        '''Wait for all player to be ready
        '''
        ready = True
        for player in self.players.itervalues():
            ready = ready and player['ready']
        if not ready:
            return

        #create clients layout
        self.send_all('GAME1')
        self.timeout = time() + TIMER_1
        self.send_all('TIME %d %d' % (time(), int(self.timeout)))

        #display sub-scenarii selector on clients
        self.send_all('SELECTOR') 
        self.state = 'game0'  

    def run_game0(self):

        if scenariol == -2:
            sleep(0.2)
            return

        #self.layout.remove_widget(self.selector)
        self.send_all('REMOVESELECTOR')
        self.init_ui()
        self.items_given = []
        self.layers_given = {}
        
        affected = [-1]
        self.imagemap.layers = []
        for client in self.controler.clients:
            place = int(self.players[client]['place']) - 1
            self.send_to(client, 'COLOR %d %d %d' % map_colors[place])
            self.send_to(client, 'LOGO %s' % map_logos[place])
            #deal with "all layers" (one on each client)
            if not scenariol == -1 : 
                layer = str(layers[scenariol])
            else :
                l = len(layers) - 1
                r = -1
                if place > l : 
                    place = 0
                else : 
                    while r in affected :
                        r = int( random() * l )
                affected.append(r)
                #print affected
                place = r 
                layer = str(layers[place])
            self.imagemap.layers = self.imagemap.layers + [layer] 
            self.send_to(client, 'LAYER %s' % layer)
            self.layers_given[client] = layer 
            self.send_to(client, 'MAPSIZE %d %d' % map_coordinates[1] )
            self.send_to(client, 'MAPPOS %d %d' % map_coordinates[0])

        #create map
        self.send_all('MAP')
        
        # deliver randomly index
        litems = len(self.imagemap.data)
        if litems:
            r = range(litems)
            allfinished = False
            while not allfinished:
                allfinished = True
                index = r.pop(randint(0, litems - 1))
                litems -= 1
                #print litems
                for client in self.controler.clients: 
                    player = self.players[client]
                    if player['ready'] is False:
                        continue
                    if player['count'] > MAX_CLIENT_ITEMS - 1:
                        continue 
                    if self.thumb_index_match_layer(index, client) == True :
                        #print r, litems
                        self.send_to(client, 'GIVE %d' % index)
                        player['count'] += 1
                        self.items_given.append((client, index))
                        allfinished = allfinished and False 
                        break
                    allfinished = allfinished and False
                if litems == 0 : allfinished = True       
  
        self.state = 'game1'
        self.send_all('LAYOUTALL')

 
    def run_game1(self):
        '''First game, place items on the imagemap without ordering
        '''
        if time() > self.timeout:
            self.state = 'reset_for_game2'
            return

    def run_reset_for_game2(self):
        '''Make correction on imagemap !
        '''
        # order !
        index_sent = []
        for thumb in self.scat.children:
            if not isinstance(thumb, MapThumbnail):
                continue
            #print thumb.item
            # are we far ? Check if thumb matches the place
            x,y = thumb.pos
            x += thumb.width/2. 
            filename = self.imagemap.pos2mapitem(x,y)
            if filename is False :
                continue
            if filename == thumb.item['filename'] : #, thumb.item['filename']
                for client in self.controler.clients:
                    thumb.update_color(True)
                    self.send_to(client, 'THVALID %d' % thumb.index)
            else :
                for client in self.controler.clients:
                    thumb.update_color(False)
                    thumb.shake()
                    self.send_to(client, 'THNOTVALID %d' % thumb.index)
            index_sent.append(thumb.index)

        for client, index in self.items_given:
            if index in index_sent:
                continue
            self.send_to(client, 'THNOTVALID %d' % index)
        
        # do game 2
        self.timeout = time() + TIMER_2
        self.send_all('TIME %d %d' % (time(), int(self.timeout)))
        self.send_all('GAME2')
        self.send_all('GAME2')
        self.send_all('GAME2')
        self.state = 'game2'

    def run_game2(self):
        if time() > self.timeout:
            self.state = 'reset_for_game3'
            return

    def run_reset_for_game3(self):
        #move all thumbs to the right location on map
        
        #delete all existing items
        for child in self.scat.children[:]:
            if isinstance(child,MapThumbnail):
                self.scat.remove_widget(child)
        #place all thumbs on the map
        index = 0
        clients = self.controler.clients
        #add all items to the map 
        for item in self.imagemap.data :
            filename = item['filename']
            if self.imagemap.filename_match_layer(filename):
                self.imagemap.display_mapitem(filename, True, (0,0,0,1))    
            item = self.create_and_add_item(clients.keys()[0] ,index)
            item.auto_color = False
            index +=1
        
        #move thumbs to the right position
        self.send_all('PLACETHUMBS')
        self.send_all('GAME2')
        self.state = 'game3'
        self.timeout = time() + TIMER_3
        self.send_all('TIME %d %d' % (time(), int(self.timeout)))
        
    def run_game3(self):
        if time() > self.timeout:
            self.clear()
            self.controler.switch_scenario('choose')
            self.controler.load_all()
    
           

scenario_class = MapServer
