import threading # to have mutliple things going on in parralel (ie. networking, vision, gui)
import json # configuration
import queue # network outbox
import PySimpleGUI as sg # gui
import time # time deltas
from os import path # check if files exist

#local
import vision # self explanitory
import net # self explanitory

DIGITS = set() # type: set[CompoundDigit]
DELTA_TIME = 0
log = lambda value: print(f"[core] {value}")

class ConfigurationError(Exception): pass

class CompoundDigit():
    TYPE="score"
    # delta_threshold = 8

    def __init__(self, ref_list: list[str], name: str, text_ref: str):
        self.ref_list = ref_list
        self.name = name
        self.text_ref = text_ref
        self.initalize()
        DIGITS.add(self)
        
    def initalize(self):
        self.digits: list[vision.Number] = []
        for refrence_name in self.ref_list:
            number = vision.find_number(refrence_name)
            if number == None:
                raise ConfigurationError(f"Unable to construct Compound Digit, Number Refrence \"{refrence_name}\" doesn't have an Number attached to it.")
            self.digits.append(number)
        self.last_valid_value = 0
    
    def process_number(self) -> float | int:
        digits_result = [digit.number_value for digit in self.digits]
        if -2 in digits_result:
            log("Compound Digit failed to parse because one or more of the digits failed to pare into actual numbers") 
            log("TIP: Are you sure that your vision is clean and all your points are in the corect?")
            return -1
        
        i = 0
        for result in digits_result:
            i *= 10
            if result != -1: i += result
        return i
    
    @staticmethod
    def to_text(value: int | float):
        return str(value)
    
    def process(self) -> bool:
        number = self.process_number()
        if number == -1: return False
        if (self.last_valid_value != number): #and (abs(self.last_valid_value-number) <= self.delta_threshold or self.last_valid_value == 0): # if change in value and (the change isn't to great or we don't have a value yet)
            self.last_valid_value = number
            return True
        return False

class TimerCompoundDigit(CompoundDigit):
    TYPE="time"
    def process_number(self):
        if self.digits[-1].number_value == -1: # down to seconds
            i = 0
            val = 0
            while True:
                digit = self.digits[i].number_value
                if digit == -1: break
                val *= 10
                val += digit
            return (val / 10)
        else:
            num = super().process_number()
            mins = num // 100
            secs = num % 100
            return ((mins * 60) + secs)
    
    @staticmethod
    def to_text(value):
        if value > 60:
            mins = value // 60
            secs = value % 60
            return f"{mins}:{str(secs):{'0'}>2}"
        else:
            return str(round(value,1))
        
class QuaterCompoundDigit(CompoundDigit):
    TYPE="period"
    quater_text = {
        1: "1st",
        2: "2nd",
        3: "3rd",
        4: "4th",
        5: "OT"
    }

    @staticmethod
    def to_text(value):
        assert isinstance(value, int)
        return QuaterCompoundDigit.quater_text[value]

class ThreadContianer():
    def __init__(self, function, name: str, start: bool, cleanup, *args, **kwargs):
        self.target = function
        self.cleanup = cleanup
        self.name = name
        self.enabled = True
        self.args = args
        self.kwargs = kwargs
        self.thread = None
        if start: self.spawn()
    
    def loop(self, *args, **kwargs):
        log(f"Started thread {self.name}")
        while self.enabled:
            self.target(*args, **kwargs)
        if self.cleanup != None: self.cleanup()

    def spawn(self):
        self.enabled = True
        self.thread = threading.Thread(target=self.loop, name=self.name, daemon=True, args=self.args, kwargs=self.kwargs)
        self.thread.start()
    
    def kill(self):
        if self.thread == None: return
        self.enabled = False
        self.thread.join()
    
    def restart(self):
        self.kill()
        self.spawn()

