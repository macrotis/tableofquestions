#!/usr/bin/env python3
# MY NAME IS MACROTIS
# KING OF ALL YOU SEE HERE
# LOOK ON MY WORKS, YE MIGHTY
# AND DESPAIR!
# (n. b. this is probably not how you make a Jeopardy board,
#  in fact it's not how you do anything with tkinter.)
import time
import json
import os
import re
import sys
from datetime import datetime
from math import ceil, log
from queue import Empty, Queue
from threading import Event as ThreadingEvent, Thread
from tkinter import *
from tkinter import ttk
from tkinter import font

current_q, current_q_num = None, 0
last_round_num = 0

class Contestant(object):
    @classmethod
    def _python_scoping_is_crap(cls, inst):
        return lambda ev: cls._cleanup_name_outer(inst)

    def __init__(self, name=''):
        self.editlock = False
        self.name = StringVar()
        self.name.set(name)
        self.name.trace(
            'w', lambda nm, idx, mode, var=self.name: self._cleanup_name_inner()
        )
        self.score = DoubleVar()
        self.score.set(0.0)

    def _cleanup_name_inner(self):
        if not self.editlock:
            self.editlock = True
            self.name.set(re.sub('[\t ]+', ' ', self.name.get()))
            self.editlock = False

    def _cleanup_name_outer(self):
        if not self.editlock:
            self.editlock = True # Probably unnecessary, we're single-threaded
            self.name.set(self.name.get().strip())
            self.editlock = False

class DebugThread(Thread):
    def __init__(self, *args, **kwargs):
        self.last_run = datetime.now()
        self.contestants_seen = set()
        self.contestant_penalty_times = {}
        self.config = {}
        self.config_queue = Queue()
        Thread.__init__(self)

    def merge_configs(self, c_hash):
        for key, value in c_hash.iteritems():
            self.config[key] = value

    def run(self):
        global debug_contestant_queue
        global buzzer_queue
        global program_running
        global accepting_answers
        global question_open
        while program_running.is_set():
            try:
                self.merge_configs(self.config_queue.get(timeout = 0.005))
            except Empty:
                pass

            current_run = datetime.now()
            try:
                current_contestant = debug_contestant_queue.get(
                    timeout=0.0005
                )
            except Empty:
                if not question_running.is_set():
                    if self.contestants_seen:
                        print("Reset the contestants_seen")
                        self.contestants_seen = set()
            else:
                if not question_running.is_set():
                    pass
                elif not accepting_answers.is_set():
                    if self.contestants_seen:
                        self.contestants_seen = set()
                    if current_contestant in self.contestant_penalty_times:
                        self.contestant_penalty_times[
                            current_contestant
                        ] = self.contestant_penalty_times[
                            current_contestant
                        ] + self.config.get('premature_answer_lockout', 0.0)
                else:
                    if current_contestant in self.contestants_seen: continue
                    if current_contestant in self.contestant_penalty_times:
                        nccpt = nccpt - \
                                (current_run - self.last_run).total_seconds()
                        if nccpt <= 0:
                            del self.contestant_penalty_times[
                                current_contestant
                            ]
                        else:
                            continue
                    self.contestants_seen.add(current_contestant)
                    buzzer_queue.put(current_contestant)
                    self.last_run = current_run

def queue_empty(q):
    while not q.empty():
        q.get()

debug_contestant_queue = Queue()
buzzer_queue = Queue()
program_running = ThreadingEvent()
accepting_answers = ThreadingEvent()
question_running = ThreadingEvent()

fp = open(sys.argv[1], 'r')
game = json.load(fp)['game']
round_qbuttons = []

admin_window = Tk()
admin_window.title("ToQ Admin")
admin_window.resizable(0, 0) # Yeah, I'm a jerk. I also need to get this done.
display_window = Toplevel(admin_window)
display_window.title("Table O' Questions!")

atto_secs_left, anto_secs_left = DoubleVar(), DoubleVar()
atto_secs_left_label = StringVar()

cat_font = font.Font(family='Comic Sans MS', weight='bold', size=20)
logo_font = font.Font(family='Comic Sans MS', weight='bold', size=32)

is_fullscreen = ThreadingEvent()
def toggle_fullscreen_display_window(ev, last_geometry={}):
    if not is_fullscreen.is_set():
        display_window.wm_attributes('-fullscreen', 1)
        is_fullscreen.set()
    else:
        display_window.wm_attributes('-fullscreen', 0)
        is_fullscreen.clear()

