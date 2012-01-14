import pyglet

from pyglet.graphics import *
from pyglet.gl import *

import types
from time import time

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 720

class Control(pyglet.event.EventDispatcher):
    def __init__(self, x=0, y=0, width=100, height=100, zindex=0, parent=None, can_focus=False, *args, **kwargs):
        if parent is None:
            parent = Overlay.cur_overlay
            overlay = parent
        else:
            if parent:
                overlay = parent
                while not isinstance(overlay, Overlay):
                    overlay = overlay.parent
            else:
                overlay = self
                
        self.__dict__.update({
            'parent': parent,
            'x': x, 'y': y,
            'width': width, 'height': height,
            'zindex': zindex,
            'can_focus': can_focus,
        })
        self.control_list = []
        self.continuation = None
        self.overlay = overlay
        self._control_hit = None # control under cursor now, for tracking enter/leave events
        if parent:
            parent.add_control(self)
    
    def add_control(self, c):
        self.control_list.append(c)
        
    def remove_control(self, c):
        self.control_list.remove(c)
    
    def delete(self):
        self.parent.remove_control(self)
    
    def controls_frompoint(self, x, y):
        l = []
        for c in self.control_list:
            if c.x <= x <= c.x + c.width and c.y <= y <= c.y + c.height:
                l.append(c)
        return l
    
    def control_frompoint1(self, x, y):
        l = self.controls_frompoint(x, y)
        # l.sort(key=lambda c: c.zindex, reverse=True)
        l.sort(key=lambda c: c.zindex)
        l.reverse()
        return l[0] if l else None
    
    def stop_drawing(self):
        if self.continuation:
            self.continuation.close()
            self.continuation = None
    
    def do_draw(self, dt):
        if self.continuation:
            try:
                self.continuation.send(dt)
            except StopIteration:
                self.continuation = None
                ''' Animation are supposed to be written like this:
                def the_drawing(dt):
                    for i in range(n_frames):
                        do_the_drawing_step(i, dt)
                        dt = (yield)
                When StopIteration occurs, nothing was done.
                call do_draw again to do the drawing
                '''
                return self.do_draw(dt)
                
        elif hasattr(self, 'draw'):
            rst = self.draw(dt)
            if type(rst) == types.GeneratorType:
                try:
                    rst.next()
                    self.continuation = rst
                except StopIteration:
                    print 'Stop first'
                
        else:
            # default behavior
            if not hasattr(self, 'label'):
                self.label = pyglet.text.Label(text=self.__class__.__name__,
                                               font_size=10,color=(0,0,0,255),
                                               x=self.width//2, y=self.height//2,
                                               anchor_x='center', anchor_y='center')
            glPushAttrib(GL_POLYGON_BIT)
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
            glColor3f(1.0, 1.0, 1.0)
            glRecti(0, 0, self.width, self.height)
            glColor3f(0.0, 0.0, 0.0)
            glRecti(0, 0, 4, 4)
            glRecti(self.width-4, 0, self.width, 4)
            glRecti(0, self.height-4, 4, self.height)
            glRecti(self.width-4, self.height-4, self.width, self.height)
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            glRecti(0, 0, self.width, self.height)
            glBegin(GL_POLYGON)
            glVertex2f(0,0)
            glVertex2f(0,10)
            glVertex2f(10,10)
            glVertex2f(10, 0)
            glEnd()
            glPopAttrib()
            self.label.draw()
        
        self._draw_subcontrols(dt)
    
    def _draw_subcontrols(self, dt):
        self.control_list.sort(key=lambda c: c.zindex)
        for c in self.control_list:
            glPushMatrix()
            glTranslatef(c.x, c.y, 0)
            c.do_draw(dt)
            glPopMatrix()
    
    def set_focus(self):
        if not self.can_focus: return
        o = self.parent
        while not isinstance(o, Overlay):
            o = o.parent
        
        if o:
            if o.current_focus != self:
                if o.current_focus:
                    o.current_focus.dispatch_event('on_lostfocus')
                self.dispatch_event('on_focus')
                o.current_focus = self