def load_config(filepath: str):
    if path.exists(filepath):
        with open(filepath, 'r') as f:
            data = json.load(f) # type: dict[str, any]
        return data
    return {
        "input": {
            "camera_number": 0
        },
        "regions": {
        },
        "components": {
        },
        "output": {
            "weburl": "http://127.0.0.1:8088",
            "input_id": 3
        }
    }

def make_gui(cfg: dict[str, any]):
    menu_def = [['&Application', ["&Disbale All Region Opencv Debug Views"]],
                ['&Help', ['&About']] ]
    
    vision_core_tab_layout = [
        [sg.Button("Make New Region", key="-NEW_REGION-")],
        [sg.Text("Camera Number:"), sg.Spin([i for i in range(256)], initial_value=cfg["input"]["camera_number"], key='-CAMERA_VALUE-'), sg.Button("Update Camera", key="-SET_CAMERA-")],
        [sg.Button("Close Vision Core Debug Windows", key="-CLOSE_OPENCV_DEBUG_VISION_CORE-"), sg.Button("Open Vision Core Debug Windows", key="-OPEN_OPENCV_DEBUG_VISION_CORE-")]
    ]

    region_tab_layout = [
        [sg.Text("Selected Region:"), sg.Combo([region for region in cfg["regions"]], key='-REGION_SELECTOR-'), sg.Button("Refresh Regions", key="-REFRESH_REGION-")],
        [sg.Button("Rebound Region", key="-REBOUND_REGION-"), sg.Button("Erase Region", key="-ERASE_REGION-")],
        [sg.Text("Add Number:")],
        [sg.Button("7 Digit Bounding Box", key="-ADD_NUMBER_7_FULL_AUTO-")],#, sg.Button("7 Digit Scanning", key="-ADD_NUMBER_7_FULLER_AUTO-")],
        [sg.Button("2 Digit Manual Selection", key="-ADD_NUMBER_2-"), sg.Button("7 Digit Manual Selection", key="-ADD_NUMBER_7_SEMI_AUTO-")],
        [sg.Text("Debug Views: ")],
        [sg.Button("Hide All Debug Views", key="-CLOSE_OPENCV_DEBUG_REGION-"), sg.Button("Toggle Preprocess", key="-REGION_TOGGLE_PRE-"), sg.Button("Toggle Mask", key="-REGION_TOGGLE_MASK-"), sg.Button("Toggle Mask Controls", key="-REGION_TOGGLE_MASK_CONTROL-")],
        [sg.Button("Toggle Critical Points", key="-REGION_TOGGLE_CRIT-"), sg.Button("Toggle Composite HSV", key="-REGION_TOGGLE_COMP-"), sg.Button("Toggle Individual HSV", key="-REGION_TOGGLE_INDVIDUAL-")]
        # [sg.Button("Toggle PREPROCESS")]
    ]
    all_numbers = [] #type: list[vision.Number]
    for region in vision.REGIONS:
        all_numbers.extend(region.numbers)
    
    all_number_refs = set([number.refrence_name for number in all_numbers])
    all_used_numbers = [] #type: list[vision.Number]
    for digit in DIGITS:
        all_used_numbers.extend(digit.digits)

    all_used_number_refs = set([number.refrence_name for number in all_used_numbers])

    all_unused_number_refs = all_number_refs - all_used_number_refs

    compound_digit_layout = [
        [sg.Button("Create New Compound Digit", key="-NEW_COMPOUND-"), sg.Text("Type:"), sg.Combo(["score", "time", "period"], default_value="score", key="-COMPOUND_TYPE-")],
        [sg.Text("Selected Compound Digit:"), sg.Combo([digit.name for digit in DIGITS], key="-COMPOUND_SELECTOR-"), sg.Button("Erase Compound", key="-ERASE_COMPOUND-"), sg.Button("Re-Sort", key="-COMPOUND_RESORT-")],
        [sg.Button("Add Number to Compound Digit", key="-ADD_TO_COMPOUND-"), sg.Combo(list(all_unused_number_refs), key="-COMPOUND_ADDITION-")],
        [sg.Button("Remove Number from Compound Digit", key="-REMOVE_FROM_COMPOUND-"), sg.Combo([], key="-COMPOUND_SUBTRACTION-")],
        [sg.Text("Vmix Title:"), sg.Input(".Text", key="-COMPOUND_VMIX-"), sg.Button("Set Vmix Title", key="-SET_VMIX_COMPOUND-")],
        [sg.Button("Evaluate", key="-COMPOUND_EVAL-"), sg.Text("Result:"), sg.Text("", key="-COMPOUND_RESULT-")],
        [sg.Button("Refresh Tab", key="-REFRESH_COMPOUND_NUMBERS-")]
    ]

    number_tab = [
        [sg.Text("Selected Number:"), sg.Combo(list(all_number_refs), key="-NUMBER_SELECTOR-"), sg.Button("Refresh Numbers", key="-REFRESH_NUMBERS-")],
        [sg.Button("Erase Number", key="-ERASE_NUMBER-")],
        [sg.Text("Re-position Number:")],
        [sg.Button("7 Digit Bounding Box", key="-REPOS_NUMBER_7_FULL_AUTO-")],#, sg.Button("7 Digit Scanning", key="-REPOS_NUMBER_7_FULLER_AUTO-")],
        [sg.Button("2 Digit Manual Selection", key="-REPOS_NUMBER_2-"), sg.Button("7 Digit Manual Selection", key="-REPOS_NUMBER_7_SEMI_AUTO-")],
        [sg.Button("Evaluate", key="-NUMBER_EVAL-"), sg.Text("Result:"), sg.Text("", key="-NUMBER_RESULT-")]
    ]

    net_tab_layout = [
        [sg.Text("Vmix Web Controller Address:"), sg.Input(cfg["output"]["weburl"], key='-WEB_URL-')],
        [sg.Text("Vmix Scoreboard input:"), sg.Spin([i for i in range(64)], initial_value=cfg["output"]["input_id"], key='-WEB_INPUT-'), sg.Button("Apply Changes", key='-WEB_UPDATE-')],
        [sg.Button("Disable Networking", key="-WEB_DISABLE-"), sg.Button("Enable Networking", key="-WEB_ENABLE-")]
    ]

    system_tab_layout = [
        [sg.Button("Kill Vision", key="-KILL_VISION-"), sg.Button("Restart Vision", key="-RESTART_VISION-")],
        [sg.Button("Kill Networking", key="-KILL_NET-"), sg.Button("Restart Networking", key="-RESTART_NET-")],
        [sg.Button("Load Configuration", key="-LOAD_CONFIG-"), sg.Button("Save Configuration", key="-SAVE_CONFIG-")],
        [sg.Text("Protip: Saving configurations will save you time")],
        # [sg.Text("Double Protip: if you save your file as defualtcfg.json in the same working directory the program will load up the config the first time")],
        [sg.Button("Drop into Debugger", key="-DEBUGGER-")],
        [sg.Text(f"Frametime: {DELTA_TIME}MS", key="-DELTA_TIME-")]
    ]

    layout =  [ [sg.MenubarCustom(menu_def, key='-MENU-')]]
    layout += [[sg.TabGroup([[ sg.Tab('Vision Core', vision_core_tab_layout),
                               sg.Tab("Regions", region_tab_layout),
                               sg.Tab("Compound Digits", compound_digit_layout),
                               sg.Tab("Numbers", number_tab),
                               sg.Tab("Networking", net_tab_layout),
                               sg.Tab('System', system_tab_layout)]], key='-TAB_GROUP-', expand_x=True, expand_y=True)]]

    window = sg.Window('SSN Computer Vision Scoreboard Vmix Intergration', layout)
                # [sg.Text('SSN S.A.B.E.R.', size=(38, 1), justification='center', font=("Helvetica", 16), relief=sg.RELIEF_RIDGE, k='-TEXT HEADING-', enable_events=True)]]
    return window