display_window.bind('<Control-f>', toggle_fullscreen_display_window)
display_window.bind('<Control-F>', toggle_fullscreen_display_window)
display_frame = Frame(display_window)
display_frame.place(
    anchor=CENTER, 
    relx=0.5, 
    rely=0.5, 
    relwidth=1.1, 
    relheight=1.1
)
display_canvas_config_callbacks = set()
display_canvas = Canvas(display_frame, bg='blue')
display_canvas.pack(fill=BOTH, expand=True)
# Expect the display frame to be broken, unbroken, and all sorts of other
# things in-between.
def clean_up_canvas():
    display_canvas.delete(ALL)
    for cb in display_canvas_config_callbacks:
        display_canvas.unbind(cb)
    display_canvas_config_callbacks.clear()

def canvas_wh():
    orig_w = display_canvas.winfo_width()
    orig_h = display_canvas.winfo_height()
    new_w, new_h = map(lambda d: int(d / 1.1), (orig_w, orig_h))
    shift_w = int((orig_w - new_w) / 2)
    shift_h = int((orig_h - new_h) / 2)
    return (new_w, new_h, shift_w, shift_h)

def paint_opening_screen(*args):
    clean_up_canvas()
    w, h, sw, sh = canvas_wh()
    display_canvas.create_text(
        int((w / 2) + sw),
        int((h / 2) + sh),
        text="Table O' Questions!",
        fill='white',
        font=logo_font
    )
    display_canvas_config_callbacks.add(paint_opening_screen)

def scribble_contestant_window(h_offset=None):
    w, h, sw, sh = canvas_wh()
    if h_offset is None:
        h_offset = int((h / 2) + sh)
    contestant_count = len(contestants)
    box_height = int(0.25 * h - 10)
    box_width = int(((w - 5) - (contestant_count * 5)) / contestant_count)
    y0, y1 = (5 + h_offset), (5 + box_height + h_offset)
    for i in range(0, contestant_count):
        x0 = ((5 * (i+1)) + i * box_width) + sw
        x1 = ((5 * (i+1)) + (i + 1) * box_width) + sw
        display_canvas.create_rectangle(x0, y0, x1, y1, outline='white')
        xu, yu = map(int, (((x1 - x0) / 4 + x0), ((y1 - y0) / 4 + y0)))
        xl, yl = map(int, (((x1 - x0) * 3 / 4 + x0), ((y1 - y0) * 3 / 4 + y0)))
        display_canvas.create_text(
            xu,
            yu,
            text=contestants[i].name.get(),
            fill='white',
            font=cat_font
        )
        c_score = contestants[i].score.get()
        display_canvas.create_text(
            xl,
            yl,
            text=c_score,
            fill='white' if c_score >= 0.0 else 'red',
            font=cat_font
        )

def scribble_question(low_bound):
    global current_q
    w, h, sw, sh = canvas_wh()
    lb = low_bound - 5
    ub = sh + 5
    xm = int((w / 2) + sw)
    ym = int((lb - ub) / 2 + ub)
    display_canvas.create_text(
        xm,
        ym,
        text=current_q['content'],
        fill='white',
        font=logo_font
    )

def scribble_answer(low_bound):
    global current_q
    w, h, sw, sh = canvas_wh()
    lb = low_bound - 5
    ub = sh + 5
    xm = int((w / 2) + sw)
    ym = int((lb - ub) / 2 + ub)
    display_canvas.create_text(
        xm,
        ym,
        text=current_q['answer'],
        fill='white',
        font=logo_font
    )

def paint_question_presentation(*args):
    global current_q_i
    clean_up_canvas()
    w, h, sw, sh = canvas_wh()
    h = int(0.75 * h)
    lh = int(0.8 * h)
    scribble_question(lh + sh)
    xm = int((w / 2) + sw)
    ym = int((h - lh) / 2 + lh + sh)
    display_canvas.create_text(
        sw + 5,
        ym,
        text="%d points." % (
            (current_q_i + 1) * game[current_round]['point_increment']
        ),
        anchor=W,
        fill='white',
        font=cat_font
    )
    scribble_contestant_window(h + sh)
    display_canvas_config_callbacks.add(paint_question_presentation)

def paint_answer_presentation(*args):
    global current_round
    global current_q_i
    if current_round < len(game):
        clean_up_canvas()
        w, h, sw, sh = canvas_wh()
        h = int(0.75 * h)
        lh = int(0.8 * h)
        scribble_answer(lh + sh)
        xm = int((w / 2) + sw)
        ym = int((h - lh) / 2 + lh + sh)
        display_canvas.create_text(
            sw + 5,
            ym,
            text="%d points." % (
                (current_q_i + 1) * game[current_round]['point_increment']
            ),
            anchor=W,
            fill='white',
            font=cat_font
        )
        scribble_contestant_window(h + sh)
        display_canvas_config_callbacks.add(paint_answer_presentation)

