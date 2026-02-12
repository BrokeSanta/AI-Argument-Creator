import ollama
import pygame
import sys
import secrets
import pyttsx3
import threading
import time
import json
from groq import Groq
import math
mode_of_ai = 1
groq_api_key = ""
ollama_model = ""
groq_model = ""
whos_speaking = None
wiggle_phase = 0.0
WIGGLE_AMPLITUDE = 10.5
WIGGLE_SPEED = 11.0
FIRST_POS = (0, 0)
SECOND_POS = (1100, 0)
try:
    with open("settings.json",'r') as f:
        whatwegot = json.loads(f.read())
        mode_of_ai = whatwegot["mode"]
        ollama_model = whatwegot["ollama_model"]
        groq_api_key = whatwegot["groq_api_key"]
        groq_model = whatwegot.get("groq_model", "llama-3.3-70b-versatile")
        
except FileNotFoundError:
    with open("settings.json",'w') as f:
        diict = {
            "mode": 1,
            "ollama_model": "llama3.1:8b",
            "groq_api_key": "Enter here",
            "groq_model": "llama-3.3-70b-versatile"
        }
        diict_json = json.dumps(diict, indent=4)
        f.write(diict_json)
    sys.exit()

# Initialize Groq client if mode is 2
groq_client = None
if mode_of_ai == 2:
    if groq_api_key == "Enter here" or not groq_api_key:
        print("Error: Please set your Groq API key in settings.json")
        sys.exit()
    groq_client = Groq(api_key=groq_api_key)

class TTS:
    def __init__(self):
        self.engine = None
        self.thread = None
        self.should_stop = False
        self.is_speaking = False
        
    def speak(self, text):
        # Signal any existing speech to stop
        self.should_stop = True
        
        # Wait for previous thread to finish (with timeout)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.5)
        
        self.should_stop = False
        
        def do_tts():
            try:
                # Create new engine for this speech
                engine = pyttsx3.init()
                self.is_speaking = True
                # Check if we should stop before speaking
                if not self.should_stop:
                    engine.say(text)
                    
                    # Run in chunks so we can check should_stop
                    engine.startLoop(False)
                    while engine.isBusy() and not self.should_stop:
                        engine.iterate()
                        time.sleep(0.01)
                    engine.endLoop()
                
                engine.stop()
                del engine
            except Exception as e:
                print(f"TTS Error: {e}")
            finally:
                self.is_speaking = False
        
        self.thread = threading.Thread(target=do_tts, daemon=True)
        self.thread.start()
    
    def stop(self):
        self.should_stop = True
        self.is_speaking = False

