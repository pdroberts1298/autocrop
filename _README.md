# Film negative auto-crop plugin for Lightroom 6

This is a proof of concept plugin for Adobe Lightroom 6 that automatically crops
scanned film negatives to only the exposed area of the emulsion using OpenCV.

The detection works, but it could be better. Currently it does a single pass:

1. Mask out extremely bright points (eg. light coming through the sprocket holes)
2. Threshold the image starting from zero, increasing in steps
3. At each threshold, collect the rotated bounding rectangle around the largest contour/blob (larger than a minimum size)
4. Once the largest contour/blob is too large, stop collecting rects
5. Calculate the crop for the image using the median of the collected rectangles

This works most of the time, but fails on images that threshold to many smaller contours that don't join (eg. one in each corner).

[Images of this running can be seen on Hackaday.io](https://hackaday.io/project/162842-35mm-flim-negative-scanning/log/159448-auto-cropping-scanned-negatives-with-opencv)

## Setup

### Running on Windows (rough)

- OpenCV and Python installed in the Windows 10 Linux Subsystem (because Python+OpenCV natively on Windows is a pain to set up)
- Xming (X server for Windows) running to allow windows from the Python script

### Running on OSX

The easiest way to install OpenCV at the time of writing is through [Homebrew](https://brew.sh/):

```sh
# Install OpenCV 3.x with Python Bindings
brew install opencv@3

# Let Python know about the OpenCV bindings
for dir in $(find $(brew --prefix opencv@3)/lib -maxdepth 2 -name 'site-packages'); do \
    _pythonVersion=$(basename $(dirname "$dir"))
    _pathfile="/usr/local/lib/$_pythonVersion/site-packages/opencv3.pth"; \
    echo "Adding $_pathfile"; \
    echo "$dir" > "$_pathfile"; \
done

# Check it worked
python -c 'import cv2' && echo 'OK!'
```

Then clone this Gist into your Lightroom plugin folder:

```sh
cd "$HOME/Library/Application Support/Adobe/Lightroom/Modules/"
git clone https://gist.github.com/91cb5d28d330550a1dc56fa29215cb85.git AutoCrop.lrplugin
```

Restart Lightroom and you should now see "Negative Auto Crop" listed under *File -> Plug-in Manager*. Use *File -> Plug-in Extras -> Auto Crop Negative* to run the script.

## Notes

It's easiest to hack on the Python script by running it directly with a test image, rather than running it through Lightroom. Running from Lightroom is slower and you'll only see an exit code if the script has a problem.

The Python and Lua components of this are independent; you can switch the Python script out for any external program, as long as it writes the same data out for Lightroom.

### Communication between Lua and Python

The Lightroom API doesn't provide a way to read any output stream from a subprocess, so the crop data computed in Python is written to a text file and picked up by the Lua plugin.

The format of this file is five numbers separated by new lines. The first four numbers are edge positions in the range `0.0` to `1.0` (factors of the image dimension). The last number is the rotation/straightening angle in the range `-45.0` to `45.0`:

```
Left edge
Right edge
Top edge
Bottom edge
Rotation
```

In practice this looks like:

```
0.027
0.974
0.03333333333333333
0.982
-0.1317138671875
```

These numbers are always relative to the exported image's orientation. The Lua side handles any rotation needed to match the internal orientation of the image in Lightroom.

### Lightroom's Lua API

Lightroom's API is very poorly documented (unless I'm missing some newer docs that Adobe has locked away behind a login). It doesn't appear to be intended for anything other than exporting to custom APIs - seems strange considering how extensible Photoshop is with scripts and plugins.

Images can be cropped through the Lightroom Lua API using the parameters `CropLeft`, `CropRight`, `CropTop`, and `CropBottom`. These aren't listed on the `LrDevelopController` page of the SDK docs, but are listed in the docs under `LrPhoto:getDevelopSettings`. Note that the sides (top, right, etc) are *always* relative to the orientation `AB`, not necessarily the top, right, etc of the exported image.

The `orientation` param is a two character string that represents the two corners at the top of the image:

```
AB:         BC:       CD:         DA:

A-----B     B---C     C-----D     D---A
|     |     |   |     |     |     |   |
D-----C     |   |     B-----A     |   |
            A---D                 C---B

(Each of these is rotated anti-clockwise by 90 degrees)
```

In my testing, `orientation` couldn't be read using `LrDevelopController:getValue()`, but I could retrieve it using `LrPhoto:photo:getDevelopSettings`.