def paint_question_open(*args):
    global current_q_i
    global atto_secs_left
    clean_up_canvas()
    w, h, sw, sh = canvas_wh()
    h = int(0.75 * h)
    lh = int(0.8 * h)
    scribble_question(lh)
    xm = int((w / 2) + sw)
    ym = int((h - lh) / 2 + lh + sh)
    display_canvas.create_text(
        sw + 5,
        ym,
        text="%d points." % (
            (current_q_i + 1) * game[current_round]['point_increment']
        ),
        anchor=W,
        fill='white',
        font=cat_font
    )
    display_canvas.create_text(
        w + sw - 5,
        ym,
        text=("{:%d.3f} seconds to attempt" % (
            log(game[current_round]['attempt_timeout'], 10)
        )).format(max(0, atto_secs_left.get())),
        anchor=E,
        fill='white',
        font=cat_font
    )
    scribble_contestant_window(h + sh)
    display_canvas_config_callbacks.add(paint_question_open)

def paint_question_attempt(*args):
    global current_q_i
    global anto_secs_left
    clean_up_canvas()
    w, h, sw, sh = canvas_wh()
    h = int(0.75 * h)
    lh = int(0.8 * h)
    scribble_question(lh)
    xm = int((w / 2) + sw)
    ym = int((h - lh) / 2 + lh + sh)
    display_canvas.create_text(
        sw + 5,
        ym,
        text="%d points." % (
            (current_q_i + 1) * game[current_round]['point_increment']
        ),
        anchor=W,
        fill='white',
        font=cat_font
    )
    display_canvas.create_text(
        w + sw - 5,
        ym,
        text=("{:%d.3f} seconds to answer" % (
            log(game[current_round]['answer_timeout'], 10)
        )).format(max(0, anto_secs_left.get())),
        anchor=E,
        fill='white',
        font=cat_font
    )
    scribble_contestant_window(h + sh)
    display_canvas_config_callbacks.add(paint_question_attempt)

def paint_game_board(*args):
    clean_up_canvas()
    w, h, sw, sh = canvas_wh()
    h = int(0.75 * h)
    cats = game[current_round]['categories']
    cat_count = len(cats)
    box_width = int(((w - 5) - (cat_count * 5)) / cat_count)
    max_q_count = max(map(lambda c: len(c['questions']), cats))
    box_height = int(((h - 5) - ((max_q_count + 1) * 5)) / (max_q_count + 1))
    for i in range(0, cat_count):
        x0 = ((5 * (i+1)) + i * box_width) + sw
        x1 = ((5 * (i+1)) + (i + 1) * box_width) + sw
        y0, y1 = (5 + sh), (5 + box_height + sh)
        display_canvas.create_rectangle(x0, y0, x1, y1, outline='white')
        xm, ym = map(int, (((x1 - x0) / 2 + x0), ((y1 - y0) / 2) + y0))
        display_canvas.create_text(
            xm,
            ym,
            text=cats[i]['name'],
            fill='white',
            font=cat_font
        )
        for j in range(0, max_q_count):
            if j >= len(cats[i]['questions']):
                break
            elif 'answered' in cats[i]['questions'][j] and \
                 cats[i]['questions'][j]['answered'] is True:
                continue
            y0 = ((5 * (j+2)) + (j+1) * box_height) + sh
            y1 = ((5 * (j+2)) + (j+2) * box_height) + sh
            display_canvas.create_rectangle(x0, y0, x1, y1, outline='white')
            ym = (y1 - y0) / 2 + y0
            display_canvas.create_text(
                xm,
                ym,
                text=((j+1) * game[current_round]['point_increment']),
                fill='white',
                font=cat_font
            )
    scribble_contestant_window(h + sh)
    display_canvas_config_callbacks.add(paint_game_board)

def paint_round_over(*args):
    clean_up_canvas()
    w, h, sw, sh = canvas_wh()
    scribble_contestant_window(int(0.475 * h - sh))
    display_canvas_config_callbacks.add(paint_round_over)

def fire_display_canvas_evhs(ev):
    for evh in display_canvas_config_callbacks:
        evh(ev)

display_window.bind('<Configure>', fire_display_canvas_evhs)
paint_opening_screen()

admin_notebook = ttk.Notebook(admin_window)
round_count = 0
current_round = -1
contestants = [Contestant(), Contestant(), Contestant()]