def get_ai_response(system_prompt, messages):
    """Get AI response from either Ollama or Groq based on mode
    
    Args:
        system_prompt: The system instruction
        messages: List of conversation messages (without system prompt)
    """
    if mode_of_ai == 1:
        # Ollama mode
        response = ollama.chat(
            model=ollama_model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                *messages
            ]
        )
        return response['message']['content']
    elif mode_of_ai == 2:
        # Groq mode
        groq_messages = [
            {'role': 'system', 'content': system_prompt},
            *messages
        ]
        
        response = groq_client.chat.completions.create(
            model=groq_model,
            messages=groq_messages,
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    else:
        raise ValueError(f"Invalid mode_of_ai: {mode_of_ai}")

tts = TTS()
textbox_padding_x = 40
firstcharacterp = 1
secondcharacterp = 1
topicchoosen = False
finishedinit = False
firststart = True
turn = 1
client = None
# Chat histories
firstchat_history = []
secondchat_history = []
first_system_prompt = ""
second_system_prompt = ""

firstcharaname = ""
secondcharaname = ""
firstbackground = ""
secondbackground = ""
firstcharaavatar = None
secondcharaavatar = None
inputtext = ""
topic = ""
past_answer = ""
on_wait = False
last_first_thinker = None
last_second_thinker = None

def render_text_ellipsis(text: str, font: pygame.font.Font, colour: tuple, max_width: int):
    if font.size(text)[0] <= max_width:
        return font.render(text, True, colour)
    ellipsis_width = font.size("...")[0]
    trimmed = text
    while font.size(trimmed)[0] + ellipsis_width > max_width:
        trimmed = trimmed[:-1]
    return font.render(trimmed + "...", True, colour)

def wrap_text(text, font, max_width):
    words = text.split(" ")
    lines = []
    current_line = ""

    for word in words:
        # Check if the word itself is too long
        if font.size(word)[0] > max_width:
            # If we have a current line, save it first
            if current_line:
                lines.append(current_line)
                current_line = ""
            
            # Break the long word into chunks
            while word:
                chunk = ""
                for char in word:
                    test_chunk = chunk + char
                    if font.size(test_chunk)[0] <= max_width:
                        chunk = test_chunk
                    else:
                        if chunk:
                            lines.append(chunk)
                        chunk = char
                        break
                
                if chunk:
                    word = word[len(chunk):]
                    if word:
                        lines.append(chunk)
                    else:
                        current_line = chunk
                else:
                    break
        else:
            test_line = current_line + (" " if current_line else "") + word
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

    if current_line:
        lines.append(current_line)

    return lines

def ellipsis_line(text, font, max_width):
    ellipsis = "..."
    while font.size(text + ellipsis)[0] > max_width and text:
        text = text[:-1]
    return text + ellipsis

def render_text_paragraph(
    text,
    colour,
    max_width,
    max_height=200,
    start_size=40,
    min_size=20
):
    text = text.replace("\n", " ").replace("\r", "")
    size = start_size

    while size >= min_size:
        font = pygame.font.Font(None, size)
        lines = wrap_text(text, font, max_width)
        
        # Calculate total height needed for these lines
        total_height = len(lines) * font.get_height()

        if total_height <= max_height:
            # Fits! Render normally
            rendered = [font.render(line, True, colour) for line in lines]
            return rendered, font

        # Doesn't fit, decrease size and recalculate wrapping
        size -= 1

    # Still too big at minimum size → force cut with ellipsis
    font = pygame.font.Font(None, min_size)
    lines = wrap_text(text, font, max_width)
    line_height = font.get_height()
    
    # Calculate how many lines fit in max_height
    max_lines_that_fit = max_height // line_height
    
    if len(lines) > max_lines_that_fit:
        clipped = lines[:max_lines_that_fit]
        clipped[-1] = ellipsis_line(clipped[-1], font, max_width)
    else:
        clipped = lines

    rendered = [font.render(line, True, colour) for line in clipped]
    return rendered, font

pygame.init()
screen = pygame.display.set_mode((1600, 900),pygame.RESIZABLE | pygame.SCALED)
font = pygame.font.Font(None, 40)
pygame.display.set_caption("AI Argument Creator")
textbox = pygame.image.load("textbox.png").convert_alpha()
background = pygame.image.load("classroom.png").convert()
thinker1 = pygame.image.load("thinker_1.png").convert()
thinker2 = pygame.image.load("thinker_2.png").convert()
thinker3 = pygame.image.load("thinker_3.png").convert()
textbox_rect = textbox.get_rect()
textbox_rect.topleft = (0, 600)
borderbox = pygame.Rect(0, 0, 1550, 250)
borderbox.centerx = textbox_rect.centerx
borderbox.bottom = textbox_rect.bottom - 5
pygame.mixer.init()
ding = pygame.mixer.Sound("ding.wav")

def random_thinker(exclude=None):
    """Get a random thinker that's different from the excluded one"""
    thinkers = {
        1: thinker1,
        2: thinker2,
        3: thinker3
    }
    numbers = [1,2,3]
    
    if exclude is not None and exclude in thinkers:
        numbers.remove(exclude)
    
    rand_number = secrets.randbelow(len(numbers))
    rand_number2 = numbers[rand_number]
    return thinkers[rand_number2], rand_number2

clock = pygame.time.Clock()
while True:
    delta = clock.tick(60) / 1000
    wiggle_offset = 0
    if tts.is_speaking:
        wiggle_phase += WIGGLE_SPEED * delta
        wiggle_offset = int(math.sin(wiggle_phase) * WIGGLE_AMPLITUDE)
    else:
        wiggle_phase = 0.0
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.TEXTINPUT:
            inputtext += event.text
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                inputtext = inputtext[:-1]
            elif event.key == pygame.K_RETURN:
                if firstcharacterp == 1:
                    firstcharaname = inputtext
                    firstcharacterp = 2
                    inputtext = ""
                elif firstcharacterp == 2:
                    firstbackground = inputtext
                    firstcharacterp = 3
                    inputtext = ""
                elif secondcharacterp == 1:
                    secondcharaname = inputtext
                    secondcharacterp = 2
                    inputtext = ""
                elif secondcharacterp == 2:
                    secondbackground = inputtext
                    secondcharacterp = 3
                    inputtext = ""
                elif topicchoosen == False:
                    topic = inputtext
                    finishedinit = True
                    topicchoosen = True
                    inputtext = ""
                else:
                    if on_wait:
                        tts.stop()
                        whos_speaking = None
                        on_wait = False
    
    screen.blit(background, (0, 0))
    
    if not finishedinit:
        questiontxt = ""
        if firstcharacterp == 1:
            questiontxt = "Who's your first character?"
        elif firstcharacterp == 2:
            questiontxt = f"Tell More about {firstcharaname}"
        elif secondcharacterp == 1:
            questiontxt = "Who's your second character?"
        elif secondcharacterp == 2:
            questiontxt = f"Tell More about {secondcharaname}"
        elif topicchoosen == False:
            questiontxt = "What's the topic?"
        
        max_text_width = textbox_rect.width - textbox_padding_x * 2
        text = render_text_ellipsis(questiontxt, font, (0, 0, 0), max_text_width)
        text_rect = text.get_rect()
        text_rect.centerx = textbox_rect.centerx
        text_rect.top = textbox_rect.top + 20
        (answeringtextcollection, font_external) = render_text_paragraph(inputtext, (0, 0, 0), 1550, 250, 40, 20)
        screen.blit(textbox, textbox_rect)
        screen.blit(text, text_rect)
        y = borderbox.top
        for line in answeringtextcollection:
            line_rect = line.get_rect()
            line_rect.top = y
            line_rect.left = borderbox.left
            screen.blit(line, line_rect)
            y += font_external.get_height()
    else:
        if firststart:
            # Initialize system prompts
            first_system_prompt = f"You are {firstcharaname}. You're in a conversation with {secondcharaname} about {topic}. When you receive messages, they are from {secondcharaname}. Your specifications/personality: {firstbackground}. try to keep it 200 words or lower. Also don't use emojis."
            second_system_prompt = f"You are {secondcharaname}. You're in a conversation with {firstcharaname} about {topic}. When you receive messages, they are from {firstcharaname}. Your specifications/personality: {secondbackground}. try to keep it 200 words or lower. Also don't use emojis."
            
            max_text_width_name = textbox_rect.width - textbox_padding_x
            nametext = render_text_ellipsis(firstcharaname, font, (90, 90, 255), max_text_width_name)
            nametext_rect = nametext.get_rect()
            nametext_rect.left = textbox_rect.left + 20
            nametext_rect.top = textbox_rect.top + 20
            
            # Get first response using unified function
            res_text = get_ai_response(
                first_system_prompt,
                [{'role': 'user', 'content': 'Start'}]
            )
            
            firstchat_history.append({'role': 'user', 'content': 'Start the conversation'})
            firstchat_history.append({'role': 'assistant', 'content': res_text})
            
            (answertext, font_externala) = render_text_paragraph(res_text, (0, 0, 0), 1550, 250, 40, 20)
            past_answer = res_text
            (firstcharaavatar,last_first_thinker) = random_thinker()
            (second_copy_avatar, last_second_thinker) = random_thinker()
            secondcharaavatar = pygame.transform.flip(second_copy_avatar, True, False)
            y = borderbox.top
            first_pos = FIRST_POS
            second_pos = SECOND_POS
            if tts.is_speaking:
                if whos_speaking == "first":
                    first_pos = (FIRST_POS[0],FIRST_POS[1] + wiggle_offset)
                elif whos_speaking == "second":
                    second_pos = (SECOND_POS[0], SECOND_POS[1] + wiggle_offset)
            screen.blits([
                (firstcharaavatar, first_pos),
                (secondcharaavatar, second_pos),
                (textbox, textbox_rect),
                (nametext, nametext_rect)
            ])
            for line in answertext:
                line_rect = line.get_rect()
                line_rect.top = y
                line_rect.left = borderbox.left
                screen.blit(line, line_rect)
                y += font_externala.get_height()
            firststart = False
            turn = 2
            on_wait = True
            ding.play()
            whos_speaking = "first"
            tts.speak(past_answer)
        else:
            if on_wait:
                max_text_width_name = textbox_rect.width - textbox_padding_x
                nametext = render_text_ellipsis(firstcharaname if turn == 2 else secondcharaname, font, (90, 90, 255), max_text_width_name)
                nametext_rect = nametext.get_rect()
                nametext_rect.left = textbox_rect.left + 20
                nametext_rect.top = textbox_rect.top + 20
                (answertext, font_externala) = render_text_paragraph(past_answer, (0, 0, 0), 1550, 250, 40, 20)
                y = borderbox.top
                first_pos = FIRST_POS
                second_pos = SECOND_POS
                if tts.is_speaking:
                    if whos_speaking == "first":
                        first_pos = (FIRST_POS[0], FIRST_POS[1] + wiggle_offset)
                    elif whos_speaking == "second":
                        second_pos = (SECOND_POS[0], SECOND_POS[1] + wiggle_offset)
                screen.blits([
                    (firstcharaavatar, first_pos),
                    (secondcharaavatar, second_pos),
                    (textbox, textbox_rect),
                    (nametext, nametext_rect)
                ])
                for line in answertext:
                    line_rect = line.get_rect()
                    line_rect.top = y
                    line_rect.left = borderbox.left
                    screen.blit(line, line_rect)
                    y += font_externala.get_height()
            else:
                max_text_width_name = textbox_rect.width - textbox_padding_x
                nametext = render_text_ellipsis(firstcharaname if turn == 1 else secondcharaname, font, (90, 90, 255), max_text_width_name)
                nametext_rect = nametext.get_rect()
                nametext_rect.left = textbox_rect.left + 20
                nametext_rect.top = textbox_rect.top + 20
                
                res_text = None
                if turn == 1:
                    # First character responds to second character's message
                    res_text = get_ai_response(
                        first_system_prompt,
                        [*firstchat_history, {'role': 'user', 'content': f"{secondcharaname}: {past_answer}"}]
                    )
                    firstchat_history.append({'role': 'user', 'content': f"{secondcharaname}: {past_answer}"})
                    firstchat_history.append({'role': 'assistant', 'content': res_text})
                    whos_speaking = "first"
                    (firstcharaavatar,last_first_thinker) = random_thinker(exclude=last_first_thinker)
                else:
                    # Second character responds to first character's message
                    res_text = get_ai_response(
                        second_system_prompt,
                        [*secondchat_history, {'role': 'user', 'content': f"{firstcharaname}: {past_answer}"}]
                    )
                    secondchat_history.append({'role': 'user', 'content': f"{firstcharaname}: {past_answer}"})
                    secondchat_history.append({'role': 'assistant', 'content': res_text})
                    whos_speaking = "second"
                    # Get the original (non-flipped) version for exclusion check
                    (new_thinker, last_second_thinker) = random_thinker(last_second_thinker)
                    secondcharaavatar = pygame.transform.flip(new_thinker, True, False)
                
                (answertext, font_externala) = render_text_paragraph(res_text, (0, 0, 0), 1550, 250, 40, 20)
                past_answer = res_text
                y = borderbox.top
                first_pos = FIRST_POS
                second_pos = SECOND_POS
                if tts.is_speaking:
                    if whos_speaking == "first":
                        first_pos = (FIRST_POS[0], FIRST_POS[1] + wiggle_offset)
                    elif whos_speaking == "second":
                        second_pos = (SECOND_POS[0], SECOND_POS[1] + wiggle_offset)
                screen.blits([
                    (firstcharaavatar, first_pos),
                    (secondcharaavatar, second_pos),
                    (textbox, textbox_rect),
                    (nametext, nametext_rect)
                ])
                for line in answertext:
                    line_rect = line.get_rect()
                    line_rect.top = y
                    line_rect.left = borderbox.left
                    screen.blit(line, line_rect)
                    y += font_externala.get_height()
                
                if turn == 1:
                    turn = 2
                else:
                    turn = 1
                on_wait = True
                ding.play()
                tts.speak(past_answer)
    
    pygame.display.update()