def gui_code(vision_thread: ThreadContianer, net_thread: ThreadContianer, vision_core: vision.VisionCore, network_controller: net.Vmix_controller, cfg: dict[str, any]):
    window = make_gui(cfg)
    while True:
        event, values = window.read(25)
        time.sleep(0)
        if event != sg.TIMEOUT_EVENT:
            print(event)
        if event == sg.WIN_CLOSED: 
            vision_thread.kill()
            net_thread.kill()
            return
        if event == sg.TIMEOUT_EVENT: 
            window["-DELTA_TIME-"].update(f"Frametime: {DELTA_TIME}MS")
        # System Region Tab
        if event == "Disbale All Region Opencv Debug Views":
            for region in vision.REGIONS:
                region.debug_state = 0
        if event == "-KILL_VISION-":
            vision_thread.kill()
        if event == "-RESTART_VISION-":
            vision_thread.restart()
        if event == "-KILL_NET-":
            net_thread.kill()
        if event == "-RESTART_NET-":
            net_thread.restart()
        
        #Vision Core Tab
        if event == "-NEW_REGION-":
            name = sg.popup_get_text("New Region Name", title="Region Name")
            if name == "" or name == None:
                sg.popup("Invalid Region Name: cannot be empty.")
                continue
            if name in vision.REGIONS:
                sg.popup("Invalid Region Name: In use.")
                continue
            bbox = vision_core.select_bbox()
            region = vision.Region(name, bbox)
            window['-REGION_SELECTOR-'].update(values=[region.region_name for region in vision.REGIONS])
        if event == "-SET_CAMERA-":
            vision_core.initalize_channel(values['-CAMERA_VALUE-'])
        if event == "-CLOSE_OPENCV_DEBUG_VISION_CORE-":
            vision_core.debug_state = 0
        if event == "-OPEN_OPENCV_DEBUG_VISION_CORE-":
            vision_core.debug_state = 3
        
        # Region tab
        if event == "-REBOUND_REGION-":
            region = values['-REGION_SELECTOR-']
            if region == '': continue
            r = None
            for re in vision.REGIONS:
                if re.region_name == region: 
                    r = re
                    break
            if r == None: raise RuntimeError("How? How did you manage this?")
            result = sg.popup("This Action will also null all number's positions in this region, meaning you will have to reposition the numbers", custom_text=("OK", "Abort"))
            if result == "Abort" or result == None: continue
            enabled = vision_thread.enabled
            if enabled: vision_thread.kill()
            for number in r.numbers:
                number.points = [vision.Point([0,0]), ] * len(number.points)
            bbox = vision_core.select_bbox()
            r.bbox = bbox
            if enabled: vision_thread.spawn()
        if event == "-ERASE_REGION-":
            region = values['-REGION_SELECTOR-']
            if region == '': continue
            r = None
            for re in vision.REGIONS:
                if re.region_name == region: 
                    r = re
                    break
            if r == None: raise RuntimeError("How? How did you manage this?")
            result = sg.popup("This Action will also erase all numbers in this region", custom_text=("OK", "Abort"))
            if result == "Abort" or result == None: continue
            enabled = vision_thread.enabled
            if enabled: vision_thread.kill()
            for number in r.numbers:
                for digit in DIGITS:
                    digit.digits.remove(number)
            if enabled: vision_thread.spawn()
            r.close()   
        if event.startswith("-ADD_NUMBER_"):
            region = values['-REGION_SELECTOR-']
            if region == '': continue

            ref_name = sg.popup_get_text("New Number Name", title="Number Name")
            if ref_name == "" or ref_name == None:
                sg.popup("Invalid Region Name: cannot be empty.")
                continue
            number_existant = vision.find_number(ref_name)
            if number_existant != None:
                sg.popup("Invalid Region Name: In use.")
                continue

            event = event.removeprefix("-ADD_NUMBER_")
            r = None
            for re in vision.REGIONS:
                if re.region_name == region: 
                    r = re
                    break
            if r == None: raise RuntimeError("How? How did you manage this?")
            loop = None
            if event == "2-": loop = vision.Callback_Number_Two(r.mask)
            if event == "7_SEMI_AUTO-": loop = vision.Callback_Number_Manual(r.mask)
            if event == "7_FULL_AUTO-": loop = vision.Callback_Number_Manual_Tool(r.mask)
            if event == "7_FULLER_AUTO-": loop = vision.Callback_Number_Auto(r.mask)
            loop.loop()
            number = vision.Number(ref_name, loop.points)
            r.numbers.append(number)
            continue
        if event == "-CLOSE_OPENCV_DEBUG_REGION-":
            region = values['-REGION_SELECTOR-']
            if region == '': continue
            r = None
            for re in vision.REGIONS:
                if re.region_name == region: 
                    r = re
                    break
            if r == None: raise RuntimeError("How? How did you manage this?")
            r.debug_state = 0
        if event.startswith("-REGION_TOGGLE_"):
            region = values['-REGION_SELECTOR-']
            if region == '': continue
            # event = event.removeprefix("-ADD_NUMBER_")
            r = None
            for re in vision.REGIONS:
                if re.region_name == region: 
                    r = re
                    break
            if r == None: raise RuntimeError("How? How did you manage this?")
            event = event.removeprefix("-REGION_TOGGLE_")
            if event == "PRE-": r.debug_state ^= vision.Region.DEBUG_PREPROCESS
            if event == "MASK-": r.debug_state ^= vision.Region.DEBUG_MASKED
            if event == "MASK_CONTROL-": r.debug_state ^= vision.Region.DEBUG_MASK_CONTROLS
            if event == "CRIT-": r.debug_state ^= vision.Region.DEBUG_CRITICAL_POINTS
            if event == "COMP-": r.debug_state ^= vision.Region.DEBUG_COMPOSITE_HSV
            if event == "INDVIDUAL-": r.debug_state ^= vision.Region.DEBUG_INDIVIDUAL_HSV
            continue
        if event == "-REFRESH_REGION-":
            window['-REGION_SELECTOR-'].update(values=[region.region_name for region in vision.REGIONS])
        
        #Compound digit tab
        if event == "-NEW_COMPOUND-":
            compound_type = values['-COMPOUND_TYPE-']
            name = sg.popup_get_text("New Compound Name", title="Compound Name")
            if name == "" or name == None:
                sg.popup("Invalid Compound Name: cannot be empty.")
                continue
            if name in [digit.name for digit in DIGITS]:
                sg.popup("Invalid Compound Name: In use.")
                continue
            title = sg.popup_get_text("New Vmix Title Name", title="Vmix Title Name")
            if name == "" or name == None:
                sg.popup("Invalid Vmix Title Name: cannot be empty")
                continue
            if compound_type == "score": CompoundDigit([], name, title)
            if compound_type == "time": TimerCompoundDigit([], name, title)
            if compound_type == "period": QuaterCompoundDigit([], name, title)
            names = [digit.name for digit in DIGITS]
            window["-COMPOUND_SELECTOR-"].update(values=names)
        if event == "-REFRESH_COMPOUND_NUMBERS-":
            window["-COMPOUND_SELECTOR-"].update(value=values["-COMPOUND_SELECTOR-"], values=[digit.name for digit in DIGITS])
            all_numbers = [] #type: list[vision.Number]
            for region in vision.REGIONS:
                all_numbers.extend(region.numbers)
            
            all_number_refs = set([number.refrence_name for number in all_numbers])
            all_used_numbers = [] #type: list[vision.Number]
            for digit in DIGITS:
                all_used_numbers.extend(digit.digits)

            all_used_number_refs = set([number.refrence_name for number in all_used_numbers])

            all_unused_number_refs = list(all_number_refs - all_used_number_refs)
            
            if len(all_unused_number_refs) > 0:
                window["-COMPOUND_ADDITION-"].update(value=all_unused_number_refs[0], values=all_unused_number_refs)
            else: 
                window["-COMPOUND_ADDITION-"].update(value="", values=[])
            compound_name = values["-COMPOUND_SELECTOR-"]
            if compound_name == "": continue
            compound = None
            for comp in DIGITS:
                if comp.name == compound_name:
                    compound = comp
                    break
            if compound == None: raise RuntimeError("How? How did you manage this?")
            used_number_refs = [number.refrence_name for number in compound.digits]
            if len(used_number_refs) > 0:
                window["-COMPOUND_SUBTRACTION-"].update(value=used_number_refs[0], values=used_number_refs)
            else:
                window["-COMPOUND_SUBTRACTION-"].update(value="", values=[])
            window["-COMPOUND_VMIX-"].update(value=compound.text_ref)
        if event == "-ADD_TO_COMPOUND-":
            compound_name = values["-COMPOUND_SELECTOR-"]
            if compound_name == "": continue
            compound = None
            for comp in DIGITS:
                if comp.name == compound_name:
                    compound = comp
                    break
            if compound == None: raise RuntimeError("How? How did you manage this?")
            num_ref = values["-COMPOUND_ADDITION-"]
            if num_ref == "": continue
            number = vision.find_number(num_ref)
            if number == None: raise RuntimeError("How? How did you manage this?")
            compound.digits.append(number)
            compound.digits.sort(key=lambda x: x.points[1].x)
        if event == "-REMOVE_FROM_COMPOUND-":
            compound_name = values["-COMPOUND_SELECTOR-"]
            if compound_name == "": continue
            compound = None
            for comp in DIGITS:
                if comp.name == compound_name:
                    compound = comp
                    break
            if compound == None: raise RuntimeError("How? How did you manage this?")
            num_ref = values["-COMPOUND_SUBTRACTION-"]
            if num_ref == "": continue
            if num_ref not in [number.refrence_name for number in compound.digits]: continue
            number = None
            for numb in compound.digits:
                if numb.refrence_name == num_ref:
                    number = numb
                    break
            if number == None: raise RuntimeError("How? How did you manage this?")
            compound.digits.remove(number)
            compound.digits.sort(key=lambda x: x.points[1].x)
        if event == "-COMPOUND_EVAL-":
            compound_name = values["-COMPOUND_SELECTOR-"]
            if compound_name == "": continue
            compound = None
            for comp in DIGITS:
                if comp.name == compound_name:
                    compound = comp
                    break
            if compound == None: raise RuntimeError("How? How did you manage this?")
            value = compound.to_text(compound.last_valid_value)
            window["-COMPOUND_RESULT-"].update(value=value)
        if event == "-COMPOUND_RESORT-":
            compound_name = values["-COMPOUND_SELECTOR-"]
            if compound_name == "": continue
            compound = None
            for comp in DIGITS:
                if comp.name == compound_name:
                    compound = comp
                    break
            if compound == None: raise RuntimeError("How? How did you manage this?")
            compound.digits.sort(key=lambda x: x.points[1].x)

        # Number Tab
        if event == "-ERASE_NUMBER-":
            ref_name = values["-NUMBER_SELECTOR-"]
            number = vision.find_number(ref_name)
            if number == None: continue
            result = sg.popup("This Action will also erase all this number from its region and the compound digit if its in it", custom_text=("OK", "Abort"))
            if result == "Abort" or result == None: continue
            for region in vision.REGIONS: region.numbers.remove(number)
            for digit in DIGITS: digit.digits.remove(number)
            all_numbers = [] #type: list[vision.Number]
            for region in vision.REGIONS:
                all_numbers.extend(region.numbers)
            
            all_number_refs = [number.refrence_name for number in all_numbers]
            window["-NUMBER_SELECTOR-"].update(values=all_number_refs)
        if event.startswith("-REPOS_NUMBER_"):
            ref_name = values["-NUMBER_SELECTOR-"]
            number = vision.find_number(ref_name)
            if number == None: continue
            region = None
            for r in vision.REGIONS:
                if number in r.numbers:
                    region = r
                    break
            if region == None: raise RuntimeError("How? How did you manage this?")
            event = event.removeprefix("-REPOS_NUMBER_")
            loop = None
            if event == "2-": loop = vision.Callback_Number_Two(region.mask)
            if event == "7_SEMI_AUTO-": loop = vision.Callback_Number_Manual(region.mask)
            if event == "7_FULL_AUTO-": loop = vision.Callback_Number_Manual_Tool(region.mask)
            if event == "7_FULLER_AUTO-": loop = vision.Callback_Number_Auto(region.mask)
            loop.loop()
            number.points = loop.points
            continue
        if event == "-REFRESH_NUMBERS-":
            all_numbers = [] #type: list[vision.Number]
            for region in vision.REGIONS:
                all_numbers.extend(region.numbers)
            
            all_number_refs = [number.refrence_name for number in all_numbers]
            window["-NUMBER_SELECTOR-"].update(values=all_number_refs)
        if event == "-NUMBER_EVAL-":
            ref_name = values["-NUMBER_SELECTOR-"]
            number = vision.find_number(ref_name)
            if number == None: continue
            window["-NUMBER_RESULT-"].update(value=str(number.number_value))

        # Networking
        if event == '-WEB_UPDATE-':
            new_url = values['-WEB_URL-']
            new_channel = int(values['-WEB_INPUT-'])
            network_controller.set_url(new_url)
            network_controller.input_channel = new_channel
        if event == "-WEB_DISABLE-":
            network_controller.enabled = False
        if event == "-WEB_ENABLE-":
            network_controller.enabled = True

        # System Tab
        if event == "-LOAD_CONFIG-":
            filepath = sg.popup_get_file("Open Configuration", "Open Configuration")
            if filepath == "" or filepath == None: continue
                
            new_cfg = load_config(filepath)
            enabled = vision_thread.enabled
            if enabled: vision_thread.kill()
            vision.REGIONS.clear()
            vision.ACTIVE_REGIONS.clear()
            DIGITS.clear()
            vision_core.initalize_channel(vision.cv.imread("8888.jpg"))#new_cfg["input"]["camera_number"])
            network_controller.enabled = True
            network_controller.set_url(new_cfg["output"]["weburl"])
            network_controller.input_channel = new_cfg["output"]["input_id"]
        
            for region_name in new_cfg["regions"]:
                specific_cfg = new_cfg["regions"][region_name]
                numbers = [vision.Number(numbercfg, [vision.Point(value) for value in specific_cfg["numbers"][numbercfg]]) for numbercfg in specific_cfg["numbers"]]
                vision.Region(region_name,
                            specific_cfg["bbox"], 
                            vision.Point(specific_cfg["hue_thresholding"]),
                            vision.Point(specific_cfg["saturation_thresholding"]),
                            vision.Point(specific_cfg["value_thresholding"]),
                            numbers)
            
            for component_name in new_cfg["components"]:
                specific_cfg = new_cfg["components"][component_name]
                numbers = specific_cfg["numbers"]
                if specific_cfg["type"] == "time": TimerCompoundDigit(numbers, component_name, specific_cfg["text_title"])
                elif specific_cfg["type"] == "period": QuaterCompoundDigit(numbers, component_name, specific_cfg["text_title"])
                else: CompoundDigit(numbers, component_name, specific_cfg["text_title"])
            if enabled: vision_thread.spawn()

        if event == "-SAVE_CONFIG-":
            vision_core.img_channel = 0
            config_obj = {
                "input": {
                    "camera_number": vision_core.img_channel
                },
                "regions": {
                    region.region_name: {
                        "bbox": region.bbox,
                        "hue_thresholding": [vision.uint8_to_real_hue(v) for v in region.hue_thresholding.to_list()],
                        "saturation_thresholding": [vision.uint8_to_real_snv(v) for v in region.sat_thresholding.to_list()],
                        "value_thresholding": [vision.uint8_to_real_snv(v) for v in region.val_thresholding.to_list()],
                        "numbers": {
                            number.refrence_name: [point.to_list() for point in number.points]
                            for number in region.numbers 
                        }
                    } for region in vision.REGIONS
                },
                "components": {
                    digit.name: {
                        "type": digit.TYPE,
                        "text_title": digit.text_ref,
                        "numbers": [number.refrence_name for number in digit.digits]
                    } for digit in DIGITS},
                "output": {
                    "weburl": network_controller.url,
                    "input_id": network_controller.input_channel
                }
            }

            filepath = sg.popup_get_file("Save As...", "Save As...")
            if filepath == "" or filepath == None: continue

            with open(filepath, 'w') as f:
                json.dump(config_obj, f)

        if event == "-DEBUGGER-":
            breakpoint()