def get_score_for_contestant(contestant):
    acc = 0
    for i in range(0, len(game)):
        rnd = game[i]
        if not ('is_practice' in rnd and rnd['is_practice']) or \
           i == current_round:
            if 'last_chance' in rnd and rnd['last_chance'] is True:
                # do something
                pass
            else:
                for kitty in rnd['categories']:
                    for j in range(0, len(kitty['questions'])):
                        q = kitty['questions'][j]
                        if 'attempts' in q and contestant in q['attempts']:
                            sign = 1 if q['attempts'][contestant] else -1
                            acc += sign * (j + 1) * rnd['point_increment']
                        elif 'wagers' in q and contestant in q['wagers']:
                            lookit = q['wagers'][contestant]
                            if len(lookit) == 2:
                                wager, got_it = lookit
                                if got_it:
                                    acc += wager
                                else:
                                    acc -= wager
    return acc

def count_all_the_points(ev):
    for contestant in contestants:
        contestant.score.set(get_score_for_contestant(contestant))

def make_start_round_callback(round_num):
    def round_cb():
        global current_round
        current_round = round_num
        count_all_the_points(None)
        round_frame = admin_notebook.winfo_children()[round_num]
        cats_frame, game_frame = round_frame.winfo_children()[:2]
        game_button = game_frame.winfo_children()[1]
        game_button.state(['disabled'])
        game_button.config(text='Running...')
        for cat in cats_frame.winfo_children():
            for qf in cat.winfo_children()[1:]:
                q_button = qf.winfo_children()[2]
                q_button.state(['!disabled'])
        paint_game_board()
    return round_cb

def make_question_callback(round_num, cat_num, q_num):
    this_q = game[round_num]['categories'][cat_num]['questions'][q_num]
    def question_cb():
        global current_q
        global current_q_i
        current_q = this_q
        current_q_i = q_num
        q_buttons = round_qbuttons[round_num][1]
        for q_button in q_buttons:
            if q_button[0] != this_q:
                q_button[1].state(['disabled'])
            else:
                print(this_q['content'])
                q_button[1].config(text='Open')
                q_button[1].config(command=make_open_callback(
                    round_num, cat_num, q_num
                ))
        paint_question_presentation()
        question_running.set()
    return question_cb

def see_if_correct(qref, contestant, timeout):
    global anto_secs_left
    ret = {'ret': False, 'verified': False}
    check_window = Toplevel(admin_window)
    ttk.Label(check_window, text="Did they get it?").pack()
    timeout_label = ttk.Label(check_window, text="%s seconds left" % timeout)
    timeout_label.pack(side=BOTTOM)
    bframe = ttk.Frame(check_window)
    bframe.pack(side=BOTTOM)
    def click_yes():
        ret['verified'] = True
        ret['ret'] = True
    def click_no():
        ret['verified'] = True
    ttk.Button(bframe,
               text="Yes", 
               command=click_yes).grid(column=0, row=0)
    ttk.Button(bframe,
               text="No",
               command=click_no).grid(column=1, row=0)
    start_time = datetime.now()
    time_spent = 0
    anto_secs_left.set(timeout - time_spent)
    paint_question_attempt()
    while time_spent < timeout:
        # TODO: Update the game display too!
        if ret['verified']:
            break
        time_spent = (datetime.now() - start_time).total_seconds()
        time_spent_width = int(ceil(log(time_spent, 10)))
        anto_secs_left.set(timeout - time_spent)
        if (timeout - time_spent) > 0:
            timeout_label.config(
                text=("{:%s.3f} seconds left" 
                      % time_spent_width).format(timeout - time_spent)
            )
        else:
            timeout_label.config(
                text="Time expired"
            )
        admin_window.update()
        paint_question_attempt()
        time.sleep(0.001)
    timeout_label.config(text="Time expired")
    while True:
        if ret['verified']:
            break
        admin_window.update()
        time.sleep(0.001)
    qref[contestant] = ret['ret']
    check_window.destroy()
    return ret['ret']