class Overlay(Control):
    '''
    Represents current screen
    '''
    cur_overlay = None
    def __init__(self, *args, **kwargs):
        Control.__init__(self, width=WINDOW_WIDTH, height=WINDOW_HEIGHT, parent=False)
        self.__dict__.update(kwargs)
        self.last_mouse_press = [  # WONTFIX: Button combinations not supported.
            (0.0, None, 0.0, 0.0), # (time(), self._control_hit, x, y) LEFT
            (0.0, None, 0.0, 0.0), # MIDDLE
            None,                  # Not used
            (0.0, None, 0.0, 0.0), # RIGHT
        ]
        self.last_mouse_release = [
            (0.0, None, 0.0, 0.0), # (time(), self._control_hit, x, y) LEFT
            (0.0, None, 0.0, 0.0), # MIDDLE
            None,                  # Not used
            (0.0, None, 0.0, 0.0), # RIGHT
        ]
        self.current_focus = None
    
    def draw(self, dt):
        main_window.clear()
    
    def switch(self):
        ori = Overlay.cur_overlay
        Overlay.cur_overlay = self
        main_window.set_handlers(self)
        return ori
    
    def on_resize(self, width, height):
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, width, 0, height, -1000, 1000)
        glMatrixMode(GL_MODELVIEW)
        return pyglet.event.EVENT_HANDLED
    
    def _position_events(self, _type, x, y, *args):
        def dispatch(this, lx, ly):
            '''
            # Every hit control get event
            
            l = this.controls_frompoint(lx, ly)
            
            last = set(this._controls_hit)
            now = set(l)
            for c in last - now:
                c.dispatch_event('on_mouse_leave', lx - c.x, ly - c.y)
            
            for c in now - last:
                c.dispatch_event('on_mouse_enter', lx - c.x, ly - c.y)
            
            this._controls_hit = l
            
            if not l:
                if this is not self:
                    this.dispatch_event(_type, lx, ly, *args)
            else:
                for c in l:
                    dispatch(c, lx-c.x, ly-c.y)
            '''
            
            # Top most control get event
            c = this.control_frompoint1(lx, ly)
            lc = this._control_hit
            if c != lc:
                if lc:
                    lc.dispatch_event('on_mouse_leave', lx - lc.x, ly - lc.y)
                if c:
                    c.dispatch_event('on_mouse_enter', lx - c.x, ly - c.y)
            this._control_hit = c
            
            if not c:
                # Now 'this' has no subcontrols hit, so 'this' got this event
                # TODO: if 'this' don't handle it, its parent should handle.
                if this is not self:
                    if _type == 'on_mouse_press':
                        this.set_focus()
                    this.dispatch_event(_type, lx, ly, *args)
            else:
                dispatch(c, lx - c.x, ly - c.y) # TODO: not recursive
            
        dispatch(self, x, y)
    
    def on_mouse_press(self, x, y, button, modifier):
        self.last_mouse_press[button] = (time(), self._control_hit, x, y)
        self._position_events('on_mouse_press', x, y, button, modifier)
    
    def on_mouse_release(self, x, y, button, modifier):
        lp = self.last_mouse_press[button]
        lr = self.last_mouse_release[button]
        cr = (time(), self._control_hit, x, y)
        self.last_mouse_release[button] = cr
        self._position_events('on_mouse_release', x, y, button, modifier)
        # single click
        if cr[1] == lp[1]:
            self._position_events('on_mouse_click', x, y, button, modifier)
        
        # double click
        if cr[0]-lr[0] < 0.2: # time limit
            if abs(cr[2] - lr[2]) + abs(cr[3] - lr[3]) < 4: # shift limit
                if cr[1] == lr[1]: # Control limit
                    self._position_events('on_mouse_dblclick', x, y, button, modifier)

    on_mouse_motion = lambda self, *args: self._position_events('on_mouse_motion', *args)
    on_mouse_drag = lambda self, *args: self._position_events('on_mouse_drag', *args)
    on_mouse_scroll = lambda self, *args: self._position_events('on_mouse_scroll', *args)
    
    def _text_events(self, *args):
        if self.current_focus:
            self.current_focus.dispatch_event(*args)
    
    on_key_press = lambda self, *args: self._text_events('on_key_press', *args)
    on_key_release = lambda self, *args: self._text_events('on_key_release', *args)
    on_text = lambda self, *args: self._text_events('on_text', *args)
    on_text_motion = lambda self, *args: self._text_events('on_text_motion', *args)
    on_text_motion_select = lambda self, *args: self._text_events('on_text_motion_select', *args)

Control.register_event_type('on_key_press')
Control.register_event_type('on_key_release')
Control.register_event_type('on_text')
Control.register_event_type('on_text_motion')
Control.register_event_type('on_text_motion_select')
Control.register_event_type('on_mouse_motion')
Control.register_event_type('on_mouse_press')
Control.register_event_type('on_mouse_drag')
Control.register_event_type('on_mouse_release')
Control.register_event_type('on_mouse_scroll')
Control.register_event_type('on_mouse_enter')
Control.register_event_type('on_mouse_leave')
Control.register_event_type('on_mouse_click')
Control.register_event_type('on_mouse_dblclick')
Control.register_event_type('on_focus')
Control.register_event_type('on_lostfocus')

def init_gui():
    global main_window
    main_window = pyglet.window.Window(width=WINDOW_WIDTH, height=WINDOW_HEIGHT, caption='GensouKill')
    
    # main window setup {{
    glClearColor(1, 1, 1, 1)
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    
    def_overlay = Overlay()
    def_overlay.name = 'Overlay'
    def_overlay.switch()
    # }} main window setup
    
    fps = pyglet.clock.ClockDisplay()
    
    def _mainwindow_draw(dt):
        Overlay.cur_overlay.do_draw(dt)
        fps.draw()
        #main_window.flip()
    pyglet.clock.schedule_interval(_mainwindow_draw, 1/60.0)

if __name__ == '__main__':
    init_gui()
    Control(100, 100, can_focus=True).name = 'Foo'
    Control(150, 150, can_focus=True).name = 'Bar'
    Control(170, 170, can_focus=True).name = 'Youmu'
    '''
    o = Overlay()
    o = o.switch()
    Control(170, 170)
    Control(150, 150)
    Control(100, 100)
    def sss(dt):
        global o
        o = o.switch()'''
    #pyglet.clock.schedule_interval(sss, 1)
    
    pyglet.app.run()