def main():
    # sys.setswitchinterval(0.005) # FEEL MY MAXIMUM SPEED.
    cfg = load_config("defualtcfg.json")
    log("Initalizing Vision Core, this may take a few secs...")
    vision_core = vision.VisionCore(vision.cv.imread("8888.jpg"))#cfg["input"]["camera_number"])
    log("Vision Core done loading")
    output_queue: queue.Queue[tuple[str, str]] = queue.Queue()
    network_controller = net.Vmix_controller(cfg["output"]["weburl"],cfg["output"]["input_id"])

    for region_name in cfg["regions"]:
        specific_cfg = cfg["regions"][region_name]
        numbers = [vision.Number(numbercfg, [vision.Point(value) for value in specific_cfg["numbers"][numbercfg]]) for numbercfg in specific_cfg["numbers"]]
        vision.Region(region_name,
                      specific_cfg["bbox"], 
                      vision.Point(specific_cfg["hue_thresholding"]),
                      vision.Point(specific_cfg["saturation_thresholding"]),
                      vision.Point(specific_cfg["value_thresholding"]),
                      numbers)
    
    for component_name in cfg["components"]:
        specific_cfg = cfg["components"][component_name]
        numbers = specific_cfg["numbers"]
        if specific_cfg["type"] == "time": TimerCompoundDigit(numbers, component_name, specific_cfg["text_title"])
        elif specific_cfg["type"] == "period": QuaterCompoundDigit(numbers, component_name, specific_cfg["text_title"])
        else: CompoundDigit(numbers, component_name, specific_cfg["text_title"])

    def vision_function():
        global DELTA_TIME
        t_start = time.time()
        vision_core.run_frame()
        for digit in DIGITS:
            if digit.process():
                output_queue.put((digit.text_ref, digit.to_text(digit.last_valid_value)))
        t_end = time.time()
        vision_core.wait_key(1)
        DELTA_TIME = round((t_end - t_start) * 1000,1)
        # print(DELTA_TIME)
    
    def vison_cleanup():
        vision_core.debug_state_last_frame = 0
        for region in vision.REGIONS:
            region.debug_state_last_frame = 0
        vision.cv.destroyAllWindows()
        
    def networking_function():
        try:
            output = output_queue.get_nowait()
        except queue.Empty:
            time.sleep(0)
            return
        try:
            network_controller.send_request(*output)
        except Exception as e:
            log(f"Network error, {e}")
        output_queue.task_done()
    
    # profiler = cProfile.Profile()
    # profiler.enable()
    # vision_function()
    # profiler.disable()
    # s = io.StringIO()
    # ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    # ps.print_stats()
    # print(s.getvalue())
    vision_thread = ThreadContianer(vision_function, "Vision Function", True, vison_cleanup)
    # vision_thread.loop()
    networking_thread = ThreadContianer(networking_function, "Networking Function", True, None)
    # vision_thread.thread.join()
    gui_code(vision_thread, networking_thread, vision_core, network_controller, cfg)
    # print("Loop Begin")
    # i = 0
    # while True:
    #     i += 1
    #     time.sleep(1)
    #     print(f"Loop iter {i}")

if __name__ == "__main__": main()