def handle_open_question(round_num, cat_num, q_num, start_at, timeout, win,
                         debug_contestant_picker=None):
    global accepting_answers
    global buzzer_queue
    global atto_secs_left
    global atto_secs_left_label
    this_round = game[round_num]
    this_q = this_round['categories'][cat_num]['questions'][q_num]
    q_buttons = round_qbuttons[round_num][1]
    im = datetime.now()
    d = (im - start_at).total_seconds()
    atto_secs_left.set(timeout - d)
    atto_secs_left_label.set((
        "{:%d.3f}" % int(ceil(log(this_round['attempt_timeout'], 10)))
    ).format(max(0, atto_secs_left.get())))
    paint_question_open()
    if d > timeout:
        for q_button in q_buttons:
            if q_button[0] == this_q:
                q_button[1].state(['!disabled'])
                break
        win.destroy()
        accepting_answers.clear()
        queue_empty(buzzer_queue)
        paint_answer_presentation()
        return
    else:
        do_it_again = lambda: handle_open_question(
            round_num, cat_num, q_num, start_at, timeout, win,
            debug_contestant_picker
        )
        try:
            contestant_attempt = buzzer_queue.get(timeout=0.001)
        except Empty:
            admin_window.after(10, do_it_again)
        else:
            if 'attempts' not in this_q:
                this_q['attempts'] = {}
            if contestant_attempt in this_q['attempts'].keys():
                admin_window.after(10, do_it_again)
            else:
                # Now see if these guys got it right
                if see_if_correct(this_q['attempts'],
                                  contestant_attempt,
                                  this_round['answer_timeout'])\
                    or len(this_q['attempts'].keys()) == len(contestants):
                    for q_button in q_buttons:
                        if q_button[0] == this_q:
                            q_button[1].state(['!disabled'])
                    accepting_answers.clear()
                    queue_empty(buzzer_queue)
                    win.destroy()
                    print("lolwat")
                    paint_answer_presentation()
                else:
                    admin_window.after(10, lambda: handle_open_question(
                        round_num, cat_num, q_num, datetime.now(), timeout, win,
                        debug_contestant_picker
                    ))
                count_all_the_points(None)

def make_open_callback(round_num, cat_num, q_num):
    global accepting_answers
    global contestants
    this_round = game[round_num]
    this_q = this_round['categories'][cat_num]['questions'][q_num]
    def open_cb():
        global atto_secs_left
        q_buttons = round_qbuttons[round_num][1]
        # TODO: Handle timeouts, answering questions
        for q_button in q_buttons:
            if q_button[0] == this_q:
                q_button[1].config(
                    text='Clear',
                    command=make_clear_callback(round_num,
                                                cat_num,
                                                q_num)
                )
                q_button[1].state(['disabled'])
                break
        print(this_q['answer'])
        this_q['answered'] = True
        game[round_num]['answered_questions'] += 1
        #wait_window = Toplevel(admin_window)
        #ttk.Label(wait_window, text='Waiting for answers...').pack()
        # This is debug stuff
        # Get rid of it for "production"
        wait_window = Toplevel(admin_window)
        pw_frame = ttk.Frame(wait_window)
        pw_frame.grid(column=0, row=0)
        ttk.Label(pw_frame, text="Choose the contestant").grid(
            column=0, row=0
        )
        two_frame = Frame(pw_frame)
        two_frame.grid(column=0, row=1)
        ttk.Label(
            two_frame, 
            textvariable=atto_secs_left_label
        ).grid(
            column=0, row=0
        )
        ttk.Label(two_frame, text=' seconds left to attempt').grid(
            column=1, row=0
        )
        bee_frame = ttk.Frame(pw_frame)
        bee_frame.grid(column=0, row=2)
        
        def make_inject_contestant_buzz(contestant, button):
            def inner_inject_contestant_buzz():
                debug_contestant_queue.put(contestant)
                button.state(['disabled'])
            return inner_inject_contestant_buzz

        print(len(contestants))
        contestant_pos=0
        for contestant in contestants:
            butt = ttk.Button(
                bee_frame,
                textvariable=contestant.name
            )
            butt.config(
                command=make_inject_contestant_buzz(contestant, butt)
            )
            butt.grid(column=contestant_pos, row=0)
            contestant_pos += 1
            if 'attempts' in this_q and contestant in this_q['attempts']:
                butt.state(['disabled'])

        # debug crap ends here

        accepting_answers.set()
        handle_open_question(
            round_num,
            cat_num,
            q_num,
            datetime.now(),
            this_round['attempt_timeout'],
            wait_window
        )
    return open_cb

def make_clear_callback(round_num, cat_num, q_num):
    this_q = game[round_num]['categories'][cat_num]['questions'][q_num]
    def clear_cb():
        q_buttons = round_qbuttons[round_num][1]
        for q_button in q_buttons:
            if q_button[0] == this_q:
                q_button[1].config(text='Spent')
                q_button[1].state(['disabled'])
            elif not ('answered' in q_button[0] and q_button[0]['answered']):
                q_button[1].state(['!disabled'])
        rnd = game[round_num]
        question_running.clear()
        count_all_the_points(None)
        if rnd['question_count'] == rnd['answered_questions']:
            round_teardown(round_num)
        else:
            paint_game_board()
    return clear_cb

