import cv2 as cv # Computer vision
import numpy as np # math

ACTIVE_REGIONS = set() # type: set[Region]
REGIONS = set() # type: set[Region]

##
# Helpers
##

log = lambda value: print(f"[vision] {value}")

real_to_uint8_hue = lambda hue: int(hue * 0.5)
uint8_to_real_hue = lambda hue: int(hue * 2)

real_to_uint8_snv = lambda snv: int(round(snv * (255/100), 2))
uint8_to_real_snv = lambda snv: int(round(snv * (100/255), 2))

flag_active = lambda value, flag: (value & flag) == flag

class Point():
    # I needed this because lists / tuples both suck as 2d points
    def __init__(self, iteratable: list[int] | tuple[int, int]):
        if isinstance(iteratable[0], Point): assert False
        if isinstance(iteratable[1], Point): assert False
        self.x = iteratable[0]
        self.y = iteratable[1]

    def to_tuple(self) -> tuple[int, int]:
        return (self.x, self.y)
    
    def to_list(self) -> list[int, int]:
        return [self.x, self.y]
    
    def to_tuple_yx(self) -> tuple[int, int]:
        return (self.y, self.x)
    
    def to_tuple_yx(self) -> tuple[int, int]:
        return [self.y, self.x]

    def __eq__(self, value) -> bool:
        if isinstance(value, (tuple, list)):
            value = Point(value)
        if isinstance(value, Point):
            return self.to_tuple() == value.to_tuple()
        return False
    
    def __ne__(self, value) -> bool:
        return not self.__eq__(value)

    def __getitem__(self, i: int):
        assert (i == 0 or i == 1)
        if i == 0: return self.x
        if i == 1: return self.y
    
    def __setitem__(self, i: int, value):
        assert (i == 0 or i == 1)
        if i == 0: self.x = value
        if i == 1: self.y = value

    def __len__(self): return 2

    def gen(self):
        yield self.x
        yield self.y

    def __add__(self, value):
        if isinstance(value, (tuple, list)):
            value = Point(value)
        assert isinstance(value, Point)
        return Point([self.x + value.x, self.y + value.y])
    
    def __radd__(self, value):
        if isinstance(value, (tuple, list)):
            value = Point(value)
        assert isinstance(value, Point)
        return Point([self.x + value.x, self.y + value.y])
    
    def __sub__(self, value):
        if isinstance(value, (tuple, list)):
            value = Point(value)
        assert isinstance(value, Point)
        return Point([self.x - value.x, self.y - value.y])
    
    def __rsub__(self, value):
        if isinstance(value, (tuple, list)):
            value = Point(value)
        assert isinstance(value, Point)
        return Point([value.x - self.x, value.y - self.y])
    
    def __floordiv__(self, value):
        return Point([self.x // value, self.y // value])
    
    def __str__(self):
        return f"Point<x: {self.x}, y: {self.y}>"
    
    def __repr__(self): return self.__str__()

UP = Point((0, -1))
DOWN = Point((0, 1))
LEFT = Point((-1, 0))
RIGHT = Point((1, 0))

class CritPoint():
    def __init__(self, refrence_name: str, point: Point):
        self.refrence_name = refrence_name
        self.point = point
        self.active = False

class Number():
    LOOKUP_VALUE = {
        # EMPTY, TOP_MID, MID_MID, LOW_MID, 
        # TOP_LEFT, TOP_RIGHT, LOW_LEFT, LOW_RIGHT
        0b00000000: -1,
        0b01011111: 0,
        0b00000101: 1,
        0b01110110: 2,
        0b01110101: 3,
        0b00101101: 4,
        0b01111001: 5,
        0b01111011: 6,
        0b01000101: 7,
        0b01111111: 8,
        0b01111101: 9,
    }

    def __init__(self, refrence_name: str, points: list[Point]):
        assert (len(points) == 2 or len(points) == 7) 
        self.refrence_name = refrence_name
        self.points = points
        self.activations = [False,] * len(points)
        self.number_value = -1
        # self.has_changed = False

    def update_activations(self, activations: list[bool]):
        self.activations = activations
        if len(self.activations) == 2:
            if all(activations): 
                self.number_value = 1
            elif not all(activations) and not any(activations):
                self.number_value = 0
            else:
                self.number_value = -2
            return
        
        val = 0
        for i in range(7):
            val <<= 1
            val += (2 * int(activations[i]))
        val >>= 1
        if val not in Number.LOOKUP_VALUE: self.number_value = -2
        else: self.number_value = Number.LOOKUP_VALUE[val]

class Callback_Number_Manual():
    WINDOW_TITLE = "7-Segment Number Creation Manual"
    POINT_AMOUNT = 7

    def __init__(self, img):
        self.points: list[Point] = []
        self.done = False
        self.img = cv.cvtColor(img, cv.COLOR_GRAY2BGR)
        cv.imshow(self.WINDOW_TITLE, img)
        cv.setMouseCallback(self.WINDOW_TITLE, self.callback)
    
    def callback(self, event, x, y, flags, param):
        if event == cv.EVENT_LBUTTONDOWN:
            # print(x,y)
            self.points.append(Point((x, y)))
    
    def loop(self):
        while len(self.points) != self.POINT_AMOUNT:
            cv.waitKey(5)
        cv.destroyWindow(self.WINDOW_TITLE)

class Callback_Number_Two(Callback_Number_Manual):
    WINDOW_TITLE = "2-Segment Number Creation Manual"
    POINT_AMOUNT = 2

class Callback_Number_Auto(Callback_Number_Manual):
    WINDOW_TITLE = "7-Segment Number Creation Automatic Scan"
    
    def callback(self, event, x, y, flags, param):
        if event == cv.EVENT_LBUTTONDOWN:
            self.points = scan_segments(Point([x, y]), self.img)

class Callback_Number_Manual_Tool(Callback_Number_Manual):
    WINDOW_TITLE = "7-Segment Number Creation Manual tooling"
    
    def __init__(self, img):
        super().__init__(img)
        
        self.phase = 0
        self.top_left: Point = None
        self.bottom_right: Point = None
    
    def phase_0(self, event, point: Point):
        img = self.img.copy()
        img = cv.circle(img, point.to_tuple(), 5, (0x00, 0x00, 0xff), -1)
        cv.imshow(self.WINDOW_TITLE, img)
        if event == cv.EVENT_LBUTTONDOWN:
            self.top_left = point
            self.phase += 1
    
    def phase_1(self, event, point: Point):
        img = self.img.copy()
        img = cv.rectangle(img, self.top_left.to_tuple(), point.to_tuple(), (0x00, 0xff, 0x00), 4)
        top_right = Point([point.x, self.top_left.y])
        bottom_left = Point([self.top_left.x, point.y])

        top_segment = (top_right + self.top_left) // 2
        img = cv.circle(img, top_segment.to_tuple(), 5, (0x00, 0xff, 0xff), -1)

        bottom_segment = (bottom_left + point) // 2
        img = cv.circle(img, bottom_segment.to_tuple(), 5, (0x00, 0xff, 0xff), -1)

        middle_segment = (self.top_left + point) // 2
        img = cv.circle(img, middle_segment.to_tuple(), 5, (0x00, 0xff, 0xff), -1)

        middle_left_segment = (self.top_left + bottom_left) // 2
        middle_right_segment = (top_right + point) // 2

        top_left_segment = (middle_left_segment + self.top_left) // 2
        img = cv.circle(img, top_left_segment.to_tuple(), 5, (0x00, 0xff, 0xff), -1)

        bottom_left_segment = (middle_left_segment + bottom_left) // 2
        img = cv.circle(img, bottom_left_segment.to_tuple(), 5, (0x00, 0xff, 0xff), -1)

        top_right_segment = (middle_right_segment + top_right) // 2
        img = cv.circle(img, top_right_segment.to_tuple(), 5, (0x00, 0xff, 0xff), -1)

        bottom_right_segment = (middle_right_segment + point) // 2
        img = cv.circle(img, bottom_right_segment.to_tuple(), 5, (0x00, 0xff, 0xff), -1)


        img = cv.circle(img, self.top_left.to_tuple(), 5, (0x00, 0x00, 0xff), -1)
        img = cv.circle(img, point.to_tuple(), 5, (0xff, 0x00, 0x00), -1)

        cv.imshow(self.WINDOW_TITLE, img)
        if event == cv.EVENT_LBUTTONDOWN:
            self.bottom_right = point
            self.phase += 1
            self.points = [top_segment, middle_segment, bottom_segment, top_left_segment, top_right_segment, bottom_left_segment, bottom_right_segment]

    def callback(self, event, x, y, flags, param):
        point = Point([x,y])
        if self.phase == 0: self.phase_0(event, point)
        elif self.phase == 1: self.phase_1(event, point)
        # if event == cv.EVENT_LBUTTONDOWN:
        #     # print(x,y)
        #     self.points = scan_segments(Point([x, y]), self.img)

class Region():
    DEBUG_PREPROCESS = 0x01
    DEBUG_MASKED = 0x02
    DEBUG_CRITICAL_POINTS = 0x04
    DEBUG_MASK_CONTROLS = 0x08
    DEBUG_COMPOSITE_HSV = 0x10
    DEBUG_INDIVIDUAL_HSV = 0x20

    def __init__(self, 
            region_name: str,
            bbox: tuple[int, int, int, int],
            hue_thresholding: Point = None, 
            sat_thresholding: Point = None, 
            val_thresholding: Point = None, 
            numbers: list[Number] = None,
            critical_points: list[CritPoint] = None):
        self.region_name = region_name

        self.bbox = bbox
        
        if hue_thresholding: self.hue_thresholding = Point([real_to_uint8_hue(v) for v in hue_thresholding.gen()])
        else: self.hue_thresholding = Point((0, 180))

        if sat_thresholding: self.sat_thresholding = Point([real_to_uint8_snv(v) for v in sat_thresholding.gen()])
        else: self.sat_thresholding = Point((0, 255))
        
        if val_thresholding: self.val_thresholding = Point([real_to_uint8_snv(v) for v in val_thresholding.gen()])
        else: self.val_thresholding = Point((0, 255))

        if numbers: self.numbers = numbers
        else: self.numbers = []

        if critical_points: self.critical_points = critical_points
        else: self.critical_points = []

        self.debug_state = (Region.DEBUG_MASKED + Region.DEBUG_PREPROCESS + Region.DEBUG_MASK_CONTROLS + Region.DEBUG_CRITICAL_POINTS) * 0
        self.debug_state_last_frame = 0
        
        REGIONS.add(self)
        ACTIVE_REGIONS.add(self)
    
    def do_frame(self, capture: np.ndarray):
        ROI = capture[self.bbox[0]:self.bbox[2],self.bbox[1]:self.bbox[3]]
        self.buffer = ROI.copy()
        blured = cv.GaussianBlur(ROI, (3,3), 0)
        hsv_frame = cv.cvtColor(blured, cv.COLOR_BGR2HSV)
        mask = cv.inRange(hsv_frame, 
            (self.hue_thresholding[0], self.sat_thresholding[0], self.val_thresholding[0]),
            (self.hue_thresholding[1], self.sat_thresholding[1], self.val_thresholding[1])
        )
        self.mask = mask.copy()

        for crit in self.critical_points:
            crit.active = mask[*crit.point.to_tuple_yx()] == 255
        
        for number in self.numbers:
            activations = [mask[*point.to_tuple_yx()] == 255 for point in number.points]
            number.update_activations(activations)

        if (self.debug_state != 0 or self.debug_state_last_frame != 0):
            self.process_debug_windows(Region.DEBUG_PREPROCESS, "pre-process", ROI)
            # self.process_debug_windows(Region.DEBUG_MASKED, "mask", mask) # we need to do special things with trackbars
            self.process_debug_windows(Region.DEBUG_COMPOSITE_HSV, "composite-hsv", hsv_frame)
            self.process_debug_windows(Region.DEBUG_INDIVIDUAL_HSV, "hue", hsv_frame[:,:,0])
            self.process_debug_windows(Region.DEBUG_INDIVIDUAL_HSV, "sat", hsv_frame[:,:,1])
            self.process_debug_windows(Region.DEBUG_INDIVIDUAL_HSV, "val", hsv_frame[:,:,2])

            crit_points_overlay = mask.copy()

            if flag_active(self.debug_state, Region.DEBUG_CRITICAL_POINTS):
                # : np.ndarray = mask.copy()
                crit_points_overlay = cv.cvtColor(mask, cv.COLOR_GRAY2BGR)
                
                for crit in self.critical_points:
                    crit_points_overlay = cv.circle(crit_points_overlay, crit.point.to_tuple(), 5, (0x00, 0xff, 0x00) if crit.active else (0x00, 0x00, 0xff), -1)
                
                for number in self.numbers:
                    for i in range(len(number.points)):
                        position = number.points[i].to_tuple()
                        activation = number.activations[i]
                        crit_points_overlay = cv.circle(crit_points_overlay, position, 5, (0x00, 0xff, 0x00) if activation else (0x00, 0x00, 0xff), -1)
                
            self.process_debug_windows(Region.DEBUG_CRITICAL_POINTS, "crit", crit_points_overlay)
                
            if flag_active(self.debug_state, Region.DEBUG_MASKED):
                window_name = f"DEBUG: {self.region_name}@mask"
                
                if not flag_active(self.debug_state, Region.DEBUG_MASK_CONTROLS) and flag_active(self.debug_state_last_frame, Region.DEBUG_MASK_CONTROLS):
                    cv.destroyWindow(window_name)
                
                cv.imshow(window_name, mask)
                
                if flag_active(self.debug_state, Region.DEBUG_MASK_CONTROLS) and not flag_active(self.debug_state_last_frame, Region.DEBUG_MASK_CONTROLS):
                    cv.createTrackbar("Hue min", window_name, 0, 360, lambda x: self.threshold_slider_callback(0, False, x))
                    cv.createTrackbar("Hue max", window_name, 0, 360, lambda x: self.threshold_slider_callback(0, True, x))
                    cv.createTrackbar("Sat min", window_name, 0, 100, lambda x: self.threshold_slider_callback(1, False, x))
                    cv.createTrackbar("Sat max", window_name, 0, 100, lambda x: self.threshold_slider_callback(1, True, x))
                    cv.createTrackbar("Val min", window_name, 0, 100, lambda x: self.threshold_slider_callback(2, False, x))
                    cv.createTrackbar("Val max", window_name, 0, 100, lambda x: self.threshold_slider_callback(2, True, x))
                
            if not flag_active(self.debug_state, Region.DEBUG_MASKED) and flag_active(self.debug_state_last_frame, Region.DEBUG_MASKED):
                cv.destroyWindow(f"DEBUG: {self.region_name}@mask")

        self.debug_state_last_frame = self.debug_state

    def threshold_slider_callback(self, channel: int, upper: bool, value: int):
        if channel == 0: self.hue_thresholding[int(upper)] = real_to_uint8_hue(value)
        if channel == 1: self.sat_thresholding[int(upper)] = real_to_uint8_snv(value)
        if channel == 2: self.val_thresholding[int(upper)] = real_to_uint8_snv(value)

    def process_debug_windows(self, flag: int, step_name: str, frame: np.ndarray):
        window_name = f"DEBUG: {self.region_name}@{step_name}"
        if flag_active(self.debug_state, flag):
            cv.imshow(window_name, frame)
        
        if flag_active(self.debug_state_last_frame, flag) and not flag_active(self.debug_state, flag):
            cv.destroyWindow(window_name)
    
    def dump_configuration(self) -> dict:
        return {
            "cords": [[self.bbox[0], self.bbox[1]], [self.bbox[2], self.bbox[3]]],
            "hue_thresholding": [uint8_to_real_hue(self.hue_thresholding[0]), uint8_to_real_hue(self.hue_thresholding[1])],
            "saturation_thresholding": [uint8_to_real_snv(self.sat_thresholding[0]), uint8_to_real_snv(self.sat_thresholding[1])],
            "value_thresholding": [uint8_to_real_snv(self.val_thresholding[0]), uint8_to_real_snv(self.val_thresholding[1])],
            "numbers": {number.refrence_name: number.points for number in self.numbers},
            "critical_points": {crit.refrence_name: crit.point for crit in self.critical_points}
        }  

    def activate(self):
        ACTIVE_REGIONS.add(self)
    
    def deactivate(self):
        ACTIVE_REGIONS.remove(self)
    
    def has_window_open(self) -> bool:
        return any(
            [flag_active(self.debug_state, flag) for flag in [
                self.DEBUG_PREPROCESS,
                self.DEBUG_MASKED,
                self.DEBUG_CRITICAL_POINTS,
                self.DEBUG_COMPOSITE_HSV,
                self.DEBUG_INDIVIDUAL_HSV
            ]]
        )

    def close(self):
        self.debug_state = 0
        blank = np.zeros((64, 64, 1), np.uint8)
        self.process_debug_windows(Region.DEBUG_PREPROCESS, "pre-process", blank)
        self.process_debug_windows(Region.DEBUG_MASKED, "mask", blank)
        self.process_debug_windows(Region.DEBUG_COMPOSITE_HSV, "composite-hsv", blank)
        self.process_debug_windows(Region.DEBUG_INDIVIDUAL_HSV, "hue", blank)
        self.process_debug_windows(Region.DEBUG_INDIVIDUAL_HSV, "sat", blank)
        self.process_debug_windows(Region.DEBUG_INDIVIDUAL_HSV, "val", blank)
        self.process_debug_windows(Region.DEBUG_CRITICAL_POINTS, "crit", blank)
        if self in ACTIVE_REGIONS: ACTIVE_REGIONS.remove(self)
        if self in REGIONS: REGIONS.remove(self)

def find_number(refrence_name: str) -> Number | None:
    for region in REGIONS:
        for number in region.numbers:
            if number.refrence_name == refrence_name:
                return number
    return None

def find_crit(refrence_name: str) -> CritPoint | None:
    for region in REGIONS:
        for crit in region.critical_points:
            if crit.refrence_name == refrence_name:
                return crit
    return None

class VisionCore():
    DEBUG_SHOW = 0x01
    DEBUG_SHOW_BBOX = 0x02

    def __init__(self, img_channel: int):
        self.img_channel = img_channel
        self.initalize_channel()
        self.buff = np.zeros((64, 64, 1), np.uint8)
        self.debug_state = (VisionCore.DEBUG_SHOW + VisionCore.DEBUG_SHOW_BBOX) * 1
        self.debug_state_last_frame = 0
        self.arc = False

    def initalize_channel(self, img_channel: int = None):
        if isinstance(img_channel, (np.ndarray, int)):
            self.img_channel = img_channel
        try:
            if isinstance(self.img_channel, np.ndarray):
                self.video = None
                return True
            self.video = cv.VideoCapture(self.img_channel, cv.CAP_DSHOW)
            self.video.set(cv.CAP_PROP_FRAME_WIDTH, 1280)
            self.video.set(cv.CAP_PROP_FRAME_HEIGHT, 720),
            self.video.set(cv.CAP_PROP_FPS, 60) # Tell the camera to output at 720p with compression.
            # "This is the only way it could have ended"
            self.video.set(cv.CAP_PROP_FOURCC, cv.VideoWriter.fourcc('M', 'J', 'P', 'G'))
            return False
        except: 
            log("Unable to Initialize Vision Core")
            self.video = None
            return True

    def run_frame(self) -> bool:
        if self.video == None:
            sucsess = self.initalize_channel()
            if not sucsess: 
                log("Vision Core Cannot Unable To Run Due to Invalid Camera Channel")
                return False
        returned, capture = False, None
        if isinstance(self.img_channel, np.ndarray): returned, capture = True, self.img_channel.copy()
        else: returned, capture = self.video.read()
        if not returned:
            self.video = None
            return False
        self.buff = capture.copy()
        # print(capture.shape)
        
        for region in ACTIVE_REGIONS:
            region.do_frame(capture)
        
        if self.debug_state != 0 or self.debug_state_last_frame != 0:
            win_name = "DEBUG: vision-core@input"
            if flag_active(self.debug_state, VisionCore.DEBUG_SHOW):
                if flag_active(self.debug_state, VisionCore.DEBUG_SHOW_BBOX):
                    for region in ACTIVE_REGIONS:
                        capture = cv.rectangle(capture, 
                                            (region.bbox[1], region.bbox[0]), 
                                            (region.bbox[3], region.bbox[2]),
                                            (0x00,0xff,0x00), 4)
                        # cv.FONT
                        cv.putText(capture, region.region_name, (region.bbox[1], region.bbox[0]), 2, 1.0, (0x00, 0xff, 0x00))
                        # capture = cv.addText(
                        #     capture, region.region_name, (region.bbox[1], region.bbox[0]), "Comic Sans MS"
                        # )
                
                cv.imshow(win_name, capture)
            
            if not flag_active(self.debug_state, VisionCore.DEBUG_SHOW) and flag_active(self.debug_state_last_frame, VisionCore.DEBUG_SHOW):
                cv.destroyWindow(win_name)
            
            self.debug_state_last_frame = self.debug_state
        
        self.arc = False
        if not flag_active(self.debug_state, self.DEBUG_SHOW):
            if not any([region.has_window_open() for region in REGIONS]):
                self.arc = True

        return True

    def select_bbox(self) -> tuple[int, int, int, int]:
        rectangle = cv.selectROI("Region Selection", self.buff, printNotice=False)
        cv.destroyWindow("Region Selection")
        return (rectangle[1], rectangle[0], rectangle[1] + rectangle[3], rectangle[0] + rectangle[2])

    def wait_key(self, delay: int = 33) -> int:
        if self.arc: return -1
        else: return cv.waitKey(delay)

def scan(starting_position: Point, direction: Point, mask: np.ndarray) -> list[Point]:
    pos = Point(starting_position.to_tuple())
    seen_valid = False
    while True:
        valid = mask[*pos.to_tuple_yx()] == 255
        if valid: seen_valid = valid
        pos = pos + direction
        if not valid and seen_valid: break
    upper = pos
    pos = Point(pos.to_tuple())
    seen_valid = False
    while True:
        valid = mask[*pos.to_tuple_yx()] == 255
        if valid: seen_valid = valid
        pos = pos - direction
        if not valid and seen_valid: break
    # lower = pos # pos is lower
    return [pos, upper]

def center_segment(starting_position: Point, mask: np.ndarray) -> tuple[Point, list[Point], list[Point]]:
    x_parts = scan(starting_position, RIGHT, mask) # type: list[Point]
    x = (x_parts[0] + x_parts[1]) // 2
    starting_position[0] = x.x
    y_parts = scan(starting_position, DOWN, mask) # type: list[Point]
    y = (y_parts[0] + y_parts[1]) // 2
    return (Point((x.x, y.y)), x_parts, y_parts)

def scan_segments(starting_position: Point, mask: np.ndarray) -> list[Point]:
    #   2  
    # 4   5
    #   1  
    # 6   7
    #   3  


    center_digit, center_x_bounds, center_y_bounds = center_segment(starting_position, mask)

    top_digit_first_pass = scan(Point([center_digit.x, center_y_bounds[0].y + UP.y]), UP, mask)
    top_digit, top_x_bounds, top_y_bounds = center_segment((top_digit_first_pass[0] + top_digit_first_pass[1]) // 2, mask)

    bottom_digit_first_pass = scan(Point([center_digit.x, center_y_bounds[1].y + UP.y]), DOWN, mask)
    bottom_digit, bottom_x_bounds, bottom_y_bounds = center_segment((bottom_digit_first_pass[0] + bottom_digit_first_pass[1]) // 2, mask)

    # mask = cv.circle(mask, center_digit.to_tuple(), 5, (0x7F,), -1)
    # mask = cv.circle(mask, top_digit.to_tuple(), 5, (0x7F,), -1)
    # mask = cv.circle(mask, bottom_digit.to_tuple(), 5, (0x7F,), -1)
    # cv.imshow("SCAN-dev", mask)
    # cv.waitKey(4000)

    top_left_digit_first_pass = scan(Point([center_x_bounds[0].x, ((center_y_bounds[0] + top_y_bounds[1]) // 2).y]), LEFT, mask)
    top_left_digit, top_left_x_bounds, top_left_y_bounds = center_segment((top_left_digit_first_pass[0] + top_left_digit_first_pass[1]) // 2, mask)

    top_right_digit_first_pass = scan(Point([center_x_bounds[1].x, ((center_y_bounds[0] + top_y_bounds[1]) // 2).y]), RIGHT, mask)
    top_right_digit, top_right_x_bounds, top_right_y_bounds = center_segment((top_right_digit_first_pass[0] + top_right_digit_first_pass[1]) // 2, mask)

    bottom_left_digit_first_pass = scan(Point([center_x_bounds[0].x, ((center_y_bounds[1] + bottom_y_bounds[0]) // 2).y]), LEFT, mask)
    bottom_left_digit, bottom_left_x_bounds, bottom_left_y_bounds = center_segment((bottom_left_digit_first_pass[0] + bottom_left_digit_first_pass[1]) // 2, mask)

    bottom_right_digit_first_pass = scan(Point([center_x_bounds[1].x, ((center_y_bounds[1] + bottom_y_bounds[0]) // 2).y]), RIGHT, mask)
    bottom_right_digit, bottom_right_x_bounds, bottom_right_y_bounds = center_segment((bottom_right_digit_first_pass[0] + bottom_right_digit_first_pass[1]) // 2, mask)
    
    return [top_digit, center_digit, bottom_digit, top_left_digit, top_right_digit, bottom_left_digit, bottom_right_digit]
