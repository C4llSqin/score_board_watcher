# Scoreboard Watcher

## Libaries used
| Libary | Version | Reason |
| :----: | :-----: | :----: |
| `opencv-python` | `4.11.0.86` | Computer vision to read scoreboard |
| `numpy` | `1.26.4 `| Required for opencv-python and helps with vision reading |
| `PySimpleGUI` | `4.61.0.206 Unreleased`, <br />(Commit `1fa911c`), (Included in source, Unmodified from `1fa911c`) | A graphical libary that doesn't suck and doesn't require licensing nightmares |
| `requests` | `2.32.3` | An easier way to do http requests rather than using python's base libary `urllib` |

## How the computer vision works overview
The Program has an Computer Vision hierarchy of:
 - The Vision Core
   - Its Regions
     - Its numbers

### Vision Core
There is only one vision core and this is the main way the program takes in input (the camera feed of the scoreboard) and then pass it along to its children regions.

### Region
A region is a child of the vision core, It takes in a sub view of that vision core and applys thresholding operations to make sure its children numbers can read the scoreboard.

### Number
A number is a set of points on a region that are positioned in a way that can evaulate every segment on a 7 segment or 2 segment display digit

## How the program outputs to vmix
The Program has an Output hierarchy of:
 - The Network Controller
   - Comound Digits
     - Numbers

### Network Controller
Like the Vision Core, there is only one Network Controller, this gets fed from all of the Compound digits that gets updated from the computer vision and then sends a request to vmix.

### Compound Digits
A compound digit is group of numbers that gets evaluated in compound. The main ones are the score compound digit which represents the set of numbers as an whole number, in contrast to the timer compound digit which represents the Numbers as time.

## Getting Started
Install Python `3.11.8` from <a>https://www.python.org/downloads/release/python-3118/</a>

#### Tip: Be sure to click the button "Add Python to PATH", this will ensure that all of python and its tools will be on the PATH envirement variable meaning whenever you try to call executeable belonging to python, windows will be able to find that file.

Open up command prompt in the folder that contains `core.py`, `net.py`, `vision.py`, this file, and `requirements.txt`. This can be done by clicking to the top of your file explorer window and typing in `cmd`.

Then You need to execute the folowing command to install all this program's dependancys

```batch
pip install -r requirements.txt
```

Components of this command:
 - pip: python's package manager
 - install: tell pip to install packages
 - `-r`: read from file
 - requriements.txt: the list of program depenencies

## Program Operation Instructions
Take a look at both [How the computer vision works overview](#how-the-computer-vision-works-overview) and [How the program outputs to vmix](#how-the-program-outputs-to-vmix) first to get a basic understaning to how this program works

### Vision Core Tab
Theres a really good reason that this is the first tab, upon program startup the camera feed should result popup and it should be pass though with no overlays visable. Before you start you need to determine which camera the scoreboard is on. This can be done by cycling though the channels like a TV, until you find the feed with the scoreboard. In order to change camera numbers you have to press "**Update Camera**". Once you have the correct channel, you can start assesing what you need from the scoreboard. Then you can start defining Regions with the **Make New Region** Button.

### Regions
This is the next step in the production line of program operation, Before you

#### Tip: Don't worry the act of changing camera channels make take a bit of time, It will also make all current open debug windows close while the swap is happening.

#### Tip: Make sure Vmix isn't using any cameras yet because it could own the video feed by the camera pointed at the scoreboard, which prevents this program from owning said video feed which it needs.