def make_all_in_callback(round_num, cat_num, q_num):
    this_q = game[round_num]['categories'][cat_num]['questions'][q_num]
    def all_in_cb():
        # TODO: Implement that workflow
        print("All in has its own workflow")
        this_q['answered'] = True
        game[round_num]['answered_questions'] += 1
        q_buttons = round_qbuttons[round_num][1]
        for q_button in q_buttons:
            if q_button[0] == this_q:
                q_button[1].config(
                    text='Clear',
                    command=make_clear_callback(round_num, cat_num, q_num)
                )
            else:
                q_button[1].state(['disabled'])
    return all_in_cb

def round_teardown(round_num):
    global current_round
    global last_round
    print("All done!")
    cur_round_frame = admin_notebook.winfo_children()[current_round]
    cat_frame, game_frame = cur_round_frame.winfo_children()[:2]
    round_button = game_frame.winfo_children()[1]
    round_button.config(text='Finished')
    round_button.state(['disabled'])
    count_all_the_points(None)
    paint_round_over()
    if current_round < len(game) - 1:
        new_round_frame = admin_notebook.winfo_children()[current_round + 1]
        cat_frame, game_frame = new_round_frame.winfo_children()[:2]
        round_button = game_frame.winfo_children()[1]
        if 'last_chance' in game[current_round + 1] \
           and game[current_round + 1]['last_chance'] is True:
            round_button.config(text='Start Last Chance')
        else:
            round_button.config(text='Start Round')
        round_button.state(['!disabled'])
        admin_notebook.select(admin_notebook.tabs()[current_round + 1])

def make_round_teardown_callback(round_num):
    def rt_cb():
        round_teardown(round_num)
    return rt_cb

def make_lcpa_callback(round_num):
    this_round = game[round_num]
    def lcpa_cb():
        # TODO: Update game display
        print(this_round['answer'])
        round_frame = admin_notebook.winfo_children()[round_num]
        cat_frame, game_frame = round_frame.winfo_children()[:2]
        round_button = game_frame.winfo_children()[1]
        round_button.config(
            text='Clear',
            command=make_round_teardown_callback(round_num)
        )
    return lcpa_cb

def make_lcopen_callback(round_num):
    this_round = game[round_num]
    def lcopen_cb():
        #TODO: Set up timers, callback to open inputs
        round_frame = admin_notebook.winfo_children()[round_num]
        cat_frame, game_frame = round_frame.winfo_children()[:2]
        round_button = game_frame.winfo_children()[1]
        round_button.config(
            text='Present Answer',
            command=make_lcpa_callback(round_num)
        )
    return lcopen_cb

def make_lcpq_callback(round_num):
    this_round = game[round_num]
    def lcpq_cb():
        # TODO: Update game display
        print(this_round['question'])
        round_frame = admin_notebook.winfo_children()[round_num]
        cat_frame, game_frame = round_frame.winfo_children()[:2]
        round_button = game_frame.winfo_children()[1]
        round_button.config(
            text='Open',
            command=make_lcopen_callback(round_num)
        )
    return lcpq_cb

def make_last_chance_callback(round_num):
    this_round = game[round_num]
    def lc_cb():
        round_frame = admin_notebook.winfo_children()[round_num]
        cat_frame, game_frame = round_frame.winfo_children()[:2]
        round_button = game_frame.winfo_children()[1]
        round_button.config(
            text='Present Question',
            command=make_lcpq_callback(round_num)
        )
    return lc_cb

round_timers = []
for rnd in game:
    round_count += 1
    round_frame = ttk.Frame(admin_notebook)
    round_frame.grid(column=0, row=0, sticky=NW)
    cats_frame = ttk.Frame(round_frame)
    cats_frame.grid(column=0, row=0, sticky=EW)
    game_frame = ttk.Frame(round_frame)
    game_frame.grid(column=0, row=1, sticky=EW)
    ttk.Separator(game_frame, orient=HORIZONTAL).pack(side=TOP, fill=X)
    if 'last_chance' not in rnd or rnd['last_chance'] is not True:
        max_cat_len = max(map(lambda k: len(k['questions']), rnd['categories']))
        rnd['question_count'] = sum(map(
            lambda k: len(k['questions']), rnd['categories']
        ))
        rnd['answered_questions'] = 0
        q_buttons = []
        for i in range(0, len(rnd['categories'])):
            cat = rnd['categories'][i]
            cat_frame = ttk.Frame(cats_frame)
            cat_frame.grid(column=i, row=0, rowspan=max_cat_len, sticky=N)
            ttk.Label(cat_frame, text=cat['name']).grid(column=0, row=0)
            questions = cat['questions']
            for j in range(0, len(questions)):
                q = cat['questions'][j]
                q_frame = ttk.Labelframe(
                    cat_frame,
                    text="%s: %s" % (cat['name'],
                                     (j + 1) * rnd['point_increment']),
                )
                q_frame.grid(column=0, row=(j + 1), sticky=N)
                ttk.Label(q_frame,
                          text='Q: ' + q['content']).grid(column=0,
                                                          row=0,
                                                          sticky=W)
                ttk.Label(q_frame,
                          text='A: ' + q['answer']).grid(column=0,
                                                         row=1,
                                                         sticky=W)
                if 'all_in' in q and q['all_in'] is True:
                    q_button = ttk.Button(
                        q_frame,
                        text='All In!',
                        command=make_all_in_callback(round_count - 1, i, j)
                    )
                else:
                    q_button = ttk.Button(
                        q_frame,
                        text='Fire',
                        command=make_question_callback(round_count - 1, i, j)
                    )
                q_button.state(['disabled'])
                q_button.grid(column=0, row=2)
                q_buttons.append((q, q_button))
        admin_notebook.add(round_frame, text="Round #%s" % round_count)
        round_qbuttons.append((rnd, q_buttons))
        if round_count == 1:
            game_button = ttk.Button(
                game_frame,
                text='Start Round',
                command=make_start_round_callback(0)
            )
        else:
            game_button = ttk.Button(
                game_frame,
                text='Pending...',
                command=make_start_round_callback(round_count - 1)
            )
            game_button.state(['disabled'])
        if 'is_practice' in rnd and rnd['is_practice'] is True:
            p = ttk.Label(game_frame, text='practice')
        else:
            p = ttk.Label(game_frame, text='for realz')
        p.pack(side=RIGHT)
        ali = ttk.Label(game_frame, text='ali. %s, ' % rnd['all_in_timeout'])
        ali.pack(side=RIGHT)
        ans = ttk.Label(game_frame, text='ans. %s, ' % rnd['answer_timeout'])
        ans.pack(side=RIGHT)
        att = ttk.Label(game_frame, text='att. %s, ' % rnd['attempt_timeout'])
        att.pack(side=RIGHT)
    else:
        rnd['question_count'] = 1
        rnd['answered_questions'] = 0
        round_timer = DoubleVar()
        round_timer.set(rnd['last_chance_timeout'])
        round_timers.append(round_timer)
        cat_frame = ttk.Labelframe(cats_frame, text='Category')
        cat_frame.grid(column=0, row=0)
        rtlf = ttk.Frame(cats_frame)
        rtlf.grid(column=1, row=3)
        rtl = ttk.Label(rtlf, textvariable=round_timers[-1], anchor=CENTER)
        rtl.pack(padx=20)
        ttk.Label(cat_frame, text=rnd['category']).grid(column=0, row=0)
        q_frame = ttk.Labelframe(cats_frame, text='Question')
        q_frame.grid(column=0, row=1)
        ttk.Label(q_frame, text=rnd['question']).grid(column=0, row=0)
        c_frame = ttk.Labelframe(cats_frame, text='Answer')
        c_frame.grid(column=0, row=2)
        ttk.Label(c_frame, text=rnd['answer']).grid(column=0, row=0)
        admin_notebook.add(round_frame,
                           text="Last Chance: Round #%s" % round_count)
        round_qbuttons.append((rnd, None))
        contestant_count = 0
        contestant_frame = ttk.Labelframe(cats_frame, text='Contestants')
        contestant_frame.grid(column=0, row=3)
        for contestant in contestants:
            ttk.Label(contestant_frame, textvariable=contestant.name).grid(
                column=0, row=contestant_count
            )
            ttk.Label(contestant_frame, text=' wagered ').grid(
                column=1, row=contestant_count
            )
            if not 'wagers' in rnd:
                rnd['wagers'] = {}
            rnd['wagers'][contestant] = DoubleVar()
            cw_entry = ttk.Entry(contestant_frame,
                                 textvariable=rnd['wagers'][contestant])
            cw_entry.state(['disabled'])
            cw_entry.config(width=10)
            cw_entry.grid(column=2, row=contestant_count)
            ttk.Label(contestant_frame, text=' and ').grid(
                column=3, row=contestant_count
            )
            g_butt = ttk.Button(contestant_frame, text='got it')
            g_butt.state(['disabled'])
            g_butt.grid(column=4, row=contestant_count)
            f_butt = ttk.Button(contestant_frame, text='flubbed it')
            f_butt.state(['disabled'])
            f_butt.grid(column=5, row=contestant_count)
            contestant_count += 1
        if round_count == 1:
            game_button = ttk.Button(
                game_frame,
                text='Start Last Chance',
                command=make_last_chance_callback(0)
            )
        else:
            game_button = ttk.Button(
                game_frame,
                text='Pending...',
                command=make_last_chance_callback(round_count - 1)
            )
            game_button.state(['disabled'])
        if 'is_practice' in rnd and rnd['is_practice'] is True:
            p = ttk.Label(game_frame, text='practice')
        else:
            p = ttk.Label(game_frame, text='for realz')
        p.pack(side=RIGHT)
        w = ttk.Label(game_frame,
                      text='runs for % s, ' % rnd['last_chance_timeout'])
        w.pack(side=RIGHT)
    ttk.Frame(round_frame).grid(column=0, row=2)
    game_button.pack(side=LEFT)
admin_notebook.pack(fill=BOTH, expand=True)
admin_notebook.enable_traversal()
contestant_pane = Frame(admin_window)

def repaint_display_window_on_change(*args):
    fire_display_canvas_evhs(None)
    display_window.update()

for i in range(0, len(contestants)):
    contestant = contestants[i]
    c_entry = ttk.Entry(contestant_pane, textvariable=contestant.name)
    c_entry.grid(column=i, row=0)
    c_entry.bind('<FocusOut>', Contestant._python_scoping_is_crap(contestant))
    c_score = ttk.Label(contestant_pane, textvariable=contestant.score)
    c_score.grid(column=i, row=1)
    contestant.name.trace("w", repaint_display_window_on_change)
    contestant.score.trace("w", repaint_display_window_on_change)
contestant_pane.pack(side=BOTTOM, expand=True)

# Hack to get all the questions aligned in the admin interface
admin_window.update_idletasks()
max_cf_height = max(map(
    lambda rnd: rnd.winfo_children()[0].winfo_reqheight(),
    admin_notebook.winfo_children()
))
for rnd_frame in admin_notebook.winfo_children():
    cats_frame, game_frame = rnd_frame.winfo_children()[:2]
    cats_frame.grid_configure(
        ipady=(max_cf_height - cats_frame.winfo_reqheight()) / 2,
        pady=5,
        padx=5
    )
    if not isinstance(cats_frame.winfo_children()[0], ttk.Labelframe):
        for cat in cats_frame.winfo_children():
            q_frames = cat.winfo_children()[1:]
            max_qf_height = max(map(lambda qf: qf.winfo_reqheight(), q_frames))
            for qf in q_frames:
                qf.grid_configure(
                    pady=(max_qf_height - qf.winfo_reqheight()),
                    padx=5
                )

def force_resize_update(ev, updatelock=ThreadingEvent(), last_max=[0]):
    if not updatelock.is_set():
        updatelock.set()
        admin_window.update_idletasks()
        max_tab_width = max(map(
            lambda rnd: rnd.winfo_reqwidth(),
            admin_notebook.winfo_children()
        ))
        if [max_tab_width] != last_max and abs(last_max[0] - max_tab_width) > 2:
            for rnd in admin_notebook.winfo_children():
                rnd.winfo_children()[2].grid_configure(
                    padx=max_tab_width/2
                )
            admin_window.update_idletasks()
            last_max.remove(last_max[0])
            last_max.append(max_tab_width)
        updatelock.clear()

force_resize_update('nope')
admin_window.bind('<Configure>', force_resize_update)

program_running.set()
dat_buzzer_thread = DebugThread()

def stop_dat_buzzer_thread(ev):
    global program_running
    global dat_buzzer_thread
    program_running.clear()
    print("Joining the buzzer thread")
    dat_buzzer_thread.join()
    print("Joined the buzzer thread")

def clean_up_after_tk(*args):
    if os.uname()[0] == 'Darwin':
        admin_window.destroy()
    stop_dat_buzzer_thread(None)

admin_window.createcommand('exit', clean_up_after_tk)
dat_buzzer_thread.start()
admin_window.mainloop()
# Some people would like to believe there's an existence after the mainloop
# Some people would be hilariously wrong.
# SOME PEOPLE DON'T HAVE REAL WORK TO DO
# (some people ought to be ignored)
# unless it's not on OS X
clean_up_after_tk()
